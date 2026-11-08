import math,time,json
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
rclpy.init()
node=rclpy.create_node('lidar_usb_check')
rows=[]
def callback(msg):
    valid=[r for r in msg.ranges if math.isfinite(r) and msg.range_min <= r <= msg.range_max]
    rows.append((time.monotonic(),len(msg.ranges),len(valid),min(valid) if valid else None,max(valid) if valid else None,msg.header.frame_id,msg.header.stamp.sec+msg.header.stamp.nanosec/1e9,msg.scan_time))
sub=node.create_subscription(LaserScan,'/scan',callback,qos_profile_sensor_data)
end=time.monotonic()+15
while time.monotonic()<end:
    rclpy.spin_once(node,timeout_sec=0.2)
rate=(len(rows)-1)/(rows[-1][0]-rows[0][0]) if len(rows)>1 else 0
print(json.dumps({'messages':len(rows),'hz':round(rate,2),'first':rows[0] if rows else None,'last':rows[-1] if rows else None,'min_valid_points':min((r[2] for r in rows),default=0)}))
node.destroy_node()
rclpy.shutdown()
raise SystemExit(0 if len(rows)>10 and min(r[2] for r in rows)>0 else 1)
