"""S3 raw TCP lidar + chassis TF, sharing ROS_DOMAIN_ID=0 and system time."""
from pathlib import Path
import sys
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, LogInfo, RegisterEventHandler, EmitEvent
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration, Command, FindExecutable
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.actions import Node


def generate_launch_description():
    local = Path(__file__).resolve().parent
    root = Path("/mnt/e/FishBot_Course/s3_lidar_car_2026-11-05")
    host = LaunchConfiguration('s3_ip')
    arguments = [DeclareLaunchArgument('s3_ip'),
                 DeclareLaunchArgument('rviz', default_value='true'),
                 DeclareLaunchArgument('robot_model', default_value='false')]
    mount_defaults = dict(laser_x='0.0033', laser_y='-0.01115', laser_z='0.05', laser_roll='0.0', laser_pitch='0.0', laser_yaw='-1.6406094968746698')
    for name, value in mount_defaults.items():
        arguments.append(DeclareLaunchArgument(name, default_value=value))
    bridge = ExecuteProcess(cmd=[sys.executable, '-u',
        str(local/'lidar_tcp_bridge.py'), '--host', host, '--status-file', str(local/'stream-status.json'),
        '--serial', '/tmp/fishbot_s3_lidar'], output='screen')
    driver = Node(package='ydlidar', executable='ydlidar_node', name='ydlidar_node',
        parameters=[str(local/'lidar_slam.yaml'), {'use_sim_time': False}],
        prefix=f'{sys.executable} {local / "wait_stream.py"} {local / "stream-status.json"}',
        output='screen')
    static_tf = Node(package='tf2_ros', executable='static_transform_publisher',
        name='fishbot_laser_mount', condition=UnlessCondition(LaunchConfiguration('robot_model')), arguments=[
            '--x', LaunchConfiguration('laser_x'), '--y', LaunchConfiguration('laser_y'),
            '--z', LaunchConfiguration('laser_z'), '--roll', LaunchConfiguration('laser_roll'),
            '--pitch', LaunchConfiguration('laser_pitch'), '--yaw', LaunchConfiguration('laser_yaw'),
            '--frame-id', 'base_link', '--child-frame-id', 'laser_link'], output='screen')
    description_cmd = [FindExecutable(name='xacro'), ' ', str(local/'model/fishbot_measured.urdf.xacro')]
    for name in mount_defaults:
        description_cmd += [' ', name, ':=', LaunchConfiguration(name)]
    robot_model = Node(package='robot_state_publisher', executable='robot_state_publisher', name='fishbot_description',
        parameters=[{'robot_description': ParameterValue(Command(description_cmd), value_type=str), 'use_sim_time': False}],
        condition=IfCondition(LaunchConfiguration('robot_model')), output='screen')
    rviz = Node(package='rviz2', executable='rviz2', name='fishbot_dual_rviz',
        arguments=['-d', str(root/'dual_robot.rviz')], parameters=[{'use_sim_time': False}],
        condition=IfCondition(LaunchConfiguration('rviz')), output='screen')
    return LaunchDescription(arguments + [
        LogInfo(msg='Measured 2026-11-07 plate-center geometry. Requires matching center-frame chassis firmware; yaw remains coarse.'),
        bridge, driver, static_tf, robot_model, rviz,
        RegisterEventHandler(OnProcessExit(target_action=bridge, on_exit=[
            EmitEvent(event=Shutdown(reason='Lidar TCP bridge exited'))])),
        RegisterEventHandler(OnProcessExit(target_action=driver, on_exit=[
            EmitEvent(event=Shutdown(reason='Lidar driver exited'))]))])
