@echo off
setlocal

set "APP_ROOT=%~dp0"
set "PROJECT_ROOT=%APP_ROOT%.."
set "PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Ambiente Python 3.12 ainda nao configurado. Executando instalacao...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%APP_ROOT%install_all.ps1"
    if errorlevel 1 goto :error
)

"%PYTHON%" "%APP_ROOT%scripts\verify_python_runtime.py" --check-imports
if errorlevel 1 goto :error

echo Iniciando Vision-Estrutural AI com Python 3.12...
cd /d "%APP_ROOT%"
"%PYTHON%" main.py
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" pause
exit /b %EXIT_CODE%

:error
echo Falha ao preparar o runtime Python 3.12.
pause
exit /b 1
