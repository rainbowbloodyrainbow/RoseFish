#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
root=/mnt/e/FishBot_Course/s3_lidar_car_2026-11-05
ws=/home/zsw2/fishbot_dual_ws
mkdir -p "$ws/src"
if [ ! -f "$ws/src/ydlidar_ros2/package.xml" ]; then
    python3 - "$root/host/ydlidar_driver_source.tar.gz" "$ws/src" <<'PY'
import pathlib,sys,tarfile
root=pathlib.Path(sys.argv[2]).resolve()
with tarfile.open(sys.argv[1]) as archive:
    for member in archive.getmembers():
        target=(root/member.name).resolve()
        if not target.is_relative_to(root) or member.issym() or member.islnk():
            raise RuntimeError('Unsafe archive member')
    archive.extractall(root)
PY
fi
cd "$ws"
colcon build --packages-select ydlidar --symlink-install --parallel-workers 2 \
    --cmake-args -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release
