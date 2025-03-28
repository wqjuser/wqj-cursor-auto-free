import warnings
import os
import platform
import subprocess
import time
import threading
import shutil
import argparse
import sys
import locale

# Ignore specific SyntaxWarning
warnings.filterwarnings("ignore", category=SyntaxWarning, module="DrissionPage")

CURSOR_LOGO = """
   ██████╗██╗   ██╗██████╗ ███████╗ ██████╗ ██████╗ 
  ██╔════╝██║   ██║██╔══██╗██╔════╝██╔═══██╗██╔══██╗
  ██║     ██║   ██║██████╔╝███████╗██║   ██║██████╔╝
  ██║     ██║   ██║██╔══██╗╚════██║██║   ██║██╔══██╗
  ╚██████╗╚██████╔╝██║  ██║███████║╚██████╔╝██║  ██║
   ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝
"""

def setup_console():
    """设置控制台以支持ANSI颜色和Unicode字符"""
    if platform.system() == 'Windows':
        # 启用ANSI转义序列
        os.system('')
        # 设置控制台编码为UTF-8
        if sys.version_info >= (3, 7):
            sys.stdout.reconfigure(encoding='utf-8')
        else:
            # Python 3.6及以下版本
            import codecs
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)

def safe_print_colored(text, color_code=""):
    """安全打印带颜色的文本"""
    try:
        if platform.system() == 'Windows':
            # Windows下尝试直接打印
            print(f"{color_code}{text}\033[0m")
        else:
            # 其他系统正常打印
            print(f"{color_code}{text}\033[0m")
    except UnicodeEncodeError:
        # 如果发生编码错误，尝试不带颜色打印
        try:
            print(text)
        except UnicodeEncodeError:
            # 如果还是失败，打印ASCII版本
            print("CURSOR")

def print_logo():
    """打印CLI版本的logo"""
    setup_console()
    safe_print_colored(CURSOR_LOGO, "\033[96m")
    safe_print_colored("Building Cursor Keep Alive...".center(56), "\033[93m")
    print()

def print_gui_logo():
    """打印GUI版本的logo"""
    setup_console()
    safe_print_colored(CURSOR_LOGO, "\033[96m")
    safe_print_colored("Building Cursor Pro GUI...".center(56), "\033[93m")
    print()


class LoadingAnimation:
    def __init__(self):
        self.is_running = False
        self.animation_thread = None

    def start(self, message="Building"):
        self.is_running = True
        self.animation_thread = threading.Thread(target=self._animate, args=(message,))
        self.animation_thread.start()

    def stop(self):
        self.is_running = False
        if self.animation_thread:
            self.animation_thread.join()
        print("\r" + " " * 70 + "\r", end="", flush=True)  # Clear the line

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
    print(f"\r{prefix} |{bar}| {percent}% Complete", end="", flush=True)
    if progress == total:
        print()


def simulate_progress(message, duration=1.0, steps=20):
    print(f"\033[94m{message}\033[0m")
    for i in range(steps + 1):
        time.sleep(duration / steps)
        progress_bar(i, steps, prefix="Progress:", length=40)


def filter_output(output):
    """ImportantMessage"""
    if not output:
        return ""
    important_lines = []
    for line in output.split("\n"):
        # Only keep lines containing specific keywords
        if any(
            keyword in line.lower()
            for keyword in ["error:", "failed:", "completed", "directory:"]
        ):
            important_lines.append(line)
    return "\n".join(important_lines)


def create_manifest_file():
    """创建请求管理员权限的manifest文件"""
    print(f"\033[93mCreating app.manifest...\033[0m")
    
    with open("app.manifest", "w", encoding="utf-8") as f:
        f.write('''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <assemblyIdentity type="win32" name="CursorPro" version="1.0.0.0" processorArchitecture="*"/>
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel level="requireAdministrator" uiAccess="false"/>
      </requestedPrivileges>
    </security>
  </trustInfo>
  <compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1">
    <application>
      <!-- Windows 10 和 Windows Server 2016 -->
      <supportedOS Id="{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}"/>
      <!-- Windows 8.1 和 Windows Server 2012 R2 -->
      <supportedOS Id="{1f676c76-80e1-4239-95bb-83d0f6d0da78}"/>
      <!-- Windows 8 和 Windows Server 2012 -->
      <supportedOS Id="{4a2f28e3-53b9-4441-ba9c-d69d4a4a6e38}"/>
      <!-- Windows 7 和 Windows Server 2008 R2 -->
      <supportedOS Id="{35138b9a-5d96-4fbd-8e2d-a2440225f93a}"/>
      <!-- Windows Vista 和 Windows Server 2008 -->
      <supportedOS Id="{e2011457-1546-43c5-a5fe-008deee3d3f0}"/>
    </application>
  </compatibility>
</assembly>''')
    
    simulate_progress("Created app.manifest...", 0.5)
    return "app.manifest"


def create_spec_file(is_gui=False):
    """创建PyInstaller规范文件"""
    system = platform.system().lower()
    arch = os.environ.get('MACOS_ARCH', '')
    
    # 根据系统和架构设置文件名
    if system == 'darwin':
        if arch == 'arm64':
            app_name = "CursorPro-MacOS-ARM64" if not is_gui else "CursorProGUI-MacOS-ARM64"
            target_arch = "arm64"
        else:
            app_name = "CursorPro-MacOS-Intel" if not is_gui else "CursorProGUI-MacOS-Intel"
            target_arch = "x86_64"
    elif system == 'windows':
        app_name = "CursorPro-Windows" if not is_gui else "CursorProGUI-Windows"
        target_arch = None
    else:  # linux
        app_name = "CursorPro-Linux" if not is_gui else "CursorProGUI-Linux"
        target_arch = None
    
    file_name = f"{app_name}.spec"
    entry_point = "start_gui.py" if is_gui else "cursor_pro_keep_alive.py"
    # 直接计算console值，不带引号，这样在spec文件中会是实际的布尔值
    console_value = "False" if is_gui else "True"    
    print(f"\033[93mCreating {file_name}...\033[0m")
    
    # 准备hiddenimports列表
    common_imports = [
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
    
    # 只在GUI版本中添加PyQt6和cursor_gui
    if is_gui:
        common_imports = ['PyQt6', 'cursor_gui'] + common_imports
    
    # 将列表转换为格式化的字符串
    hidden_imports = ',\n        '.join(f"'{item}'" for item in common_imports)
    
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.win32 import winmanifest

block_cipher = None

# 确保使用正确的manifest文件
manifest_path = 'app.manifest'

# 定义是否为GUI版本
is_gui = {str(is_gui).capitalize()}

a = Analysis(
    ['{entry_point}'],
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

if sys.platform == 'darwin':  # macOS specific configuration
    if is_gui:  # GUI版本生成.app
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
            target_arch='{target_arch}' if '{target_arch}' else None,
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
            name='{app_name}',
        )
        
        app = BUNDLE(
            coll,
            name='{app_name}.app',
            icon='icon.icns' if os.path.exists('icon.icns') else None,
            bundle_identifier='com.cursor.pro.gui',
            info_plist={{
                'NSHighResolutionCapable': 'True',
                'LSBackgroundOnly': 'False',
                'CFBundleName': '{app_name}',
                'CFBundleDisplayName': 'Cursor Pro GUI',
                'CFBundleGetInfoString': 'Cursor Pro GUI Application',
                'CFBundleVersion': '1.0.0',
                'CFBundleShortVersionString': '1.0.0',
                'CFBundleIdentifier': 'com.cursor.pro.gui',
                'CFBundleExecutable': '{app_name}',
                'CFBundlePackageType': 'APPL',
                'CFBundleSignature': '????',
                'LSMinimumSystemVersion': '10.13.0',
                'NSAppleEventsUsageDescription': 'This app needs to access Apple Events for automation.',
                'NSRequiresAquaSystemAppearance': 'No',
                'LSApplicationCategoryType': 'public.app-category.utilities',
                'NSPrincipalClass': 'NSApplication',
                'NSAppleScriptEnabled': 'True',
                'LSEnvironment': {{
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
                }},
                'LSUIElement': False,  # 允许在Dock中显示
                'NSSupportsAutomaticGraphicsSwitching': True,
                'NSRequiresAquaSystemAppearance': False,  # 支持暗色模式
                'NSMicrophoneUsageDescription': 'This app does not need microphone access.',
                'NSCameraUsageDescription': 'This app does not need camera access.',
                'NSLocationUsageDescription': 'This app does not need location access.',
                'NSDocumentsFolderUsageDescription': 'This app needs access to the Documents folder.',
                'NSDesktopFolderUsageDescription': 'This app needs access to the Desktop folder.'
            }}
        )
    else:  # 命令行版本生成Unix可执行文件
        exe = EXE(
            pyz,
            a.scripts,
            a.binaries,
            a.zipfiles,
            a.datas,
            [],
            name='{app_name}',
            debug=False,
            bootloader_ignore_signals=False,
            strip=False,
            upx=True,
            upx_exclude=[],
            runtime_tmpdir=None,
            console=True,
            disable_windowed_traceback=False,
            argv_emulation=False,
            target_arch='{target_arch}' if '{target_arch}' else None,
            codesign_identity=None,
            entitlements_file=None,
            icon='icon.icns' if os.path.exists('icon.icns') else None,
        )
else:  # Windows and Linux configuration
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='{app_name}',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console={console_value},
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon='icon.ico' if os.path.exists('icon.ico') else None,
        manifest=manifest_path,
        uac_admin=True,  # 显式请求管理员权限
    )
"""
    
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(spec_content)
    
    simulate_progress(f"Created {file_name}...", 0.5)
    return file_name


def run_pyinstaller(spec_file, output_dir, system):
    """运行PyInstaller打包应用程序"""
    pyinstaller_command = [
        "pyinstaller",
        spec_file,
        "--distpath", output_dir,
        "--workpath", f"build/{system}",
        "--noconfirm",
    ]

    loading = LoadingAnimation()
    try:
        simulate_progress("Running PyInstaller...", 2.0)
        loading.start("Building in progress")
        
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
            print(f"\033[91mBuild failed with error code {process.returncode}\033[0m")
            if stderr:
                print("\033[91mError Details:\033[0m")
                print(stderr)
            return False

        if stderr:
            filtered_errors = [
                line for line in stderr.split("\n")
                if any(keyword in line.lower() 
                      for keyword in ["error:", "failed:", "completed", "directory:"])
            ]
            if filtered_errors:
                print("\033[93mBuild Warnings/Errors:\033[0m")
                print("\n".join(filtered_errors))
        
        # 清理macOS GUI构建时生成的中间文件夹
        if system == "darwin" and "GUI" in spec_file:
            app_name = "CursorProGUI"
            intermediate_folder = os.path.join(output_dir, app_name)
            if os.path.exists(intermediate_folder) and os.path.isdir(intermediate_folder):
                print(f"\033[93m清理中间文件夹: {intermediate_folder}\033[0m")
                try:
                    shutil.rmtree(intermediate_folder)
                except Exception as e:
                    print(f"\033[91m清理中间文件夹失败: {str(e)}\033[0m")

        return True
    except Exception as e:
        loading.stop()
        print(f"\033[91mBuild failed: {str(e)}\033[0m")
        return False
    finally:
        loading.stop()


def check_build_result(output_dir, system, is_gui=False):
    """检查构建结果"""
    # 根据系统和架构设置文件名
    if system == "darwin":  # macOS
        arch = os.environ.get('MACOS_ARCH', '')
        if arch == 'arm64':
            app_name = "CursorPro-MacOS-ARM64" if not is_gui else "CursorProGUI-MacOS-ARM64"
        else:
            app_name = "CursorPro-MacOS-Intel" if not is_gui else "CursorProGUI-MacOS-Intel"
    elif system == 'windows':
        app_name = "CursorPro-Windows" if not is_gui else "CursorProGUI-Windows"
    else:  # linux
        app_name = "CursorPro-Linux" if not is_gui else "CursorProGUI-Linux"
    
    # 根据操作系统检查不同的输出文件
    if system == "darwin":  # macOS
        if is_gui:  # GUI版本检查.app文件
            app_path = os.path.join(output_dir, f"{app_name}.app")
            if os.path.exists(app_path):
                print(f"\n\033[92mBuild completed successfully!\033[0m")
                print(f"\033[92m{app_name}.app has been created at: {app_path}\033[0m")
                return True
            else:
                print(f"\n\033[91mBuild failed: {app_name}.app was not created\033[0m")
                return False
        else:  # 命令行版本检查Unix可执行文件
            exe_path = os.path.join(output_dir, app_name)
            if os.path.exists(exe_path):
                print(f"\n\033[92mBuild completed successfully!\033[0m")
                print(f"\033[92m{app_name} has been created at: {exe_path}\033[0m")
                return True
            else:
                print(f"\n\033[91mBuild failed: {app_name} was not created\033[0m")
                return False
    else:  # Windows 或 Linux
        exe_path = os.path.join(output_dir, f"{app_name}.exe" if system == "windows" else app_name)
        if os.path.exists(exe_path):
            print(f"\n\033[92mBuild completed successfully!\033[0m")
            print(f"\033[92m{os.path.basename(exe_path)} has been created at: {exe_path}\033[0m")
            return True
        else:
            print(f"\n\033[91mBuild failed: {os.path.basename(exe_path)} was not created\033[0m")
            return False


def build(minimal=True, is_gui=False):
    """构建应用程序"""
    # Clear screen
    os.system("cls" if platform.system().lower() == "windows" else "clear")

    # Print logo
    if is_gui:
        print_gui_logo()
    else:
        print_logo()

    system = platform.system().lower()
    output_dir = f"dist/{system if system != 'darwin' else 'mac'}"

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    simulate_progress("Creating output directory...", 0.5)

    # 创建清单文件
    create_manifest_file()
    
    # 创建spec文件
    spec_file = create_spec_file(is_gui)
    
    # 运行PyInstaller
    if run_pyinstaller(spec_file, output_dir, system):
        # 检查构建结果
        return check_build_result(output_dir, system, is_gui)
    
    return False


def build_gui():
    """构建GUI应用程序"""
    return build(minimal=False, is_gui=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Cursor Pro applications")
    parser.add_argument("--gui", action="store_true", help="Build GUI application")
    args = parser.parse_args()
    
    if args.gui:
        build_gui()
    else:
        build()  # 默认构建命令行版本