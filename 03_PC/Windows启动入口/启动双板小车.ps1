param([string]$S3IP = '', [switch]$NoRviz)
$ErrorActionPreference = 'Stop'
$rootPath = 'E:\FishBot_Course\s3_lidar_car_2026-11-05'
$pythonPath = 'C:\Users\28764\.platformio\penv\Scripts\python.exe'
$env:PYTHONIOENCODING = 'utf-8'
if (-not $S3IP) {
    $S3IP = (Get-Content -LiteralPath "$rootPath\link.json" -Raw | ConvertFrom-Json).s3_ip
}
$parsedIP = $null
if (-not [System.Net.IPAddress]::TryParse($S3IP, [ref]$parsedIP) -or $parsedIP.AddressFamily -ne 'InterNetwork') {
    throw 'S3IP must be a valid IPv4 address.'
}
$wlanAddress = Get-NetIPAddress -InterfaceAlias 'WLAN' -AddressFamily IPv4 | Where-Object IPAddress -eq '10.212.8.109'
if (-not $wlanAddress) { throw 'Connect this PC to the chassis hotspot first (expected PC IP: 10.212.8.109).' }
$serviceText = & wsl.exe -d Ubuntu -- python3 /mnt/e/FishBot_Course/s3_lidar_car_2026-11-05/service_status.py
if ($LASTEXITCODE -ne 0) { throw 'Could not query WSL services.' }
$services = $serviceText | ConvertFrom-Json
function Start-PythonService([string]$ScriptPath, [string]$LogStem) {
    $existing = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
        $_.CommandLine -and $_.CommandLine.Contains($ScriptPath)
    }
    if (-not $existing) {
        Start-Process -FilePath $pythonPath -ArgumentList @('-u',$ScriptPath) -WindowStyle Hidden `
            -RedirectStandardOutput "$rootPath\$LogStem.log" `
            -RedirectStandardError "$rootPath\$LogStem-error.log" | Out-Null
    }
}
if (-not $services.agent) {
    Start-Process -FilePath 'wsl.exe' -ArgumentList @('-d','Ubuntu','--','bash',
        '/mnt/e/FishBot_Course/keyboard_control/start_agent.sh') -WindowStyle Hidden `
        -RedirectStandardOutput "$rootPath\agent.log" -RedirectStandardError "$rootPath\agent-error.log" | Out-Null
}
Start-PythonService 'E:\FishBot_Course\d0wd_link_2026-10-30\udp_relay.py' 'chassis-relay'
Start-PythonService 'E:\FishBot_Course\keyboard_control\keyboard_server.py' 'keyboard-server'
if (-not $services.lidar) {
    $rvizFlag = if ($NoRviz) {'false'} else {'true'}
    Start-Process -FilePath 'wsl.exe' -ArgumentList @('-d','Ubuntu','--','bash',
        '/mnt/e/FishBot_Course/s3_lidar_car_2026-11-05/run_dual.sh',$S3IP,$rvizFlag) -WindowStyle Hidden `
        -RedirectStandardOutput "$rootPath\dual-run.log" -RedirectStandardError "$rootPath\dual-error.log" | Out-Null
}
Write-Output "Dual-board services started/reused. S3: $S3IP TCP 8889. Keyboard: http://127.0.0.1:8765/"
Write-Output 'Robot starts without an enabled motion command. Mounting TF remains uncalibrated.'
