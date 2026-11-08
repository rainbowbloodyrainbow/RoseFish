"""Wait for this bringup's PTY before starting the original driver."""
import os
from pathlib import Path
import sys
import time

deadline=time.monotonic()+10
while not Path('/tmp/fishbot_s3_lidar').exists():
    if time.monotonic()>deadline:
        raise SystemExit('S3 bridge did not create its PTY within 10 seconds')
    time.sleep(0.05)
os.execv(sys.argv[1],sys.argv[1:])
