"""Wait for actual validated TCP lidar data before driver initialization."""
import json,os,sys,time
from pathlib import Path
path=Path(sys.argv[1]);last_report=0
while True:
 try:
  state=json.loads(path.read_text())
  if state.get('receiving') and time.time()-state.get('updated',0)<2 and state.get('valid_packets',0)>0:
   print('LIDAR_STREAM_READY; starting driver',flush=True)
   os.execv(sys.argv[2],sys.argv[2:])
 except (OSError,ValueError):pass
 if time.monotonic()-last_report>5:
  print('WAITING_FOR_LIDAR_STREAM: driver not started until live TCP data arrives',flush=True);last_report=time.monotonic()
 time.sleep(.2)
