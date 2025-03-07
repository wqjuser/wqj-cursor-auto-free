#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
手动嵌入清单文件到EXE
此脚本用于在打包后手动嵌入清单文件，确保应用程序以管理员权限运行
"""

import os
import sys
import subprocess
import time
import platform

def print_colored(text, color):
    """打印彩色文本"""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "purple": "\033[95m",
        "cyan": "\033[96m",
        "white": "\033[97m",
        "reset": "\033[0m"
    }
    print(f"{colors.get(color, '')}{text}{colors['reset']}")

def find_mt_exe():
    """查找Windows SDK中的mt.exe工具"""
    mt_paths = [
        r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64\mt.exe",
        r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.18362.0\x64\mt.exe",
        r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.17763.0\x64\mt.exe",
        r"C:\Program Files (x86)\Windows Kits\10\bin\x64\mt.exe",
        r"C:\Program Files (x86)\Windows Kits\8.1\bin\x64\mt.exe"
    ]
    
    for path in mt_paths:
        if os.path.exists(path):
            return path
    
    return None

def find_resource_hacker():
    """查找Resource Hacker工具"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"reshakerfile\shell\open\command") as key:
            reshacker_cmd = winreg.QueryValue(key, None)
            reshacker_path = reshacker_cmd.split('"')[1] if '"' in reshacker_cmd else reshacker_cmd.split(' ')[0]
            
            if os.path.exists(reshacker_path):
                return reshacker_path
    except:
        pass
    
    # 尝试常见安装路径
    common_paths = [
        r"C:\Program Files (x86)\Resource Hacker\ResourceHacker.exe",
        r"C:\Program Files\Resource Hacker\ResourceHacker.exe"
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            return path
    
    return None

def embed_manifest_with_mt(exe_path, manifest_path):
    """使用mt.exe嵌入清单文件"""
    mt_exe = find_mt_exe()
    if not mt_exe:
        print_colored("未找到mt.exe工具，无法使用此方法嵌入清单", "yellow")
        return False
    
    print_colored(f"找到mt.exe: {mt_exe}", "green")
    print_colored(f"正在嵌入清单文件到: {exe_path}", "blue")
    
    # 使用mt.exe嵌入清单
    mt_command = [
        mt_exe,
        "-manifest", manifest_path,
        "-outputresource:" + exe_path + ";#1"
    ]
    
    print_colored(f"执行命令: {' '.join(mt_command)}", "blue")
    
    try:
        process = subprocess.run(
            mt_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
            errors='ignore'
        )
        
        if process.returncode == 0:
            print_colored("清单文件嵌入成功！", "green")
            return True
        else:
            print_colored(f"嵌入清单文件失败: {process.stderr}", "red")
            return False
    except Exception as e:
        print_colored(f"执行mt.exe时出错: {str(e)}", "red")
        return False

def embed_manifest_with_reshacker(exe_path, manifest_path):
    """使用Resource Hacker嵌入清单文件"""
    reshacker_path = find_resource_hacker()
    if not reshacker_path:
        print_colored("未找到Resource Hacker工具，无法使用此方法嵌入清单", "yellow")
        return False
    
    print_colored(f"找到Resource Hacker: {reshacker_path}", "green")
    print_colored(f"正在使用Resource Hacker嵌入清单文件到: {exe_path}", "blue")
    
    try:
        # 创建Resource Hacker脚本
        script_content = f"""
[FILENAMES]
Exe="{exe_path}"
SaveAs="{exe_path}"
Log=
[COMMANDS]
-addoverwrite "{manifest_path}", RT_MANIFEST, 1, 0
"""
        script_path = "reshacker_script.txt"
        with open(script_path, "w") as f:
            f.write(script_content)
            
        # 运行Resource Hacker
        print_colored(f"执行Resource Hacker脚本...", "blue")
        process = subprocess.run(
            [reshacker_path, "-script", script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
            errors='ignore'
        )
        
        # 删除临时脚本
        if os.path.exists(script_path):
            os.remove(script_path)
        
        if process.returncode == 0:
            print_colored("使用Resource Hacker嵌入清单文件成功！", "green")
            return True
        else:
            print_colored(f"使用Resource Hacker嵌入清单文件失败: {process.stderr}", "red")
            return False
    except Exception as e:
        print_colored(f"使用Resource Hacker时出错: {str(e)}", "red")
        return False

def main():
    """主函数"""
    # 清屏
    os.system("cls" if platform.system().lower() == "windows" else "clear")
    
    print_colored("=" * 60, "cyan")
    print_colored("清单文件嵌入工具 - 确保应用程序以管理员权限运行", "cyan")
    print_colored("=" * 60, "cyan")
    
    # 警告信息
    print_colored("\n警告: 此工具可能会破坏可执行文件结构，导致程序无法运行！", "red")
    print_colored("建议使用PyInstaller的内置功能在打包时嵌入清单文件，而不是在打包后修改可执行文件。", "yellow")
    print_colored("如果您已经尝试过使用此工具，并且程序无法运行，请重新构建程序。\n", "yellow")
    
    confirm = input("是否继续？(y/n): ").strip().lower()
    if confirm != 'y':
        print_colored("操作已取消", "yellow")
        return
    
    # 检查操作系统
    if platform.system().lower() != "windows":
        print_colored("此工具仅支持Windows系统", "red")
        return
    
    # 查找EXE文件
    possible_dirs = [
        "dist/win32",
        "dist/windows",
        "dist",
        "dist/win",
        "."
    ]
    
    exe_path = None
    for dir_path in possible_dirs:
        if os.path.exists(dir_path):
            possible_exe = os.path.join(dir_path, "CursorPro.exe")
            if os.path.exists(possible_exe):
                exe_path = possible_exe
                print_colored(f"找到EXE文件: {exe_path}", "green")
                break
    
    if not exe_path:
        print_colored("未找到EXE文件，请手动指定", "yellow")
        exe_path = input("请输入EXE文件的完整路径: ").strip()
        if not os.path.exists(exe_path):
            print_colored("指定的EXE文件不存在", "red")
            return
    
    # 查找清单文件
    manifest_path = "app.manifest"
    if not os.path.exists(manifest_path):
        print_colored(f"未找到清单文件: {manifest_path}", "yellow")
        print_colored("正在创建默认清单文件...", "blue")
        
        with open(manifest_path, "w", encoding="utf-8") as f:
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
    
    manifest_path = os.path.abspath(manifest_path)
    print_colored(f"EXE文件: {exe_path}", "white")
    print_colored(f"清单文件: {manifest_path}", "white")
    print_colored("=" * 60, "cyan")
    
    # 尝试使用mt.exe嵌入清单
    print_colored("方法1: 使用mt.exe嵌入清单", "blue")
    if embed_manifest_with_mt(exe_path, manifest_path):
        print_colored("清单文件嵌入成功！应用程序现在应该显示管理员权限图标", "green")
        return
    
    # 如果mt.exe失败，尝试使用Resource Hacker
    print_colored("\n方法2: 使用Resource Hacker嵌入清单", "blue")
    if embed_manifest_with_reshacker(exe_path, manifest_path):
        print_colored("清单文件嵌入成功！应用程序现在应该显示管理员权限图标", "green")
        return
    
    # 如果两种方法都失败
    print_colored("\n两种方法都失败，请尝试手动嵌入清单文件", "yellow")
    print_colored("1. 下载并安装Resource Hacker: http://www.angusj.com/resourcehacker/", "white")
    print_colored("2. 打开Resource Hacker，加载EXE文件", "white")
    print_colored("3. 右键点击'Manifest'资源，选择'Add a new Resource...'", "white")
    print_colored("4. 选择清单文件，点击'Open'", "white")
    print_colored("5. 保存修改后的EXE文件", "white")
    
    # 提供另一种方法：使用editbin工具
    print_colored("\n方法3: 使用Visual Studio的editbin工具", "blue")
    print_colored("如果您安装了Visual Studio，可以尝试以下命令:", "white")
    print_colored(f'editbin.exe /SUBSYSTEM:WINDOWS /MANIFESTUAC:level="requireAdministrator" "{exe_path}"', "white")

if __name__ == "__main__":
    main()
    print("\n按回车键退出...", end="", flush=True)
    input() 