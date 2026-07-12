@echo off
REM Start da API pública de Consulta — processo/porta DISTINTOS do portal
REM interno (portal/run_dev.py, :21380). Esta API roda em :21390 (STORY-02).
REM
REM Uso: consulta-publica-api\run_consulta_publica.bat
cd /d "%~dp0"
"C:\Users\Thierry\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 21390
