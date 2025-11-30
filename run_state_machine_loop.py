"""
Run StateMachine using a pyserial loop:// port so you can see the prints
and verify transitions interactively without hardware.

Usage (PowerShell):
  pip install pyserial
  python .\main\run_state_machine_loop.py

This script will:
 - open a virtual loopback serial port (loop://)
 - wrap it with a small adapter exposing read()/write() used by StateMachine
 - step through a sequence of events (INICIAL -> WEBSERVER_ON -> CAM_ONLINE -> ...)
 - simulate Arduino responses by writing values into the loop before calling events

You will see the prints from `state_machine.py` (via handle_event) in the console.
"""

import time
import serial
import shared
from state_machine import StateMachine


class PySerialAdapter:
    """Adapter to expose the minimal SerialControl API used by StateMachine.
    It wraps a pyserial Serial-like object (serial_for_url('loop://')).
    """

    def __init__(self, ser):
        self.ser = ser

    def is_ok(self):
        return self.ser is not None

    def read(self):
        try:
            line = self.ser.readline().decode(errors='ignore').strip()
            if line == '':
                return None
            print(f"[ADAPTER] read() -> '{line}'")
            try:
                return int(line)
            except Exception:
                return None
        except Exception as e:
            print(f"[ADAPTER] read exception: {e}")
            return None

    def write(self, value):
        try:
            s = (str(value) + "\n").encode()
            self.ser.write(s)
            print(f"[ADAPTER] write({value})")
            return True
        except Exception as e:
            print(f"[ADAPTER] write error: {e}")
            return False


def send_to_serial_raw(ser, value):
    """Write a raw value to the underlying pyserial object (simulate Arduino sending)."""
    ser.write((str(value) + "\n").encode())
    # small delay so data appears to reader
    time.sleep(0.05)


def main():
    print("Abrindo porta: loop:// (baud=9600)")
    ser = serial.serial_for_url('loop://', timeout=1)
    adapter = PySerialAdapter(ser)
    # assign to shared so state_machine will use it
    shared.serial_ctrl = adapter

    machine = StateMachine()

    def step_and_print(event):
        print(f"\n--- Chamando handle_event: {event} ---")
        machine.handle_event({'type': event})
        print(f"Estado atual: {machine.state}")

    # Sequence similar to the test script, but using loop://
    try:
        step_and_print('INICIAL')

        # Simulate webserver up
        shared.webserver_ok = True
        step_and_print('WEBSERVER_ON')

        # Simulate camera available
        shared.web_data['camera_ok'] = True
        step_and_print('CAM_ONLINE')

        step_and_print('WEB_DONE')

        # Prepare handshake: Arduino will send 0
        send_to_serial_raw(ser, 0)
        step_and_print('SERIAL_ON')

        # After our write(1), Arduino should send 2 - simulate it
        send_to_serial_raw(ser, 2)
        step_and_print('SERIAL_ON_ACK')

        # Now in IDLE - simulate object detection
        shared.web_data['obj_detected'] = True
        step_and_print('IDLE')

        # simulate Arduino responds with 4 for grab
        send_to_serial_raw(ser, 4)
        step_and_print('OBJETO_DETECTADO')

        # simulate Arduino responds with 6 for gondola
        send_to_serial_raw(ser, 6)
        step_and_print('OBJ_DEFINED')

        # simulate Arduino responds with 8 to move
        send_to_serial_raw(ser, 8)
        step_and_print('GONDOLA_SET')

        # simulate Arduino responds with 10 to drop
        send_to_serial_raw(ser, 10)
        step_and_print('DROP_OBJECT')

        print("\nSequência finalizada. Verifique os prints acima para validar a lógica.")

    finally:
        try:
            ser.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
