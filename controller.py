import threading
from queue import Queue
from main.vision import VisionSystem
from state_machine import StateMachine
from shared import event_queue, serial_ctrl
import time

event_queue = Queue()

vision = VisionSystem(event_queue)
machine = StateMachine()

def vision_thread():
    vision.loop()

def state_machine_thread():
    while True:
        event = event_queue.get()
        machine.handle_event(event)

threading.Thread(target=vision_thread, daemon=True).start()
threading.Thread(target=state_machine_thread, daemon=True).start()

while True:
    time.sleep(1)
