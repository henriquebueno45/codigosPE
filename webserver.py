from flask import Flask, Response, render_template_string, request, jsonify
from shared import web_data, frame_lock, camera_config, web_lock, crop_config, camera_restart
import shared
import builtins
import cv2
import time

app = Flask(__name__)

# Intercepta chamadas a print() no processo e envia para o buffer de logs
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
    --warning: #fbbf24;

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
    flex: 1;
    display: flex;
}

img.camera {
    width: 100%;
    height: 100%;
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

input {
    padding: 8px 12px;
    border-radius: 8px;
    border: 1px solid rgba(255,255,255,0.1);
    background: rgba(255,255,255,0.05);
    color: var(--text);
    font-size: 14px;
}

input:focus {
    outline: none;
    border-color: var(--accent);
}

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
/*      GONDOLA STYLES      */
/* ======================== */
.gondola-grid {
    margin-top: 10px;
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
}

.gondola-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.05);
    padding: 10px 12px;
    border-radius: 10px;
    min-width: 140px;
    text-align: center;
    display: flex;
    flex-direction: column;
    gap: 8px;
    cursor: grab;
    transition: all 0.2s;
}

.gondola-card:active {
    cursor: grabbing;
}

.gondola-card.dragging {
    opacity: 0.5;
    transform: scale(0.95);
}

.gondola-card.drag-over {
    border-color: var(--accent);
    background: rgba(63, 140, 250, 0.1);
}

/* ACTIVE GONDOLA HIGHLIGHT */
.gondola-card.active {
    border: 2px solid var(--success);
    background: rgba(74, 222, 128, 0.15);
    box-shadow: 0 0 20px rgba(74, 222, 128, 0.3);
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0%, 100% { box-shadow: 0 0 20px rgba(74, 222, 128, 0.3); }
    50% { box-shadow: 0 0 30px rgba(74, 222, 128, 0.5); }
}

.gondola-badge {
    display: inline-block;
    padding: 6px 10px;
    border-radius: 16px;
    background: var(--accent);
    color: white;
    font-weight: 600;
    position: relative;
}

.gondola-card.active .gondola-badge {
    background: var(--success);
}

.gondola-meta { 
    color: var(--muted); 
    font-size: 13px; 
}

.gondola-controls { 
    display:flex; 
    gap:6px; 
    justify-content:center; 
}

.gondola-controls button {
    padding: 6px 8px;
    font-size: 12px;
    border-radius: 8px;
}

/* DUPLICATE WARNING */
.duplicate-warning {
    background: rgba(251, 191, 36, 0.15);
    border: 1px solid var(--warning);
    padding: 8px;
    border-radius: 8px;
    color: var(--warning);
    font-size: 12px;
    margin-top: 4px;
    display: none;
}

.gondola-card.duplicate {
    border-color: var(--warning);
    background: rgba(251, 191, 36, 0.1);
}

.gondola-card.duplicate .duplicate-warning {
    display: block;
}

/* ======================== */
/*      MODAL STYLES        */
/* ======================== */
.modal-overlay {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    backdrop-filter: blur(4px);
    z-index: 1000;
    align-items: center;
    justify-content: center;
}

.modal-overlay.show {
    display: flex;
    animation: fadeIn 0.2s;
}

.modal {
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
    padding: 24px;
    max-width: 400px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.8);
}

.modal h3 {
    margin: 0 0 12px 0;
    font-size: 18px;
}

.modal p {
    color: var(--muted);
    margin: 0 0 20px 0;
    line-height: 1.5;
}

.modal-buttons {
    display: flex;
    gap: 10px;
    justify-content: flex-end;
}

.modal-buttons button {
    padding: 8px 16px;
}

.btn-danger {
    background: var(--danger);
}

.btn-danger:hover {
    background: #ff5252;
}

.btn-secondary {
    background: rgba(255,255,255,0.1);
}

.btn-secondary:hover {
    background: rgba(255,255,255,0.15);
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

        <div class="camera-wrapper">
            <img class="camera" src="/video_feed" alt="Camera feed">
        </div>

        <div id="status">Carregando status...</div>

        <div class="controls" style="margin-top:12px;">
            <button onclick="window.location.reload()">Recarregar Página</button>
        </div>
        
        <div class="controls" style="margin-top:12px;">
            <h3>Gôndolas</h3>
            <div id="gondola_list" class="gondola-grid"></div>
            <div style="margin-top:8px; display:flex; gap:10px; align-items:center;">
                <input id="new_gondola_label" placeholder="Label (ex: pliers)" />
                <input id="new_gondola_pos" placeholder="Pos (ex: 71)" style="width:80px;"/>
                <button id="add_gondola">Adicionar</button>
                <button id="save_gondolas">Salvar Gôndolas</button>
            </div>
        </div>
    </div>

    <div class="right card">
        <div class="logs-title">Logs do Sistema</div>
        <div id="logs" class="logs"></div>
    </div>

</div>

<!-- CONFIRMATION MODAL -->
<div id="confirmModal" class="modal-overlay">
    <div class="modal">
        <h3 id="modalTitle">Confirmar Ação</h3>
        <p id="modalMessage">Tem certeza que deseja continuar?</p>
        <div class="modal-buttons">
            <button class="btn-secondary" onclick="closeModal()">Cancelar</button>
            <button class="btn-danger" id="modalConfirm">Confirmar</button>
        </div>
    </div>
</div>

<script>
// ========================
// MODAL SYSTEM
// ========================
function showModal(title, message, onConfirm) {
    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalMessage').textContent = message;
    document.getElementById('confirmModal').classList.add('show');
    
    const confirmBtn = document.getElementById('modalConfirm');
    confirmBtn.onclick = function() {
        closeModal();
        onConfirm();
    };
}

function closeModal() {
    document.getElementById('confirmModal').classList.remove('show');
}

// ========================
// STATUS & LOGS
// ========================
setInterval(()=>{
    fetch('/status').then(r=>r.json()).then(d=>{
        const el = document.getElementById('status');

        if(!d.camera_ok){
            el.innerHTML = '<b class="status-error">● Câmera não inicializada</b>';
        } else {
            el.innerHTML = '<b class="status-ok">● Operacional</b> — Último objeto: <b>' +
                d.last_label + '</b> (' + d.last_conf.toFixed(2) + ')';
        }
        
        // Update current gondola highlight
        if(d.current_gondola !== undefined && d.current_gondola !== null) {
            window._current_gondola = d.current_gondola;
            highlightCurrentGondola();
        }
    }).catch(()=>{});
}, 400);

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

// ========================
// GONDOLA MANAGEMENT
// ========================
window._gondolas = [];
window._current_gondola = null;

async function fetchGondolas(){
    try{
        let res = await fetch('/gondolas');
        if(!res.ok) return;
        let arr = await res.json();
        window._gondolas = arr || [];
        renderGondolas();
    }catch(e){console.error(e)}
}

function findDuplicatePositions() {
    const positions = {};
    const duplicates = new Set();
    
    window._gondolas.forEach((g, idx) => {
        const pos = g.position_id;
        if(positions[pos] !== undefined) {
            duplicates.add(pos);
        }
        positions[pos] = idx;
    });
    
    return duplicates;
}

function highlightCurrentGondola() {
    document.querySelectorAll('.gondola-card').forEach(card => {
        card.classList.remove('active');
    });
    
    if(window._current_gondola !== null) {
        const card = document.querySelector(`[data-position="${window._current_gondola}"]`);
        if(card) {
            card.classList.add('active');
            card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }
}

function renderGondolas(){
    const el = document.getElementById('gondola_list');
    if(!window._gondolas) window._gondolas = [];
    
    const duplicates = findDuplicatePositions();
    
    el.innerHTML = '';
    for(let i=0;i<window._gondolas.length;i++){
        const it = window._gondolas[i];
        const isDuplicate = duplicates.has(it.position_id);
        const isActive = window._current_gondola === it.position_id;
        
        const div = document.createElement('div');
        div.className = 'gondola-card';
        if(isDuplicate) div.classList.add('duplicate');
        if(isActive) div.classList.add('active');
        
        div.setAttribute('draggable', 'true');
        div.setAttribute('data-idx', i);
        div.setAttribute('data-position', it.position_id);
        
        div.innerHTML = `
            <div class='gondola-badge'>${escapeHtml(it.label||'')}</div>
            <div class='gondola-meta'>Pos ID: <b>${it.position_id||''}</b></div>
            ${isDuplicate ? '<div class="duplicate-warning">⚠️ ID duplicado!</div>' : ''}
            <div class='gondola-controls'>
                <button class='g_edit' data-idx='${i}'>Editar</button>
                <button class='g_remove' data-idx='${i}'>Remover</button>
            </div>
        `;
        
        // Drag events
        div.addEventListener('dragstart', handleDragStart);
        div.addEventListener('dragend', handleDragEnd);
        div.addEventListener('dragover', handleDragOver);
        div.addEventListener('drop', handleDrop);
        div.addEventListener('dragleave', handleDragLeave);
        
        el.appendChild(div);
    }
    
    // Bind button events
    document.querySelectorAll('.g_remove').forEach(b=>b.onclick = function(ev){
        const idx = Number(ev.target.dataset.idx);
        const item = window._gondolas[idx];
        showModal(
            'Remover Gôndola',
            `Tem certeza que deseja remover "${item.label}" (Pos ${item.position_id})?`,
            () => {
                window._gondolas.splice(idx,1);
                renderGondolas();
            }
        );
    });
    
    document.querySelectorAll('.g_edit').forEach(b=>b.onclick = function(ev){
        const idx = Number(ev.target.dataset.idx);
        const item = window._gondolas[idx];
        const div = b.closest('.gondola-card');
        div.innerHTML = `
            <input class='g_label' data-idx='${idx}' value='${escapeHtml(item.label||'')}' placeholder='Label' /> 
            <input class='g_pos' data-idx='${idx}' value='${item.position_id||''}' style='width:80px;' /> 
            <div class='gondola-controls'>
                <button class='g_save' data-idx='${idx}'>Salvar</button>
                <button class='g_cancel' data-idx='${idx}'>Cancelar</button>
            </div>
        `;
        
        div.querySelector('.g_save').onclick = function(){
            const label = div.querySelector('.g_label').value.trim();
            const pos = parseInt(div.querySelector('.g_pos').value) || item.position_id;
            window._gondolas[idx] = {label: label, position_id: pos};
            renderGondolas();
        };
        
        div.querySelector('.g_cancel').onclick = function(){ 
            renderGondolas(); 
        };
    });
}

// ========================
// DRAG & DROP
// ========================
let dragSrcIdx = null;

function handleDragStart(e) {
    dragSrcIdx = parseInt(this.getAttribute('data-idx'));
    this.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
}

function handleDragEnd(e) {
    this.classList.remove('dragging');
    document.querySelectorAll('.gondola-card').forEach(card => {
        card.classList.remove('drag-over');
    });
}

function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';
    this.classList.add('drag-over');
    return false;
}

function handleDragLeave(e) {
    this.classList.remove('drag-over');
}

function handleDrop(e) {
    if (e.stopPropagation) {
        e.stopPropagation();
    }
    
    const dropIdx = parseInt(this.getAttribute('data-idx'));
    
    if (dragSrcIdx !== dropIdx) {
        // Reorder array
        const item = window._gondolas[dragSrcIdx];
        window._gondolas.splice(dragSrcIdx, 1);
        window._gondolas.splice(dropIdx, 0, item);
        renderGondolas();
    }
    
    return false;
}

// ========================
// ADD & SAVE GONDOLAS
// ========================
document.addEventListener('DOMContentLoaded', function(){
    fetchGondolas();
    
    document.getElementById('add_gondola').onclick = function(){
        const l = document.getElementById('new_gondola_label').value.trim();
        const p = parseInt(document.getElementById('new_gondola_pos').value) || 71 + (window._gondolas ? window._gondolas.length : 0);
        
        if(l){
            window._gondolas.push({label:l, position_id:p});
            renderGondolas();
            document.getElementById('new_gondola_label').value = '';
            document.getElementById('new_gondola_pos').value = '';
        }
    }

    document.getElementById('save_gondolas').onclick = async function(){
        const duplicates = findDuplicatePositions();
        
        if(duplicates.size > 0) {
            showModal(
                'IDs Duplicados Detectados',
                `Existem ${duplicates.size} position IDs duplicados: ${Array.from(duplicates).join(', ')}. Deseja salvar mesmo assim?`,
                saveToDB
            );
        } else {
            showModal(
                'Salvar Gôndolas',
                `Deseja salvar ${window._gondolas.length} gôndola(s)?`,
                saveToDB
            );
        }
    }
    
    async function saveToDB() {
        try{
            const res = await fetch('/set_gondolas', {
                method:'POST', 
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify({gondolas: window._gondolas})
            });
            
            if(res.ok){
                alert('✓ Gôndolas salvas com sucesso!');
                fetchGondolas();
            } else {
                alert('✗ Erro ao salvar gôndolas');
            }
        }catch(e){
            alert('✗ Erro ao salvar gôndolas');
        }
    }
});
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
        # Add current_gondola to status response
        current_gondola = web_data.get("current_gondola", None)
        return {
            "camera_ok": web_data["camera_ok"],
            "last_label": web_data["last_label"],
            "last_conf": web_data["last_conf"],
            "current_gondola": current_gondola
        }


@app.route('/gondolas')
def get_gondolas():
    with web_lock:
        gondolas = shared.gondolas
        result = []
        if isinstance(gondolas, list):
            if len(gondolas) > 0 and isinstance(gondolas[0], dict):
                result = gondolas
            else:
                for i, label in enumerate(gondolas):
                    result.append({'label': str(label), 'position_id': 71 + i})
        return jsonify(result)


@app.route("/set_gondolas", methods=['POST'])
def set_gondolas():
    data = request.get_json(force=True)
    if not data or 'gondolas' not in data:
        return jsonify({'error': 'No gondolas data provided'}), 400

    with web_lock:
        glist = data['gondolas']
        new_gondolas = []
        if isinstance(glist, list):
            for i, entry in enumerate(glist):
                if isinstance(entry, dict):
                    label = entry.get('label', '')
                    pos = int(entry.get('position_id', 71 + i))
                    new_gondolas.append({'label': str(label), 'position_id': pos})
                else:
                    new_gondolas.append({'label': str(entry), 'position_id': 71 + i})
        else:
            return jsonify({'error': 'gondolas must be a list'}), 400

        shared.gondolas = new_gondolas
        shared.web_data['gondola_positions'] = list(new_gondolas)

    return jsonify({'message': 'Gôndolas atualizadas'})


@app.route('/logs')
def get_logs():
    with shared.web_logs_lock:
        return jsonify(list(shared.web_logs))


@app.route('/config', methods=['GET'])
def get_config():
    with web_lock:
        return jsonify({
            'camera_index': camera_config.get('camera_index', 0),
            'width': camera_config.get('width', 640),
            'height': camera_config.get('height', 480),
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

        try:
            crop_config['x_min'] = int(data.get('x_min', crop_config.get('x_min', 0)))
            crop_config['x_max'] = int(data.get('x_max', crop_config.get('x_max', camera_config.get('width', 640))))
            crop_config['y_min'] = int(data.get('y_min', crop_config.get('y_min', 0)))
            crop_config['y_max'] = int(data.get('y_max', crop_config.get('y_max', camera_config.get('height', 480))))
        except Exception:
            pass

    return jsonify({'message': 'Configuração atualizada'})