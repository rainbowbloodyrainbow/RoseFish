"""Passive physical turn-angle measurement; never publishes velocity."""
import json,time,math
from pathlib import Path
import rclpy
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
from rclpy.qos import qos_profile_sensor_data
r=Path(__file__).resolve().parent;rclpy.init();n=rclpy.create_node('fishbot_turn_angle_capture');recent=[];last_write=0;commands=[]
f=(r/'odom.jsonl').open('a');g=(r/'commands.jsonl').open('a')
def odom(m):
 global last_write
 p=m.pose.pose.position;q=m.pose.pose.orientation;row={'unix':time.time(),'stamp':m.header.stamp.sec+m.header.stamp.nanosec/1e9,'x':p.x,'y':p.y,'yaw':math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)),'v':m.twist.twist.linear.x,'w':m.twist.twist.angular.z,'vy':m.twist.twist.linear.y}
 f.write(json.dumps(row)+'\n');f.flush();recent.append(row);recent[:]=recent[-100:]
 if time.monotonic()-last_write>.1:
  try:
   t=r/'live.tmp';t.write_text(json.dumps({'latest':row,'recent':recent[-30:]}));t.replace(r/'live.json')
  except PermissionError:pass
  last_write=time.monotonic()
def cmd(m):
 row={'unix':time.time(),'v':m.linear.x,'w':m.angular.z};g.write(json.dumps(row)+'\n');g.flush()
subs=[n.create_subscription(Odometry,'/odom',odom,qos_profile_sensor_data),n.create_subscription(Twist,'/cmd_vel',cmd,qos_profile_sensor_data)]
try:
 end=time.monotonic()+1800
 while time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.05)
finally:f.close();g.close();n.destroy_node();rclpy.shutdown()
