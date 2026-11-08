import argparse,json,re,subprocess,threading,time
from pathlib import Path
import serial

root=Path(__file__).parent
parser=argparse.ArgumentParser()
parser.add_argument('--duration',type=float,choices=(.8,3.),default=.8)
parser.add_argument('--direction',type=int,choices=(-1,1),default=1)
args=parser.parse_args()
label=f"{'forward' if args.direction==1 else 'reverse'}-{args.duration:g}s"
state={'recorded_at':0,'wifi':0,'agent':0,'valid':0,'ticks':[0,0],'pwm':[0,0],'fault':False}
pattern=re.compile(r'WiFi=(\d+) Agent=(\d+) cmd_valid=(\d+).*?PWM=(-?\d+),(-?\d+).*?ticks=(-?\d+),(-?\d+)')
done=threading.Event()
def save():
    with (root/'native-motor-status.jsonl').open('a') as stream:
        stream.write(json.dumps(state)+'\n')
(root/'native-motor-status.jsonl').write_text('')
save()
port=serial.Serial(port=None,baudrate=115200,timeout=.1)
port.dtr=False;port.rts=False;port.port='COM11';port.open()
def monitor():
    buffer=b''
    try:
        with (root/f'native-motor-{label}-serial.log').open('wb') as log:
            while not done.is_set():
                data=port.read(port.in_waiting or 1)
                if not data:continue
                log.write(data);log.flush();buffer+=data
                while b'\n' in buffer:
                    line,buffer=buffer.split(b'\n',1)
                    text=line.decode('utf-8',errors='replace')
                    if 'First fault:' in text or 'latched hardware/control fault' in text:
                        state['fault']=True;state['fault_line']=text;save()
                    m=pattern.search(text)
                    if m:
                        a=list(map(int,m.groups()))
                        state.update(recorded_at=time.time(),wifi=a[0],agent=a[1],valid=a[2],pwm=a[3:5],ticks=a[5:7])
                        save()
    except BaseException as e:
        state['fault']=True;state['monitor_error']=str(e);save()

thread=threading.Thread(target=monitor,daemon=True);thread.start()
try:
    result=subprocess.run(['wsl','-d','Ubuntu','--','bash','-lc',f'source /opt/ros/humble/setup.bash && python3 /mnt/e/FishBot_Course/d0wd_link_2026-10-30/native_motor_test.py --duration {args.duration:g} --direction {args.direction}'],timeout=50)
    time.sleep(2)
finally:
    done.set();thread.join(timeout=2);port.close()
print('FINAL SERIAL STATE',json.dumps(state),flush=True)
raise SystemExit(result.returncode)
