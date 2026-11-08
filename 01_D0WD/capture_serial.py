import argparse
import time
from pathlib import Path
import serial

parser = argparse.ArgumentParser()
parser.add_argument('--seconds', type=float, default=20)
parser.add_argument('--output', default='native-serial.log')
parser.add_argument('--port', default='COM11')
args = parser.parse_args()
port = serial.Serial(port=None, baudrate=115200, timeout=.25)
port.dtr = False
port.rts = False
port.port = args.port
port.open()
try:
    end = time.monotonic() + args.seconds
    with Path(__file__).with_name(args.output).open('wb') as log:
        while time.monotonic() < end:
            data = port.read(port.in_waiting or 1)
            if data:
                log.write(data)
                log.flush()
finally:
    port.close()
print('Serial capture saved:', args.output)
