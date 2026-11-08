import argparse
from pathlib import Path
import time
import serial

p = argparse.ArgumentParser()
p.add_argument('--port', required=True)
p.add_argument('--seconds', type=float, default=12)
p.add_argument('--output', default='serial.log')
p.add_argument('--reset', action='store_true')
a = p.parse_args()
s = serial.Serial(port=None, baudrate=115200, timeout=0.2)
s.dtr = False
s.rts = False
s.port = a.port
s.open()
if a.reset:
    # Standard ESP32 UART bridge: DTR released, RTS pulses EN low.
    s.rts = True
    time.sleep(0.10)
    s.rts = False
try:
    end = time.monotonic()+a.seconds
    with Path(a.output).open('wb') as f:
        while time.monotonic() < end:
            data = s.read(s.in_waiting or 1)
            if data:
                f.write(data)
                f.flush()
finally:
    s.close()
