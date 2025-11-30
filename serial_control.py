# serial.py
import serial
import time

class SerialControl:
    def __init__(self, port="/dev/ttyUSB0", baudrate=9600):
        try:
            self.ser = serial.Serial(port, baudrate=baudrate, timeout=1)
            print("[SERIAL] Porta aberta com sucesso.")
        except Exception as e:
            print(f"[SERIAL] Erro ao abrir porta: {e}")
            self.ser = None

    def is_ok(self):
        return self.ser is not None and self.ser.is_open

    def read(self):
        if not self.is_ok():
            print("[SERIAL] Porta não está disponível para leitura.")
            return None

        while self.ser.in_waiting == 0:
            time.sleep(0.01)

        try:
            command = self.ser.readline().decode().strip()
            print(f"[SERIAL] Recebido: {command}")
            return int(command)
        except:
            print("[SERIAL] Erro lendo serial.")
            return None

    def write(self, value):
        if not self.is_ok():
            print("[SERIAL] Porta não está disponível para escrita.")
            return False

        try:
            cmd = (str(value) + "\n").encode()
            self.ser.write(cmd)
            print(f"[SERIAL] Enviado: {value}")
            return True
        except:
            print("[SERIAL] Erro escrevendo serial.")
            return False
