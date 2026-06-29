@echo off
setlocal

REM Build exclusivamente com o ambiente oficial Python 3.12.
set "APP_ROOT=%~dp0"
set "PYTHON=%APP_ROOT%..\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Ambiente Python 3.12 ausente. Execute install_all.ps1 primeiro.
    exit /b 1
)

"%PYTHON%" "%APP_ROOT%scripts\verify_python_runtime.py" --check-imports
if errorlevel 1 exit /b 1

cd /d "%APP_ROOT%"
"%PYTHON%" -m nuitka --standalone --lto=no --jobs=4 --output-dir=dist_nuitka --main=main.py --enable-plugin=numpy --enable-plugin=pyside6 --include-qt-plugins=all
