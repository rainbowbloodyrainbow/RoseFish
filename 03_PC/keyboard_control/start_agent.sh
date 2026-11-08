#!/usr/bin/env bash
set -e
source /opt/ros/humble/setup.bash
source /home/zsw2/micro_ros_agent_ws/install/setup.bash
exec /home/zsw2/micro_ros_agent_ws/install/micro_ros_agent/lib/micro_ros_agent/micro_ros_agent udp4 --port 8888 -v4
