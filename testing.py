import cv2
import numpy as np
import matplotlib.pyplot as plt

# Camera
cam = cv2.VideoCapture(1)
if not cam.isOpened():
    cam.open(1)

# Create window and trackbar to adjust collision line position in real-time
cv2.namedWindow('Camera', cv2.WINDOW_NORMAL)

while True:
    ret, frame = cam.read()
    if not ret:
        print("Falha ao capturar frame")
        break

    #frame.apply_filters(frame)
    cv2.imshow("Camera",frame)


    # Pressione 'q' para sair
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break

cam.release()
cv2.destroyAllWindows()