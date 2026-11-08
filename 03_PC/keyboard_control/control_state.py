"""Control logic shared by the ROS bridge and offline preview."""
import math

INPUT_TIMEOUT = 0.30
FEEDBACK_TIMEOUT = 0.60
TRACK_M = 0.1355
MAX_LINEAR = 0.20
MAX_ANGULAR = 0.8
MAX_WHEEL = 0.20
MAX_LINEAR_ACCEL = 0.10  # m/s^2
MAX_ANGULAR_ACCEL = 0.50  # rad/s^2
MAX_RAMP_DT = 0.10  # Do not catch up a delayed scheduler with a speed jump.


class ControlState:
    def __init__(self):
        self.armed = False
        self.last_input = -math.inf
        self.v = self.w = 0.0
        self.target_v = self.target_w = 0.0
        self.reason = '请先启用控制'
        self.last_output = None

    def stop(self, reason):
        self.armed = False
        self.v = self.w = 0.0
        self.target_v = self.target_w = 0.0
        self.reason = reason

    def receive(self, packet, now, connected):
        # A fresh heartbeat must not silently revive an expired command.
        self.output(now, connected)
        kind = packet.get('type')
        if kind == 'stop':
            self.stop('已停车；请重新启用')
        elif kind == 'arm':
            self.armed = True
            self.last_input = now
            self.v = self.w = 0.0
            self.target_v = self.target_w = 0.0
            self.last_output = now
            self.reason = '已启用：按住方向键移动'
        elif kind == 'command':
            v, w = packet.get('v'), packet.get('w')
            if (type(v) not in (int, float) or type(w) not in (int, float)
                    or not math.isfinite(v) or not math.isfinite(w)):
                self.stop('无效速度指令')
                return
            self.last_input = now
            if self.armed:
                v, w = float(v), float(w)
                self.target_v = max(-MAX_LINEAR, min(MAX_LINEAR, v))
                self.target_w = max(-MAX_ANGULAR, min(MAX_ANGULAR, w))
                peak = max(abs(self.target_v - self.target_w * TRACK_M / 2),
                           abs(self.target_v + self.target_w * TRACK_M / 2))
                if peak > MAX_WHEEL:
                    self.target_v *= MAX_WHEEL / peak
                    self.target_w *= MAX_WHEEL / peak
                # Releasing a direction bypasses the ramp for that component.
                if self.target_v == 0.0:
                    self.v = 0.0
                if self.target_w == 0.0:
                    self.w = 0.0
        else:
            self.stop('未知控制指令')

    def output(self, now, connected):
        # Agent/odom availability is informational; only input freshness gates output.
        if self.armed and now - self.last_input > INPUT_TIMEOUT:
            self.stop('键盘心跳超时：已停车，请重新启用')
        if not self.armed:
            return (0.0, 0.0)
        if self.last_output is None:
            self.last_output = now
        dt = max(0.0, min(now - self.last_output, MAX_RAMP_DT))
        self.last_output = max(now, self.last_output)
        dv, dw = self.target_v - self.v, self.target_w - self.w
        # Follow one straight segment in (v,w); the wheel-speed feasible region
        # is convex, so capped endpoints also keep both wheels within the cap.
        fraction = 1.0
        if dv:
            fraction = min(fraction, MAX_LINEAR_ACCEL * dt / abs(dv))
        if dw:
            fraction = min(fraction, MAX_ANGULAR_ACCEL * dt / abs(dw))
        self.v += fraction * dv
        self.w += fraction * dw
        return (self.v, self.w)
