param(
    [ValidateSet('build', 'flash', 'monitor', 'flash-monitor')]
    [string]$Action = 'build',
    [string]$Port = 'COM5'
)
$ErrorActionPreference = 'Stop'
$idfRoot = 'D:\Espressif\frameworks\esp-idf-v5.3.1'
$env:IDF_TOOLS_PATH = 'D:\Espressif'
$env:Path = 'D:\Espressif\python_env\idf5.3_py3.11_env\Scripts;' + $env:Path
. "$idfRoot\export.ps1"
Push-Location $PSScriptRoot
try {
    $arguments = @("$idfRoot\tools\idf.py")
    if ($Action -eq 'build') {
        $env:IDF_TARGET = 'esp32s3'
        $arguments += 'build'
    } else {
        $arguments += @('-p', $Port)
        if ($Action -eq 'flash-monitor') {
            $arguments += @('flash', 'monitor')
        } else {
            $arguments += $Action
        }
    }
    & python @arguments
    if ($LASTEXITCODE -ne 0) { throw "ESP-IDF command failed: $LASTEXITCODE" }
} finally {
    Pop-Location
}
