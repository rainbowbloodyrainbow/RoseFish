source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
export LIBGL_ALWAYS_SOFTWARE=1 QT_X11_NO_MITSHM=1
exec rviz2 -d /mnt/e/FishBot_Course/slam_real_2026-11-05/turn_checks/20261108_181646_ramp_left90/odom_test.rviz --ros-args -r __node:=fishbot_turn_test_view -p use_sim_time:=false
