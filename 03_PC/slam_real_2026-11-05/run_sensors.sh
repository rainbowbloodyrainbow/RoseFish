#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
source /home/zsw2/fishbot_dual_ws/install/setup.bash
export ROS_DOMAIN_ID=0 LIBGL_ALWAYS_SOFTWARE=1
root=/mnt/e/FishBot_Course/slam_real_2026-11-05
python3 -B "$root/validate_geometry_deployment.py"
exec ros2 launch "$root/sensors.launch.py" s3_ip:="${1:-10.212.8.152}" rviz:=false robot_model:=true
