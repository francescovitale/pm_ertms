import os
import sys
import json
import random
import math
import pandas as pd
from sklearn.model_selection import train_test_split

from pm4py.objects.log.util import dataframe_utils
from pm4py.objects.conversion.log import converter as log_converter
from pm4py.objects.log.exporter.xes import exporter as xes_exporter

input_file = "Input/handover_event_logs.json"
output_dir = "Output/GeneratedDataset/"
trace_fragment_lengths = [5, 10, 15]

def load_base_traces():
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found. Please run the prototype test suite first.")
        sys.exit(1)

    df = pd.read_json(input_file)
    
    df['Activity'] = df['Activity'] + "_" + df['Component']
    
    components = df['Component'].unique().tolist()
    component_activities = {comp: df[df['Component'] == comp]['Activity'].unique().tolist() for comp in components}

    df = df.sort_values(by=['CaseID', 'Timestamp'])
    base_traces = [group.to_dict('records') for _, group in df.groupby('CaseID')]
    
    return base_traces, components, component_activities

import random

def inject_anomaly(trace, target_component, component_activities, random_seed=None):
    rng = random.Random(random_seed)
    
    anomaly_types = ["skipped", "drastically-wrong-order", "wrong", "storm"]
    
    anomalous_trace = []
    
    for event in trace:
        current_event = dict(event)
        
        if current_event.get('Component') == target_component:
            anomaly_to_inject = rng.choice(anomaly_types)
            
            if anomaly_to_inject == "skipped":
                continue
                
            elif anomaly_to_inject == "drastically-wrong-order":
                if len(anomalous_trace) > 0:
                    random_past_index = rng.randint(0, len(anomalous_trace) - 1)
                    anomalous_trace.insert(random_past_index, current_event)
                else:
                    anomalous_trace.append(current_event)
                    
            elif anomaly_to_inject == "wrong":
                random_activity = rng.choice(component_activities[target_component])
                current_event['Activity'] = random_activity
                anomalous_trace.append(current_event)
                
            elif anomaly_to_inject == "storm":
                storm_count = rng.randint(3, 5)
                for _ in range(storm_count):
                    anomalous_trace.append(dict(current_event))
        else:
            anomalous_trace.append(current_event)
            
    for i, e in enumerate(anomalous_trace):
        e['Timestamp'] = i + 1
        e['EventID'] = f"{e['CaseID']}_E{i + 1:03d}"
        
    return anomalous_trace

def fragment_traces(traces, trace_fragment_length):
    fragmented_traces = []

    for trace in traces:
        trace_length = len(trace)
        remaining_events = trace_length % trace_fragment_length
        n_fragments = math.floor(trace_length / trace_fragment_length)
        
        for i in range(n_fragments):
            current_length = (i * trace_fragment_length) + trace_fragment_length
            fragment = trace[0:current_length]
            
            frag_copy = [dict(event) for event in fragment]
            
            for event in frag_copy:
                event['CaseID'] = f"{event['CaseID']}_W{current_length}"
                
            fragmented_traces.append(frag_copy)
            
        if remaining_events != 0:
            fragment = trace[0:trace_length]
            frag_copy = [dict(event) for event in fragment]
            
            for event in frag_copy:
                event['CaseID'] = f"{event['CaseID']}_W{trace_length}"
                
            fragmented_traces.append(frag_copy)

    return fragmented_traces

def convert_to_event_log(traces_list):
    if not traces_list:
        return None
        
    flat_events = [event for trace in traces_list for event in trace]
    df = pd.DataFrame(flat_events)
    
    df.rename(columns={
        'CaseID': 'case:concept:name',
        'Activity': 'concept:name',
        'Timestamp': 'time:timestamp'
    }, inplace=True)
    
    if pd.api.types.is_numeric_dtype(df['time:timestamp']):
        df['time:timestamp'] = pd.to_datetime(df['time:timestamp'], unit='s', origin='2024-01-01')
        
    df = dataframe_utils.convert_timestamp_columns_in_df(df)
    parameters = {log_converter.Variants.TO_EVENT_LOG.value.Parameters.CASE_ID_KEY: 'case:concept:name'}
    return log_converter.apply(df, parameters=parameters, variant=log_converter.Variants.TO_EVENT_LOG)

def generate_datasets(training_test_percentage):
    print("Loading base traces from JSON...")
    base_traces, components, component_activities = load_base_traces()
    
    print("Generating dataset...")
    
    ob_training_event_logs = {}
    ob_test_event_logs = {}
    
    for component in components:
        ob_training_event_logs[component] = {}
        ob_test_event_logs[component] = {}
        
        simulated_ob_traces = []
        for trace in base_traces:
            anomalous_trace = inject_anomaly(trace, component, component_activities)
            simulated_ob_traces.append(anomalous_trace)

        for frag_length in trace_fragment_lengths:
            fragmented_traces = fragment_traces(simulated_ob_traces, frag_length)
            
            training_frags, test_frags = train_test_split(fragmented_traces, test_size=training_test_percentage)
            
            ob_training_event_logs[component][frag_length] = convert_to_event_log(training_frags)
            ob_test_event_logs[component][frag_length] = convert_to_event_log(test_frags)

    return ob_training_event_logs, ob_test_event_logs

def save_event_logs(ob_training_event_logs, ob_test_event_logs):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    ob_train_dir = os.path.join(output_dir, "Training")
    ob_test_dir = os.path.join(output_dir, "Test")
    os.makedirs(ob_train_dir, exist_ok=True)
    os.makedirs(ob_test_dir, exist_ok=True)

    for component in ob_training_event_logs:
        comp_train_dir = os.path.join(ob_train_dir, component)
        comp_test_dir = os.path.join(ob_test_dir, component)
        os.makedirs(comp_train_dir, exist_ok=True)
        os.makedirs(comp_test_dir, exist_ok=True)
        
        for frag_length in ob_training_event_logs[component]:
            train_log = ob_training_event_logs[component][frag_length]
            test_log = ob_test_event_logs[component][frag_length]
            
            if train_log is not None:
                xes_exporter.apply(train_log, os.path.join(comp_train_dir, f"EL_{frag_length}.xes"))
            if test_log is not None:
                xes_exporter.apply(test_log, os.path.join(comp_test_dir, f"EL_{frag_length}.xes"))

    print(f"\n[SUCCESS] Exported dataset to '{output_dir}'")

if __name__ == "__main__":
    try:
        training_test_percentage = float(sys.argv[1])
    except IndexError:
        print("Usage: python generate_dataset.py <test_percentage>")
        print("Example: python generate_dataset.py 0.2")
        sys.exit(1)

    ob_train_logs, ob_test_logs = generate_datasets(training_test_percentage)
    save_event_logs(ob_train_logs, ob_test_logs)