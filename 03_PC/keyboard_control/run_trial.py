"""Coordinate the bounded trial with an odometry observer already running."""
import json
import argparse
from pathlib import Path
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('--port', default='COM12')
args = parser.parse_args()
root = Path(__file__).resolve().parent
begin = time.time()
serial_root = root.parent/'d0wd_link_2026-10-30'
serial_error = (root/'trial-serial-error.log').open('w', encoding='utf-8')
capture = subprocess.Popen([sys.executable, '-B', str(serial_root/'capture_serial.py'),
    '--port', args.port, '--seconds', '28', '--output', 'diagnostic-after-network-fix.log'],
    stdout=subprocess.DEVNULL, stderr=serial_error)
with (root/'trial-observer.log').open('w', encoding='utf-8') as out, \
        (root/'trial-observer-error.log').open('w', encoding='utf-8') as err:
    observer = subprocess.Popen(['wsl.exe', '-d', 'Ubuntu', '--', 'bash', '-lc',
        'source /opt/ros/humble/setup.bash && python3 /mnt/e/FishBot_Course/keyboard_control/observe_trial.py'],
        stdout=out, stderr=err)
    deadline = time.monotonic()+15
    while True:
        try:
            ready = json.loads((root/'observer-ready.json').read_text())['t'] >= begin
        except (OSError, ValueError):
            ready = False
        if ready:
            break
        if observer.poll() is not None or time.monotonic() > deadline:
            observer.terminate()
            raise RuntimeError('Odometry observer failed to start; trial was not run')
        time.sleep(0.05)
    print('Observer ready; running one bounded forward trial.', flush=True)
    if capture.poll() is not None:
        raise RuntimeError('Serial capture failed; trial was not run')
    result = subprocess.run([sys.executable, '-B', str(root/'trial_once.py')], timeout=8)
    observer.wait(timeout=26)
    capture.wait(timeout=12)
    serial_error.close()
    odom = json.loads((root/'trial-odom.json').read_text())
    command = json.loads((root/'trial-command.json').read_text())
    first = command['samples'][0]['t']
    last = command['samples'][-1]['t']
    overlap = [s for s in odom['samples'] if first <= s['t'] <= last+1]
    print(json.dumps(dict(trial_exit_code=result.returncode,
        odom_count=len(odom['samples']), overlap_count=len(overlap),
        path_m=odom['path_m'], peak_v=odom['max_abs_v'],
        last_odom=odom['samples'][-1] if odom['samples'] else None,
        final_command=command['final'])), flush=True)
    raise SystemExit(result.returncode)
