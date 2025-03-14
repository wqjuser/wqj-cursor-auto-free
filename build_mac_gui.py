#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import platform
import subprocess
import time
import threading
import shutil
import argparse
import warnings

# 忽略特定的SyntaxWarning
warnings.filterwarnings("ignore", category=SyntaxWarning, module="DrissionPage")

CURSOR_LOGO = """
   ██████╗██╗   ██╗██████╗ ███████╗ ██████╗ ██████╗ 
  ██╔════╝██║   ██║██╔══██╗██╔════╝██╔═══██╗██╔══██╗
  ██║     ██║   ██║██████╔╝███████╗██║   ██║██████╔╝
  ██║     ██║   ██║██╔══██╗╚════██║██║   ██║██╔══██╗
  ╚██████╗╚██████╔╝██║  ██║███████║╚██████╔╝██║  ██║
   ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝
"""

class LoadingAnimation:
    def __init__(self):
        self.is_running = False
        self.animation_thread = None

    def start(self, message="构建中"):
        self.is_running = True
        self.animation_thread = threading.Thread(target=self._animate, args=(message,))
        self.animation_thread.start()

    def stop(self):
        self.is_running = False
        if self.animation_thread:
            self.animation_thread.join()
        print("\r" + " " * 70 + "\r", end="", flush=True)  # 清除行

    def _animate(self, message):
        animation = "|/-\\"
        idx = 0
        while self.is_running:
            print(f"\r{message} {animation[idx % len(animation)]}", end="", flush=True)
            idx += 1
            time.sleep(0.1)


def progress_bar(progress, total, prefix="", length=50):
    filled = int(length * progress // total)
    bar = "█" * filled + "░" * (length - filled)
    percent = f"{100 * progress / total:.1f}"
    print(f"\r{prefix} |{bar}| {percent}% 完成", end="", flush=True)
    if progress == total:
        print()


def simulate_progress(message, duration=1.0, steps=20):
    print(f"\033[94m{message}\033[0m")
    for i in range(steps + 1):
        time.sleep(duration / steps)
        progress_bar(i, steps, prefix="进度:", length=40)


def safe_print_colored(text, color_code=""):
    """安全打印带颜色的文本"""
    try:
        print(f"{color_code}{text}\033[0m")
    except UnicodeEncodeError:
        # 如果发生编码错误，尝试不带颜色打印
        try:
            print(text)
        except UnicodeEncodeError:
            # 如果还是失败，打印ASCII版本
            print("CURSOR")


def print_gui_logo():
    """打印GUI版本的logo"""
    safe_print_colored(CURSOR_LOGO, "\033[96m")
    safe_print_colored("构建Cursor Pro macOS GUI版本...".center(56), "\033[93m")
    print()


def create_mac_spec_file():
    """创建专用于macOS的PyInstaller规范文件"""
    spec_file = "CursorProMacGUI.spec"
    entry_point = "cursor_gui.py"
    app_name = "CursorProGUI"
    
    print(f"\033[93m创建 {spec_file}...\033[0m")
    
    # 准备hiddenimports列表
    common_imports = [
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
    ]
    
    # 将列表转换为格式化的字符串
    hidden_imports = ',\n        '.join(f"'{item}'" for item in common_imports)
    
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-

import sys
import os

block_cipher = None

a = Analysis(
    ['{entry_point}'],
    pathex=[],
    binaries=[],
    datas=[
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
        {hidden_imports}
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# macOS专用配置
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='{app_name}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 设置为False以隐藏控制台窗口
    icon='icon.icns' if os.path.exists('icon.icns') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='{app_name}'
)

app = BUNDLE(
    coll,
    name='{app_name}.app',
    icon='icon.icns' if os.path.exists('icon.icns') else None,
    bundle_identifier='com.cursor.pro.gui',
    info_plist={{
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
        'CFBundleName': '{app_name}',
        'CFBundleDisplayName': 'Cursor Pro GUI',
        'CFBundleGetInfoString': 'Cursor Pro GUI Application',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleIdentifier': 'com.cursor.pro.gui',
        'CFBundleExecutable': '{app_name}',
        'CFBundlePackageType': 'APPL',
        'LSMinimumSystemVersion': '10.13.0',
        'NSAppleEventsUsageDescription': 'This app needs to access Apple Events for automation.',
        'LSUIElement': '0',  # 允许在Dock中显示
        'NSSupportsAutomaticGraphicsSwitching': True,
        'NSMainNibFile': '',  # 关键: 空字符串确保使用默认入口点
        'NSHumanReadableCopyright': 'Copyright © 2023 Cursor Pro. All rights reserved.',
        'NSAppTransportSecurity': {{
            'NSAllowsArbitraryLoads': True
        }},
        'LSEnvironment': {{
            'PYTHONHOME': '.',
            'PYTHONPATH': '.',
            'QT_MAC_WANTS_LAYER': '1',
            'QT_AUTO_SCREEN_SCALE_FACTOR': '1',
            'PATH': '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin',
            'LANG': 'zh_CN.UTF-8'
        }}
    }}
)
"""
    
    with open(spec_file, "w", encoding="utf-8") as f:
        f.write(spec_content)
    
    simulate_progress(f"已创建 {spec_file}...", 0.5)
    return spec_file


def create_launcher_script():
    """创建macOS启动器脚本，确保应用能够正确启动"""
    launcher_script = "mac_launcher.py"
    print(f"\033[93m创建 {launcher_script}...\033[0m")
    
    content = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import platform
import pathlib

def get_bundle_resource_path():
    
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # PyInstaller打包的应用
        bundle_path = pathlib.Path(sys._MEIPASS).parent
        if platform.system() == 'Darwin':
            # 在macOS下，如果是.app包内，需要特殊处理
            app_path = pathlib.Path(os.path.dirname(os.path.abspath(sys.executable)))
            if '.app/Contents/MacOS' in str(app_path):
                # 使用相对路径，从执行文件位置计算资源位置
                return app_path.parent.parent / 'Resources'
        return bundle_path
    else:
        # 直接运行脚本
        return pathlib.Path(os.path.dirname(os.path.abspath(__file__)))

def main():
    
    # 获取当前路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 设置工作目录，确保相对路径正确
    os.chdir(current_dir)
    
    # 添加当前目录到Python路径
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    # 获取资源路径
    resource_path = get_bundle_resource_path()
    
    # 为环境变量设置正确的路径
    os.environ['PYTHONPATH'] = str(resource_path)
    os.environ['QT_MAC_WANTS_LAYER'] = '1'
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
    
    try:
        # 导入并运行GUI模块
        import cursor_gui
        cursor_gui.main()
    except ImportError as e:
        print(f"错误: 无法导入cursor_gui模块: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"启动应用时出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
"""
    
    with open(launcher_script, "w", encoding="utf-8") as f:
        f.write(content)
    
    simulate_progress(f"已创建 {launcher_script}...", 0.5)
    return launcher_script


def run_pyinstaller(spec_file, output_dir):
    """运行PyInstaller打包应用程序"""
    pyinstaller_command = [
        "pyinstaller",
        spec_file,
        "--distpath", output_dir,
        "--workpath", "build/mac",
        "--noconfirm",
        "--clean",  # 清理之前的构建文件
        "--log-level", "INFO"  # 提供更多日志信息
    ]

    loading = LoadingAnimation()
    try:
        simulate_progress("运行PyInstaller...", 2.0)
        loading.start("构建中")
        
        process = subprocess.Popen(
            pyinstaller_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
            errors='ignore'
        )
        
        stdout, stderr = process.communicate()
        loading.stop()

        if process.returncode != 0:
            print(f"\033[91m构建失败，错误代码 {process.returncode}\033[0m")
            if stderr:
                print("\033[91m错误详情:\033[0m")
                print(stderr)
            return False

        if stderr:
            filtered_errors = [
                line for line in stderr.split("\n")
                if any(keyword in line.lower() 
                      for keyword in ["error:", "failed:", "completed", "directory:"])
            ]
            if filtered_errors:
                print("\033[93m构建警告/错误:\033[0m")
                print("\n".join(filtered_errors))

        return True
    except Exception as e:
        loading.stop()
        print(f"\033[91m构建失败: {str(e)}\033[0m")
        return False
    finally:
        loading.stop()


def fix_mac_app_structure(output_dir, app_name):
    """修复macOS应用程序结构，确保能正确启动"""
    app_path = os.path.join(output_dir, f"{app_name}.app")
    if not os.path.exists(app_path):
        print(f"\033[91m错误: 找不到应用包 {app_path}\033[0m")
        return False
    
    print(f"\033[93m修复应用包结构...\033[0m")
    
    # 添加启动器脚本
    launcher_path = "mac_launcher.py"
    try:
        if os.path.exists(launcher_path):
            resources_dir = os.path.join(app_path, "Contents", "Resources")
            macos_dir = os.path.join(app_path, "Contents", "MacOS")
            
            # 确保目录存在
            os.makedirs(resources_dir, exist_ok=True)
            os.makedirs(macos_dir, exist_ok=True)
            
            # 复制启动器脚本到Resources目录
            shutil.copy2(launcher_path, os.path.join(resources_dir, "launcher.py"))
            
            # 创建启动脚本
            startup_script_path = os.path.join(macos_dir, "startup.sh")
            with open(startup_script_path, "w") as f:
                f.write(f"""#!/bin/bash
cd "$(dirname "$0")"
chmod +x ./{app_name}
export PYTHONHOME="."
export PYTHONPATH="../Resources"
export QT_MAC_WANTS_LAYER=1
export QT_AUTO_SCREEN_SCALE_FACTOR=1
export LANG=zh_CN.UTF-8
./{app_name}
""")
            
            # 设置启动脚本可执行权限
            os.chmod(startup_script_path, 0o755)
            
            # 修改Info.plist以使用启动脚本
            info_plist_path = os.path.join(app_path, "Contents", "Info.plist")
            if os.path.exists(info_plist_path):
                import plistlib
                
                try:
                    with open(info_plist_path, 'rb') as f:
                        plist = plistlib.load(f)
                    
                    # 修改执行文件名为启动脚本
                    plist['CFBundleExecutable'] = 'startup.sh'
                    
                    with open(info_plist_path, 'wb') as f:
                        plistlib.dump(plist, f)
                    
                    print("\033[92mInfo.plist已更新\033[0m")
                except Exception as e:
                    print(f"\033[91m更新Info.plist时出错: {str(e)}\033[0m")
                    return False
            
            print("\033[92m应用包结构已修复\033[0m")
            return True
        else:
            print(f"\033[91m错误: 找不到启动器脚本 {launcher_path}\033[0m")
            return False
    except Exception as e:
        print(f"\033[91m修复应用包结构时出错: {str(e)}\033[0m")
        return False


def check_build_result(output_dir, app_name):
    """检查构建结果"""
    app_path = os.path.join(output_dir, f"{app_name}.app")
    if os.path.exists(app_path) and os.path.isdir(app_path):
        print(f"\n\033[92m构建成功完成!\033[0m")
        print(f"\033[92m{app_name}.app 已创建于: {app_path}\033[0m")
        return True
    else:
        print(f"\n\033[91m构建失败: {app_name}.app 未创建\033[0m")
        return False


def build_mac_gui():
    """构建macOS GUI应用程序"""
    # 清屏
    os.system("clear")

    # 打印logo
    print_gui_logo()

    output_dir = "dist/mac"
    app_name = "CursorProGUI"

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    simulate_progress("创建输出目录...", 0.5)
    
    # 创建启动器脚本
    create_launcher_script()
    
    # 创建spec文件
    spec_file = create_mac_spec_file()
    
    # 运行PyInstaller
    if run_pyinstaller(spec_file, output_dir):
        # 修复应用结构
        if fix_mac_app_structure(output_dir, app_name):
            # 检查构建结果
            return check_build_result(output_dir, app_name)
    
    return False


if __name__ == "__main__":
    if platform.system() != 'Darwin':
        print("\033[91m错误: 这个脚本只能在macOS系统上运行!\033[0m")
        sys.exit(1)
    
    build_mac_gui() 