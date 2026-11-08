"""Read-only simultaneous scan, odometry and timestamped TF verification."""
import json
import math
from pathlib import Path
import time
import rclpy
from rclpy.duration import Duration
from rclpy.time import Time
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
from tf2_ros import Buffer, TransformListener, TransformException

rclpy.init()
node = rclpy.create_node('fishbot_dual_check')
buffer = Buffer(cache_time=Duration(seconds=15))
listener = TransformListener(buffer, node)
scans, odoms, transforms = [], [], []
pending = []

def scan(msg):
    valid = [x for x in msg.ranges if math.isfinite(x) and msg.range_min <= x <= msg.range_max]
    stamp = msg.header.stamp.sec+msg.header.stamp.nanosec/1e9
    scans.append(dict(t=time.monotonic(), count=len(msg.ranges), valid=len(valid),
        frame=msg.header.frame_id, age=time.time()-stamp,
        min_m=min(valid) if valid else None, max_m=max(valid) if valid else None))
    pending.append((Time.from_msg(msg.header.stamp), msg.header.frame_id))
    if len(pending)>100: del pending[:-100]

def odom(msg):
    stamp=msg.header.stamp.sec+msg.header.stamp.nanosec/1e9
    odoms.append(dict(t=time.monotonic(), age=time.time()-stamp,
        parent=msg.header.frame_id, child=msg.child_frame_id,
        v=msg.twist.twist.linear.x, w=msg.twist.twist.angular.z))

subscriptions = [node.create_subscription(LaserScan, '/scan', scan, qos_profile_sensor_data),
                 node.create_subscription(Odometry, '/odom', odom, qos_profile_sensor_data)]
end=time.monotonic()+20
while time.monotonic()<end:
    rclpy.spin_once(node, timeout_sec=0.05)
    for timestamp,frame in pending[:]:
        try:
            buffer.lookup_transform('odom',frame,timestamp)
            transforms.append(True)
            pending.remove((timestamp,frame))
        except TransformException:
            pass

def rate(rows):
    return (len(rows)-1)/(rows[-1]['t']-rows[0]['t']) if len(rows)>1 else 0

result=dict(scan_messages=len(scans), scan_hz=rate(scans),
    min_valid_points=min((s['valid'] for s in scans),default=0),
    scan_last=scans[-1] if scans else None, odom_messages=len(odoms), odom_hz=rate(odoms),
    odom_last=odoms[-1] if odoms else None,
    timestamped_tf_success=len(transforms), pending_tf=len(pending),
    mounting_calibrated=False)
result['passed']=len(scans)>10 and result['min_valid_points']>0 and len(odoms)>10 and len(transforms)>10
Path(__file__).with_name('dual-check.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result),flush=True)
node.destroy_node()
rclpy.shutdown()
raise SystemExit(0 if result['passed'] else 1)
