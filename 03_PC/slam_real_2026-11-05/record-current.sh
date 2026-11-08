source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
exec ros2 bag record -o /mnt/e/FishBot_Course/slam_real_2026-11-05/sessions/20261108_164407_restart/rosbag /scan /odom /tf /tf_static /map /cmd_vel
