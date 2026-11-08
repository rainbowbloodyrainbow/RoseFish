$ErrorActionPreference='Stop'
& wsl.exe -d Ubuntu -- python3 /mnt/e/FishBot_Course/s3_lidar_car_2026-11-05/close_rviz_views.py
if ($LASTEXITCODE -ne 0) { throw 'Could not close previous car RViz views.' }
Write-Output 'Starting RViz with LIBGL_ALWAYS_SOFTWARE=1. Keep this terminal open.'
& wsl.exe -d Ubuntu -- bash /mnt/e/FishBot_Course/s3_lidar_car_2026-11-05/open_rviz_preview.sh
