"""Passive angular scan snapshot for physical orientation check."""
import argparse,json,math,time,statistics
from pathlib import Path
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
ap=argparse.ArgumentParser();ap.add_argument('output');ap.add_argument('--seconds',type=float,default=8);a=ap.parse_args()
rclpy.init();n=rclpy.create_node('fishbot_orientation_snapshot');bins=[[]for _ in range(72)];count=0
def cb(m):
 global count
 count+=1
 for i,r in enumerate(m.ranges):
  if math.isfinite(r)and m.range_min<=r<=m.range_max:
   degree=math.degrees(m.angle_min+i*m.angle_increment)
   idx=int(round((degree+180)/5))%72;bins[idx].append(float(r))
sub=n.create_subscription(LaserScan,'/scan',cb,qos_profile_sensor_data)
end=time.monotonic()+a.seconds
while time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.05)
result={'unix':time.time(),'scans':count,'angle_bins_deg':[-180+5*i for i in range(72)],'median_m':[statistics.median(v)if v else None for v in bins]}
Path(a.output).write_text(json.dumps(result,indent=2));print(json.dumps(result));n.destroy_node();rclpy.shutdown();raise SystemExit(0 if count>=20 else 1)
