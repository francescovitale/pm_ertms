from pm4py.objects.log.importer.xes import importer as xes_importer
from pm4py.objects.petri_net.importer import importer as pnml_importer
from pm4py.algo.simulation.playout.petri_net import algorithm as simulator
from pm4py.objects.petri_net.exporter import exporter as pnml_exporter
from pm4py.objects.conversion.log import converter as log_converter
from pm4py.objects.log.util import dataframe_utils
from pm4py.objects.log.exporter.xes import exporter as xes_exporter
import pm4py

from sklearn.model_selection import train_test_split
import sys
import os
import numpy as np
from itertools import combinations,permutations
import datetime
import random
import pandas as pd
import func_timeout
import time
import math

input_dir = "Input/"

output_dir = "Output/"
output_petrinets_dir = output_dir + "PetriNets/"
output_eventlogs_dir = output_dir + "EventLogs/"

trace_fragment_lengths = [5, 10, 15]
component_anomaly_perc = 0.5

def read_process_models():

	petri_net = {}

	rbc_handover_model = pm4py.read_bpmn(input_dir + "RBC_HANDOVER.bpmn")

	petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.convert_to_petri_net(rbc_handover_model)

	return petri_net

def export_original_petri_nets(petri_net):
	pnml_exporter.apply(petri_net["network"], petri_net["initial_marking"], output_petrinets_dir + "RBC_HANDOVER.pnml", final_marking = petri_net["final_marking"])

def generate_datasets(petri_net, n_procedures, n_norm_traces, n_anom_traces, n_dataset_replicas, training_test_percentage):

	datasets = {}

	bc_event_logs, ob_training_event_logs, ob_test_event_logs = simulate_petri_net(petri_net, n_procedures, n_norm_traces, n_anom_traces, n_dataset_replicas, training_test_percentage)

	return bc_event_logs, ob_training_event_logs, ob_test_event_logs

def simulate_petri_net(petri_net, n_procedures, n_norm_traces, n_anom_traces, n_dataset_replicas, training_test_percentage):

	# the dictionaries are organized as follows:
	## bc_event_logs -> replica -> trace_fragment -> event_log
	## ob_training_event_logs -> replica -> component -> trace_fragment -> event_log
	## ob_test_event_logs -> replica -> component -> trace_fragment -> event_log

	bc_event_logs = {}
	ob_training_event_logs = {}
	ob_test_event_logs = {}

	for i in range(0,n_dataset_replicas):
		activities, components = get_activities(petri_net)
		component_procedures = get_component_procedures(components, n_procedures)
		activity_component_procedures = get_activity_component_procedures(activities, component_procedures)

		simulated_traces = simulate_traces(petri_net, n_norm_traces) # n_norm_traces -> these are used to build the model
		simulated_bc_traces = []
		for idx,trace in enumerate(simulated_traces):
			simulated_bc_traces.append(substitute_activities(trace, activity_component_procedures, n_procedures, 1.0))

		bc_event_logs[i] = build_event_log(simulated_bc_traces)

		ob_training_event_logs[i] = {}
		ob_test_event_logs[i] = {}
		simulated_traces = simulate_traces(petri_net, n_anom_traces) # n_anom_traces -> these are used to check for deviations
		for idx_c, component in enumerate(components):
			ob_training_event_logs[i][component] = {}
			ob_test_event_logs[i][component] = {}
			n_component_traces = int(n_anom_traces/(len(components)))
			simulated_ob_traces = []
			for idx_t, trace in enumerate(simulated_traces[n_component_traces*idx_c:(n_component_traces*idx_c+n_component_traces)]):
				substituted_trace = substitute_activities(trace, activity_component_procedures, n_procedures, 1.0)
				substituted_anomalous_trace = inject_anomaly(substituted_trace, component, n_procedures)
				simulated_ob_traces.append(substituted_anomalous_trace)

			for trace_fragment_length in trace_fragment_lengths:
				fragmented_traces = fragment_traces(simulated_ob_traces, trace_fragment_length)
				training_fragmented_traces, test_fragmented_traces = train_test_split(fragmented_traces, test_size=training_test_percentage)
				ob_training_event_logs[i][component][trace_fragment_length] = build_event_log(training_fragmented_traces)
				ob_test_event_logs[i][component][trace_fragment_length] = build_event_log(test_fragmented_traces)

	return bc_event_logs, ob_training_event_logs, ob_test_event_logs

def get_activities(petri_net):
	activities = []
	components = []
	transitions = list(petri_net["network"]._PetriNet__get_transitions())

	for transition in transitions:
		transition = transition._Transition__get_label()
		if transition != None:
			activities.append(transition)

	for activity in activities:
		components.append(activity.split("_")[-2])
	components = list(set(components))

	return activities, components

def get_component_procedures(components, n_procedures):

	component_procedures = {}

	for component in components:
		component_procedures[component] = []
		for i in list(range(0, n_procedures)):
			component_procedures[component].append(component + "_" + str(i))	

	return component_procedures

def get_activity_component_procedures(activities, component_procedures):

	activity_component_procedures = {}

	for activity in activities:
		component = activity.split("_")[-2]
		procedure_list = component_procedures[component].copy()
		random.seed()
		random.shuffle(procedure_list)
		activity_component_procedures[activity] = procedure_list

	return activity_component_procedures

def simulate_traces(petri_net, n_traces):

	simulated_event_log = simulator.apply(petri_net["network"], petri_net["initial_marking"], variant=simulator.Variants.BASIC_PLAYOUT, parameters={simulator.Variants.BASIC_PLAYOUT.value.Parameters.NO_TRACES: n_traces})
	traces = []
	for trace in simulated_event_log:
		state_transitions = []
		for event in trace:
			state_transitions.append(event["concept:name"])
		traces.append(state_transitions)
			
	return traces

def substitute_activities(trace, activity_component_procedures, n_procedures, rho):

	per_activity_probabilities = [None]*n_procedures
	for i in range(0, n_procedures):
		if i == 0:
			per_activity_probabilities[i] = rho
		else:
			per_activity_probabilities[i] = (1-rho)/(n_procedures-1)

	for idx,activity in enumerate(trace):
		procedure = random.choices(list(activity_component_procedures[activity]), weights=per_activity_probabilities, k=1)[0]
		trace[idx] = procedure

	return trace

def build_event_log(traces):

	event_log = []

	event_idx = 0
	for case_idx, trace in enumerate(traces):
		caseid = case_idx
		for procedure in trace:
			event_timestamp = timestamp_builder(event_idx)
			event = [caseid, procedure, event_timestamp]
			event_log.append(event)
			event_idx += 1

	event_log = pd.DataFrame(event_log, columns=['CaseID', 'Event', 'Timestamp'])
	event_log.rename(columns={'Event': 'concept:name'}, inplace=True)
	event_log.rename(columns={'Timestamp': 'time:timestamp'}, inplace=True)
	event_log = dataframe_utils.convert_timestamp_columns_in_df(event_log)
	parameters = {log_converter.Variants.TO_EVENT_LOG.value.Parameters.CASE_ID_KEY: 'CaseID'}
	event_log = log_converter.apply(event_log, parameters=parameters, variant=log_converter.Variants.TO_EVENT_LOG)

	return event_log

def timestamp_builder(number):
	
	ss = number
	mm, ss = divmod(ss, 60)
	hh, mm = divmod(mm, 60)
	ignore, hh = divmod(hh, 24)
	
	ss = ss%60
	mm = mm%60
	hh = hh%24
	
	return "1900-01-01T"+str(hh)+":"+str(mm)+":"+str(ss)

def inject_anomaly(trace, component, n_procedures):

	anomalous_trace = []

	anomaly_types = ["skipped", "wrongly-ordered", "wrong"]

	for idx,activity in enumerate(trace):
		if activity.split("_")[0] == component:
			anomaly_to_inject = random.choice(anomaly_types)
			if anomaly_to_inject == "skipped":
				continue
			elif anomaly_to_inject == "wrongly-ordered":
				if len(anomalous_trace) != 0:
					temp = anomalous_trace[-1]
					anomalous_trace[-1] = trace[idx]
					anomalous_trace.append(temp)
					
			elif anomaly_to_inject == "wrong":
				anomalous_trace.append(trace[idx].split("_")[0] + "_" + str(random.randint(0,n_procedures-1)))
		else:
			anomalous_trace.append(activity)

	return anomalous_trace

def fragment_traces(traces, trace_fragment_length):

	fragmented_traces = []

	for trace in traces:
		trace_length = len(trace)
		remaining_traces = trace_length % trace_fragment_length
		n_fragments = math.floor(trace_length/trace_fragment_length)
		for i in range(0,n_fragments):
			fragment = trace[0:(i*trace_fragment_length)+trace_fragment_length]
			fragmented_traces.append(fragment)
		if remaining_traces != 0:
			fragmented_traces.append(trace[0:(n_fragments*trace_fragment_length)+remaining_traces])

	return fragmented_traces

def save_event_logs(bc_event_logs, ob_training_event_logs, ob_test_event_logs):

	for replica in bc_event_logs:
		os.mkdir(output_eventlogs_dir + str(replica))
		
		os.mkdir(output_eventlogs_dir + str(replica) + "/BehaviorCharacterization")
		xes_exporter.apply(bc_event_logs[replica], output_eventlogs_dir + str(replica) + "/BehaviorCharacterization/EL.xes")

		os.mkdir(output_eventlogs_dir + str(replica) + "/OnlineBehavior")
		os.mkdir(output_eventlogs_dir + str(replica) + "/OnlineBehavior/Training")
		os.mkdir(output_eventlogs_dir + str(replica) + "/OnlineBehavior/Test")

		for component in ob_training_event_logs[replica]:
			os.mkdir(output_eventlogs_dir + str(replica) + "/OnlineBehavior/Training/" + component)
			os.mkdir(output_eventlogs_dir + str(replica) + "/OnlineBehavior/Test/" + component)
			for trace_fragment in ob_training_event_logs[replica][component]:
				xes_exporter.apply(ob_training_event_logs[replica][component][trace_fragment], output_eventlogs_dir + str(replica) + "/OnlineBehavior/Training/" + component + "/EL_" + str(trace_fragment) + ".xes")
				xes_exporter.apply(ob_training_event_logs[replica][component][trace_fragment], output_eventlogs_dir + str(replica) + "/OnlineBehavior/Test/" + component + "/EL_" + str(trace_fragment) + ".xes")

	return None

try:
	n_procedures = int(sys.argv[1])
	n_norm_traces = int(sys.argv[2])
	n_anom_traces = int(sys.argv[3])
	n_dataset_replicas = int(sys.argv[4])
	training_test_percentage = float(sys.argv[5])
except:
	print("Enter the right number of input arguments")
	sys.exit()

petri_net = read_process_models()
export_original_petri_nets(petri_net)
bc_event_logs, ob_training_event_logs, ob_test_event_logs = generate_datasets(petri_net, n_procedures, n_norm_traces, n_anom_traces, n_dataset_replicas, training_test_percentage)
save_event_logs(bc_event_logs, ob_training_event_logs, ob_test_event_logs)


