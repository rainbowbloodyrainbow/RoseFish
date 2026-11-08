"""Read-only process ownership check for the dual-board launcher."""
import json
from pathlib import Path

agent='/home/zsw2/micro_ros_agent_ws/install/micro_ros_agent/lib/micro_ros_agent/micro_ros_agent'
launch='/mnt/e/FishBot_Course/s3_lidar_car_2026-11-05/dual_robot.launch.py'
result={'agent':False,'lidar':False}
for item in Path('/proc').glob('[0-9]*'):
    try:
        args=(item/'cmdline').read_bytes().decode(errors='replace').split('\0')
        if args[0]==agent and '8888' in args: result['agent']=True
        if launch in args and 'launch' in args: result['lidar']=True
    except (OSError,IndexError):
        pass
print(json.dumps(result))
