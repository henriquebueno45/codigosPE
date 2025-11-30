import cv2
import numpy as np
import serial

ser = serial.Serial("/dev/ttyUSB0", baudrate=9600, timeout=1)

# Camera
cam = cv2.VideoCapture(1)
if not cam.isOpened():
    cam.open(1)

# Create window and trackbar to adjust collision line position in real-time
#cv2.namedWindow('Camera', cv2.WINDOW_NORMAL)
initial_line_pct = 60
cv2.createTrackbar('Line %', 'Camera', initial_line_pct, 100, lambda x: None)

def get_Object(frame, line_frac=0.6):
    # Use a combined approach:
    # 1) threshold to keep only very bright regions
    # 2) detect blobs (bright areas) with SimpleBlobDetector
    # 3) for each blob, extract ROI and find contours
    # 4) accept region if contour approximates to 4 vertices (quadrilateral)
    #    and is large and very bright (so it's a large white square)
    image = frame.copy()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Binary threshold to isolate very white regions (tune threshold as needed)
    _, thresh = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY)

    # Setup SimpleBlobDetector parameters to detect bright blobs
    params = cv2.SimpleBlobDetector_Params()
    params.filterByColor = True
    params.blobColor = 255
    params.filterByArea = True
    params.minArea = 1500
    params.maxArea = 1000000
    params.filterByCircularity = False
    params.filterByConvexity = False
    params.filterByInertia = False

    detector = cv2.SimpleBlobDetector_create(params)
    keypoints = detector.detect(thresh)

    output = image.copy()
    detected_any = False
    crossed = False

    # compute collision line Y coordinate as fraction of image height
    h, w = image.shape[:2]
    line_y = int(h * line_frac)
    # default line color (blue) -> will turn red if collision detected
    line_color = (255, 0, 0)
    line_thickness = 2

    for kp in keypoints:
        cx = int(kp.pt[0])
        cy = int(kp.pt[1])
        radius = int(max(kp.size * 1.5, 20))


        x1 = max(cx - radius, 0)
        y1 = max(cy - radius, 0)
        x2 = min(cx + radius, image.shape[1] - 1)
        y2 = min(cy + radius, image.shape[0] - 1)

        roi_thresh = thresh[y1:y2, x1:x2]
        if roi_thresh.size == 0:
            continue

        contours, _ = cv2.findContours(roi_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        # take largest contour in the ROI
        cnt = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(cnt)
        if area < 1500:
            continue

        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

        # Shift approx points to image coords
        approx_shifted = approx.copy()
        approx_shifted[:, 0, 0] = approx_shifted[:, 0, 0] + x1
        approx_shifted[:, 0, 1] = approx_shifted[:, 0, 1] + y1

        

        if len(approx) == 4 and cv2.isContourConvex(approx):
            bx, by, bw, bh = cv2.boundingRect(approx)
            # aspect ratio check (allow some tolerance)
            ar = float(bw) / float(bh) if bh != 0 else 0
            if 0.6 <= ar <= 1.6:
                # check mean brightness inside bounding rect on original gray
                mean_val = cv2.mean(gray[y1 + by:y1 + by + bh, x1 + bx:x1 + bx + bw])[0]
                if mean_val >= 220:
                    # shift bounding rect coords to image
                    bx_img = x1 + bx
                    by_img = y1 + by
                    bw_img = bw
                    bh_img = bh

                    cv2.drawContours(output, [approx_shifted], -1, (0, 255, 0), 3)
                    cv2.putText(output, 'White Square', (bx_img, max(by_img - 10, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    cv2.circle(output, (cx, cy), 5, (0, 0, 255), -1)
                    detected_any = True

                    # collision detection: check if bounding box crosses the horizontal line
                    if by_img <= line_y <= (by_img + bh_img):
                        crossed = True

        # optional: draw blob center and size for debugging
        cv2.circle(output, (cx, cy), int(kp.size // 2), (255, 0, 0), 2)

    # draw collision line (red if crossed)
    if crossed:
        line_color = (0, 0, 255)
        cv2.putText(output, 'Crossed!', (10, line_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    cv2.line(output, (0, line_y), (w - 1, line_y), line_color, line_thickness)

    return output, crossed
        # # Usa o frame original (BGR) para desenhar, assim o webserver verá a linha e boxes
        # gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # # rotate gray 90 degrees clockwise
        # gray = cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE)
        # linhas, colunas = gray.shape

        # # Limiarização (já gera 0 ou 255)
        # _, mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

        # # Encontrar contornos (objetos binários)
        # contours, _ = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # # Linha central vertical (desenha no frame BGR)
        # center_x = linhas // 2
        # cv2.line(frame, (center_x, 0), (center_x, linhas), (0, 255, 0), 2)

        # passagem = False
        # for cnt in contours:
        #     area = cv2.contourArea(cnt)
        #     # Ignorar ruído muito pequeno (ajuste se necessário)
        #     if area < 1500 or area > 75000:
        #         continue
        #     x, y, w, h = cv2.boundingRect(cnt)
        #     cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)

        #     # Verifica se a linha central cruza a bounding box
        #     if x <= center_x <= x + w:
        #         passagem = True
        #         cv2.putText(frame, 'Passagem detectada', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        # # Se houve passagem, pinta a linha de vermelho
        # if passagem:
        #     cv2.line(frame, (center_x, 0), (center_x, linhas), (0, 0, 255), 2)
        #     print(f"Área da região branca: {np.sum(mask == 255)}")
        #     return True, mask

        # return False

# Resolução: 480 - 640
while True:
    ret, frame = cam.read()
    if not ret:
        print("Falha ao capturar frame")
        break

    # read trackbar to get current line position (percentage of frame height)
    pos = cv2.getTrackbarPos('Line %', 'Camera')
    line_frac = max(0, min(pos / 100.0, 1.0))

    output, crossed = get_Object(frame, line_frac=line_frac)

    # optional: react to crossing (print/log)
    if crossed:
        print("Linha cruzada: objeto detectado cruzou a linha")
        ser.write(b'1\n')

    # cv2.imshow('Camera', output)

    # # Pressione 'q' para sair
    # key = cv2.waitKey(1) & 0xFF
    # if key == ord('q'):
    #     break

cam.release()
cv2.destroyAllWindows()
