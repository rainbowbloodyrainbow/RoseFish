"""Passive SLAM preflight: no velocity publisher or hardware writes."""
import argparse,json,math,time
from pathlib import Path
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
from tf2_ros import Buffer,TransformListener
from rclpy.time import Time
ap=argparse.ArgumentParser();ap.add_argument('--seconds',type=float,default=15);ap.add_argument('--output');args=ap.parse_args()
rclpy.init();n=rclpy.create_node('fishbot_slam_preflight');b=Buffer();listener=TransformListener(b,n)
rows={'scan':[],'odom':[],'cmd_vel':[]};pending=[];ok=0

def receive(kind,m):
 t=time.monotonic()
 if kind=='cmd_vel':rows[kind].append(dict(t=t,v=m.linear.x,w=m.angular.z));return
 stamp=m.header.stamp.sec+m.header.stamp.nanosec/1e9
 r=dict(t=t,stamp=stamp,age=time.time()-stamp,frame=m.header.frame_id)
 if kind=='scan':
  r.update(valid=sum(math.isfinite(x)and m.range_min<=x<=m.range_max for x in m.ranges),points=len(m.ranges),scan_time=m.scan_time,angle_increment=m.angle_increment)
  pending.append((Time.from_msg(m.header.stamp),m.header.frame_id,t))
 else:r.update(child=m.child_frame_id,v=m.twist.twist.linear.x,w=m.twist.twist.angular.z,x=m.pose.pose.position.x,y=m.pose.pose.position.y)
 rows[kind].append(r)
subs=[n.create_subscription(LaserScan,'/scan',lambda m:receive('scan',m),qos_profile_sensor_data),n.create_subscription(Odometry,'/odom',lambda m:receive('odom',m),qos_profile_sensor_data),n.create_subscription(Twist,'/cmd_vel',lambda m:receive('cmd_vel',m),qos_profile_sensor_data)]
end=time.monotonic()+args.seconds
while time.monotonic()<end:
 rclpy.spin_once(n,timeout_sec=0.02)
 for stamp,frame,t in pending[:]:
  try:b.lookup_transform('odom',frame,stamp);ok+=1;pending.remove((stamp,frame,t))
  except Exception:pass
result=dict(at_unix=time.time(),window_s=args.seconds,timestamped_tf_success=ok,pending_tf=len(pending),mounting_calibrated=False)
for kind,rs in rows.items():
 gaps=[rs[i]['t']-rs[i-1]['t']for i in range(1,len(rs))];ages=[r['age']for r in rs if 'age'in r];stamps=[r['stamp']for r in rs if 'stamp'in r]
 result[kind]=dict(count=len(rs),hz=(len(rs)-1)/(rs[-1]['t']-rs[0]['t'])if len(rs)>1 else 0,max_gap_s=max(gaps,default=None),age_min_s=min(ages,default=None),age_max_s=max(ages,default=None),stamp_nonincreasing=sum(stamps[i]<=stamps[i-1]for i in range(1,len(stamps))),last=rs[-1]if rs else None)
 if kind=='scan':result[kind]['min_valid_points']=min((r['valid']for r in rs),default=0)
 if kind=='cmd_vel':result[kind]['nonzero_count']=sum(abs(r['v'])+abs(r['w'])>1e-9 for r in rs)
fail=[]
for kind in ('scan','odom'):
 r=result[kind]
 if r['count']<20 or r['hz']<4:fail.append(kind+' data absent or too slow')
 if r['max_gap_s']is not None and r['max_gap_s']>1:fail.append(kind+' gap >1s')
 if r['age_max_s']is not None and (r['age_max_s']>0.5 or r['age_min_s']<-.15):fail.append(kind+' clock/latency outside provisional limits')
 if r['stamp_nonincreasing']:fail.append(kind+' non-increasing timestamps')
if rows['scan'] and any(v['frame']!='laser_link' for v in rows['scan']):fail.append('unexpected laser frame')
if rows['odom'] and any(v['frame']!='odom' or v['child']!='base_link' for v in rows['odom']):fail.append('unexpected odometry frames')
if n.get_publishers_info_by_topic('/map'):fail.append('an existing map publisher is present; avoid duplicate SLAM')
if ok<max(10,result['scan']['count']*.90):fail.append('timestamped TF insufficient')
if result['scan']['min_valid_points']<30:fail.append('too few valid lidar points')
if result['cmd_vel']['nonzero_count']:fail.append('nonzero commands during static startup')
result.update(passed=not fail,failures=fail)
print(json.dumps(result,ensure_ascii=False),flush=True)
if args.output:Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2))
n.destroy_node();rclpy.shutdown();raise SystemExit(1 if fail else 0)
