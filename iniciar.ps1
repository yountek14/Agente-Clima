
Write-Host "=== Iniciando Agente-Clima v1.0 ===" -ForegroundColor Cyan
Write-Host ""

$ruta = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ruta

$flask = Start-Process -NoNewWindow -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList "app.py" -PassThru

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "=== Servidores activos ===" -ForegroundColor Green
Write-Host "  Flask API: http://localhost:5000" -ForegroundColor Yellow
Write-Host "  Frontend:  abre static/index.html con Live Server en VS Code" -ForegroundColor Yellow
Write-Host ""
Write-Host "Presiona ENTER para detener Flask y salir."
Read-Host | Out-Null
$flask.Kill()
Write-Host "Flask detenido." -ForegroundColor Red
