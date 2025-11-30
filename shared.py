import threading
from queue import Queue
from serial_control import SerialControl
from robot_controller import RobotController
from collections import deque
import time
# ---------------------------------------------------------------
# FILA DE EVENTOS (para comunicação visão -> máquina de estados)
# ---------------------------------------------------------------
event_queue = Queue()
robot_ctrl = RobotController()
# ---------------------------------------------------------------
# FILA PARA SOLICITAR AÇÕES À VISÃO (opcional; pode ser usada no futuro)
# ---------------------------------------------------------------
vision_queue = Queue()

# ---------------------------------------------------------------
# RESULTADOS DA VISÃO (para compartilhar com webserver)
# ---------------------------------------------------------------
vision_result = {
    "new_detection": False,
    "data": None,  # Exemplo: {label:"parafuso", conf:0.87, bbox:[x1,y1,x2,y2]}
}

# Lock para proteger visão/webserver
frame_lock = threading.Lock()

# ---------------------------------------------------------------
# DADOS QUE O WEBSERVER USA
# ---------------------------------------------------------------
web_data = {
    "camera_ok": False,
    "state": "IDLE",
    # current frame (None until vision writes one)
    "frame": None,
    "last_label": "Nenhum objeto detectado",
    "last_conf": 0.0,
    "obj_detected":False,
    "tool_identified": False,
    "label_detected_object": None
}

web_lock = threading.Lock()
webserver_ok = False  # <--- NOVO
cv_on = False
serial_ctrl = SerialControl("/dev/ttyUSB0", 9600)

# Configuração da câmera (pode ser alterada via web)
camera_config = {
    "camera_index": 0,
    "width": 640,
    "height": 480
}

# Configuração de recorte (em pixels, coordenadas na imagem original):
# x_min, y_min inclusive; x_max, y_max exclusive. Por padrão não recorta (usa toda a imagem).
crop_config = {
    "x_min": 0,
    "y_min": 0,
    "x_max": camera_config["width"],
    "y_max": camera_config["height"]
}

# Evento para reiniciar a câmera a partir do webserver
camera_restart = threading.Event()

# Mapeamento de gôndolas (ex.: lista de posições / IDs) — controlado pelo webserver
gondolas = []

# Buffer de logs para o webserver (mensagens exibidas na UI)
# Cada item: {'ts': <float epoch>, 'msg': <string>}
web_logs = deque(maxlen=500)
web_logs_lock = threading.Lock()

def append_log(msg: str):
    """Adiciona uma mensagem ao buffer de logs para exibição na web.
    Não repete mensagens consecutivas idênticas (reduz ruído).
    """
    if msg is None:
        return
    try:
        s = str(msg)
    except Exception:
        s = repr(msg)

    with web_logs_lock:
        if len(web_logs) == 0 or web_logs[-1]['msg'] != s:
            web_logs.append({'ts': time.time(), 'msg': s})