"""
Test serial helper for Windows (and cross-platform).

Usage examples (PowerShell):
    # install dependency
    pip install pyserial

    # run loopback (no hardware required)
    python .\main\test_serial_loop.py

    # test a real COM port (use COM3 or your port)
    python .\main\test_serial_loop.py --port COM3 --baud 9600

Notes:
- The default mode uses pyserial's "loop://" virtual port which echoes writes back.
- For a real device, either the device must echo what you send or you must wire TX->RX (hardware loopback) to test echo.
- The script writes a few test messages and tries to read them back.
"""

import argparse
import time
import sys

try:
    import serial
    from serial.tools import list_ports
except Exception as e:
    print("pyserial não encontrado. Rode: pip install pyserial")
    raise


def list_com_ports():
    ports = list(list_ports.comports())
    if not ports:
        print("Nenhuma porta serial detectada.")
    else:
        print("Portas detectadas:")
        for p in ports:
            print(f" - {p.device}: {p.description}")


def open_port(url, baud, timeout=1):
    if url.startswith('loop://'):
        # loopback virtual port
        ser = serial.serial_for_url(url, timeout=timeout)
    else:
        ser = serial.Serial(url, baudrate=baud, timeout=timeout)
    return ser


def basic_echo_test(ser):
    """Write test messages and try to read them back."""
    messages = ["TEST1", "42", "HELLO"]
    results = []

    for m in messages:
        to_send = (m + "\n").encode()
        ser.write(to_send)
        # small pause to let data loop back / be processed
        time.sleep(0.1)
        try:
            line = ser.readline().decode(errors='ignore').strip()
        except Exception:
            line = None
        results.append((m, line))
        print(f"enviado: '{m}'  <- lido: '{line}'")

    return results


def main():
    parser = argparse.ArgumentParser(description='Test serial port (loop:// or real COM port)')
    parser.add_argument('--port', default='loop://', help="Porta ou URL. Ex: 'loop://' para teste, 'COM3' para Windows")
    parser.add_argument('--baud', type=int, default=9600, help='Baudrate (para portas reais)')
    args = parser.parse_args()

    print("### Lista de portas no sistema ###")
    try:
        list_com_ports()
    except Exception as e:
        print(f"Erro listando portas: {e}")

    print(f"\nAbrindo porta: {args.port} (baud={args.baud})")
    try:
        ser = open_port(args.port, args.baud)
    except Exception as e:
        print(f"Falha ao abrir porta {args.port}: {e}")
        sys.exit(1)

    print("Porta aberta. Rodando teste de eco (3 mensagens)...")
    try:
        results = basic_echo_test(ser)
    finally:
        try:
            ser.close()
        except Exception:
            pass

    success = all(r[0] == r[1] for r in results)
    if success:
        print("\nTeste OK: eco válido para todas as mensagens.")
    else:
        print("\nTeste incompleto: algumas mensagens não retornaram. Revise conexões / dispositivo.")


if __name__ == '__main__':
    main()
