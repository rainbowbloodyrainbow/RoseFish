#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
export LIBGL_ALWAYS_SOFTWARE=1
export QT_X11_NO_MITSHM=1
root=/mnt/e/FishBot_Course/s3_lidar_car_2026-11-05
python3 - "$root" <<'PY'
from pathlib import Path
import sys,yaml
r=Path(sys.argv[1])
d=yaml.safe_load((r/'dual_robot.rviz').read_text())
d['Visualization Manager']['Global Options']['Fixed Frame']='laser_link'
for display in d['Visualization Manager']['Displays']:
    if display.get('Class')=='rviz_default_plugins/Odometry':
        display['Enabled']=False
d['Window Geometry'].update(Width=1100,Height=780,X=40,Y=40)
(r/'laser_preview.rviz').write_text(yaml.safe_dump(d,allow_unicode=True,sort_keys=False))
PY
exec rviz2 -d "$root/laser_preview.rviz" --ros-args -r __node:=fishbot_laser_preview
