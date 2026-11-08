"""Capture debug console without sending commands or intentionally resetting ESP32."""
import argparse
from pathlib import Path
import time
import serial

parser = argparse.ArgumentParser()
parser.add_argument('--port', default='COM5')
parser.add_argument('--seconds', type=float, default=20)
parser.add_argument('--output', default='uart_capture.log')
parser.add_argument('--reset', action='store_true', help='Reset EN via RTS after opening to capture boot/IP logs')
args = parser.parse_args()
port = serial.Serial()
port.port = args.port
port.baudrate = 115200
port.timeout = 0.25
port.dtr = False
port.rts = False
captured = bytearray()
try:
    port.open()
    if args.reset:
        port.rts = True
        time.sleep(0.1)
        port.rts = False
    end = time.monotonic() + args.seconds
    while time.monotonic() < end:
        block = port.read(max(1, port.in_waiting))
        if block:
            captured.extend(block)
finally:
    if port.is_open:
        port.close()
Path(args.output).write_bytes(captured)
print(captured.decode('utf-8', errors='replace'))
