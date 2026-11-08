#!/usr/bin/env bash
set -eo pipefail
package=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
target=${1:-"$HOME/lidar_wifi_final"}
if [ -e "$target" ]; then
    echo "Target already exists; choose a new empty path: $target" >&2
    exit 1
fi
source /opt/ros/humble/setup.bash
command -v colcon >/dev/null
mkdir -p "$target/src"
tar -xzf "$package/ydlidar_driver_source.tar.gz" -C "$target/src"
cp -a "$package/scripts" "$package/config" "$target/"
cd "$target"
colcon build --packages-select ydlidar --symlink-install \
    --cmake-args -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release --parallel-workers 2
chmod +x scripts/*.sh
printf 'Installed to %s\n' "$target"
