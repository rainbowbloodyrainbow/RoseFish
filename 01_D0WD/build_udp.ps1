$ErrorActionPreference='Stop'
$env:IDF_PATH='D:\esp323232\.espressif\v6.0.1\esp-idf'
$env:IDF_TOOLS_PATH='C:\Espressif\tools'
$env:IDF_PYTHON_ENV_PATH='C:\Espressif\tools\python\v6.0.1\venv'
$env:ESP_IDF_VERSION='6.0.1'
$env:ESP_ROM_ELF_DIR='C:\Espressif\tools\esp-rom-elfs\20241011'
$env:PATH='C:\Espressif\tools\python\v6.0.1\venv\Scripts;C:\Espressif\tools\cmake\4.0.3\bin;C:\Espressif\tools\ninja\1.12.1;C:\Espressif\tools\xtensa-esp-elf\esp-15.2.0_20251204\xtensa-esp-elf\bin;C:\Program Files\Git\cmd;C:\Windows\System32;C:\Windows'
& "$env:IDF_PYTHON_ENV_PATH\Scripts\python.exe" "$env:IDF_PATH\tools\idf.py" -C "$PSScriptRoot\udp_base" -B "$PSScriptRoot\udp_base\build" build *> "$PSScriptRoot\udp-build.log"
$taskExit=$LASTEXITCODE
Get-Content -LiteralPath "$PSScriptRoot\udp-build.log" -Tail 24
exit $taskExit
