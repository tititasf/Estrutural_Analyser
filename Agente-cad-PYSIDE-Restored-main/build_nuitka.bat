@echo off
REM Build com Python 3.12 — NAO usar Python 3.14+ (STATUS_STACK_BUFFER_OVERRUN no Windows com PySide6/QThread)
C:\Users\Thierry\AppData\Local\Programs\Python\Python312\python.exe -m nuitka --standalone --lto=no --jobs=4 --output-dir=dist_nuitka --main=main.py --enable-plugin=numpy --enable-plugin=pyside6 --include-qt-plugins=all
