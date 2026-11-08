#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0 LIBGL_ALWAYS_SOFTWARE=1 QT_X11_NO_MITSHM=1
exec rviz2 -d /mnt/e/FishBot_Course/slam_real_2026-11-05/slam.rviz --ros-args -r __node:=fishbot_slam_view -p use_sim_time:=false
