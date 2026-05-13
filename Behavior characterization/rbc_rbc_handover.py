class SimulationLogger:
    def __init__(self, trace_id, config):
        self.trace_id = trace_id
        self.config = config
        self.events = []
        self.logical_clock = 0

    def tick(self, steps=1):
        self.logical_clock += steps

    def record(self, component, action, details=""):
        self.logical_clock += 1
        
        event = {
            "CaseID": self.trace_id,
            "EventID": f"{self.trace_id}_E{self.logical_clock:03d}",
            "Timestamp": self.logical_clock, 
            "Activity": action,
            "Component": component
        }
        self.events.append(event)

class DMI:
    def __init__(self, logger):
        self.logger = logger
        self.current_display = "Normal Setup"

    def update_display(self, message):
        self.current_display = message
        self.logger.record("DMI", "DISPLAY_UPDATE", message)

    def show_announcement(self): self.update_display("Transition Announcement Symbol")
    def clear_announcement(self): self.update_display("Transition Executing (No Symbol)")
    def show_arbc_active(self, target_data): self.update_display(f"ARBC Active | {target_data}")
    def show_error(self, error_msg): self.update_display(f"ALARM: {error_msg}")

class EVC:
    def __init__(self, logger, config, dmi, rtm):
        self.logger = logger
        self.config = config
        self.dmi = dmi
        self.rtm = rtm
        self.train_length = 200 
        self.supervision_granted = False
        self.emergency_brake_active = False

    def process_transition_order(self, border_ma):
        self.logger.record("EVC", "PROCESS_MA", "Transition order validated")
        self.dmi.show_announcement()

    def evaluate_front_end_position(self, current_pos, border_pos):
        if current_pos >= border_pos and not self.supervision_granted and not self.emergency_brake_active:
            self.logger.record("EVC", "EVALUATE_FRONT", "Front end reached border")
            self.dmi.clear_announcement()
            
            if self.config["has_dual_radio"]:
                self.rtm.send_position_report("BOTH", current_pos)
            else:
                self.rtm.send_position_report("HRBC", current_pos)

    def evaluate_rear_end_position(self, current_pos, border_pos):
        rear_position = current_pos - self.train_length
        if rear_position >= border_pos and not self.emergency_brake_active:
            self.logger.record("EVC", "EVALUATE_REAR", "Rear end cleared border")
            self.rtm.send_position_report("HRBC", current_pos)

    def apply_supervision(self, supervision_data):
        self.logger.record("EVC", "APPLY_SUPERVISION", "New ARBC targets applied")
        self.supervision_granted = True
        self.dmi.show_arbc_active(supervision_data)

    def trigger_emergency_brake(self):
        self.logger.record("EVC", "EMERGENCY_BRAKE", "Supervision failed.")
        self.emergency_brake_active = True
        self.dmi.show_error("Supervision Transfer Failed - Brake Applied")

class RTM:
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        self.session_hrbc = True
        self.session_arbc = False

    def link_components(self, evc, hrbc, arbc):
        self.evc = evc
        self.hrbc = hrbc
        self.arbc = arbc

    def receive_from_hrbc(self, msg_type, data):
        self.logger.record("RTM", f"RX_HRBC_{msg_type}")
        if msg_type == "TRANSITION_ORDER": self.evc.process_transition_order(data)
        elif msg_type == "TERMINATION_ORDER": self.terminate_hrbc()

    def receive_from_arbc(self, msg_type, data):
        self.logger.record("RTM", f"RX_ARBC_{msg_type}")
        if msg_type == "GRANT_SUPERVISION": self.evc.apply_supervision(data)

    def establish_arbc_session(self):
        self.logger.record("RTM", "REQ_SESSION_ARBC")
        if self.arbc.accept_session():
            self.session_arbc = True
            self.logger.record("RTM", "SESSION_ESTABLISHED_ARBC")
        else:
            self.logger.record("RTM", "SESSION_REJECTED_ARBC")
            self.evc.trigger_emergency_brake()

    def send_position_report(self, target, position):
        self.logger.record("RTM", "TX_POS_REPORT", f"Target: {target}")
        if target in ["BOTH", "HRBC"] and self.session_hrbc:
            self.hrbc.process_report(position, self)
        if target in ["BOTH", "ARBC"] and self.session_arbc:
            self.arbc.process_report(position, self)

    def terminate_hrbc(self):
        self.logger.record("RTM", "TERMINATE_SESSION_HRBC")
        self.session_hrbc = False
        
        if not self.config["has_dual_radio"] and not self.evc.emergency_brake_active:
            self.establish_arbc_session()
            if self.session_arbc:
                self.send_position_report("ARBC", "POST_TERMINATION_POS")

class HRBC:
    def __init__(self, logger, arbc):
        self.logger = logger
        self.arbc = arbc
        self.responsibility_transferred = False

    def coordinate_border_ma(self, train_id):
        self.logger.record("HRBC", "COORDINATE_MA")
        return self.arbc.process_coordination(train_id)

    def transmit_transition_order(self, rtm, border_ma):
        self.logger.record("HRBC", "TX_TRANSITION_ORDER")
        rtm.receive_from_hrbc("TRANSITION_ORDER", border_ma)

    def process_report(self, position, rtm):
        self.logger.record("HRBC", "RX_POS_REPORT")
        
        if not self.responsibility_transferred:
            self.logger.record("HRBC", "FORWARD_ANNOUNCEMENT_TO_ARBC")
            self.arbc.process_report(position, rtm)
        else:
            self.order_termination(rtm)

    def acknowledge_takeover(self):
        self.logger.record("HRBC", "ACK_TAKEOVER")
        self.responsibility_transferred = True

    def order_termination(self, rtm):
        self.logger.record("HRBC", "TX_TERMINATION_ORDER")
        rtm.receive_from_hrbc("TERMINATION_ORDER", None)

class ARBC:
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        self.hrbc = None
        self.front_end_reported = False

    def link_hrbc(self, hrbc):
        self.hrbc = hrbc

    def process_coordination(self, train_id):
        self.logger.record("ARBC", "PROCESS_COORDINATION")
        return f"MA_BORDER_DATA_FOR_{train_id}"

    def accept_session(self):
        self.logger.record("ARBC", "EVALUATE_SESSION_REQ")
        if self.config["arbc_rejects_session"]:
            self.logger.record("ARBC", "REJECT_SESSION")
            return False
        self.logger.record("ARBC", "ACCEPT_SESSION")
        return True

    def process_report(self, position, rtm):
        self.logger.record("ARBC", "RX_POS_REPORT")
        if not self.front_end_reported:
            self.front_end_reported = True
            self.hrbc.acknowledge_takeover()
            
        if rtm.session_arbc:
            self.grant_supervision(rtm)

    def grant_supervision(self, rtm):
        self.logger.record("ARBC", "TX_GRANT_SUPERVISION")
        rtm.receive_from_arbc("GRANT_SUPERVISION", "NEW_SPEED_LIMIT")


def run_process_instance(trace_id, config):
    logger = SimulationLogger(trace_id, config)
    border_pos = 5000
    current_pos = 4800
    speed = config.get("speed", 25)

    dmi = DMI(logger)
    rtm = RTM(logger, config)
    evc = EVC(logger, config, dmi, rtm)
    arbc = ARBC(logger, config)
    hrbc = HRBC(logger, arbc)
    
    arbc.link_hrbc(hrbc)
    rtm.link_components(evc, hrbc, arbc)

    border_ma = hrbc.coordinate_border_ma(trace_id)
    hrbc.transmit_transition_order(rtm, border_ma)
    
    if config["has_dual_radio"]:
        rtm.establish_arbc_session()

    while rtm.session_hrbc or (rtm.session_arbc and not evc.supervision_granted and not evc.emergency_brake_active):
        logger.tick(steps=1) 
        current_pos += speed
        
        evc.evaluate_front_end_position(current_pos, border_pos)
        evc.evaluate_rear_end_position(current_pos, border_pos)
        
        if evc.emergency_brake_active:
            break

    return evc, rtm, logger