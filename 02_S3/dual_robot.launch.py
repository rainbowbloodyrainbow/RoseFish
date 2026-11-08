"""S3 raw TCP lidar + chassis TF, sharing ROS_DOMAIN_ID=0 and system time."""
from pathlib import Path
import sys
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, LogInfo, RegisterEventHandler, EmitEvent
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    root = Path(__file__).resolve().parent
    host = LaunchConfiguration('s3_ip')
    arguments = [DeclareLaunchArgument('s3_ip'),
                 DeclareLaunchArgument('rviz', default_value='true')]
    for name in ('laser_x', 'laser_y', 'laser_z', 'laser_roll', 'laser_pitch', 'laser_yaw'):
        arguments.append(DeclareLaunchArgument(name, default_value='0.0'))
    bridge = ExecuteProcess(cmd=[sys.executable, '-u',
        str(root/'host/scripts/lidar_tcp_bridge.py'), '--host', host,
        '--serial', '/tmp/fishbot_s3_lidar'], output='screen')
    driver = Node(package='ydlidar', executable='ydlidar_node', name='ydlidar_node',
        parameters=[str(root/'host/config/lidar_wifi.yaml'), {'use_sim_time': False}],
        prefix=f'{sys.executable} {root / "wait_for_pty.py"}',
        output='screen')
    static_tf = Node(package='tf2_ros', executable='static_transform_publisher',
        name='fishbot_laser_mount', arguments=[
            '--x', LaunchConfiguration('laser_x'), '--y', LaunchConfiguration('laser_y'),
            '--z', LaunchConfiguration('laser_z'), '--roll', LaunchConfiguration('laser_roll'),
            '--pitch', LaunchConfiguration('laser_pitch'), '--yaw', LaunchConfiguration('laser_yaw'),
            '--frame-id', 'base_link', '--child-frame-id', 'laser_link'], output='screen')
    rviz = Node(package='rviz2', executable='rviz2', name='fishbot_dual_rviz',
        arguments=['-d', str(root/'dual_robot.rviz')], parameters=[{'use_sim_time': False}],
        condition=IfCondition(LaunchConfiguration('rviz')), output='screen')
    return LaunchDescription(arguments + [
        LogInfo(msg='Mount TF defaults to zero for integration only; mounting dimensions are not calibrated.'),
        bridge, driver, static_tf, rviz,
        RegisterEventHandler(OnProcessExit(target_action=bridge, on_exit=[
            EmitEvent(event=Shutdown(reason='Lidar TCP bridge exited'))])),
        RegisterEventHandler(OnProcessExit(target_action=driver, on_exit=[
            EmitEvent(event=Shutdown(reason='Lidar driver exited'))]))])
