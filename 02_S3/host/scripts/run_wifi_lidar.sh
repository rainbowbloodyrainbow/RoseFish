#!/usr/bin/env bash
set -eo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [ "$#" -lt 1 ]; then
    echo "Usage: bash scripts/run_wifi_lidar.sh S3_IP" >&2
    exit 2
fi
source /opt/ros/humble/setup.bash
if [ -f "$root/install/setup.bash" ]; then
    source "$root/install/setup.bash"
elif [ -f "$HOME/lidar_usb_ws/install/setup.bash" ]; then
    source "$HOME/lidar_usb_ws/install/setup.bash"
else
    echo "Build the archived driver first using install_ubuntu.sh" >&2
    exit 1
fi
set -u
if [ -e /tmp/lidar_wifi ] || [ -L /tmp/lidar_wifi ]; then
    echo "Stop the previous WiFi bridge first: /tmp/lidar_wifi already exists" >&2
    exit 1
fi
python3 -u "$root/scripts/lidar_tcp_bridge.py" --host "$1" &
bridge_pid=$!
driver_pid=''
cleanup() {
    if [ -n "$driver_pid" ]; then kill -INT -- "-$driver_pid" 2>/dev/null || true; fi
    kill -INT "$bridge_pid" 2>/dev/null || true
    wait "$bridge_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM
for attempt in {1..50}; do
    if [ -e /tmp/lidar_wifi ]; then break; fi
    if ! kill -0 "$bridge_pid" 2>/dev/null; then exit 1; fi
    sleep 0.1
done
[ -e /tmp/lidar_wifi ] || { echo "PTY did not start" >&2; exit 1; }
setsid ros2 run ydlidar ydlidar_node --ros-args -r __node:=ydlidar_node \
    --params-file "$root/config/lidar_wifi.yaml" &
driver_pid=$!
wait "$driver_pid"
