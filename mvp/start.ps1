param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$python = 'D:\anaconda\envs\py311\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw "未找到 Conda Python：$python，请修改 start.ps1 中的路径。" }
& $python (Join-Path $PSScriptRoot 'run.py') --port $Port
exit $LASTEXITCODE
