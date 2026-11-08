$Host.UI.RawUI.WindowTitle = 'FishBot Gazebo'
wsl -d Ubuntu -- bash -lc 'cd /home/zsw2/fishbot_ws/src/ros2bookcode/chapt9/fishbot_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export LIBGL_ALWAYS_SOFTWARE=1 && ros2 launch fishbot_bringup fishbot_gazebo.launch.py'
