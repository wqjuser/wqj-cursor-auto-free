# -*- mode: python ; coding: utf-8 -*-

import sys
from PyInstaller.utils.win32 import winmanifest

block_cipher = None

# 确保使用正确的manifest文件
manifest_path = 'app.manifest'

a = Analysis(
    ['cursor_pro_keep_alive.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('.env', '.'),
        ('app.manifest', '.'),
        ('logs', 'logs'),
        ('turnstilePatch', 'turnstilePatch'),
        ('cursor_auth_manager.py', '.'),
        ('patch_cursor_get_machine_id.py', '.')
    ],
    hiddenimports=[
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'requests',
        'logging',
        'json',
        'random',
        'time',
        'os',
        'sys',
        'platform',
        'ctypes',
        'subprocess',
        'threading',
        'dotenv',
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
    name='CursorPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
    manifest=manifest_path,
    uac_admin=True,  # 显式请求管理员权限
)
