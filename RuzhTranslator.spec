# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['ruzh_translator/main.py'],
    pathex=[],
    binaries=[],
    datas=[('ruzh_translator/resources/styles.qss', 'ruzh_translator/resources')],
    hiddenimports=['sqlalchemy.sql.default_comparator', 'openpyxl', 'lxml', 'rapidfuzz', 'chardet', 'pandas', 'scipy', 'unittest', 'jieba'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'PIL'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RuzhTranslator',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RuzhTranslator',
)
app = BUNDLE(
    coll,
    name='RuzhTranslator.app',
    icon=None,
    bundle_identifier='com.ruzh.translator',
)
