param([switch]$Preview, [string]$Distro = 'Ubuntu', [int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$scriptPath = Join-Path $PSScriptRoot 'hardware\keyboard_control\keyboard_server.py'
$pythonPath = 'C:\Users\28764\.platformio\penv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw "Python executable not found: $pythonPath" }
$env:PYTHONIOENCODING = 'utf-8'
$launchArgs = @($scriptPath, '--distro', $Distro, '--port', "$Port")
if ($Preview) { $launchArgs += '--preview' }
& $pythonPath @launchArgs
