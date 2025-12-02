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
    "obj_detected": False,
    "tool_identified": False,
    "label_detected_object": None,
    "count_fail": 0,
    
    # NOVO: Gôndola atualmente sendo processada (position_id ou None)
    "current_gondola": None,
    
    "gondola_positions": [
        {"label": "pliers", "position_id": 71},
        {"label": "screwdriver", "position_id": 72},
        {"label": "hammer", "position_id": 73},
        {"label": "wrench", "position_id": 74},
        {"label": "saw", "position_id": 75},
    ],
}

web_lock = threading.Lock()
webserver_ok = False
cv_on = False
serial_ctrl = SerialControl("/dev/ttyUSB0", 9600)

# Configuração da câmera (pode ser alterada via web)
camera_config = {
    "camera_index": 0,
    "width": 640,
    "height": 480
}

# Configuração de recorte (em pixels, coordenadas na imagem original):
crop_config = {
    "x_min": 0,
    "y_min": 0,
    "x_max": camera_config["width"],
    "y_max": camera_config["height"]
}

# Evento para reiniciar a câmera a partir do webserver
camera_restart = threading.Event()

# Mapeamento de gôndolas (controlado pelo webserver)
gondolas = []

# Buffer de logs para o webserver
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


# ---------------------------------------------------------------
# FUNÇÕES AUXILIARES PARA CONTROLE DE GÔNDOLA ATIVA
# ---------------------------------------------------------------

def set_current_gondola(position_id):
    """
    Define qual gôndola está sendo processada atualmente.
    Isso ativa o highlight visual no dashboard web.
    
    Args:
        position_id: O ID da posição da gôndola (ex: 71, 72, 73...)
                     ou None para remover o highlight
    
    Exemplo de uso na sua state machine:
        # Quando começar a processar uma gôndola
        shared.set_current_gondola(73)
        
        # Quando terminar
        shared.set_current_gondola(None)
    """
    with frame_lock:
        web_data["current_gondola"] = position_id
    
    if position_id is not None:
        append_log(f"🎯 Processando gôndola: Position ID {position_id}")
    else:
        append_log("✓ Gôndola finalizada")


def get_current_gondola():
    """
    Retorna o position_id da gôndola atualmente sendo processada.
    
    Returns:
        int ou None: Position ID da gôndola ativa
    """
    with frame_lock:
        return web_data.get("current_gondola")


def find_gondola_by_label(label):
    """
    Procura uma gôndola pelo label detectado.
    
    Args:
        label: String do label detectado (ex: "pliers", "hammer")
    
    Returns:
        dict ou None: Dicionário da gôndola {label, position_id} ou None
    
    Exemplo:
        gondola = shared.find_gondola_by_label("hammer")
        if gondola:
            shared.set_current_gondola(gondola['position_id'])
    """
    with web_lock:
        gondola_list = web_data.get("gondola_positions", [])
        for g in gondola_list:
            if g.get("label") == label:
                return g
        return None


def get_all_gondolas():
    """
    Retorna a lista completa de gôndolas configuradas.
    
    Returns:
        list: Lista de dicionários [{label, position_id}, ...]
    """
    with web_lock:
        return list(web_data.get("gondola_positions", []))