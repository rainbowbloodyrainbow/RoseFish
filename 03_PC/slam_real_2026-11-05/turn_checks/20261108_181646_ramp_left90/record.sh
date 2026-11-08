source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
exec ros2 bag record -o /mnt/e/FishBot_Course/slam_real_2026-11-05/turn_checks/20261108_181646_ramp_left90/rosbag /scan /odom /tf /tf_static /cmd_vel
