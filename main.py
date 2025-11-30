# main.py
import threading
import time
from vision import VisionSystem
from webserver import app
from state_machine import StateMachine

def start_web():
    import shared
    shared.webserver_ok = True
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)


if __name__ == "__main__":
    sm = StateMachine()
    vision = VisionSystem()

    t1 = threading.Thread(target=vision.loop, daemon=True)
    t1.start()

    t2 = threading.Thread(target=start_web, daemon=True)
    t2.start()

    print("[MAIN] Sistema iniciado.")
    antigo_estado = "SLA"
    while True:
        sm.handle_event({'type': sm.state})
        if antigo_estado != sm.getState():
            print(sm.getState())
            antigo_estado = sm.getState()
        time.sleep(0.05)

'''
#TODO: Dimensionamento dinâmico da câmera (o usuário deve poder ajustar a resolução via web)
#TODO: Os algoritmo de YOLO e de passagem por linha devem ser integrados em um único módulo de visão
#TODO: Fazer um diagrama no webserver com as gôndolas para que o usuário escolha onde qual peça vai ficar
'''

