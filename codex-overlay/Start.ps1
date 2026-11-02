$ErrorActionPreference = 'Stop'
$pythonCommand = Get-Command pythonw.exe -ErrorAction SilentlyContinue
if (-not $pythonCommand) { throw 'Python with tkinter is required.' }
$scriptPath = Join-Path $PSScriptRoot 'codex_quota.py'
Start-Process -FilePath $pythonCommand.Source -ArgumentList @('"' + $scriptPath + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
