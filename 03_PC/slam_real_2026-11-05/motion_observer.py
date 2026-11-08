import json,math,time,argparse
from pathlib import Path
import rclpy
from rclpy.qos import qos_profile_sensor_data,QoSProfile,DurabilityPolicy,ReliabilityPolicy
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry,OccupancyGrid
from tf2_ros import Buffer,TransformListener
from rclpy.time import Time
ap=argparse.ArgumentParser();ap.add_argument('--seconds',type=float,default=25);a=ap.parse_args()
r=Path(__file__).resolve().parent; mount=json.loads((r/'mounting.json').read_text());yaw=mount['yaw']
rclpy.init();n=rclpy.create_node('fishbot_motion_observer');b=Buffer();tl=TransformListener(b,n)
state={'scan_count':0,'odom_count':0,'map_count':0,'scan_received':0,'odom_received':0,'tf_received':0};samples=[];pending=[]

def scan(m):
 global pending
 now=time.time();state['scan_count']+=1;state['scan_received']=now;pending.append((Time.from_msg(m.header.stamp),now))
 pts=[]
 for i,v in enumerate(m.ranges):
  if math.isfinite(v)and m.range_min<=v<=m.range_max:
   angle=m.angle_min+i*m.angle_increment+yaw;x=.1+v*math.cos(angle);y=-.01+v*math.sin(angle)
   if x>.12 and abs(y)<.14:pts.append(x)
 state['forward_obstacle_x_m']=min(pts,default=8.0)

def odom(m):
 state.update(odom_count=state['odom_count']+1,odom_received=time.time(),x=m.pose.pose.position.x,y=m.pose.pose.position.y,v=m.twist.twist.linear.x,w=m.twist.twist.angular.z,qz=m.pose.pose.orientation.z,qw=m.pose.pose.orientation.w)

def mapcb(m):state.update(map_count=state['map_count']+1,map_width=m.info.width,map_height=m.info.height,map_resolution=m.info.resolution,map_known=sum(v>=0 for v in m.data),map_occupied=sum(v>=65 for v in m.data))
subs=[n.create_subscription(LaserScan,'/scan',scan,qos_profile_sensor_data),n.create_subscription(Odometry,'/odom',odom,qos_profile_sensor_data),n.create_subscription(OccupancyGrid,'/map',mapcb,QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL,reliability=ReliabilityPolicy.RELIABLE))]
end=time.monotonic()+a.seconds;report=0
while time.monotonic()<end:
 rclpy.spin_once(n,timeout_sec=.02)
 for item in pending[:]:
  stamp,received=item
  try:
   b.lookup_transform('map','laser_link',stamp)
   if time.time()-received<.35:state['tf_received']=time.time()
   pending.remove(item)
  except Exception:
   if time.time()-received>1:pending.remove(item)
 if time.monotonic()-report>.05:
  state.update(updated=time.time(),cmd_publishers=len(n.get_publishers_info_by_topic('/cmd_vel')))
  try:
   tmp=r/'live-health.tmp';tmp.write_text(json.dumps(state));tmp.replace(r/'live-health.json')
  except PermissionError:
   pass # A simultaneous Windows reader can briefly hold the target file.
  samples.append(state.copy());report=time.monotonic()
(r/'motion-observation.json').write_text(json.dumps(samples,indent=2));print(json.dumps(state));n.destroy_node();rclpy.shutdown()
