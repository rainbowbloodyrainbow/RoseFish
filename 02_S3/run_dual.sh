#!/usr/bin/env bash
set -eo pipefail
root=/mnt/e/FishBot_Course/s3_lidar_car_2026-11-05
source /opt/ros/humble/setup.bash
source /home/zsw2/fishbot_dual_ws/install/setup.bash
export ROS_DOMAIN_ID=0
export LIBGL_ALWAYS_SOFTWARE=1
ip=${1:?Usage: run_dual.sh S3_IP [true|false]}
rviz=${2:-true}
if [ -e /tmp/fishbot_s3_lidar ] || [ -L /tmp/fishbot_s3_lidar ]; then
    echo 'Lidar PTY already exists; do not run a second bridge.' >&2
    exit 1
fi
exec ros2 launch "$root/dual_robot.launch.py" s3_ip:="$ip" rviz:="$rviz"
