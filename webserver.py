# webserver.py
from flask import Flask, Response, render_template_string, request, jsonify
from shared import web_data, frame_lock, camera_config, web_lock, crop_config, camera_restart
import shared
import builtins
import cv2
import time

app = Flask(__name__)

# Intercepta chamadas a print() no processo e envia para o buffer de logs
# Isso permite registrar no painel web as mensagens que apareceriam no terminal.
_orig_print = builtins.print
def _print_wrapper(*args, **kwargs):
    try:
        _orig_print(*args, **kwargs)
    finally:
        try:
            shared.append_log(" ".join(str(a) for a in args))
        except Exception:
            pass
builtins.print = _print_wrapper

HTML = """
<html>
<head>
<title>Visão – Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">

<style>
/* ======================== */
/*       THEME COLORS       */
/* ======================== */
:root {
    --bg: #0a0f16;
    --card: rgba(255,255,255,0.06);
    --card-border: rgba(255,255,255,0.09);
    --text: #f3f7ff;
    --muted: #9aa4b6;
    --accent: #3f8cfa;
    --accent-hover: #70a8ff;
    --danger: #ff6b6b;
    --success: #4ade80;

    --radius: 14px;
    --shadow: 0 8px 25px rgba(0,0,0,0.55);
}

/* ======================== */
/*        GLOBAL STYLE      */
/* ======================== */
body {
    margin: 0;
    background: radial-gradient(circle at top, #111827, #0a0f16 60%);
    font-family: 'Inter', Arial, sans-serif;
    color: var(--text);
    animation: fadeIn 0.4s ease-out;
}

@keyframes fadeIn {
    from { opacity:0; translate:0 10px; }
    to   { opacity:1; translate:0 0; }
}

/* ======================== */
/*         TOP BAR          */
/* ======================== */
.topbar {
    backdrop-filter: blur(18px);
    background: rgba(255,255,255,0.04);
    border-bottom: 1px solid rgba(255,255,255,0.05);
    padding: 16px 28px;
    display: flex;
    align-items: center;
}

.topbar h1 {
    margin: 0;
    font-size: 21px;
    font-weight: 600;
}

.subtitle {
    margin-left: auto;
    font-size: 13px;
    color: var(--muted);
}

/* ======================== */
/*        MAIN GRID         */
/* ======================== */
.container {
    display: flex;
    gap: 26px;
    padding: 26px;
    max-width: 1400px;
    margin: auto;
}

.card {
    background: var(--card);
    border: 1px solid var(--card-border);
    padding: 20px;
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    backdrop-filter: blur(12px);
}

.left { 
    flex: 2; 
    display: flex;
    flex-direction: column;
}

/* RIGHT COLUMN (REFERENCE HEIGHT) */
.right { 
    flex: 1; 
    display:flex; 
    flex-direction:column; 
    max-height:650px;
}

/* ======================== */
/*     CAMERA SAME HEIGHT   */
/* ======================== */
.camera-wrapper {
    flex: 1;              /* ocupa a mesma altura que os logs */
    display: flex;
}

img.camera {
    width: 100%;
    height: 100%;         /* agora a câmera terá a MESMA altura */
    object-fit: cover;
    border-radius: var(--radius);
    background: #000;
    border: 1px solid rgba(255,255,255,0.07);
}

/* ======================== */
/*          STATUS          */
/* ======================== */
#status {
    margin-top: 12px;
    font-size: 15px;
    background: rgba(255,255,255,0.03);
    padding: 10px 12px;
    border-radius: var(--radius);
    border: 1px solid rgba(255,255,255,0.05);
}

.status-ok { color: var(--success); }
.status-error { color: var(--danger); }

/* ======================== */
/*          BUTTONS         */
/* ======================== */
button {
    background: var(--accent);
    color: white;
    padding: 10px 14px;
    font-size: 14px;
    border: none;
    border-radius: var(--radius);
    cursor: pointer;
    font-weight: 500;
    transition: 0.2s;
}

button:hover { background: var(--accent-hover); transform: translateY(-2px); }

/* ======================== */
/*           LOGS           */
/* ======================== */
.logs-title {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 12px;
}

.logs {
    background: rgba(0,0,0,0.22);
    padding: 12px;
    border-radius: var(--radius);
    overflow-y: auto;
    border: 1px solid rgba(255,255,255,0.05);
    flex: 1;
}

.log-item {
    padding: 8px 6px;
    font-family: monospace;
    font-size: 13px;
    border-left: 2px solid #3f8cfa55;
    margin-bottom: 6px;
    background: rgba(255,255,255,0.03);
    border-radius: 6px;
}

.log-time {
    color: var(--muted);
    margin-right: 8px;
}

/* ======================== */
/*        RESPONSIVE        */
/* ======================== */
@media (max-width: 900px) {
    .container { flex-direction: column; }
    .right { max-height: 500px; }
}
</style>
</head>

<body>

<div class="topbar">
    <h1>Painel de Processamento de Imagem</h1>
    <div class="subtitle">Monitoramento em tempo real – Projeto Especializado</div>
</div>

<div class="container">

    <div class="left card">

        <!-- CAMERA MATCHING LOG HEIGHT -->
        <div class="camera-wrapper">
            <img class="camera" src="/video_feed" alt="Camera feed">
        </div>

        <div id="status">Carregando status...</div>

        <div class="controls" style="margin-top:12px;">
            <button onclick="window.location.reload()">Recarregar Página</button>
        </div>
    </div>

    <div class="right card">
        <div class="logs-title">Logs do Sistema</div>
        <div id="logs" class="logs"></div>
    </div>

</div>

<script>
// Atualiza status
setInterval(()=>{
    fetch('/status').then(r=>r.json()).then(d=>{
        const el = document.getElementById('status');

        if(!d.camera_ok){
            el.innerHTML = '<b class="status-error">● Câmera não inicializada</b>';
        } else {
            el.innerHTML = '<b class="status-ok">● Operacional</b> — Último objeto: <b>' +
                d.last_label + '</b> (' + d.last_conf.toFixed(2) + ')';
        }
    }).catch(()=>{});
}, 400);

// Logs
let shown = new Set();
async function fetchLogs(){
    try{
        let res = await fetch('/logs');
        if(!res.ok) return;

        let arr = await res.json();
        const container = document.getElementById('logs');
        let html = '';

        for(let it of arr){
            const key = it.ts + '|' + it.msg;
            if(shown.has(key)) continue;
            shown.add(key);

            const t = new Date(it.ts*1000).toLocaleTimeString();
            html += `
                <div class="log-item">
                    <span class="log-time">[${t}]</span>${escapeHtml(it.msg)}
                </div>
            `;
        }

        if(html) container.insertAdjacentHTML('beforeend', html);
        container.scrollTop = container.scrollHeight;

    }catch(e){}
}

function escapeHtml(s){
    return s.replace(/&/g,'&amp;')
            .replace(/</g,'&lt;')
            .replace(/>/g,'&gt;');
}

setInterval(fetchLogs, 600);
window.onload = fetchLogs;
</script>

</body>
</html>
"""




@app.route("/")
def index():
    shared.webserver_ok = True
    print("[WEBSERVER] Webserver iniciado.")
    return render_template_string(HTML)


def gen_frames():
    while True:
        with frame_lock:
            frame = web_data["frame"]

        if frame is None:
            time.sleep(0.05)
            continue

        _, buffer = cv2.imencode(".jpg", frame)
        frame_bytes = buffer.tobytes()

        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" +
               frame_bytes + b"\r\n")


@app.route("/video_feed")
def video_feed():
    return Response(gen_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/status")
def status():
    with frame_lock:
        return {
            "camera_ok": web_data["camera_ok"],
            "last_label": web_data["last_label"],
            "last_conf": web_data["last_conf"]
        }


@app.route('/logs')
def get_logs():
    # Retorna os logs coletados pelo shared (mais recentes primeiro)
    with shared.web_logs_lock:
        return jsonify(list(shared.web_logs))


@app.route('/config', methods=['GET'])
def get_config():
    with web_lock:
        return jsonify({
            'camera_index': camera_config.get('camera_index', 0),
            'width': camera_config.get('width', 640),
            'height': camera_config.get('height', 480)
            ,
            'x_min': crop_config.get('x_min', 0),
            'x_max': crop_config.get('x_max', camera_config.get('width', 640)),
            'y_min': crop_config.get('y_min', 0),
            'y_max': crop_config.get('y_max', camera_config.get('height', 480))
        })


@app.route('/config', methods=['POST'])
def set_config():
    data = request.get_json(force=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    with web_lock:
        camera_config['camera_index'] = int(data.get('camera_index', camera_config.get('camera_index', 0)))
        camera_config['width'] = int(data.get('width', camera_config.get('width', 640)))
        camera_config['height'] = int(data.get('height', camera_config.get('height', 480)))

        # Crop (opcional)
        try:
            crop_config['x_min'] = int(data.get('x_min', crop_config.get('x_min', 0)))
            crop_config['x_max'] = int(data.get('x_max', crop_config.get('x_max', camera_config.get('width', 640))))
            crop_config['y_min'] = int(data.get('y_min', crop_config.get('y_min', 0)))
            crop_config['y_max'] = int(data.get('y_max', crop_config.get('y_max', camera_config.get('height', 480))))
        except Exception:
            pass

    return jsonify({'message': 'Configuração atualizada'})




