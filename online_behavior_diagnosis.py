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

input_dir = "Input/OB/"
input_eventlogs_dir = input_dir + "EventLogs/"
input_eventlogs_test_dir = input_eventlogs_dir + "Test/"
input_eventlogs_training_dir = input_eventlogs_dir + "Training/"
input_petrinet_dir = input_dir + "PetriNet/"

output_dir = "Output/OB/"
output_diagnoses_dir = output_dir + "Diagnoses/"
output_diagnoses_test_dir = output_diagnoses_dir + "Test/"
output_diagnoses_training_dir = output_diagnoses_dir + "Training/"

def read_petri_net():

	petri_net = {}

	petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pnml_importer.apply(input_petrinet_dir + "PN.pnml")

	return petri_net

def read_event_logs():

	event_logs = {}
	event_logs["Test"] = {}
	event_logs["Training"] = {}

	for component in os.listdir(input_eventlogs_training_dir):
		event_logs["Training"][component] = {}
		event_logs["Test"][component] = {}
		for event_log in os.listdir(input_eventlogs_training_dir + component):
			event_logs["Training"][component][event_log.split(".xes")[0].split("_")[-1]] = xes_importer.apply(input_eventlogs_training_dir + component + "/" + event_log)
			event_logs["Test"][component][event_log.split(".xes")[0].split("_")[-1]] = xes_importer.apply(input_eventlogs_test_dir + component + "/" + event_log)

	return event_logs
	
def compute_cc_diagnoses(event_logs, petri_net):

	cc_diagnoses = {}
	cc_timings = {}
	
	# get the activities from both the Petri net and event log
	
	activities = []
	petri_net_activities = get_petri_net_activities(petri_net)
	activities = activities + petri_net_activities	

	for component in event_logs["Training"]:
		for trace_length in event_logs["Training"][component]:
			event_log_activities = get_event_log_activities(event_logs["Training"][component][trace_length])
			activities = list(set(activities + event_log_activities))
			event_log_activities = get_event_log_activities(event_logs["Test"][component][trace_length])
			activities = list(set(activities + event_log_activities))

	activities.sort()

	cc_timings["Training"] = {}
	cc_diagnoses["Training"] = {}
	trace_lengths = list(event_logs["Training"]["evc"].keys())
	for trace_length in trace_lengths:
		timings = []
		trace_wise_diagnoses_fitness_precision = []
		for component in event_logs["Training"]:
			for trace in event_logs["Training"][component][trace_length]:
				log = (pm4py.objects.log.obj.EventLog)([trace])
				timing = time.time()
				trace_diagnoses = generate_ab_diagnoses(log, petri_net, activities)
				timings.append(time.time() - timing)
				trace_wise_diagnoses_fitness_precision.append(list(trace_diagnoses.values()) + [component])
		cc_diagnoses["Training"][trace_length] = pd.DataFrame(columns = activities + ["Fitness", "Component"], data = trace_wise_diagnoses_fitness_precision)
		cc_timings["Training"][trace_length] = sum(timings)/len(timings)

	cc_timings["Test"] = {}
	cc_diagnoses["Test"] = {}
	trace_lengths = list(event_logs["Test"]["evc"].keys())
	for trace_length in trace_lengths:
		timings = []
		trace_wise_diagnoses_fitness_precision = []
		for component in event_logs["Test"]:
			for trace in event_logs["Test"][component][trace_length]:
				log = (pm4py.objects.log.obj.EventLog)([trace])
				timing = time.time()
				trace_diagnoses = generate_ab_diagnoses(log, petri_net, activities)
				timings.append(time.time() - timing)
				trace_wise_diagnoses_fitness_precision.append(list(trace_diagnoses.values()) + [component])
		cc_diagnoses["Test"][trace_length] = pd.DataFrame(columns = activities + ["Fitness", "Component"], data = trace_wise_diagnoses_fitness_precision)
		cc_timings["Test"][trace_length] = sum(timings)/len(timings)
	

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

def save_cc_diagnoses_timings(cc_diagnoses, cc_timings):

	for trace_length in cc_diagnoses["Training"]:
		os.mkdir(output_diagnoses_training_dir + str(trace_length))
		os.mkdir(output_diagnoses_test_dir + str(trace_length))
			
		cc_diagnoses["Training"][trace_length].to_csv(output_diagnoses_training_dir + "/" + str(trace_length) + "/cc_diagnoses.csv", index=False)
		cc_diagnoses["Test"][trace_length].to_csv(output_diagnoses_test_dir + "/" + str(trace_length) + "/cc_diagnoses.csv", index=False)
			
		file = open(output_diagnoses_training_dir + "/" + str(trace_length) + "/cc_timings.txt", "w")
		file.write(str(cc_timings["Training"][trace_length]))
		file.close()
			
		file = open(output_diagnoses_test_dir + "/" + str(trace_length) + "/cc_timings.txt", "w")
		file.write(str(cc_timings["Test"][trace_length]))
		file.close()
		

	return None


try:
	pass
except:
	print("Enter the right number of input arguments")
	sys.exit()

petri_net = read_petri_net()
event_logs = read_event_logs()
cc_diagnoses, cc_timings = compute_cc_diagnoses(event_logs, petri_net)
save_cc_diagnoses_timings(cc_diagnoses, cc_timings)




