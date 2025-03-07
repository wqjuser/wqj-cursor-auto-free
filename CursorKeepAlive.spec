# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

# 确定是否是 Windows 系统
is_windows = sys.platform.startswith('win')

# 获取清单文件的绝对路径
manifest_path = os.path.abspath('app.manifest')

a = Analysis(
    ['cursor_pro_keep_alive.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('turnstilePatch', 'turnstilePatch'),
        ('cursor_auth_manager.py', '.'),
        ('patch_cursor_get_machine_id.py', '.')
    ],
    hiddenimports=[
        'cursor_auth_manager',
        'psutil',
        'aiofiles',
        'DrissionPage',
        'colorama',
        'exit_cursor',
        'browser_utils',
        'get_email_code',
        'logo',
        'config',
        'patch_cursor_get_machine_id',
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

target_arch = os.environ.get('TARGET_ARCH', None)

# 在Windows上，使用清单文件
if is_windows and os.path.exists(manifest_path):
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='CursorPro',
        debug=False,  # 禁用调试模式，避免不必要的问题
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=True,  # 确保控制台窗口保持打开
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=target_arch,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,
        manifest=manifest_path,  # 使用清单文件
        uac_admin=True  # 添加这个参数确保UAC提权
    )
else:
    # 在非Windows系统上，或者清单文件不存在时，不使用清单文件
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
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
        target_arch=target_arch,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,
    )

# 如果在 Mac 上构建
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='CursorPro.app',
        icon=None,
        bundle_identifier=None,
    )