import cv2
import time
from collections import deque
import numpy as np
from ultralytics import YOLO
from shared import event_queue, web_data, frame_lock, camera_config, web_lock
import shared


def get_Object_noYolo(frame, line_frac=0.35):
    """Detects large, very-white quadrilateral(s) and returns:
    (annotated_frame, crossed_flag, detected_any, isolated_obj, bbox)
    - isolated_obj is the cropped image of the detected piece (or None)
    - bbox is (bx, by, bw, bh) in image coords for mapping YOLO boxes back
    """
    image = frame.copy()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    _, thresh = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY)

    # try to close small gaps in the white contours so slightly-damaged/contoured pieces still form a single blob
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
    thresh = cv2.dilate(thresh, kernel, iterations=1)

    params = cv2.SimpleBlobDetector_Params()
    # allow a wider threshold sweep (helps if lighting varies)
    params.minThreshold = 10
    params.maxThreshold = 255
    params.thresholdStep = 10

    # keep looking for white blobs
    params.filterByColor = True
    params.blobColor = 255

    # relax area constraints so partially-seen pieces aren't discarded
    params.filterByArea = True
    params.minArea = 800    # lowered from 1500
    params.maxArea = 1000000

    # disable strict shape filters (contours with details won't be rejected)
    params.filterByCircularity = False
    params.filterByConvexity = False
    params.filterByInertia = False

    # allow close blobs to be considered separately if needed
    params.minDistBetweenBlobs = 10

    detector = cv2.SimpleBlobDetector_create(params)
    keypoints = detector.detect(thresh)

    output = image.copy()
    h, w = image.shape[:2]
    line_x = int(w * line_frac)
    crossed = False
    detected_any = False

    best_area = 0
    best_candidate = None

    for kp in keypoints:
        cx = int(kp.pt[0])
        cy = int(kp.pt[1])
        radius = int(max(kp.size * 1.5, 20))

        x1 = max(cx - radius, 0)
        y1 = max(cy - radius, 0)
        x2 = min(cx + radius, w - 1)
        y2 = min(cy + radius, h - 1)

        roi_thresh = thresh[y1:y2, x1:x2]
        if roi_thresh.size == 0:
            continue

        contours, _ = cv2.findContours(roi_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        cnt = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(cnt)
        if area < 1500:
            continue

        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

        if len(approx) == 4 and cv2.isContourConvex(approx):
            bx, by, bw_box, bh_box = cv2.boundingRect(approx)
            ar = float(bw_box) / float(bh_box) if bh_box != 0 else 0
            if 0.6 <= ar <= 1.6:
                mean_val = cv2.mean(gray[y1 + by:y1 + by + bh_box, x1 + bx:x1 + bx + bw_box])[0]
                if mean_val >= 220:
                    # candidate found
                    detected_any = True
                    # compute candidate absolute bbox
                    bx_img = x1 + bx
                    by_img = y1 + by
                    if area > best_area:
                        best_area = area
                        best_candidate = (approx, bx_img, by_img, bw_box, bh_box, cx, cy)

        # draw blob center for debugging
        cv2.circle(output, (cx, cy), int(kp.size // 2), (255, 0, 0), 2)

    # if we have a best candidate, draw and crop
    isolated = None
    bbox = None
    if best_candidate is not None:
        approx, bx_img, by_img, bw_box, bh_box, cx, cy = best_candidate
        approx_shifted = approx.copy()
        approx_shifted[:, 0, 0] = approx_shifted[:, 0, 0] + (bx_img - (approx_shifted[:, 0, 0].min()))
        # better: draw using original approx shifted by bx_img, by_img
        approx_shifted = approx.copy()
        approx_shifted[:, 0, 0] = approx_shifted[:, 0, 0] + (bx_img - (approx_shifted[:, 0, 0].min()))
        # but simpler: compute points from bbox
        cv2.rectangle(output, (bx_img, by_img), (bx_img + bw_box, by_img + bh_box), (0, 255, 0), 3)
        cv2.putText(output, 'White Square', (bx_img, max(by_img - 10, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.circle(output, (cx, cy), 5, (0, 0, 255), -1)
        bbox = (bx_img, by_img, bw_box, bh_box)
        # safe crop
        x0 = max(bx_img, 0)
        y0 = max(by_img, 0)
        x1 = min(bx_img + bw_box, w)
        y1 = min(by_img + bh_box, h)
        if x1 > x0 and y1 > y0:
            isolated = image[y0:y1, x0:x1].copy()

        # collision detection
        if bx_img <= line_x <= (bx_img + bw_box):
            crossed = True

    # draw vertical line
    line_color = (0, 0, 255) if crossed else (255, 0, 0)
    cv2.line(output, (line_x, 0), (line_x, h - 1), line_color, 2)
    if crossed:
        cv2.putText(output, 'Crossed!', (min(line_x + 10, w - 100), 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

    return output, crossed, detected_any, isolated, bbox


def get_Object_yolo(model, isolated_img):
    """Run YOLO on the isolated image and return a list of detections and an annotated isolated image.
    Returns (annotated_isolated, detections), where detections is list of dicts {label,conf,x1,y1,x2,y2}
    Coordinates are relative to the isolated image (not the full frame).
    """
    img = isolated_img.copy() if isolated_img is not None else None
    detections = []
    if model is None or img is None:
        return img, detections

    try:
        results = model.predict(img, verbose=False)
        #print("YOLO results:", results)
    except Exception as e:
        print(f"[VISÃO] Erro no predict: {e}")
        time.sleep(0.05)
        return img, detections

    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            label = r.names[cls_id]
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            detections.append({
                'label': label,
                'conf': conf,
                'bbox': [x1, y1, x2, y2]
            })

            # draw on isolated image
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img, f"{label} {conf:.2f}", (x1, max(y1 - 6, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    return img, detections


class VisionSystem:
    def __init__(self):
        try:
            self.model = YOLO("best.pt", verbose=False)
        except Exception:
            self.model = None

        with web_lock:
            cfg = dict(camera_config)

        self.current_config = {
            'camera_index': int(cfg.get('camera_index', 0)),
            'width': int(cfg.get('width', 640)),
            'height': int(cfg.get('height', 480))
        }

        self.cam = None
        self.open_camera(self.current_config)

        with frame_lock:
            web_data["camera_ok"] = bool(self.cam is not None and self.cam.isOpened())

        event_queue.put({"type": "CAMERA_INICIALIZADA"})
        #print("[VISÃO] Inicializado. Modelo carregado (se disponível).")
        # buffer of recent detections to debounce labels (label -> deque[timestamps])
        self.detection_buffer = {}
        # last isolated crop + bbox to allow rechecks
        self.last_isolated = None
        self.last_bbox = None
        self.last_detection_ts = None
        # time when we last sent TOOL_IDENTIFIED event to avoid flooding
        self._last_tool_identified_sent = 0

    def open_camera(self, cfg):
        try:
            if self.cam is not None:
                try:
                    self.cam.release()
                except Exception:
                    pass
        except Exception:
            pass

        idx = int(cfg.get('camera_index', 0))
        width = int(cfg.get('width', 640))
        height = int(cfg.get('height', 480))

        cam = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cam.isOpened():
            cam = cv2.VideoCapture(idx)

        if cam.isOpened():
            try:
                cam.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cam.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            except Exception:
                pass
            self.cam = cam
            self.current_config = {'camera_index': idx, 'width': width, 'height': height}
            #print(f"[VISÃO] Câmera aberta (idx={idx}) {width}x{height}")
        else:
            self.cam = None
            #print(f"[VISÃO] Falha ao abrir câmera idx={idx}")

    def loop(self):
        while True:
            # process any pending control messages for the vision system (e.g., re-check requests)
            try:
                r = shared.vision_queue.get_nowait()
                try:
                    if isinstance(r, dict) and r.get('type') == 'REQUEST_IDENTIFICATION':
                        # If we have a recent isolated crop, re-run YOLO on it
                        if self.last_isolated is not None:
                            print('[VISÃO] Received REQUEST_IDENTIFICATION; re-running YOLO on last crop')
                            iso_annot, detections = get_Object_yolo(self.model, self.last_isolated)
                            # reuse same logic as when detections occur after crossing
                            if detections:
                                best = max(detections, key=lambda d: d.get('conf', 0))
                                label = best.get('label')
                                conf = float(best.get('conf', 0.0))
                                now = time.time()
                                buf = self.detection_buffer.get(label)
                                if buf is None:
                                    buf = deque(maxlen=8)
                                    self.detection_buffer[label] = buf
                                buf.append(now)
                                while buf and now - buf[0] > 2.0:
                                    buf.popleft()
                                if conf >= 0.6 and len(buf) >= 2:
                                    shared.web_data["label_detected_object"] = label
                                    shared.web_data["tool_identified"] = True
                                    # send event if enough time elapsed since last one
                                    if now - self._last_tool_identified_sent > 0.8:
                                        shared.event_queue.put({'type': 'TOOL_IDENTIFIED', 'label': label, 'conf': conf, 'timestamp': now})
                                        self._last_tool_identified_sent = now
                except Exception:
                    pass
            except Exception:
                # no pending items
                pass
            with web_lock:
                cfg = dict(camera_config)

            cfg_check = {
                'camera_index': int(cfg.get('camera_index', 0)),
                'width': int(cfg.get('width', 640)),
                'height': int(cfg.get('height', 480))
            }

            if cfg_check != self.current_config:
                print('[VISÃO] Detectada mudança de configuração da câmera, reaplicando...')
                self.open_camera(cfg_check)
                with frame_lock:
                    web_data['camera_ok'] = bool(self.cam is not None and self.cam.isOpened())

            if self.cam is None or not self.cam.isOpened():
                event_queue.put({"type": "ERRO_CAMERA"})
                time.sleep(0.5)
                continue

            ret, frame = self.cam.read()
            if not ret or frame is None:
                event_queue.put({"type": "ERRO_CAMERA"})
                time.sleep(0.05)
                continue

            # optional rotation/crop
            try:
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                frame = frame[30:500, :]
            except Exception:
                pass

            # 1) run fast detector to isolate object
            annotated, crossed, detected_any, isolated, bbox = get_Object_noYolo(frame)
            if isolated is not None:
                # store last isolated crop/bbox for potential rechecks
                self.last_isolated = isolated.copy()
                self.last_bbox = bbox
                self.last_detection_ts = time.time()
            if crossed:
                event_queue.put({"type": "OBJETO_PASSOU_LINHA"})
                shared.web_data["obj_detected"] = True

            if not detected_any:
                #event_queue.put({"type": "SEM_OBJETO"})
                with frame_lock:
                    shared.web_data["last_label"] = "Nenhum objeto detectado"
                    web_data["last_conf"] = 0.0
                    web_data["frame"] = annotated.copy()
                time.sleep(0.05)
                continue

            # 2) if an isolated region exists, run YOLO on it
            iso_annot = None
            detections = []
            if crossed:
                #print("Cruzou a linha, então vai rodar o YOLO")
                iso_annot, detections = get_Object_yolo(self.model, isolated)
                #print("DETECTIONS APÓS RODAR O YOLO:", detections)
                if detections:
                    # choose best detection by confidence
                    best = max(detections, key=lambda d: d.get('conf', 0))
                    label = best.get('label')
                    conf = float(best.get('conf', 0.0))
                    now = time.time()

                    # maintain per-label recent timestamps
                    buf = self.detection_buffer.get(label)
                    if buf is None:
                        buf = deque(maxlen=8)
                        self.detection_buffer[label] = buf
                    buf.append(now)
                    # remove old timestamps beyond window (2s)
                    while buf and now - buf[0] > 2.0:
                        buf.popleft()

                    # require minimum confidence and at least 2 detections within the window
                    if conf >= 0.6 and len(buf) >= 2:
                        shared.web_data["label_detected_object"] = label
                        shared.web_data["tool_identified"] = True
                        # emit a clear, timestamped event so state machine reacts deterministically
                        # Avoid flooding: only put an event if we haven't recently sent one for the same label
                        if time.time() - self._last_tool_identified_sent > 0.8:
                            event_queue.put({
                            'type': 'TOOL_IDENTIFIED',
                            'label': label,
                            'conf': conf,
                            'timestamp': now
                            })
                            self._last_tool_identified_sent = time.time()
                        print("------------------------------------------------------------")
                        print("OBJETO IDENTIFICADO PELA VISÃO:", label, conf)
                    else:
                        # not stable yet
                        shared.web_data["tool_identified"] = False
                else:
                    # no detection -> reset buffers older than window
                    now = time.time()
                    for k, buf in list(self.detection_buffer.items()):
                        while buf and now - buf[0] > 2.0:
                            buf.popleft()
                        if not buf:
                            del self.detection_buffer[k]
                    shared.web_data["tool_identified"] = False
                print("------------------------------------------------------------")
                print("TO DENTRO DO VISION LOOP, DETECTIONS:", shared.web_data["tool_identified"])

            # map detections back to full image coords and draw on annotated frame
            last_label = "Nenhum objeto detectado"
            last_conf = 0.0
            if detections and bbox is not None:
                bx, by, bw_box, bh_box = bbox
                for d in detections:
                    lx1, ly1, lx2, ly2 = d['bbox']
                    # map to full frame
                    x1 = bx + lx1
                    y1 = by + ly1
                    x2 = bx + lx2
                    y2 = by + ly2

                    event_queue.put({
                        'type': 'OBJETO_DETECTADO',
                        'label': d['label'],
                        'conf': d['conf'],
                        'bbox': [x1, y1, x2, y2]
                    })
                    web_data["obj_detected"] = True
                    last_label = d['label']
                    last_conf = d['conf']

                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(annotated, f"{d['label']} {d['conf']:.2f}", (x1, max(y1 - 6, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            else:
                # no YOLO detection
                #event_queue.put({"type": "SEM_OBJETO"})
                shared.web_data["obj_detected"] = False

            # update shared data for web
            with frame_lock:
                shared.web_data['last_label'] = last_label
                shared.web_data['last_conf'] = last_conf
                shared.web_data['frame'] = annotated.copy()

            time.sleep(0.05)

