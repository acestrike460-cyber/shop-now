# Script de inicio rapido para PowerShell
Write-Host "======================================================================" -ForegroundColor Red
Write-Host "   INICIANDO SISTEMA DE ENVIOS SHALOM PERU" -ForegroundColor White
Write-Host "======================================================================" -ForegroundColor Red
Write-Host ""
Write-Host "Abriendo http://localhost:8000 en tu navegador por defecto..." -ForegroundColor Cyan
Start-Process "http://localhost:8000/"

Write-Host "Servidor en ejecucion. Presiona Ctrl + C para detenerlo." -ForegroundColor Yellow
Write-Host ""
python run.py
