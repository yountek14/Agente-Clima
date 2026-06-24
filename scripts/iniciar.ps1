
Write-Host "=== Iniciando Agente-Clima ===" -ForegroundColor Cyan
Write-Host ""

$ruta = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath (Join-Path $ruta "..")

$flask = Start-Process -NoNewWindow -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList "run.py" -PassThru

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "=== Servidores activos ===" -ForegroundColor Green
Write-Host "  App principal: http://localhost:5000" -ForegroundColor Yellow
Write-Host "  Stand Summit:  http://localhost:5000/stand" -ForegroundColor Yellow
Write-Host ""
Write-Host "Presiona ENTER para detener y salir."
Read-Host | Out-Null
$flask.Kill()
Write-Host "Flask detenido." -ForegroundColor Red
