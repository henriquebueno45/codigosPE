"""
Interactive runner for StateMachine.

- Starts a non-blocking stdin reader thread where you can type integer values
  that simulate data received from the serial device.
- Uses a lightweight in-process `InteractiveSerialMock` assigned to
  `shared.serial_ctrl` so `state_machine` reads the user-typed values.
- Dispatches events in sequence and polls the machine until it transitions,
  so the program never blocks waiting on input.

Usage (PowerShell):
  pip install pyserial
  python .\main\run_state_machine_interactive.py

How to use:
 - The script will show each dispatched event and what serial values the
   state machine expects next (hints).
 - Type an integer and press Enter to simulate the Arduino sending that
   integer (newline-terminated). You can type values at any time.
"""

import threading
import time
import queue
import shared
from state_machine import StateMachine


class InteractiveSerialMock:
    def __init__(self):
        self.incoming = queue.Queue()

    def is_ok(self):
        return True

    def read(self):
        # non-blocking read: return an int if available, otherwise None
        try:
            value = self.incoming.get_nowait()
            print(f"[MOCK SERIAL] read() -> {value}")
            return value
        except queue.Empty:
            return None

    def write(self, value):
        print(f"[MOCK SERIAL] write({value})")
        return True


def stdin_reader(mock):
    print('\nInteractive serial stdin reader started.')
    print('Type integer values and press Enter to simulate serial input (Ctrl+C to exit).')
    while True:
        try:
            s = input('> ')
        except EOFError:
            break
        except KeyboardInterrupt:
            print('\nStopping stdin reader.')
            break

        s = s.strip()
        if s == '':
            continue
        try:
            v = int(s)
            mock.incoming.put(v)
        except ValueError:
            print("Valor inválido. Digite um inteiro, p.ex. 0 or 2 or 4.")


def dispatch_and_wait(machine, event_type, poll_interval=0.5, hint=None):
    print(f"\n--- Dispatching event: {event_type} ---")
    if hint:
        print(f"(hint: {hint})")
    prev_state = machine.state
    # call handle_event repeatedly until state changes from prev_state or until a few iterations
    max_cycles = 300  # total wait time ~ max_cycles * poll_interval
    cycles = 0
    while cycles < max_cycles:
        machine.handle_event({'type': event_type})
        print(f"State: {machine.state}")
        if machine.state != prev_state:
            break
        time.sleep(poll_interval)
        cycles += 1
    if cycles >= max_cycles:
        print(f"(no state change after {max_cycles * poll_interval}s) moving on")


def main():
    mock = InteractiveSerialMock()
    shared.serial_ctrl = mock

    # start stdin reader thread (daemon so Ctrl+C stops everything)
    t = threading.Thread(target=stdin_reader, args=(mock,), daemon=True)
    t.start()

    machine = StateMachine()

    try:
        # Sequence of events to exercise the state machine
        dispatch_and_wait(machine, 'INICIAL')

        # Bring webserver up, then CAM
        shared.webserver_ok = True
        dispatch_and_wait(machine, 'WEBSERVER_ON')

        shared.web_data['camera_ok'] = True
        dispatch_and_wait(machine, 'CAM_ONLINE')

        dispatch_and_wait(machine, 'WEB_DONE')

        # Now handshake: the machine will call read() and expects 0 to reply
        dispatch_and_wait(machine, 'SERIAL_ON', hint="type '0' to simulate Arduino sending 0")

        dispatch_and_wait(machine, 'SERIAL_ON_ACK', hint="type '2' to simulate Arduino sending 2")

        # IDLE -> if web_data['obj_detected'] True it will write 3 and change
        print('\nNow state machine is in IDLE. To simulate detection, set web_data[\'obj_detected\']=True or type the corresponding serial responses when prompted.')
        # Wait a bit and then set detection so state transitions to OBJ_DETECTED example
        shared.web_data['obj_detected'] = True
        dispatch_and_wait(machine, 'IDLE', hint="(machine will write 3 when detection occurs)")

        # For grabbing object: machine expects 4
        dispatch_and_wait(machine, 'OBJETO_DETECTADO', hint="type '4' to simulate Arduino acknowledging grab")

        # For gondola: machine expects 6 then will write 71
        dispatch_and_wait(machine, 'OBJ_DEFINED', hint="type '6' to simulate Arduino asking for gondola selection")

        dispatch_and_wait(machine, 'GONDOLA_SET', hint="type '8' to simulate Arduino moved to gondola")

        dispatch_and_wait(machine, 'DROP_OBJECT', hint="type '10' to simulate Arduino drop confirmation")

        print('\nInteractive run finished. You can continue typing integers and call handle_event again if you like.')

    except KeyboardInterrupt:
        print('\nInterrupted by user.')


if __name__ == '__main__':
    main()
