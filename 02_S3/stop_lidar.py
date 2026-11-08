"""Stop only this integration launch; ROS launch cleans up its own children."""
import os
from pathlib import Path
import signal
import time

target='/mnt/e/FishBot_Course/s3_lidar_car_2026-11-05/dual_robot.launch.py'
stopping=[]
for proc in Path('/proc').glob('[0-9]*'):
    try:
        args=(proc/'cmdline').read_bytes().decode(errors='replace').split('\0')
        if target in args and 'launch' in args:
            os.kill(int(proc.name),signal.SIGINT)
            stopping.append(proc)
            print('Stopping lidar launch',proc.name)
    except (OSError,ValueError):
        pass
deadline=time.monotonic()+15
while any(proc.exists() for proc in stopping):
    if time.monotonic()>deadline:
        raise SystemExit('Lidar launch is still shutting down; wait before restarting it.')
    time.sleep(0.1)
