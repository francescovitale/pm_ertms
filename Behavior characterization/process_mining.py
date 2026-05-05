import pandas as pd
import os
import sys
import pm4py 

from pm4py.objects.conversion.log import converter as log_converter
from pm4py.objects.log.util import dataframe_utils
from pm4py.objects.log.exporter.xes import exporter as xes_exporter

input_dir = "Input/"
output_dir = "Output/NormativeBehavior/"


def read_logs():
    if not os.path.exists(input_dir):
        os.makedirs(input_dir)
        
    file_path = os.path.join(input_dir, "handover_event_logs.json")
    
    if not os.path.exists(file_path):
        print(f"Error: Could not find '{file_path}'. Please ensure your JSON log is in the {input_dir} folder.")
        sys.exit(1)
        
    df = pd.read_json(file_path)
    print(f"Successfully loaded {len(df)} events from {file_path}")
    return df

def convert_software_logs(software_logs):

    software_logs['Activity'] = software_logs['Activity'] + "_" + software_logs['Component']
    
    software_logs.rename(columns={
        'CaseID': 'case:concept:name',
        'Activity': 'concept:name',
        'Timestamp': 'time:timestamp'
    }, inplace=True)
    
    if pd.api.types.is_numeric_dtype(software_logs['time:timestamp']):
        software_logs['time:timestamp'] = pd.to_datetime(software_logs['time:timestamp'], unit='s', origin='2024-01-01')
    else:
        software_logs = dataframe_utils.convert_timestamp_columns_in_df(software_logs)
        
    software_logs = software_logs.sort_values(['time:timestamp'])
    
    event_log = log_converter.apply(software_logs, variant=log_converter.Variants.TO_EVENT_LOG)
    return event_log

def save_event_log(event_log):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    output_path = os.path.join(output_dir, "handover_event_log.xes")
    xes_exporter.apply(event_log, output_path)
    print(f"Exported XES Event Log to: {output_path}")

def save_petri_net(petri_net, variant_name):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    pnml_path = os.path.join(output_dir, f"petri_net_{variant_name}.pnml")
    img_path = os.path.join(output_dir, f"petri_net_{variant_name}.png")
    
    pm4py.write_pnml(petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"], pnml_path)
    
    pm4py.save_vis_petri_net(petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"], img_path)
    
    print(f"Exported Petri Net (PNML) to: {pnml_path}")
    print(f"Exported Petri Net Visualization to: {img_path}")

def process_discovery(event_log, variant):
    petri_net = {}

    if variant == "im":
        petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_inductive(event_log)
    elif variant == "imf25":
        petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_inductive(event_log, noise_threshold=0.25)
    elif variant == "imf50":
        petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_inductive(event_log, noise_threshold=0.50)
    elif variant == "imf75":
        petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_inductive(event_log, noise_threshold=0.75)
    elif variant == "imf99":
        petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_inductive(event_log, noise_threshold=0.99)
    elif variant == "ilp":
        petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_ilp(event_log, alpha=1-0.00)
    elif variant == "ilp25":
        petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_ilp(event_log, alpha=1-0.25)
    elif variant == "ilp50":
        petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_ilp(event_log, alpha=1-0.50)
    elif variant == "ilp75":
        petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_ilp(event_log, alpha=1-0.75)
    elif variant == "ilp99":
        petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_ilp(event_log, alpha=1-0.99)
    elif variant == "alpha":
        petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_alpha(event_log)
    elif variant == "hm":
        petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_heuristics(event_log, dependency_threshold=0.75)
    else:
        print(f"Error: Unknown variant '{variant}'")
        sys.exit(1)

    return petri_net
    


if __name__ == "__main__":
    try:
        variant = sys.argv[1]
    except IndexError:
        print("Usage: python process_miner.py <variant>")
        print("Example: python process_miner.py im")
        sys.exit()

    software_logs = read_logs()
    event_log = convert_software_logs(software_logs)
    petri_net = process_discovery(event_log, variant)
    
    save_event_log(event_log)
    save_petri_net(petri_net, variant)