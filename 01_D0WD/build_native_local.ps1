$ErrorActionPreference='Stop'
$taskRoot=$PSScriptRoot
$env:IDF_PATH='D:\esp323232\.espressif\v6.0.1\esp-idf'
$env:IDF_TOOLS_PATH='C:\Espressif\tools'
$env:IDF_PYTHON_ENV_PATH='C:\Espressif\tools\python\v6.0.1\venv'
$env:ESP_IDF_VERSION='6.0.1'
$env:ESP_ROM_ELF_DIR='C:\Espressif\tools\esp-rom-elfs\20241011'
$env:CMAKE_GENERATOR='Ninja'
$env:SHELL='C:/Progra~1/Git/bin/bash.exe'
$env:PATH="$taskRoot\host-tools;C:\Espressif\tools\python\v6.0.1\venv\Scripts;C:\Espressif\tools\cmake\4.0.3\bin;C:\Espressif\tools\ninja\1.12.1;C:\Espressif\tools\xtensa-esp-elf\esp-15.2.0_20251204\xtensa-esp-elf\bin;C:\Program Files\Git\usr\bin;C:\Program Files\Git\cmd;C:\Windows\System32;C:\Windows"
& 'C:\Espressif\tools\python\v6.0.1\venv\Scripts\python.exe' "$env:IDF_PATH\tools\idf.py" -C "$taskRoot\native-win" -B "$taskRoot\native-win\build" '-DSDKCONFIG_DEFAULTS=sdkconfig.defaults;config/local-link.defaults' build *> "$taskRoot\native-build.log"
$taskResult=$LASTEXITCODE
Get-Content -LiteralPath "$taskRoot\native-build.log" -Tail 45
exit $taskResult
