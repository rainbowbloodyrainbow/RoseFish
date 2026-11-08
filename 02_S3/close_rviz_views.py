"""Close only the RViz views created for this car, keeping sensor nodes alive."""
import os
from pathlib import Path
import signal
import time

targets=[]
for item in Path('/proc').glob('[0-9]*'):
    try:
        args=(item/'cmdline').read_bytes().decode(errors='replace').split('\0')
        if Path(args[0]).name=='rviz2' and any(
                name in args for name in ('__node:=fishbot_dual_rviz','__node:=fishbot_laser_preview')):
            os.kill(int(item.name),signal.SIGTERM)
            targets.append(item)
            print('Closed car RViz view',item.name)
    except (OSError,IndexError):
        pass
deadline=time.monotonic()+5
while any(item.exists() for item in targets) and time.monotonic()<deadline:
    time.sleep(.1)
