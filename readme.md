# A Process Mining Methodology for Run-Time Monitoring of ERTMS/ETCS Control Flow

## Packages
This project has been executed in a Python environment to implement the process mining and anomaly detection pipelines. A few libraries have been used within Python modules. Among these, the main ones are:

- pm4py 2.7.22.2
- scikit-learn 1.7.2
- numpy 1.26.4
- pandas 2.2.3
- pytest 8.4.2

Please note that the list above is not comprehensive and there could be other requirements for running the project.

## Project structure

The project is structured according to four steps of a process mining methodology for run-time anomaly detection.

```text
pm_ertms/
├───Anomaly detection and explanation
├───Behavior characterization
├───Behavior diagnosis
└───Prototype
```

### Prototype

This folder contains the ERTMS/ETCS L2 prototype implementing the RBC/RBC Handover scenario. There are two files: rbc_rbc_handover.py and test_suite.py. The former is an instrumented, object-oriented implementation of the scenario with multiple components communicating throughout the specified scenario instance. The scenario instance is triggered by the tests contained in the test_suite.py file. To run the test suite, and generate the logs, run the following command:

```pytest test_suite```

### Behavior characterization

This folder contains the logic to trigger the test suite, convert the obtained logs into the XES format, the process mining algorithms to turn the logs into workflow Petri nets, and the fault-injection source code for generating training and test sets by adding control-flow anomalies to the traces.

The batch file behavior_characterization.bat runs the logic by chaining the execution of the test_suite.py script, generate_dataset.py script, and process_mining.py script. To extract the workflow Petri nets, which will be saved under the Results folder, run the following command:

```.\behavior_characterization.bat```

### Behavior diagnosis

This folder contains the online conformance-checking implementation to extract the control-flow diagnoses of deviating traces. The batch file behavior_diagnosis.bat runs the logic. Run the following command:

```.\behavior_diagnosis.bat```

### Anomaly detection and explanation

This folder contains the clustering and anomaly explanation logic used to separate the control-flow diagnoses based on the deviating components and explain the specific deviations by providing the number of component-wise misalignments. The batch file anomaly_detection_explanation.bat runs the logic. Run the following command:

```.\anomaly_detection_explanation.bat```