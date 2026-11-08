#!/usr/bin/env bash
set -e
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source /opt/ros/humble/setup.bash
exec rviz2 -d "$root/config/lidar_wifi.rviz"
