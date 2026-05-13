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

from sklearn.cluster import KMeans, AgglomerativeClustering, SpectralClustering, Birch
from sklearn.cluster import HDBSCAN
from sklearn.metrics import balanced_accuracy_score, v_measure_score
from sklearn.metrics import pairwise_distances_argmin

def load_diagnoses(base_input_dir="Input"):
    diagnoses = {}

    if not os.path.exists(base_input_dir):
        print(f"Directory '{base_input_dir}' does not exist.")
        return diagnoses

    for algo in os.listdir(base_input_dir):
        algo_dir = os.path.join(base_input_dir, algo)
        
        if not os.path.isdir(algo_dir):
            continue
            
        diagnoses[algo] = {}
        
        for window in os.listdir(algo_dir):
            window_dir = os.path.join(algo_dir, window)
            
            if not os.path.isdir(window_dir):
                continue
                
            diagnoses[algo][window] = {}
            
            for log_type in os.listdir(window_dir):
                type_dir = os.path.join(window_dir, log_type)
                
                if not os.path.isdir(type_dir):
                    continue
                    
                csv_path = os.path.join(type_dir, "diagnoses.csv")
                
                if os.path.exists(csv_path):
                    try:
                        diagnoses[algo][window][log_type] = pd.read_csv(csv_path)
                    except Exception as e:
                        print(f"Error loading {csv_path}: {e}")

    return diagnoses
	
def build_clusters(diagnoses):
    clusters = {}
    cluster_counts = [10, 30, 50]

    for pd_algo, windows in diagnoses.items():
        clusters[pd_algo] = {}
        
        for window, types in windows.items():
            if "Training" not in types:
                continue
                
            df_train = types["Training"]
            if df_train.empty:
                continue
                
            X_train = df_train.drop(columns=["Component"])
            y_train_true = df_train["Component"]
            
            clusters[pd_algo][window] = {}

            for n in cluster_counts:
                models = {
                    "K-Means": KMeans(n_clusters=n, n_init=10, random_state=42),
                    "WARD": AgglomerativeClustering(n_clusters=n, linkage='ward'),
                    "Spectral": SpectralClustering(n_clusters=n, assign_labels='kmeans', random_state=42),
                    "BIRCH": Birch(n_clusters=n)
                }
                
                for algo_name, model in models.items():
                    if algo_name not in clusters[pd_algo][window]:
                        clusters[pd_algo][window][algo_name] = {}
                        
                    labels = model.fit_predict(X_train)
                    
                    clusters[pd_algo][window][algo_name][n] = {
                        "model": model,
                        "labels": labels,
                        "X_train": X_train,
                        "y_train_true": y_train_true 
                    }

            hdbscan_model = HDBSCAN(min_cluster_size=5)
            hdbscan_labels = hdbscan_model.fit_predict(X_train)
            
            clusters[pd_algo][window]["HDBSCAN"] = {}
            clusters[pd_algo][window]["HDBSCAN"]["auto"] = {
                "model": hdbscan_model,
                "labels": hdbscan_labels,
                "X_train": X_train,
                "y_train_true": y_train_true
            }

    return clusters
	
def classify_test_traces(diagnoses, clusters):
    accuracy_results = {}
    v_measure_results = {}

    for pd_algo, windows in diagnoses.items():
        accuracy_results[pd_algo] = {}
        v_measure_results[pd_algo] = {}

        for window, types in windows.items():
            if "Test" not in types or window not in clusters.get(pd_algo, {}):
                continue

            df_test = types["Test"]
            if df_test.empty:
                continue
            
            X_test = df_test.drop(columns=["Component"])
            y_test_true = df_test["Component"]

            accuracy_results[pd_algo][window] = {}
            v_measure_results[pd_algo][window] = {}

            for cluster_algo, configs in clusters[pd_algo][window].items():
                accuracy_results[pd_algo][window][cluster_algo] = {}
                v_measure_results[pd_algo][window][cluster_algo] = {}

                for n_clusters, cluster_data in configs.items():
                    model = cluster_data["model"]
                    train_labels = cluster_data["labels"]
                    X_train = cluster_data["X_train"]

                    cluster_to_component = {}
                    unique_clusters = set(train_labels)
                    centroids = {}
                    
                    activity_columns = [col for col in X_train.columns if col != "Fitness"]
                    
                    available_components = set([act.split("_")[-1] for act in activity_columns])
                    
                    for c in unique_clusters:
                        if c == -1:
                            continue
                        
                        cluster_traces = X_train[train_labels == c]
                        centroids[c] = cluster_traces.mean().values
                        
                        comp_scores = {comp: 0 for comp in available_components}
                        
                        for act in activity_columns:
                            comp = act.split("_")[-1]
                            comp_scores[comp] += cluster_traces[act].sum()
                        
                        cluster_to_component[c] = max(comp_scores, key=comp_scores.get)

                    test_cluster_assignments = []
                    
                    if hasattr(model, "predict") and cluster_algo not in ["Spectral", "WARD"]:
                        test_cluster_assignments = model.predict(X_test)
                    else:
                        centroid_ids = list(centroids.keys())
                        if not centroid_ids:
                            continue 
                            
                        centroid_matrix = np.array([centroids[c] for c in centroid_ids])
                        closest_indices = pairwise_distances_argmin(X_test, centroid_matrix)
                        test_cluster_assignments = [centroid_ids[idx] for idx in closest_indices]

                    y_pred = [cluster_to_component.get(c, "Unknown") for c in test_cluster_assignments]

                    acc = balanced_accuracy_score(y_test_true, y_pred)
                    v_m = v_measure_score(y_test_true, test_cluster_assignments)

                    accuracy_results[pd_algo][window][cluster_algo][n_clusters] = acc
                    v_measure_results[pd_algo][window][cluster_algo][n_clusters] = v_m

    return accuracy_results, v_measure_results
	
def save_metrics(accuracy_results, v_measure_results, output_filepath="Output/metrics_summary.csv"):
    rows = []
    
    for pd_algo in accuracy_results:
        for window in accuracy_results[pd_algo]:
            for cluster_algo in accuracy_results[pd_algo][window]:
                for n_clusters in accuracy_results[pd_algo][window][cluster_algo]:
                    
                    acc = accuracy_results[pd_algo][window][cluster_algo][n_clusters]
                    v_m = v_measure_results[pd_algo][window][cluster_algo][n_clusters]
                    
                    rows.append({
                        "Window": int(window),
                        "PD_Algorithm": pd_algo.upper(),
                        "Clustering_Algorithm": cluster_algo,
                        "N_Clusters": str(n_clusters).capitalize(),
                        "Accuracy": round(acc, 2) if isinstance(acc, float) else acc,
                        "V_Measure": round(v_m, 2) if isinstance(v_m, float) else v_m
                    })
                    
    df = pd.DataFrame(rows)
    
    if df.empty:
        print("[WARNING] No metrics to save. The dictionaries are empty.")
        return df
    
    df = df.sort_values(by=["Window", "PD_Algorithm", "Clustering_Algorithm"], ascending=[True, True, True])
    
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
    
    df.to_csv(output_filepath, index=False)
    print(f"\n[SUCCESS] Extracted {len(df)} configurations.")
    print(f"[SUCCESS] Metrics securely saved to: '{output_filepath}'")
    
    return df	
	
def calculate_test_explanations(diagnoses):
    explanations_results = []

    for pd_algo, windows in diagnoses.items():
        for window, types in windows.items():
            if "Test" not in types:
                continue

            df_test = types["Test"]
            if df_test.empty:
                continue

            activity_columns = [col for col in df_test.columns if col not in ["Fitness", "Component"]]
            available_components = sorted(list(set([act.split("_")[-1] for act in activity_columns])))

            grouped_test_data = df_test.groupby("Component")

            for injected_fault, group_df in grouped_test_data:
                comp_scores = {comp: 0.0 for comp in available_components}
                
                for act in activity_columns:
                    comp = act.split("_")[-1]
                    comp_scores[comp] += group_df[act].sum()

                num_traces = len(group_df)
                for comp in comp_scores:
                    comp_scores[comp] = comp_scores[comp] / num_traces

                row = {
                    "PD_Algorithm": pd_algo.upper(),
                    "Window": int(window),
                    "Injected_Fault": injected_fault
                }
                
                for comp, score in comp_scores.items():
                    row[f"S_{comp}"] = score
                
                explanations_results.append(row)

    return pd.DataFrame(explanations_results)

def save_test_explanations(df_explanations, output_filepath="Output/explanations_summary.csv"):
    if df_explanations.empty:
        print("[WARNING] No explanations to save.")
        return df_explanations
        
    df_explanations = df_explanations.sort_values(by=["Window", "PD_Algorithm", "Injected_Fault"])
    
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
    df_explanations.to_csv(output_filepath, index=False)
    
    print(f"[SUCCESS] Global explanations securely saved to: '{output_filepath}'")
    return df_explanations	
	
	
diagnoses = load_diagnoses()
clusters = build_clusters(diagnoses)
accuracy, v_measure = classify_test_traces(diagnoses, clusters)
save_metrics(accuracy, v_measure)
df_explanations = calculate_test_explanations(diagnoses)
save_test_explanations(df_explanations)
