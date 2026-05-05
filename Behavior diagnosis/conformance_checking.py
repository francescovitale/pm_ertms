from pm4py.objects.log.importer.xes import importer as xes_importer
from pm4py.objects.petri_net.importer import importer as pnml_importer
from pm4py.algo.simulation.playout.petri_net import algorithm as simulator
from pm4py.objects.petri_net.exporter import exporter as pnml_exporter
from pm4py.objects.conversion.log import converter as log_converter
from pm4py.objects.log.util import dataframe_utils
from pm4py.objects.log.exporter.xes import exporter as xes_exporter
from pm4py.algo.conformance.alignments.petri_net import algorithm as alignments
from pm4py.algo.evaluation.replay_fitness import algorithm as replay_fitness
import pm4py

import sys
import os
import numpy as np
from itertools import combinations,permutations
import datetime
import random
import pandas as pd
import func_timeout
import time


def load_event_logs(base_input_dir="Input"):
	"""
	Loads event logs into a nested dictionary with the exact structure:
	event_logs[type][window_length][component] = imported_log
	"""
	event_logs = {
		"Training": {},
		"Test": {}
	}

	for log_type in ["Training", "Test"]:
		type_dir = os.path.join(base_input_dir, log_type)
		
		if not os.path.exists(type_dir):
			continue

		for component in os.listdir(type_dir):
			comp_dir = os.path.join(type_dir, component)
			
			if not os.path.isdir(comp_dir):
				continue
				
			for file_name in os.listdir(comp_dir):
				if file_name.endswith(".xes"):
					# Extracts '10' from 'EL_10.xes'
					window_length = file_name.split(".xes")[0].split("_")[-1] 
					file_path = os.path.join(comp_dir, file_name)
					
					# 1. Ensure the window_length key exists under the type
					if window_length not in event_logs[log_type]:
						event_logs[log_type][window_length] = {}
						
					# 2. Assign the log to the component UNDER the window length
					event_logs[log_type][window_length][component] = xes_importer.apply(file_path)

	return event_logs

def load_petri_nets(base_input_dir="Input"):
	petri_nets = {}
	pd_algorithms = ["alpha", "ilp", "im"]

	for algo in pd_algorithms:
		algo_dir = os.path.join(base_input_dir, algo)
		pnml_file_path = os.path.join(algo_dir, f"petri_net_{algo}.pnml")
		
		if os.path.exists(pnml_file_path):
			net, initial_marking, final_marking = pnml_importer.apply(pnml_file_path)
			
			petri_nets[algo] = {
				"network": net,
				"initial_marking": initial_marking,
				"final_marking": final_marking
			}

	return petri_nets
	
def compute_cc_diagnoses(event_logs, petri_nets):
    cc_diagnoses = {"Training": {}, "Test": {}}
    cc_timings = {"Training": {}, "Test": {}}
    
    # 1. Gather all unique activities across all Petri nets and all event logs
    activities_set = set()
    
    for algo, p_net_dict in petri_nets.items():
        activities_set.update(get_petri_net_activities(p_net_dict))
        
    for log_type in ["Training", "Test"]:
        for window_length in event_logs.get(log_type, {}):
            for component in event_logs[log_type][window_length]:
                log = event_logs[log_type][window_length][component]
                activities_set.update(get_event_log_activities(log))
                
    activities = sorted(list(activities_set))

    # 2. Compute diagnoses separating Training and Test at the root
    for log_type in ["Training", "Test"]:
        # Safety check in case the dictionary doesn't have the log_type
        if log_type not in event_logs:
            continue
            
        for algo, p_net_dict in petri_nets.items():
            cc_diagnoses[log_type][algo] = {}
            cc_timings[log_type][algo] = {}
            
            for window in event_logs[log_type]:
                cc_diagnoses[log_type][algo][window] = {}
                cc_timings[log_type][algo][window] = {}
                
                for component in event_logs[log_type][window]:
                    trace_wise_diagnoses_data = []
                    timings = []
                    
                    # Fetch the specific log for this iteration
                    log = event_logs[log_type][window][component]
                    
                    for trace in log:
                        single_trace_log = pm4py.objects.log.obj.EventLog([trace])
                        
                        start_time = time.time()
                        trace_diagnoses = generate_ab_diagnoses(single_trace_log, p_net_dict, activities)
                        timings.append(time.time() - start_time)
                        
                        # We no longer need the "Type" column since they are separated by dictionary keys
                        trace_row = list(trace_diagnoses.values()) + [component]
                        trace_wise_diagnoses_data.append(trace_row)
                    
                    columns = activities + ["Fitness", "Component"]
                    df = pd.DataFrame(columns=columns, data=trace_wise_diagnoses_data)
                    
                    cc_diagnoses[log_type][algo][window][component] = df
                    cc_timings[log_type][algo][window][component] = sum(timings) / len(timings) if timings else 0.0
                
    return cc_diagnoses, cc_timings

def get_event_log_activities(event_log):
	
	activities = []
	for trace in event_log:
		for event in trace:
			if event["concept:name"] not in activities:
				activities.append(event["concept:name"])	
					
	activites = list(set(activities))

	return activities

def get_petri_net_activities(petri_net):
	activities = []
	transitions = list(petri_net["network"]._PetriNet__get_transitions())

	for transition in transitions:
		transition = transition._Transition__get_label()
		if transition != None:
			activities.append(transition)

	return activities

def generate_ab_diagnoses(log, petri_net, activities):

	ab_diagnoses = {}

	trace_activities = get_event_log_activities(log)
	last_log_activity = trace_activities[-1]

	for activity in activities:
		ab_diagnoses[activity] = 0;

	fitness, precision, aligned_traces = compute_fitness_precision(petri_net, log, "ALIGNMENT_BASED")
	temp = []
	for aligned_trace in aligned_traces:
		temp.append(list(aligned_trace.values())[0])
	aligned_traces = temp[0]
	found = False
	last_idx = 0
	while found==False and last_idx < len(aligned_traces):
		if aligned_traces[last_idx][0] == last_log_activity:
			break
		else:
			last_idx = last_idx + 1
	misaligned_activities = compute_misaligned_activities(log, [aligned_traces])	
	for misaligned_activity in misaligned_activities:
		ab_diagnoses[misaligned_activity] = misaligned_activities[misaligned_activity]
		
	ab_diagnoses["Fitness"] = fitness

	return ab_diagnoses

def compute_fitness_precision(petri_net, event_log, cc_variant):

	log_fitness = 0.0
	aligned_traces = None
	parameters = {}
	parameters[log_converter.Variants.TO_EVENT_LOG.value.Parameters.CASE_ID_KEY] = 'CaseID'
	
	if cc_variant == "ALIGNMENT_BASED":
		aligned_traces = alignments.apply_log(event_log, petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"], parameters=parameters, variant=alignments.Variants.VERSION_STATE_EQUATION_A_STAR)
		log_fitness = replay_fitness.evaluate(aligned_traces, variant=replay_fitness.Variants.ALIGNMENT_BASED)["log_fitness"]
		log_precision = pm4py.precision_alignments(event_log, petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"])
	elif cc_variant == "TOKEN_BASED":
		replay_results = tokenreplay.algorithm.apply(log = event_log, net = petri_net["network"], initial_marking = petri_net["initial_marking"], final_marking = petri_net["final_marking"], parameters = parameters, variant = tokenreplay.algorithm.Variants.TOKEN_REPLAY)
		log_fitness = replay_fitness.evaluate(results = replay_results, variant = replay_fitness.Variants.TOKEN_BASED)["log_fitness"]
		log_precision = pm4py.conformance.precision_token_based_replay()

	return log_fitness, log_precision, aligned_traces
	
def compute_misaligned_activities(event_log, aligned_traces):
	
	misaligned_activities = {}
	events = {}
	
	for aligned_trace in aligned_traces:
		for move in aligned_trace:
			log_behavior = move[0]
			model_behavior = move[1]
			if log_behavior != model_behavior:
				if log_behavior != None and log_behavior != ">>":
					try:
						events[log_behavior] = events[log_behavior]+1
					except:
						events[log_behavior] = 0
						events[log_behavior] = events[log_behavior]+1
				elif model_behavior != None and model_behavior != ">>":
					try:
						events[model_behavior] = events[model_behavior] + 1
					except:
						events[model_behavior] = 0
						events[model_behavior] = events[model_behavior]+1
	while bool(events):
		popped_event = events.popitem()
		if popped_event[1] > 0:
			misaligned_activities[popped_event[0]] = popped_event[1]

	return misaligned_activities	
	
def write_diagnoses(cc_diagnoses, output_base_dir="Output"):
    # Iterate through the cc_diagnoses dictionary (Type -> Algo -> Window -> Component)
    for log_type, algos in cc_diagnoses.items():
        for algo, windows in algos.items():
            for window, components in windows.items():
                
                # Build the target directory path: Algo / Window / Type
                target_dir = os.path.join(output_base_dir, algo, str(window), log_type)
                
                # Create the directory structure if it doesn't exist
                os.makedirs(target_dir, exist_ok=True)
                
                # Consolidate all component DataFrames for this specific window/algo/type
                dataframes_to_concat = []
                for component, df in components.items():
                    if not df.empty:
                        dataframes_to_concat.append(df)
                
                # If we have data, concatenate and save as a single CSV
                if dataframes_to_concat:
                    consolidated_df = pd.concat(dataframes_to_concat, ignore_index=True)
                    
                    file_path = os.path.join(target_dir, "diagnoses.csv")
                    consolidated_df.to_csv(file_path, index=False)
                    
    print(f"\n[SUCCESS] Exported consolidated diagnoses to '{output_base_dir}'")
    return None
	
event_logs = load_event_logs()
petri_nets = load_petri_nets()
cc_diagnoses, cc_timings = compute_cc_diagnoses(event_logs, petri_nets)
write_diagnoses(cc_diagnoses)




	