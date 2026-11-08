import argparse,json,time
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile,ReliabilityPolicy
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist

root=Path(__file__).parent
parser=argparse.ArgumentParser()
parser.add_argument('--duration',type=float,choices=(.8,3.),default=.8)
parser.add_argument('--direction',type=int,choices=(-1,1),default=1)
args=parser.parse_args()
rclpy.init();node=Node('remoteesp_motor_experiment')
qos=QoSProfile(depth=1,reliability=ReliabilityPolicy.BEST_EFFORT)
pub=node.create_publisher(Twist,'/cmd_vel',qos)
last_odom=0.;samples=[];results=[]
def on_odom(msg):
    global last_odom
    last_odom=time.monotonic()
node.create_subscription(Odometry,'/odom',on_odom,qos)
def status():
    for line in reversed((root/'native-motor-status.jsonl').read_text().splitlines()):
        try:value=json.loads(line);break
        except json.JSONDecodeError:continue
    else:raise RuntimeError('No valid serial status')
    if not samples or samples[-1]['recorded_at']!=value['recorded_at'] or samples[-1]['fault']!=value['fault']:samples.append(value)
    return value
def spin(duration):
    end=time.monotonic()+duration
    while time.monotonic()<end:rclpy.spin_once(node,timeout_sec=.01)
def healthy():
    s=status()
    if s['fault']:raise RuntimeError('Firmware/monitor fault: '+s.get('fault_line',s.get('monitor_error','latched')))
    if time.time()-s['recorded_at']>1.5 or not s['wifi'] or not s['agent']:raise RuntimeError('Agent/serial status unavailable')
    if time.monotonic()-last_odom>.35:raise RuntimeError('Odometry feedback gap exceeds 350ms')
    return s
def zero(duration=1.5):
    end=time.monotonic()+duration
    while time.monotonic()<end:pub.publish(Twist());spin(.05);status()
def ready():
    end=time.monotonic()+12
    while time.monotonic()<end:
        pub.publish(Twist());spin(.05)
        try:
            s=healthy()
            # Arrange the short pulse to overlap the firmware's 1 Hz log.
            if .25<time.time()-s['recorded_at']<.45:return s
        except RuntimeError:
            if status()['fault']:raise
    raise RuntimeError('No healthy test window before timeout')
error=None
try:
    for wheel in (0,1):
        print('NEXT:',('LEFT' if wheel==0 else 'RIGHT'),'in approximately 2 seconds',flush=True)
        zero(2)
        s=ready();start=s['ticks'][:];begin=len(samples)
        cmd=Twist();cmd.linear.x=args.direction*.015;cmd.angular.z=args.direction*(-1 if wheel==0 else 1)*.03/.1334
        print('TEST',('LEFT' if wheel==0 else 'RIGHT'),'wheel target 0.03 m/s, command duration',args.duration,'seconds',flush=True)
        end=time.monotonic()+args.duration
        try:
            while time.monotonic()<end:
                healthy();pub.publish(cmd);spin(.04)
        finally:zero()
        s=status()
        record={'wheel':['left','right'][wheel],'wheel_target_mps':args.direction*.03,'command_duration_s':args.duration,'start_ticks':start,'end_ticks':s['ticks'],'tick_delta':[s['ticks'][i]-start[i] for i in (0,1)],'peak_logged_pwm':[max([abs(v['pwm'][i]) for v in samples[begin:]] or [0]) for i in (0,1)],'stopped':s['pwm']==[0,0] and time.time()-s['recorded_at']<1.5,'fault':s['fault']}
        results.append(record);print(json.dumps(record),flush=True)
        if s['fault'] or not record['stopped']:raise RuntimeError('Test stopped because of fault or failed zero verification')
except BaseException as e:
    error=str(e);print('TEST STOPPED:',error,flush=True)
finally:
    zero(1.2)
    label=f"{'forward' if args.direction==1 else 'reverse'}-{args.duration:g}s"
    (root/f'native-motor-test-{label}-results.json').write_text(json.dumps({'results':results,'error':error,'samples':samples},indent=2))
    node.destroy_node();rclpy.shutdown()
if error:raise SystemExit(1)
