import json, math, socket, time
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist, Vector3, TransformStamped
from std_msgs.msg import String
from tf2_ros import TransformBroadcaster

class BaseBridge(Node):
    def __init__(self):
        super().__init__('d0wd_base_bridge')
        self.token=json.loads(Path(__file__).with_name('link-private.json').read_text())['token']
        self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0',9999)); self.sock.setblocking(False)
        self.peer=None; self.seq=0; self.last_cmd=0.; self.last_rx=0.; self.mode='C'; self.command=(0.,0.)
        self.baseline=None; self.x=self.y=self.yaw=0.
        self.odom=self.create_publisher(Odometry,'odom',10)
        self.ticks=self.create_publisher(Vector3,'wheel_ticks',10)
        self.status=self.create_publisher(String,'base_status',10)
        self.tf=TransformBroadcaster(self)
        self.create_subscription(Twist,'cmd_vel',self.on_cmd,10)
        self.declare_parameter('enable_wheel_test',False)
        self.create_subscription(Vector3,'base_test_pwm',self.on_pwm,10)
        self.create_timer(.02,self.tick)
        self.get_logger().info('UDP 9999 ready; command timeout 250ms; awaiting board telemetry')
    def on_cmd(self,msg):
        v,w=msg.linear.x,msg.angular.z
        if not math.isfinite(v) or not math.isfinite(w): v=w=0.
        self.command=(max(-.05,min(.05,v)),max(-.6,min(.6,w)))
        self.mode='C'; self.last_cmd=time.monotonic()
    def on_pwm(self,msg):
        if not self.get_parameter('enable_wheel_test').value:return
        if not all(math.isfinite(v) and abs(v)<=350 for v in [msg.x,msg.y]):return
        self.command=(msg.x,msg.y);self.mode='P';self.last_cmd=time.monotonic()
    def tick(self):
        while True:
            try:data,peer=self.sock.recvfrom(2048)
            except BlockingIOError:break
            try:
                f=data.decode('ascii').split()
                if len(f)!=12 or f[0]!='T' or f[1]!=self.token:continue
                boot,us,l,r=map(int,f[2:6]);sl,sr,pl,pr=map(float,f[6:10]);ack,fault=map(int,f[10:12])
                if not all(math.isfinite(v) for v in [sl,sr,pl,pr]):continue
            except (ValueError,UnicodeError):continue
            first=self.peer is None;self.peer=peer;self.last_rx=time.monotonic()
            if first:self.get_logger().info('Board telemetry received; ROS topics active')
            vx=wz=0.
            if self.baseline is not None and self.baseline[0]==boot:
                _,old_us,old_l,old_r=self.baseline;dt=(us-old_us)*1e-6
                dl=(l-old_l)*math.pi*.04730/10200.;dr=-(r-old_r)*math.pi*.04730/10200.
                if 0<dt<1.:
                    ds=(dl+dr)*.5;dyaw=(dr-dl)/.13340
                    self.x+=ds*math.cos(self.yaw+dyaw*.5);self.y+=ds*math.sin(self.yaw+dyaw*.5)
                    self.yaw=math.atan2(math.sin(self.yaw+dyaw),math.cos(self.yaw+dyaw));vx=ds/dt;wz=dyaw/dt
            self.baseline=(boot,us,l,r)
            stamp=self.get_clock().now().to_msg();qz=math.sin(self.yaw*.5);qw=math.cos(self.yaw*.5)
            odom=Odometry();odom.header.stamp=stamp;odom.header.frame_id='odom';odom.child_frame_id='base_link'
            odom.pose.pose.position.x=self.x;odom.pose.pose.position.y=self.y
            odom.pose.pose.orientation.z=qz;odom.pose.pose.orientation.w=qw
            odom.twist.twist.linear.x=vx;odom.twist.twist.angular.z=wz
            # Conservative placeholders, pending ground calibration.
            for i in [0,7,35]:odom.pose.covariance[i]=.1;odom.twist.covariance[i]=.1
            self.odom.publish(odom)
            tr=TransformStamped();tr.header=odom.header;tr.child_frame_id='base_link'
            tr.transform.translation.x=self.x;tr.transform.translation.y=self.y
            tr.transform.rotation=odom.pose.pose.orientation;self.tf.sendTransform(tr)
            raw=Vector3();raw.x=float(l);raw.y=float(r);self.ticks.publish(raw)
            status={'boot':boot,'sample_us':us,'ticks':[l,r],'pps':[sl,sr],'pwm':[pl,pr],'ack':ack,'fault':bool(fault)}
            message=String();message.data=json.dumps(status);self.status.publish(message)
            Path(__file__).with_name('latest-status.json').write_text(json.dumps(status))
        if self.peer:
            active=time.monotonic()-self.last_cmd<.25 and time.monotonic()-self.last_rx<.3
            x,y=self.command if active else (0.,0.);kind=self.mode if active else 'C'
            self.seq+=1
            self.sock.sendto(f'{kind} {self.token} {self.seq} {x:.6f} {y:.6f}\n'.encode(),self.peer)

def main():
    rclpy.init();node=BaseBridge()
    try:rclpy.spin(node)
    except (KeyboardInterrupt,ExternalShutdownException):pass
    finally:
        if node.peer:
            for _ in range(3):
                node.seq+=1;node.sock.sendto(f'C {node.token} {node.seq} 0 0\n'.encode(),node.peer)
        node.destroy_node()
        if rclpy.ok():rclpy.shutdown()
if __name__=='__main__':main()
