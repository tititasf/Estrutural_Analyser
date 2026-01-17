from PyInstaller.utils.hooks import collect_data_files, collect_all

# Collect rfc3987 syntax files (Fix ModuleNotFoundError: rfc3987)
datas = collect_data_files('rfc3987')
datas += collect_data_files('rfc3987_syntax')

# Collect simple settings for chromadb to avoid missing modules
tmp_ret = collect_all('chromadb')
datas += tmp_ret[0]
binaries = tmp_ret[1]
hiddenimports = tmp_ret[2]

# Add win32timezone and other common missing imports
hiddenimports += ['win32timezone', 'pysqlite3', 'sqlite3']

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AgenteCAD',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AgenteCAD',
)
