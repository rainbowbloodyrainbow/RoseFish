import serial,time,json,re
from pathlib import Path
r=Path(__file__).resolve().parent;meta=json.loads((r/'metadata.json').read_text());s=serial.Serial(port=None,baudrate=115200,timeout=.2);s.dtr=False;s.rts=False;s.port=meta['port'];s.open();buffer=b'';recent=[];seen=False;start=time.time()
pattern=re.compile(r'\((\d+)\).*ESP32_CAR: WiFi=(\d+) Agent=(\d+).*PWM=(-?\d+),(-?\d+) \| ticks=(-?\d+),(-?\d+)')
try:
 with (r/'serial.log').open('ab')as log,(r/'counts.jsonl').open('a',encoding='utf-8')as counts:
  end=time.monotonic()+1200
  while time.monotonic()<end:
   data=s.read(s.in_waiting or 1)
   if not data:
    if not seen and time.time()-start>12:raise RuntimeError('No D0WD ESP32_CAR telemetry; board identity not confirmed')
    continue
   buffer+=data
   while b'\n'in buffer:
    raw,buffer=buffer.split(b'\n',1);line=raw.decode(errors='replace').strip();now=time.time();log.write((str(now)+' '+line+'\n').encode());log.flush();m=pattern.search(line)
    if not m:continue
    seen=True;values=list(map(int,m.groups()));row=dict(unix=now,uptime_ms=values[0],wifi=values[1],agent=values[2],pwm_l=values[3],pwm_r=values[4],left=values[5],right=values[6]);counts.write(json.dumps(row)+'\n');counts.flush();recent.append(row);recent=recent[-12:]
    try:
     temp=r/'live.tmp';temp.write_text(json.dumps({'latest':row,'recent':recent}));temp.replace(r/'live.json')
    except PermissionError:pass
finally:s.close()
