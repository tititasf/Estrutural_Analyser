# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Lista de arquivos para incluir (ex: imagens, ícones)
added_files = [
    # ('caminho/local/icone.ico', '.'), 
]

a = Analysis(
    ['obfuscated/viga_analyzer_v2.py'], # Ponto de entrada OFUSCADO
    pathex=['obfuscated'],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'win32com', 
        'win32com.client', 
        'PySide6.QtCore', 
        'PySide6.QtWidgets', 
        'PySide6.QtGui',
        'uuid',
        'json',
        'requests',
        'licensing_service_v2',
        'login_dialog',
        'robo_laterais_viga_pyside',
        'gerador_script_viga',
        'gerador_script_combinados',
        'Ordenador_VIGA',
        'Combinador_VIGA',
        'preview_combinacao',
        'preview_principal'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AutomacaoVigas',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True, # Comprime o executável
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True, # True para ver log de erro se o app crashar no início
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None, # Adicione o caminho do seu .ico aqui se tiver
)
