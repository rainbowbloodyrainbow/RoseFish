import argparse,json,time
from pathlib import Path
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Vector3,Twist
from std_msgs.msg import String

parser=argparse.ArgumentParser()
parser.add_argument('--level',type=int,choices=range(1,351))
args=parser.parse_args()
rclpy.init();n=Node('d0wd_bench_check');samples=[];latest=None
def receive(msg):
    global latest
    latest=json.loads(msg.data);latest['_time']=time.monotonic();samples.append(latest)
n.create_subscription(String,'base_status',receive,20)
p=n.create_publisher(Vector3,'base_test_pwm',10)
stop=n.create_publisher(Twist,'cmd_vel',10)
def spin(duration):
    end=time.monotonic()+duration
    while time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.02)
def zero():
    for _ in range(4):p.publish(Vector3());stop.publish(Twist());spin(.05)
def healthy():
    if latest is None or time.monotonic()-latest['_time']>.3 or latest['fault']:raise RuntimeError('Feedback missing or fault active')
results=[]
try:
    spin(2);healthy();zero();spin(.5)
    for wheel in [0,1]:
        for level in ([args.level] if args.level else [100,200,300]):
            healthy();start=latest['ticks'][:];index=len(samples)
            print('PULSE',wheel,level,flush=True)
            end=time.monotonic()+.18
            while time.monotonic()<end:
                cmd=Vector3();cmd.x=float(level if wheel==0 else 0);cmd.y=float(level if wheel==1 else 0);p.publish(cmd);spin(.04);healthy()
            # No further command for 700ms: verify the command watchdog stops PWM.
            spin(.7);healthy();delta=[latest['ticks'][i]-start[i] for i in range(2)]
            record={'wheel':wheel,'pwm_request':level,'tick_delta':delta,'peak_pwm':[max([abs(s['pwm'][i]) for s in samples[index:]] or [0]) for i in range(2)],'stopped':latest['pwm']==[0.0,0.0],'fault':latest['fault']}
            results.append(record);print(json.dumps(record),flush=True)
            zero();spin(.5)
            if not record['stopped']:raise RuntimeError('Stop verification failed')
            if abs(delta[wheel])>=20:break
finally:
    zero();spin(.4)
    result_name=f'wheel-test-{args.level}-results.json' if args.level else 'wheel-test-results.json'
    Path(__file__).with_name(result_name).write_text(json.dumps(results,indent=2))
    n.destroy_node();rclpy.shutdown()
