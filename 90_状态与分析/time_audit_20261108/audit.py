import sqlite3,json,statistics,math,collections
from pathlib import Path
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
root=Path('/mnt/e/FishBot_Course/slam_real_2026-11-05')
bag=root/'sessions/20261108_170522_quick/rosbag/rosbag_0.db3'
c=sqlite3.connect('file:'+str(bag)+'?mode=ro',uri=True)
topics={i:(n,t) for i,n,t in c.execute('select id,name,type from topics')}
rows=collections.defaultdict(list);frames=collections.Counter();mounts={};cls={}
for tid,t,data in c.execute('select topic_id,timestamp,data from messages order by timestamp'):
 name,typ=topics[tid]
 if name not in ('/scan','/odom','/tf','/tf_static','/cmd_vel'):continue
 if typ not in cls:cls[typ]=get_message(typ)
 m=deserialize_message(data,cls[typ]);recv=t/1e9
 if name in ('/tf','/tf_static'):
  for tf in m.transforms:
   key=tf.header.frame_id+'->'+tf.child_frame_id;frames[key]+=1
   if name=='/tf_static':mounts[key]=dict(x=tf.transform.translation.x,y=tf.transform.translation.y,z=tf.transform.translation.z,qz=tf.transform.rotation.z,qw=tf.transform.rotation.w)
  continue
 if name=='/cmd_vel':rows[name].append(dict(recv=recv,v=m.linear.x,w=m.angular.z));continue
 stamp=m.header.stamp.sec+m.header.stamp.nanosec/1e9
 a=dict(recv=recv,stamp=stamp,age=recv-stamp)
 if name=='/scan':a.update(scan_time=m.scan_time,time_increment=m.time_increment,n=len(m.ranges),span=m.time_increment*(len(m.ranges)-1))
 else:a.update(v=m.twist.twist.linear.x,w=m.twist.twist.angular.z,yaw=2*math.atan2(m.pose.pose.orientation.z,m.pose.pose.orientation.w),x=m.pose.pose.position.x,y=m.pose.pose.position.y)
 rows[name].append(a)
def stats(v):
 if not v:return None
 s=sorted(v);return dict(n=len(v),min=s[0],p50=statistics.median(s),p95=s[int(.95*(len(s)-1))],max=s[-1])
result=dict(bag=str(bag),topics={n:c.execute('select count(*) from messages where topic_id=?',(i,)).fetchone()[0] for i,(n,_) in topics.items()},tf_edges=dict(frames),static_transforms=mounts)
for name,rs in rows.items():
 q=dict(count=len(rs),wall_duration_s=rs[-1]['recv']-rs[0]['recv'])
 if name=='/cmd_vel':q.update(nonzero_count=sum(abs(a['v'])+abs(a['w'])>1e-6 for a in rs),v_max=max(abs(a['v']) for a in rs),w_max=max(abs(a['w']) for a in rs));result[name]=q;continue
 q.update(age_s=stats([a['age'] for a in rs]),negative_age_count=sum(a['age']<0 for a in rs),nonincreasing_stamp=sum(b['stamp']<=a['stamp'] for a,b in zip(rs,rs[1:])))
 gaps=[b['recv']-a['recv'] for a,b in zip(rs,rs[1:])];q['arrival_gaps_s']=stats(gaps)
 segments=[];start=0
 for i in range(1,len(rs)+1):
  if i==len(rs) or rs[i]['recv']-rs[i-1]['recv']>2 or rs[i]['stamp']<=rs[i-1]['stamp']:
   ss=rs[start:i];start=i
   if len(ss)>=20:
    dt=ss[-1]['recv']-ss[0]['recv'];dst=ss[-1]['stamp']-ss[0]['stamp']
    segments.append(dict(n=len(ss),start_unix=ss[0]['recv'],duration_s=dt,stamp_progress_s=dst,age_start=ss[0]['age'],age_end=ss[-1]['age'],age_p50=statistics.median(a['age'] for a in ss),age_p95=sorted(a['age'] for a in ss)[int(.95*(len(ss)-1))],age_change_s=dt-dst))
 q['continuous_segments']=segments
 if name=='/scan':q.update(scan_time_s=stats([a['scan_time'] for a in rs]),point_span_s=stats([a['span'] for a in rs]),age_minus_scan_time_s=stats([a['age']-a['scan_time'] for a in rs]),point_counts=sorted(set(a['n'] for a in rs)))
 else:q.update(moving_count=sum(abs(a['v'])>.005 or abs(a['w'])>.03 for a in rs),max_abs_w=max(abs(a['w']) for a in rs))
 result[name]=q
(root/'diagnostics/time_audit_20261108/bag-audit.json').write_text(json.dumps(result,indent=2))
import bisect
sc=rows['/scan'];od=rows['/odom'];times=[a['recv'] for a in od]
by=collections.defaultdict(list)
for a in sc:
 i=bisect.bisect_left(times,a['recv'])
 cand=od[max(0,i-1):min(len(od),i+1)]
 if not cand:continue
 o=min(cand,key=lambda x:abs(x['recv']-a['recv']))
 if abs(o['recv']-a['recv'])>.2:continue
 label='stationary' if abs(o['v'])<.005 and abs(o['w'])<.03 else ('rotation' if abs(o['w'])>.05 and abs(o['v'])<.01 else 'moving')
 by[label].append(a['age'])
extra=dict(scan_age_by_odom_motion={k:stats(v) for k,v in by.items()},scan_time_above_0_3_s=sum(a['scan_time']>.3 for a in sc),scan_time_below_0_02_s=sum(a['scan_time']<.02 for a in sc),scan_future_ray_end_count=sum(a['stamp']+a['span']>a['recv']+.02 for a in sc))
(root/'diagnostics/time_audit_20261108/motion-audit.json').write_text(json.dumps(extra,indent=2))
print(json.dumps(extra,indent=2))
