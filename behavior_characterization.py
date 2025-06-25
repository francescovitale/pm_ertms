from pm4py.objects.log.importer.xes import importer as xes_importer
from pm4py.objects.petri_net.importer import importer as pnml_importer
from pm4py.algo.simulation.playout.petri_net import algorithm as simulator
from pm4py.objects.petri_net.exporter import exporter as pnml_exporter
from pm4py.objects.conversion.log import converter as log_converter
from pm4py.objects.log.util import dataframe_utils
from pm4py.objects.log.exporter.xes import exporter as xes_exporter
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

input_dir = "Input/BC/"

output_dir = "Output/BC/"

variant = ""

def read_event_log():

	event_log = xes_importer.apply(input_dir + "EL.xes")

	return event_log


def process_discovery(event_log, variant):

	petri_net = {}

	if variant == "im":
		petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_inductive(event_log)
	
	elif variant == "imf25":
		petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_inductive(event_log, noise_threshold = 0.25)

	elif variant == "imf50":
		petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_inductive(event_log, noise_threshold = 0.50)

	elif variant == "imf75":
		petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_inductive(event_log, noise_threshold = 0.75)

	elif variant == "imf99":
		petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_inductive(event_log, noise_threshold = 0.99)

	elif variant == "ilp":
		petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_ilp(event_log, alpha=0.00)

	elif variant == "ilp25":
		petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_ilp(event_log, alpha=0.25)

	elif variant == "ilp50":
		petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_ilp(event_log, alpha=0.50)

	elif variant == "ilp75":
		petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_ilp(event_log, alpha=0.75)

	elif variant == "ilp99":
		petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_ilp(event_log, alpha=0.99)

	elif variant == "alpha":
		petri_net["network"], petri_net["initial_marking"], petri_net["final_marking"] = pm4py.discover_petri_net_alpha(event_log)

	return petri_net

def export_petri_net(petri_net):
	pnml_exporter.apply(petri_net["network"], petri_net["initial_marking"], output_dir + "PN.pnml", final_marking = petri_net["final_marking"])

try:
	variant = sys.argv[1]
except:
	print("Enter the right number of input arguments")
	sys.exit()

event_log = read_event_log()
petri_net = process_discovery(event_log, variant)
export_petri_net(petri_net)





