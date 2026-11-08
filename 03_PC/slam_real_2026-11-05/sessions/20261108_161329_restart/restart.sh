#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
kill -INT 1146
for i in {1..40}; do
  if ! kill -0 1146 2>/dev/null; then break; fi
  sleep .2
done
if kill -0 1146 2>/dev/null; then echo "Old SLAM did not stop"; exit 1; fi
ros2 bag record -o "/mnt/e/FishBot_Course/slam_real_2026-11-05/sessions/20261108_161329_restart/rosbag" /scan /odom /tf /tf_static /map /cmd_vel > "/mnt/e/FishBot_Course/slam_real_2026-11-05/sessions/20261108_161329_restart/record.log" 2>&1 &
echo $! > "/mnt/e/FishBot_Course/slam_real_2026-11-05/sessions/20261108_161329_restart/record.pid"
exec bash /mnt/e/FishBot_Course/slam_real_2026-11-05/run_slam.sh > "/mnt/e/FishBot_Course/slam_real_2026-11-05/sessions/20261108_161329_restart/slam.log" 2>&1
