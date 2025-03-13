# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.win32 import winmanifest

block_cipher = None

# 确保使用正确的manifest文件
manifest_path = 'app.manifest'

a = Analysis(
    ['cursor_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('app.manifest', '.'),
        ('turnstilePatch', 'turnstilePatch'),
        ('cursor_auth_manager.py', '.'),
        ('patch_cursor_get_machine_id.py', '.'),
        ('start_gui.py', '.'),
        ('launcher.py', '.'),
        ('refresh_data.py', '.'),
        ('exit_cursor.py', '.'),
        ('cursor_pro_keep_alive.py', '.')
    ],
    hiddenimports=[
        'PyQt6',
        'cursor_gui',
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
        'cursor_pro_keep_alive',
        'cursor_auth_manager',
        'patch_cursor_get_machine_id',
        'refresh_data',
        'exit_cursor',
        'launcher'
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

if sys.platform == 'darwin':  # macOS specific configuration
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='CursorProGUI',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,  # 设置为False以隐藏控制台窗口
        target_arch='x86_64',
    )
    
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='CursorProGUI'
    )
    
    app = BUNDLE(
        coll,
        name='CursorProGUI.app',
        icon='icon.icns' if os.path.exists('icon.icns') else None,
        bundle_identifier='com.cursor.pro.gui',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'LSBackgroundOnly': 'False',
            'CFBundleName': 'CursorProGUI',
            'CFBundleDisplayName': 'Cursor Pro GUI',
            'CFBundleGetInfoString': 'Cursor Pro GUI Application',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleIdentifier': 'com.cursor.pro.gui',
            'CFBundleExecutable': 'CursorProGUI',
            'CFBundlePackageType': 'APPL',
            'CFBundleSignature': '????',
            'LSMinimumSystemVersion': '10.13.0',
            'NSAppleEventsUsageDescription': 'This app needs to access Apple Events for automation.',
            'NSRequiresAquaSystemAppearance': 'No',
            'LSApplicationCategoryType': 'public.app-category.utilities',
            'NSPrincipalClass': 'NSApplication',
            'NSAppleScriptEnabled': 'True',
            'LSEnvironment': {
                'QT_MAC_WANTS_LAYER': '1',
                'QT_MAC_WANTS_WINDOW': '1',
                'QT_MAC_WANTS_FOCUS': '1',
                'QT_MAC_WANTS_ACTIVATE': '1',
                'QT_AUTO_SCREEN_SCALE_FACTOR': '1',
                'QT_SCALE_FACTOR': '1',
                'QT_ENABLE_HIGHDPI_SCALING': '1',
                'OBJC_DISABLE_INITIALIZE_FORK_SAFETY': 'YES',
                'PYTHONPATH': '.',
                'PATH': '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'
            },
            'LSUIElement': False,  # 允许在Dock中显示
            'NSSupportsAutomaticGraphicsSwitching': True,
            'NSRequiresAquaSystemAppearance': False,  # 支持暗色模式
            'NSMicrophoneUsageDescription': 'This app does not need microphone access.',
            'NSCameraUsageDescription': 'This app does not need camera access.',
            'NSLocationUsageDescription': 'This app does not need location access.',
            'NSDocumentsFolderUsageDescription': 'This app needs access to the Documents folder.',
            'NSDesktopFolderUsageDescription': 'This app needs access to the Desktop folder.'
        }
    )
else:  # Windows and Linux configuration
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='CursorProGUI',
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
        icon='icon.ico' if os.path.exists('icon.ico') else None,
        manifest=manifest_path,
        uac_admin=True,  # 显式请求管理员权限
    )
