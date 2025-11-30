import threading
import time
from queue import Queue

import shared
from state_machine import StateMachine


class MockSerial:
    """Mock serial controller to simulate Arduino responses for tests.
    Methods mimic the minimal API used by the state machine: `read()` and `write()`.
    """

    def __init__(self):
        self.incoming = Queue()  # values that Arduino would send to us (ints)
        self.outgoing = Queue()  # values we send (ints)

    def is_ok(self):
        return True

    def read(self, timeout=1.0):
        try:
            # wait briefly for a value to appear (simulate blocking read)
            value = self.incoming.get(timeout=timeout)
            print(f"[MOCK SERIAL] read() -> {value}")
            return value
        except Exception:
            # simulate no data available
            return None

    def write(self, value):
        try:
            self.outgoing.put(value)
            print(f"[MOCK SERIAL] write({value})")
            return True
        except Exception as e:
            print(f"[MOCK SERIAL] write error: {e}")
            return False


def state_machine_thread_fn(machine):
    while not stop_event.is_set():
        try:
            event = shared.event_queue.get(timeout=0.1)
        except Exception:
            continue
        print(f"[TEST] Dispatching event: {event}")
        machine.handle_event(event)
        print(f"[TEST] State now: {machine.state}\n")


if __name__ == "__main__":
    # replace real serial controller with mock
    mock = MockSerial()
    shared.serial_ctrl = mock

    machine = StateMachine()

    # start thread that processes events using the StateMachine
    stop_event = threading.Event()
    t = threading.Thread(target=state_machine_thread_fn, args=(machine,), daemon=True)
    t.start()

    # Sequence of events and mock serial responses to simulate handshake and object flow
    try:
        # 1) Initialization -> WEBSERVER_ON
        shared.event_queue.put({"type": "INICIAL"})
        time.sleep(0.2)

        # 2) simulate webserver ready
        shared.webserver_ok = True
        shared.event_queue.put({"type": "WEBSERVER_ON"})
        time.sleep(0.2)

        # 3) camera online
        shared.web_data['camera_ok'] = True
        shared.event_queue.put({"type": "CAM_ONLINE"})
        time.sleep(0.2)

        # 4) web done -> serial on
        shared.event_queue.put({"type": "WEB_DONE"})
        time.sleep(0.2)

        # Prepare serial responses for handshake: Arduino will send 0 then later 2
        mock.incoming.put(0)  # for SERIAL_ON read
        shared.event_queue.put({"type": "SERIAL_ON"})
        time.sleep(0.3)

        # After our write(1) the Arduino should respond with 2, simulate that
        mock.incoming.put(2)
        shared.event_queue.put({"type": "SERIAL_ON_ACK"})
        time.sleep(0.3)

        # Now we should be in IDLE
        # Simulate object detected by vision
        shared.web_data['obj_detected'] = True
        # IDLE event triggers write(3)
        shared.event_queue.put({"type": "IDLE"})
        time.sleep(0.2)

        # To progress picking object, machine expects a read==4, then will write 5
        mock.incoming.put(4)
        # trigger object detect event (use different labels accepted by machine)
        shared.event_queue.put({"type": "OBJETO_DETECTADO"})
        time.sleep(0.3)

        # Then simulate response 6 to allow gondola selection
        mock.incoming.put(6)
        shared.event_queue.put({"type": "OBJ_DEFINED"})
        time.sleep(0.3)

        # Then simulate response 8 to move to drop
        mock.incoming.put(8)
        shared.event_queue.put({"type": "GONDOLA_SET"})
        time.sleep(0.3)

        # Then simulate response 10 to drop and finish
        mock.incoming.put(10)
        shared.event_queue.put({"type": "DROP_OBJECT"})
        time.sleep(0.3)

        print("[TEST] Outgoing messages captured on mock serial:")
        while not mock.outgoing.empty():
            print(" ->", mock.outgoing.get())

    finally:
        stop_event.set()
        t.join(timeout=1.0)
        print("[TEST] Finished")
