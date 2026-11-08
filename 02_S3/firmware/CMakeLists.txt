cmake_minimum_required(VERSION 3.16)
set(SDKCONFIG_DEFAULTS "sdkconfig.defaults;sdkconfig.wifi.defaults")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(s3_lidar_wifi)
