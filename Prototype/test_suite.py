import pytest
import json
import itertools
from rbc_rbc_handover import run_process_instance

test_scenarios = []
trace_counter = 1

radio_types = [True, False]
busy_durations = [0, 1, 2]
dropped_packets = [
    [],
    [1],
    [3, 4],
    [1, 5, 6]
]
speeds = [20, 25, 30]

matrix = itertools.product(radio_types, busy_durations, dropped_packets, speeds)

for dual_radio, busy_dur, drops, speed in matrix:
    base_name = "NORM" if dual_radio else "DEG"
    
    config = {
        "type": f"{base_name}_Matrix",
        "has_dual_radio": dual_radio,
        "arbc_rejects_session": False,
        "arbc_busy_duration": busy_dur,
        "drop_tx_counts": drops,
        "speed": speed
    }
    test_scenarios.append((f"TC_{base_name}_{trace_counter:03d}", config))
    trace_counter += 1

for i in range(1, 4):
    config = {
        "type": "Anomaly_Fatal", 
        "has_dual_radio": True, 
        "arbc_rejects_session": True, 
        "arbc_busy_duration": 0,
        "drop_tx_counts": [],
        "speed": 25
    }
    test_scenarios.append((f"TC_ANOM_{i:03d}", config))

test_scenarios = test_scenarios[:22] + test_scenarios[-3:] 


@pytest.fixture(scope="session")
def log_dataset():
    flat_event_log = []
    yield flat_event_log 
    
    with open("handover_procedure_logs.json", "w") as f:
        json.dump(flat_event_log, f, indent=2)
    print(f"\n[SUCCESS] Saved {len(flat_event_log)} procedure call events for exactly 25 test cases.")


@pytest.mark.parametrize("trace_id, config", test_scenarios)
def test_handover_safety_invariants(trace_id, config, log_dataset):
    evc, rtm, logger = run_process_instance(trace_id, config)

    if config["type"] == "Anomaly_Fatal":
        assert evc.supervision_granted is False, f"{trace_id}: Granted supervision during fatal anomaly."
        assert evc.emergency_brake_active is True, f"{trace_id}: Failed to trigger emergency brake."

    assert not (evc.supervision_granted and evc.emergency_brake_active), f"{trace_id}: Violates mutual exclusivity."

    if evc.supervision_granted:
        assert not rtm.session_hrbc, f"{trace_id}: Old session stuck open."

    for event in logger.events:
        log_dataset.append(event)