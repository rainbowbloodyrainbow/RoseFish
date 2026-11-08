#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
bash /mnt/e/FishBot_Course/keyboard_control/start_agent.sh > /mnt/e/FishBot_Course/slam_real_2026-11-05/sessions/20261108_170522_quick/agent.log 2>&1 &
echo $! > /mnt/e/FishBot_Course/slam_real_2026-11-05/sessions/20261108_170522_quick/agent.pid
bash /mnt/e/FishBot_Course/slam_real_2026-11-05/run_sensors.sh > /mnt/e/FishBot_Course/slam_real_2026-11-05/sessions/20261108_170522_quick/sensors.log 2>&1 &
echo $! > /mnt/e/FishBot_Course/slam_real_2026-11-05/sessions/20261108_170522_quick/sensors.pid
ros2 bag record -o /mnt/e/FishBot_Course/slam_real_2026-11-05/sessions/20261108_170522_quick/rosbag /scan /odom /tf /tf_static /map /cmd_vel > /mnt/e/FishBot_Course/slam_real_2026-11-05/sessions/20261108_170522_quick/record.log 2>&1 &
echo $! > /mnt/e/FishBot_Course/slam_real_2026-11-05/sessions/20261108_170522_quick/record.pid
bash /mnt/e/FishBot_Course/slam_real_2026-11-05/open_slam_rviz.sh > /mnt/e/FishBot_Course/slam_real_2026-11-05/sessions/20261108_170522_quick/rviz.log 2>&1 &
echo $! > /mnt/e/FishBot_Course/slam_real_2026-11-05/sessions/20261108_170522_quick/rviz.pid
exec ros2 launch slam_toolbox online_async_launch.py use_sim_time:=false slam_params_file:=/mnt/e/FishBot_Course/slam_real_2026-11-05/mapper.yaml > /mnt/e/FishBot_Course/slam_real_2026-11-05/sessions/20261108_170522_quick/slam.log 2>&1
