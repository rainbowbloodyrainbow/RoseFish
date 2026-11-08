import sqlite3,json,math,bisect
from pathlib import Path
from rclpy.serialization import deserialize_message
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
r=Path('/mnt/e/FishBot_Course/slam_real_2026-11-05')
c=sqlite3.connect('file:'+str(r/'sessions/20261108_170522_quick/rosbag/rosbag_0.db3')+'?mode=ro',uri=True)
t={n:i for i,n in c.execute('select id,name from topics')}
od=[];cmd=[]
for tid,stamp,blob in c.execute('select topic_id,timestamp,data from messages where topic_id in (?,?) order by timestamp',(t['/odom'],t['/cmd_vel'])):
 if tid==t['/odom']:
  m=deserialize_message(blob,Odometry);p=m.pose.pose;q=p.orientation
  od.append(dict(recv=stamp/1e9,stamp=m.header.stamp.sec+m.header.stamp.nanosec/1e9,v=m.twist.twist.linear.x,vy=m.twist.twist.linear.y,w=m.twist.twist.angular.z,x=p.position.x,y=p.position.y,yaw=2*math.atan2(q.z,q.w)))
 else:
  m=deserialize_message(blob,Twist);cmd.append(dict(recv=stamp/1e9,v=m.linear.x,w=m.angular.z))
times=[a['recv'] for a in cmd]
peak=max(range(len(od)),key=lambda i:abs(od[i]['w']));b=od[peak]
context=[]
for i in range(max(0,peak-5),min(len(od),peak+6)):
 a=od[i].copy();j=bisect.bisect_right(times,a['recv'])-1
 if j>=0:a['latest_command']=cmd[j]
 a['relative_to_peak_s']=a['recv']-b['recv']
 if i:
  prev=od[i-1];dt=a['stamp']-prev['stamp'];dyaw=math.atan2(math.sin(a['yaw']-prev['yaw']),math.cos(a['yaw']-prev['yaw']))
  a.update(header_dt_s=dt,receive_dt_s=a['recv']-prev['recv'],yaw_delta_rad=dyaw,yaw_delta_over_header_dt=dyaw/dt if dt>0 else None)
 context.append(a)
result=dict(peak_index=peak,peak=b,context=context,odom_count_abs_w_above_command_max=sum(abs(a['w'])>.45 for a in od),odom_count_abs_w_above_1=sum(abs(a['w'])>1 for a in od),max_rigid_offset_twist_error=max(abs(a['vy']-.07225*a['w']) for a in od))
(r/'diagnostics/time_audit_20261108/angular-peak.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
