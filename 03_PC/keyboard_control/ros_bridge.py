"""WSL ROS 2 process: JSON lines on stdin, Twist on /cmd_vel at 20 Hz."""
import json
import queue
import sys
import threading
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from control_state import ControlState, FEEDBACK_TIMEOUT, INPUT_TIMEOUT


def main():
    rclpy.init()
    node = rclpy.create_node('fishbot_keyboard_control')
    qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT,
                     durability=DurabilityPolicy.VOLATILE)
    pub = node.create_publisher(Twist, '/cmd_vel', qos)
    last_odom = -float('inf')

    def odom_received(_message):
        nonlocal last_odom
        last_odom = time.monotonic()

    subscription = node.create_subscription(Odometry, '/odom', odom_received, qos)
    packets = queue.Queue(maxsize=32)
    ended = threading.Event()

    def read_stdin():
        try:
            for line in sys.stdin:
                packet = json.loads(line)
                if not isinstance(packet, dict):
                    raise ValueError('Expected a JSON object')
                packets.put_nowait((time.monotonic(), packet))
        except (ValueError, queue.Full):
            pass
        finally:
            ended.set()

    threading.Thread(target=read_stdin, daemon=True).start()
    state = ControlState()
    last_status = 0.0
    try:
        while rclpy.ok() and not ended.is_set():
            start = time.monotonic()
            rclpy.spin_once(node, timeout_sec=0.0)
            connected = start - last_odom <= FEEDBACK_TIMEOUT and pub.get_subscription_count() > 0
            while not packets.empty():
                received, packet = packets.get_nowait()
                if start - received > INPUT_TIMEOUT:
                    state.stop('输入积压：请重新启用')
                    continue
                state.receive(packet, received, connected)
            v, w = state.output(start, connected)
            message = Twist()
            message.linear.x, message.angular.z = v, w
            pub.publish(message)
            if start - last_status >= 0.10:
                print(json.dumps({'armed': state.armed, 'connected': connected,
                                  'reason': state.reason, 'v': v, 'w': w,
                                  'preview': False}), flush=True)
                last_status = start
            time.sleep(max(0.0, 0.05 - (time.monotonic() - start)))
    except KeyboardInterrupt:
        pass
    finally:
        state.stop('退出')
        for _ in range(6):
            if not rclpy.ok():
                break
            pub.publish(Twist())
            time.sleep(0.05)
        node.destroy_subscription(subscription)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
