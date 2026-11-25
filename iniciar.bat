@echo off
setlocal
cd /d "%~dp0"
title Sistema de Envios Shalom Peru

echo ======================================================================
echo    INICIANDO SERVIDOR SHALOM PERU...
echo ======================================================================
echo Carpeta actual: %cd%

:: 1. Detectar si existe Python en la ruta estándar o en PATH
set "PY_CMD="
if exist "C:\Users\carlo\AppData\Local\Programs\Python\Python314\python.exe" (
    set "PY_CMD=C:\Users\carlo\AppData\Local\Programs\Python\Python314\python.exe"
) else (
    where python >nul 2>&1
    if not errorlevel 1 (
        set "PY_CMD=python"
    ) else (
        where py >nul 2>&1
        if not errorlevel 1 set "PY_CMD=py"
    )
)

if "%PY_CMD%"=="" (
    echo [ERROR] No se encontro Python instalado en el sistema.
    pause
    exit /b 1
)

echo Python detectado: %PY_CMD%
echo.
echo Abriendo navegador en http://localhost:8000/ ...
start "" "http://localhost:8000/"

echo Servidor arrancando. No cierres esta ventana.
echo Para detener el sistema: presiona Ctrl + C
echo ======================================================================
echo.

"%PY_CMD%" run.py

if errorlevel 1 (
    echo.
    echo Ocurrio un error al ejecutar el servidor.
    pause
)
