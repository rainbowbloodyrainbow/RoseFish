"""Stop only the installed chassis Agent, so the launcher can start it cleanly."""
from pathlib import Path
import os
import signal
import time

expected='/home/zsw2/micro_ros_agent_ws/install/micro_ros_agent/lib/micro_ros_agent/micro_ros_agent'
stopping=[]
for p in Path('/proc').glob('[0-9]*'):
    try:
        args=(p/'cmdline').read_bytes().decode(errors='replace').split('\0')
        if args[0]==expected and '8888' in args:
            os.kill(int(p.name),signal.SIGTERM)
            stopping.append(p)
            print('Stopped old chassis Agent',p.name)
    except (OSError,IndexError):pass
deadline=time.monotonic()+5
while any(p.exists() for p in stopping):
    if time.monotonic()>deadline:raise SystemExit('Agent did not stop')
    time.sleep(.1)
