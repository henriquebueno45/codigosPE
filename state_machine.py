# state_machine.py
from datetime import datetime
import time
import shared


class StateMachine:
    def __init__(self):
        self.state = "INICIAL"
        self.await_tool_since = None
        self.state_timestamp = time.time()

    def _set_state(self, new_state):
        self.state = new_state
        self.state_timestamp = time.time()

    def _read_serial(self, attempts=4, wait=0.05):
        """Try reading serial multiple times to avoid transient None reads."""
        for _ in range(attempts):
            try:
                value = shared.serial_ctrl.read()
            except Exception:
                value = None
            if value is not None:
                return value
            time.sleep(wait)
        return None

    def getState(self):
        return self.state
    
    def handle_event(self, event):
        if not isinstance(event, dict) or 'type' not in event:
            return

        e = event['type']

        # INITIALIZATION
        if e == "INICIAL":
            print(f"[SYS_ON] - Sistema inicializado: {datetime.now()}")
            self.state = "WEBSERVER_ON"
            return

        if e == "WEBSERVER_ON":
            if shared.webserver_ok:
                print(f"[WEBSERVER_ON] - Webserver started correctly - {datetime.now()}")
                self.state = "WEB_DONE"
            else:
                # remain waiting for webserver
                self.state = "WEBSERVER_ON"
            return

        if e == "CAM_ONLINE":
            if shared.web_data.get('camera_ok'):
                print(f"[CAM_ONLINE] - Camera initialized - {datetime.now()}")
                self.state = "WEB_DONE"
            return

        if e == "WEB_DONE":
            self.state = "SERIAL_ON"
            return

        # SERIAL INITIALIZATION / HANDSHAKE
        if e == "SERIAL_ON":
            print(f"[SERIAL_ON] - Serial started, waiting confirmation - {datetime.now()}")
            value = self._read_serial()
            if value == 0:
                try:
                    shared.serial_ctrl.write(1)
                except Exception:
                    pass
                self.state = "SERIAL_ON_ACK"
            return

        if e == "SERIAL_ON_ACK":
            print(f"[SERIAL_ACK] - Serial comms confirmed - {datetime.now()}")
            value = self._read_serial()
            if value == 2:
                self.state = "IDLE"
            return

        # IDLE: wait for vision to report detection
        if e == "IDLE":
            print(f"[IDLE]: Reading images to find objects - {datetime.now()}")
            # prefer reacting to explicit vision events; but also accept flag polling
            if shared.web_data.get("obj_detected"):
                try:
                    shared.serial_ctrl.write(3)
                except Exception:
                    pass
                self._set_state("OBJ_DETECTED")
            return

        # Vision sent a debounced tool identification event
        if e == "TOOL_IDENTIFIED":
            # update shared state from the event payload if present
            lbl = event.get('label') if isinstance(event, dict) else None
            if lbl:
                shared.web_data['label_detected_object'] = lbl
                shared.web_data['tool_identified'] = True
            # if we are idle, trigger the pick sequence
            if self.state == "IDLE":
                try:
                    shared.serial_ctrl.write(3)
                except Exception:
                    pass
                self._set_state("OBJ_DETECTED")
            return

        # Accept both names in case other modules use different labels
        if e == "OBJ_DETECTED":
            print(f"[OBJ_DETECTED]: Detected object. Grabbing object - {datetime.now()}")
            value = self._read_serial()
            print("TO DENTRO DO OBJ_DETECT, VALUE LIDO:", value)
            print("TO DENTRO DO OBJ_DETECT, TOOL_IDENTIFIED:", shared.web_data.get("tool_identified"))
            # If device reports ready for identification (4) but vision hasn't confirmed,
            # enter a short wait state for the debounced identification instead of failing.
            if value == 4 and shared.web_data.get("tool_identified"):
                if shared.web_data.get("label_detected_object") is not False:
                    shared.serial_ctrl.write(5)
                    self._set_state("OBJ_DEFINED")
            elif value == 4 and not shared.web_data.get("tool_identified"):
                # start waiting for the vision system to confirm the tool
                print("[OBJ_DETECTED] Waiting for tool identification (AWAIT_TOOL_IDENT)")
                try:
                    self.await_tool_since = time.time()
                except Exception:
                    self.await_tool_since = None
                self._set_state("AWAIT_TOOL_IDENT")
            return

        if e == "AWAIT_TOOL_IDENT":
            # if vision confirms tool within timeout, proceed; otherwise timeout back to IDLE
            if shared.web_data.get("tool_identified"):
                # write confirm and move on
                try:
                    shared.serial_ctrl.write(5)
                except Exception:
                    pass
                self._set_state("OBJ_DEFINED")
                return

            now = time.time()
            since = self.await_tool_since or self.state_timestamp
            if now - since > 3.0:
                print("[AWAIT_TOOL_IDENT] Timeout waiting for tool identification; aborting to IDLE")
                shared.web_data["obj_detected"] = False
                shared.web_data["tool_identified"] = False
                self._set_state("IDLE")
            return

        if e == "OBJ_DEFINED":
            print(f"[OBJ_DEFINED]: Object grabbed. Defining gondola - {datetime.now()}")
            value = self._read_serial()

            if value == 6:
                print("------------------------------------------------------------------------")
                print("LABEL DETECTED OBJECT:", shared.web_data.get("label_detected_object"))
                print("------------------------------------------------------------------------")
                if shared.web_data.get("label_detected_object") == "pliers":
                    valor = 71  # Adicionar lógica para definir qual objeto vai em qual gondola
                elif shared.web_data.get("label_detected_object") == "screwdriver":
                    valor = 72
                elif shared.web_data.get("label_detected_object") == "hammer":
                    valor = 73
                elif shared.web_data.get("label_detected_object") == "wrench":
                    valor = 74
                elif shared.web_data.get("label_detected_object") == "drill":
                    valor = 75
                else:
                    valor = 76               
                #valor = 71  # Adicionar lógica para definir qual objeto vai em qual gondola
                shared.serial_ctrl.write(valor)
                self.state = "GONDOLA_SET"
            return

        if e == "GONDOLA_SET":
            print(f"[GONDOLA_SET]: Gondola defined. Moving to gondola - {datetime.now()}")
            value = self._read_serial()
            if value == 8:
                try:
                    shared.serial_ctrl.write(9)
                except Exception:
                    pass
                self.state = "DROP_OBJECT"
            return

        if e == "DROP_OBJECT":
            print(f"[DROP_OBJECT]: Releasing object - {datetime.now()}")
            value = self._read_serial()
            if value == 10:
                try:
                    shared.serial_ctrl.write(11)
                except Exception:
                    pass
                # return to a safe state (acknowledge loop)
                shared.web_data["obj_detected"] = False
                shared.web_data["tool_identified"] = False
                self.state = "SERIAL_ON_ACK"
            return

        # Unknown/unhandled events: no state change
        return