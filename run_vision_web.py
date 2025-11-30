#!/usr/bin/env python3
"""
run_vision_web.py

Simple runner that starts the VisionSystem and the Flask webserver
together so you can visualize the vision algorithm via the web UI.

Usage (from project root):
    python run_vision_web.py

This script does NOT modify existing files. It adds the `main` folder
to `sys.path` so modules like `vision.py` and `webserver.py` import
their local `shared` module as intended.
"""
import os
import sys
import threading
import time

# Ensure the `main` folder is importable so modules using plain
# `from shared import ...` work as expected.
BASE_DIR = os.path.dirname(__file__)
MAIN_DIR = os.path.join(BASE_DIR, 'main')
if MAIN_DIR not in sys.path:
    sys.path.insert(0, MAIN_DIR)

try:
    from vision import VisionSystem
    import webserver
    import shared
except Exception as e:
    print("[RUN] Erro ao importar módulos de 'main':", e)
    print("[RUN] Verifique se você está rodando este script a partir do diretório do projeto.")
    raise


def start_vision():
    """Create and start the VisionSystem loop in a daemon thread."""
    print("[RUN] Inicializando VisionSystem...")
    vs = VisionSystem()
    t = threading.Thread(target=vs.loop, name='VisionLoop', daemon=True)
    t.start()
    return vs, t


def start_webserver(host='0.0.0.0', port=5000):
    """Start the Flask webserver from `webserver.app` in a daemon thread."""
    def run_app():
        print(f"[RUN] Iniciando webserver Flask em http://{host}:{port} ...")
        # disable reloader to avoid double-start when running in a thread
        webserver.app.run(host=host, port=port, threaded=True, use_reloader=False)

    t = threading.Thread(target=run_app, name='WebServer', daemon=True)
    t.start()
    return t


def main():
    print(f"[RUN] Adicionando '{MAIN_DIR}' ao sys.path e iniciando serviços...")
    vs, vthread = start_vision()
    wthread = start_webserver()

    print("[RUN] Ambos iniciados. Abra o navegador e acesse: http://<rasp_ip>:5000")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('\n[RUN] Interrompido por teclado. Encerrando...')


if __name__ == '__main__':
    main()
