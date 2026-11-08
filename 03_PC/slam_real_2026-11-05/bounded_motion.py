import json,time,re,urllib.request,argparse
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--seconds',type=float,default=2.0);args=ap.parse_args()
if not 0<args.seconds<=10:raise SystemExit('Duration must be within 0..10 seconds')
r=Path(__file__).resolve().parent;c=urllib.request.build_opener(urllib.request.ProxyHandler({}));base='http://127.0.0.1:8765'
with c.open(base,timeout=1)as f:token=re.search("const token='([^']+)'",f.read().decode()).group(1)
seq=int(time.time()*1e6);events=[];started=False;reason='not started'
def send(kind,v=0):
 global seq
 seq+=1;req=urllib.request.Request(base+'/input',data=json.dumps(dict(type=kind,seq=seq,v=v,w=0)).encode(),headers={'Content-Type':'application/json','X-Control-Token':token})
 with c.open(req,timeout=.25)as f:f.read()
def status():
 with c.open(base+'/status',timeout=.25)as f:return json.load(f)
def health():
 d=json.loads((r/'live-health.json').read_text());now=time.time()
 for k,lim in [('updated',.4),('scan_received',.4),('odom_received',.35),('tf_received',.4)]:
  if now-d.get(k,0)>lim:raise RuntimeError(k+' stale')
 if d.get('cmd_publishers')!=1:raise RuntimeError('unexpected command publishers')
 if d.get('map_count',0)<1:raise RuntimeError('map absent')
 if d.get('forward_obstacle_x_m',0)<.30:raise RuntimeError('obstacle within 0.30m corridor')
 if not status().get('connected'):raise RuntimeError('chassis disconnected')
 return d
try:
 deadline=time.monotonic()+8
 while True:
  try:before=health();break
  except Exception:
   if time.monotonic()>deadline:raise
   time.sleep(.1)
 if status()['armed']:raise RuntimeError('panel already armed')
 send('stop');send('arm');end=time.monotonic()+.5
 while not status()['armed']:
  if time.monotonic()>end:raise RuntimeError('arming failed')
  send('command');time.sleep(.04)
 started=True;begin=time.monotonic();reason=str(args.seconds)+'-second bound completed'
 while time.monotonic()-begin<args.seconds:
  d=health()
  if not status()['armed']:raise RuntimeError('control disarmed')
  if abs(d.get('v',0))>.09 or abs(d.get('w',0))>.6:raise RuntimeError('unexpected measured velocity')
  send('command',.03);events.append(dict(t=time.time(),health=d));time.sleep(.04)
except Exception as e:reason=str(e)
finally:
 for i in range(5):
  try:send('stop')
  except Exception:pass
  time.sleep(.05)
 result=dict(at_unix=time.time(),started=started,reason=reason,events=events,final=status());(r/'bounded-motion.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items()if k!='events'}));print('command_samples',len(events))
