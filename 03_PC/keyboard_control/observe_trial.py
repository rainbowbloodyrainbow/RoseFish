"""Read-only odometry observer for the short commissioning trial."""
import json
import math
from pathlib import Path
import time
import rclpy
from nav_msgs.msg import Odometry
from rclpy.qos import QoSProfile, ReliabilityPolicy

rclpy.init()
node = rclpy.create_node('keyboard_trial_observer')
samples = []

def receive(message):
    p = message.pose.pose.position
    samples.append(dict(t=time.time(), x=p.x, y=p.y,
                        v=message.twist.twist.linear.x,
                        w=message.twist.twist.angular.z))

sub = node.create_subscription(Odometry, '/odom', receive,
    QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT))
Path(__file__).with_name('observer-ready.json').write_text(json.dumps({'t': time.time()}))
end = time.monotonic() + 22
try:
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.05)
finally:
    distance = sum(math.hypot(b['x']-a['x'], b['y']-a['y'])
                   for a, b in zip(samples, samples[1:]))
    result = dict(samples=samples, path_m=distance,
                  max_abs_v=max([abs(s['v']) for s in samples] or [0]))
    Path(__file__).with_name('trial-odom.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(dict(count=len(samples), path_m=distance,
                         max_abs_v=result['max_abs_v'])), flush=True)
    node.destroy_node()
    rclpy.shutdown()
