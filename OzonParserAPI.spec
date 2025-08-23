# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('config', 'config'), ('logs', 'logs'), ('models', 'models'), ('parser', 'parser'), ('routes', 'routes'), ('utils', 'utils'), ('driver_manager', 'driver_manager'), ('requirements.txt', '.'), ('C:\\Users\\nurja\\OneDrive\\Рабочий стол\\ozon-price-api\\venv\\Lib\\site-packages\\selenium_stealth\\js', 'selenium_stealth/js')]
binaries = []
hiddenimports = ['tkinter', 'tkinter.ttk', 'tkinter.messagebox', 'tkinter.filedialog', 'selenium', 'fastapi', 'uvicorn', 'uvicorn.main', 'uvicorn.server', 'uvicorn.config', 'pydantic', 'pydantic_settings', 'pyngrok', 'pyngrok.ngrok', 'aiohttp', 'requests']
tmp_ret = collect_all('pyngrok')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


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
    a.binaries,
    a.datas,
    [],
    name='OzonParserAPI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
