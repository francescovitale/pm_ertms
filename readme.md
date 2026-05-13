# A Process Mining Methodology for Run-Time Monitoring of ERTMS/ETCS Control Flow

## Packages and run-time environment
This project has been executed on a Windows 11 machine with Python 3.11.5 and Pytest 8.4.2. A few libraries have been used within Python modules. Among these, the main ones are:

- pm4py 2.7.22.2
- scikit-learn 1.7.2
- numpy 1.26.4
- pandas 2.2.3

Please note that this list is not comprehensive and there may be additional dependencies required to run the project.

---

## Project structure

The project is structured according to four steps of a process mining methodology for run-time anomaly detection.

```
pm_ertms/
├── Anomaly detection and explanation
├── Behavior characterization
├── Behavior diagnosis
└── Prototype
```

---

## Full pipeline execution order

The methodology is intended to be executed as a sequential pipeline:

1. Prototype execution  
   Generates system execution traces from the instrumented RBC/RBC Handover scenario.

2. Behavior characterization  
   Converts execution logs into XES format, applies process mining techniques to derive workflow Petri nets, and generates synthetic anomalies via fault injection.

3. Behavior diagnosis  
   Performs online conformance checking on traces to identify deviations and produce control-flow diagnoses.

4. Anomaly detection and explanation  
   Clusters diagnostic outputs and provides explanations of deviations in terms of component-level misalignments.

---

## Prototype

This folder contains the ERTMS/ETCS L2 prototype implementing the RBC/RBC Handover scenario. It includes two files:

- rbc_rbc_handover.py
- test_suite.py

The former is an instrumented object-oriented implementation of the scenario with multiple interacting components. The scenario is executed via the test cases defined in test_suite.py.

To run the test suite and generate logs:

```bash
pytest test_suite
```

---

## Behavior characterization

This folder contains the logic to trigger the test suite, convert logs into XES format, apply process mining algorithms to derive workflow Petri nets, and perform fault injection for generating anomalous traces.

The batch file behavior_characterization.bat chains the execution of:
- test_suite.py
- generate_dataset.py
- process_mining.py

To execute the full characterization pipeline:

```bash
.\behavior_characterization.bat
```

The resulting Petri nets and injected traces are saved in the Results folder.

---

## Behavior diagnosis

This folder implements online conformance checking to extract control-flow diagnoses of deviating traces.

It also includes a Dataset subfolder containing data generated from the behavior characterization step.

The repository already includes outputs from a previous execution under the Dataset folder for convenience.

The batch file behavior_diagnosis.bat executes the diagnosis pipeline and stores results in the Results folder:

```bash
.\behavior_diagnosis.bat
```

---

## Anomaly detection and explanation

This folder contains clustering and explanation logic used to group diagnostic results based on deviating components and to quantify control-flow misalignments.

It also includes a Diagnoses folder containing outputs from a previous execution of the behavior diagnosis step.

The batch file anomaly_detection_explanation.bat runs the full pipeline and stores results in the Results folder:

```bash
.\anomaly_detection_explanation.bat
```