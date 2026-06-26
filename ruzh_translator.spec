# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Ruzh Translator macOS .app bundle."""

import sys
from pathlib import Path

# Project root (parent of the spec file)
ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / 'ruzh_translator' / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Include stylesheet
        (str(ROOT / 'ruzh_translator' / 'resources' / 'styles.qss'),
         'ruzh_translator/resources'),
    ],
    hiddenimports=[
        # SQLAlchemy dialects
        'sqlalchemy.sql.default_comparator',
        # Optional NLP packages (gracefully fail if missing)
        # 'sentence_transformers',
        # 'pymorphy3',
        # 'jieba',
        # 'yake',
        # 'nltk',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude large packages we don't need
        'tkinter',
        'unittest',
        'test',
        'pydoc',
        'distutils',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

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
    console=False,  # No console window on macOS
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add .icns path here if you have an app icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RuzhTranslator',
)

app = BUNDLE(
    coll,
    name='RuzhTranslator.app',
    icon=None,  # Add .icns path here if you have an app icon
    bundle_identifier='com.ruzh.translator',
    info_plist={
        'CFBundleName': 'Ruzh Translator',
        'CFBundleDisplayName': 'Ruzh Translator',
        'CFBundleShortVersionString': '0.1.0',
        'CFBundleVersion': '0.1.0',
        'CFBundleExecutable': 'RuzhTranslator',
        'CFBundlePackageType': 'APPL',
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'Ruzh Task File',
                'CFBundleTypeRole': 'Editor',
                'LSHandlerRank': 'Owner',
                'LSItemContentTypes': ['com.ruzh.task'],
            },
        ],
        'LSMinimumSystemVersion': '12.0',
        'NSHighResolutionCapable': True,
        'NSHumanReadableCopyright': '© 2025 Ruzh Translator',
    },
)
