#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
root=/mnt/e/FishBot_Course/slam_real_2026-11-05
exec 9>"$root/slam.lock"
flock -n 9 || { echo 'This SLAM entry is already running'; exit 1; }
python3 -B "$root/preflight.py" --seconds 12 --output "$root/preflight-latest.json"
exec ros2 launch slam_toolbox online_async_launch.py use_sim_time:=false slam_params_file:="$root/mapper.yaml"
