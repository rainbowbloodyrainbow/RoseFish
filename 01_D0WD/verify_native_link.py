import json,math,time
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile,ReliabilityPolicy
from nav_msgs.msg import Odometry
from tf2_msgs.msg import TFMessage
from geometry_msgs.msg import Twist

rclpy.init()
node=Node('remoteesp_link_check')
qos=QoSProfile(depth=20,reliability=ReliabilityPolicy.BEST_EFFORT)
received={'odom':[],'tf':[]};invalid=[];stamps={}

def receive_odom(msg):
    received['odom'].append(time.monotonic())
    stamps['odom']=msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9
    p=msg.pose.pose.position;q=msg.pose.pose.orientation
    if msg.header.frame_id!='odom' or msg.child_frame_id!='base_link' or not all(math.isfinite(v) for v in (p.x,p.y,q.z,q.w)) or abs(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w-1)>.01:
        invalid.append('odom')

def receive_tf(msg):
    for tr in msg.transforms:
        if tr.header.frame_id=='odom' and tr.child_frame_id=='base_link':
            received['tf'].append(time.monotonic())
            stamps['tf']=tr.header.stamp.sec+tr.header.stamp.nanosec*1e-9

node.create_subscription(Odometry,'/odom',receive_odom,qos)
node.create_subscription(TFMessage,'/tf',receive_tf,qos)
pub=node.create_publisher(Twist,'/cmd_vel',qos)
timer=node.create_timer(.05,lambda:pub.publish(Twist()))
start=time.monotonic()
try:
    while time.monotonic()-start<20:rclpy.spin_once(node,timeout_sec=.05)
finally:
    for _ in range(3):pub.publish(Twist());rclpy.spin_once(node,timeout_sec=.03)
    result={'duration_s':time.monotonic()-start,'invalid_messages':invalid,'command':'zero Twist at 20Hz'}
    for key,values in received.items():
        result[key]={'count':len(values),'average_hz':(len(values)-1)/(values[-1]-values[0]) if len(values)>1 else 0,'max_gap_s':max((b-a for a,b in zip(values,values[1:])),default=None),'last_stamp_age_s':time.time()-stamps[key] if key in stamps else None}
    Path(__file__).with_name('native-link-check.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)
    node.destroy_node();rclpy.shutdown()
