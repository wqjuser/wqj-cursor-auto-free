#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import os
import platform
import re
import shutil
import sys
import time
import tempfile
import psutil
from typing import Tuple, Optional, List
import asyncio
import aiofiles
import aiofiles.os
import aiofiles.tempfile

# 仅在 Windows 系统上导入 winreg
if platform.system() == "Windows":
    import winreg

# 配置日志
def setup_logging():
    """配置并返回logging实例"""
    logger = logging.getLogger(__name__)
    
    # 清除所有已存在的处理器
    logger.handlers.clear()
    
    # 防止日志重复
    logger.propagate = False
    
    # 设置日志级别为DEBUG以显示所有信息
    logger.setLevel(logging.INFO)
    
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

# 初始化日志
logger = setup_logging()

def get_install_location_from_registry() -> Optional[str]:
    """
    从 Windows 注册表中查找 Cursor 的安装位置
    """
    # 如果不是 Windows 系统，直接返回 None
    if platform.system() != "Windows":
        logger.debug("非 Windows 系统，跳过注册表查找")
        return None
        
    logger.debug("开始从注册表查找 Cursor 安装位置...")
    registry_paths = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{DADADADA-ADAD-ADAD-ADAD-ADADADADADAD}}_is1"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\62625861-8486-5be9-9e46-1da50df5f8ff")
    ]

    for hkey, path in registry_paths:
        logger.debug(f"正在检查注册表路径: HKEY_CURRENT_USER\\{path}")
        try:
            with winreg.OpenKey(hkey, path) as key:
                logger.debug(f"成功打开注册表键: HKEY_CURRENT_USER\\{path}")
                try:
                    # 使用 DisplayIcon 值来获取 Cursor.exe 的路径
                    cursor_exe = winreg.QueryValueEx(key, "DisplayIcon")[0]
                    logger.debug(f"找到 DisplayIcon 值: {cursor_exe}")
                    
                    if cursor_exe:
                        logger.debug(f"DisplayIcon 值不为空")
                        if os.path.isfile(cursor_exe):
                            logger.info(f"从注册表找到 Cursor 安装位置: {cursor_exe}")
                            return cursor_exe
                        else:
                            logger.debug(f"DisplayIcon 指向的文件不存在: {cursor_exe}")
                    else:
                        logger.debug("DisplayIcon 值为空")
                except WindowsError as e:
                    logger.debug(f"无法读取 DisplayIcon 值: {str(e)}")
        except WindowsError as e:
            logger.debug(f"无法打开注册表键 HKEY_CURRENT_USER\\{path}: {str(e)}")
            continue
    
    logger.debug("在注册表中未找到 Cursor 安装位置")
    return None

def get_cursor_process_path() -> Optional[str]:
    """
    通过进程查找正在运行的 Cursor
    """
    try:
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                if proc.info['name'].lower() == 'cursor.exe':
                    exe_path = proc.info['exe']
                    logger.info(f"从运行进程找到 Cursor: {exe_path}")
                    return exe_path
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        logger.error(f"查找进程时出错: {str(e)}")
    return None

async def find_cursor_exe() -> Optional[str]:
    """
    查找Cursor.exe或Cursor应用的路径

    Returns:
        Optional[str]: 如果找到则返回Cursor可执行文件的完整路径，否则返回None
    """
    logger.info("开始搜索 Cursor 可执行文件...")
    
    system = platform.system()
    
    if system == "Windows":
        # 1. 首先从注册表查找
        logger.info("查找注册表...")
        cursor_exe = get_install_location_from_registry()
        if cursor_exe:
            return cursor_exe
            
        # 2. 从运行进程中查找
        cursor_exe = get_cursor_process_path()
        if cursor_exe:
            return cursor_exe

        # 获取所有可能的驱动器
        import string
        from ctypes import windll
        
        def get_drives():
            drives = []
            bitmask = windll.kernel32.GetLogicalDrives()
            for letter in string.ascii_uppercase:
                if bitmask & 1:
                    drives.append(f"{letter}:")  # 不添加反斜杠，让 os.path.join 处理
                bitmask >>= 1
            return drives
        
        # 首先检查环境变量定义的路径（最常见的安装位置）
        env_paths = [
            os.path.join(os.getenv("LOCALAPPDATA", ""), "Programs", "Cursor"),
            os.path.join(os.getenv("PROGRAMFILES", ""), "Cursor"),
            os.path.join(os.getenv("PROGRAMFILES(X86)", ""), "Cursor"),
            os.path.join(os.getenv("APPDATA", ""), "Programs", "Cursor"),
            os.path.join(os.getenv("USERPROFILE", ""), "AppData", "Local", "Programs", "Cursor")
        ]
        
        logger.info("检查环境变量定义的路径...")
        for base_path in env_paths:
            if base_path:
                cursor_path = os.path.join(base_path, "Cursor.exe")
                logger.debug(f"检查路径: {cursor_path}")
                if os.path.isfile(cursor_path):
                    logger.info(f"找到 Cursor.exe: {cursor_path}")
                    return cursor_path
        
        # 检查所有驱动器下的常见安装位置
        logger.info("检查所有驱动器下的安装位置...")
        common_install_dirs = [
            "Cursor",
            "cursor",
            os.path.join("Program Files", "Cursor"),
            os.path.join("Program Files (x86)", "Cursor"),
            os.path.join("Users", os.getenv("USERNAME", ""), "AppData", "Local", "Programs", "Cursor")
        ]
        
        # 搜索所有驱动器
        for drive in get_drives():
            logger.debug(f"检查驱动器 {drive}")
            for install_dir in common_install_dirs:
                full_path = f"{drive}\\{install_dir}\\Cursor.exe"
                logger.debug(f"检查路径: {full_path}")
                if os.path.isfile(full_path):
                    logger.info(f"找到 Cursor.exe: {full_path}")
                    return full_path
        
        # 检查环境变量PATH中的所有目录
        if "PATH" in os.environ:
            logger.info("在 PATH 环境变量中搜索...")
            for path_dir in os.environ["PATH"].split(os.pathsep):
                location = os.path.join(path_dir, "Cursor.exe")
                logger.debug(f"检查 PATH 中的路径: {location}")
                if os.path.isfile(location):
                    logger.info(f"在 PATH 中找到 Cursor.exe: {location}")
                    return location
        
        # 如果在常见位置没找到，尝试使用where命令
        logger.info("使用 where 命令搜索 Cursor.exe...")
        try:
            import subprocess
            result = subprocess.run(["where", "Cursor.exe"], 
                                  capture_output=True, 
                                  text=True, 
                                  check=False)
            if result.returncode == 0:
                paths = result.stdout.strip().split('\n')
                if paths:
                    logger.info(f"使用 where 命令找到 Cursor.exe: {paths[0]}")
                    return paths[0]  # 返回第一个找到的路径
        except Exception as e:
            logger.error(f"使用 where 命令搜索失败: {str(e)}")
    
    elif system == "Darwin":  # macOS
        # 在 macOS 上查找 Cursor.app
        common_paths = [
            "/Applications/Cursor.app/Contents/MacOS/Cursor",
            os.path.expanduser("~/Applications/Cursor.app/Contents/MacOS/Cursor")
        ]
        
        for path in common_paths:
            if os.path.isfile(path):
                logger.info(f"在 macOS 上找到 Cursor: {path}")
                return path
                
        # 从运行进程中查找
        cursor_exe = get_cursor_process_path()
        if cursor_exe:
            return cursor_exe
            
    elif system == "Linux":
        # 在 Linux 上查找 Cursor
        common_paths = [
            "/usr/bin/cursor",
            "/usr/local/bin/cursor",
            "/opt/Cursor/cursor",
            "/usr/share/cursor/cursor"
        ]
        
        for path in common_paths:
            if os.path.isfile(path):
                logger.info(f"在 Linux 上找到 Cursor: {path}")
                return path
                
        # 从运行进程中查找
        cursor_exe = get_cursor_process_path()
        if cursor_exe:
            return cursor_exe
    
    # 如果所有方法都失败了，提示用户输入路径
    logger.warning(f"未找到 Cursor 可执行文件，请手动输入完整路径")
    time.sleep(1)
    user_path = input("请输入Cursor可执行文件的完整路径: ").strip()
    if os.path.isfile(user_path):
        logger.info(f"使用用户提供的路径: {user_path}")
        return user_path
        
    logger.error("无法找到有效的Cursor可执行文件路径")
    return None


async def get_cursor_app_path() -> Optional[str]:
    """
    获取Cursor应用程序的安装根目录

    Returns:
        Optional[str]: 如果找到则返回Cursor的安装根目录，否则返回None
    """
    # 使用缓存的cursor_exe路径（如果存在）
    if hasattr(get_cursor_app_path, 'cursor_exe'):
        return os.path.dirname(get_cursor_app_path.cursor_exe)
        
    cursor_exe = await find_cursor_exe()
    if not cursor_exe:
        return None
        
    # 缓存找到的路径
    get_cursor_app_path.cursor_exe = cursor_exe
    return os.path.dirname(cursor_exe)


async def get_cursor_paths() -> Tuple[str, str]:
    """
    根据不同操作系统获取 Cursor 相关路径

    Returns:
        Tuple[str, str]: (package.json路径, main.js路径)的元组

    Raises:
        OSError: 当找不到有效路径或系统不支持时抛出
    """
    # 使用缓存的路径（如果存在）
    if hasattr(get_cursor_paths, 'cached_paths'):
        return get_cursor_paths.cached_paths
        
    system = platform.system()
    logger.info(f"当前操作系统: {system}")
    
    if system == "Windows":
        # 首先尝试查找实际安装路径
        app_path = await get_cursor_app_path()
        if app_path:
            resources_path = os.path.join(app_path, "resources", "app")
            if os.path.exists(resources_path):
                pkg_path = os.path.join(resources_path, "package.json")
                main_path = os.path.join(resources_path, "out", "main.js")
                # 缓存找到的路径
                get_cursor_paths.cached_paths = (pkg_path, main_path)
                return get_cursor_paths.cached_paths
            else:
                logger.warning(f"resources/app 目录不存在: {resources_path}")
        
        # 如果找不到，使用默认路径
        logger.info("使用默认安装路径...")
        base = os.path.join(os.getenv("LOCALAPPDATA", ""), "Programs", "Cursor", "resources", "app")
        pkg_path = os.path.join(base, "package.json")
        main_path = os.path.join(base, "out", "main.js")
        # 缓存找到的路径
        get_cursor_paths.cached_paths = (pkg_path, main_path)
        return get_cursor_paths.cached_paths

    paths_map = {
        "Darwin": {
            "base": "/Applications/Cursor.app/Contents/Resources/app",
            "package": "package.json",
            "main": "out/main.js"
        },
        "Linux": {
            "bases": ["/opt/Cursor/resources/app", "/usr/share/cursor/resources/app"],
            "package": "package.json",
            "main": "out/main.js"
        }
    }

    if system not in paths_map:
        error_msg = f"不支持的操作系统: {system}"
        logger.error(error_msg)
        raise OSError(error_msg)

    if system == "Linux":
        logger.info("在 Linux 系统中搜索 Cursor 安装路径...")
        for base in paths_map["Linux"]["bases"]:
            pkg_path = os.path.join(base, paths_map["Linux"]["package"])
            if os.path.exists(pkg_path):
                main_path = os.path.join(base, paths_map["Linux"]["main"])
                # 缓存找到的路径
                get_cursor_paths.cached_paths = (pkg_path, main_path)
                return get_cursor_paths.cached_paths
        error_msg = "在 Linux 系统上未找到 Cursor 安装路径"
        logger.error(error_msg)
        raise OSError(error_msg)

    base_path = paths_map[system]["base"]
    pkg_path = os.path.join(base_path, paths_map[system]["package"])
    main_path = os.path.join(base_path, paths_map[system]["main"])
    # 缓存找到的路径
    get_cursor_paths.cached_paths = (pkg_path, main_path)
    return get_cursor_paths.cached_paths


def check_system_requirements(pkg_path: str, main_path: str) -> bool:
    """
    检查系统要求

    Args:
        pkg_path: package.json 文件路径
        main_path: main.js 文件路径

    Returns:
        bool: 检查是否通过
    """
    for file_path in [pkg_path, main_path]:
        if not os.path.isfile(file_path):
            logger.error(f"文件不存在: {file_path}")
            return False

        if not os.access(file_path, os.W_OK):
            logger.error(f"没有文件写入权限: {file_path}")
            return False

    return True


def version_check(version: str, min_version: str = "", max_version: str = "") -> bool:
    """
    版本号检查

    Args:
        version: 当前版本号
        min_version: 最小版本号要求
        max_version: 最大版本号要求

    Returns:
        bool: 版本号是否符合要求
    """
    version_pattern = r"^\d+\.\d+\.\d+$"
    try:
        if not re.match(version_pattern, version):
            logger.error(f"无效的版本号格式: {version}")
            return False

        def parse_version(ver: str) -> Tuple[int, ...]:
            return tuple(map(int, ver.split(".")))

        current = parse_version(version)

        if min_version and current < parse_version(min_version):
            logger.error(f"版本号 {version} 小于最小要求 {min_version}")
            return False

        if max_version and current > parse_version(max_version):
            logger.error(f"版本号 {version} 大于最大要求 {max_version}")
            return False

        return True

    except Exception as e:
        logger.error(f"版本检查失败: {str(e)}")
        return False


async def modify_main_js(main_path: str) -> bool:
    """
    异步修改 main.js 文件

    Args:
        main_path: main.js 文件路径

    Returns:
        bool: 修改是否成功
    """
    try:
        # 获取原始文件的权限和所有者信息
        original_stat = await aiofiles.os.stat(main_path)
        original_mode = original_stat.st_mode
        original_uid = original_stat.st_uid
        original_gid = original_stat.st_gid

        tmp_path = None
        async with aiofiles.tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
            async with aiofiles.open(main_path, "r", encoding="utf-8") as main_file:
                content = await main_file.read()

            # 执行替换
            patterns = {
                r"async getMachineId\(\)\{return [^??]+\?\?([^}]+)\}": r"async getMachineId(){return \1}",
                r"async getMacMachineId\(\)\{return [^??]+\?\?([^}]+)\}": r"async getMacMachineId(){return \1}"
            }

            for pattern, replacement in patterns.items():
                content = re.sub(pattern, replacement, content)

            await tmp_file.write(content)
            tmp_path = tmp_file.name

        # 使用 shutil.move 移动文件
        shutil.move(tmp_path, main_path)

        # 恢复原始文件的权限和所有者
        os.chmod(main_path, original_mode)  # 使用同步的 os.chmod
        if os.name != 'nt':  # 在非Windows系统上设置所有者
            os.chown(main_path, original_uid, original_gid)

        logger.info("main.js文件修改成功")
        return True

    except Exception as e:
        logger.error(f"修改文件时发生错误: {str(e)}")
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return False


def backup_files(pkg_path: str, main_path: str) -> bool:
    """
    备份原始文件

    Args:
        pkg_path: package.json 文件路径（未使用）
        main_path: main.js 文件路径

    Returns:
        bool: 备份是否成功
    """
    try:
        # 只备份 main.js
        backup_main = f"{main_path}.bak"
        if os.path.exists(backup_main):
            logger.info(f"main.js已存在备份文件，跳过备份步骤")
            return True
            
        if os.path.exists(main_path):
            shutil.copy2(main_path, backup_main)
            logger.info(f"已备份 main.js: {backup_main}")

        return True
    except Exception as e:
        logger.error(f"备份文件失败: {str(e)}")
        return False


def restore_backup_files(pkg_path: str, main_path: str) -> bool:
    """
    恢复备份文件

    Args:
        pkg_path: package.json 文件路径（未使用）
        main_path: main.js 文件路径

    Returns:
        bool: 恢复是否成功
    """
    try:
        # 只恢复 main.js
        backup_main = f"{main_path}.bak"
        if os.path.exists(backup_main):
            shutil.copy2(backup_main, main_path)
            logger.info(f"已恢复 main.js")
            return True

        logger.error("未找到备份文件")
        return False
    except Exception as e:
        logger.error(f"恢复备份失败: {str(e)}")
        return False


async def main(restore_mode=False) -> None:
    """
    主函数

    Args:
        restore_mode: 是否为恢复模式
    """
    try:
        # 获取路径
        pkg_path, main_path = await get_cursor_paths()

        # 检查系统要求
        if not check_system_requirements(pkg_path, main_path):
            sys.exit(1)

        if restore_mode:
            # 恢复备份
            if restore_backup_files(pkg_path, main_path):
                logger.info("备份恢复完成")
            else:
                logger.error("备份恢复失败")
            return

        # 获取版本号
        try:
            with open(pkg_path, "r", encoding="utf-8") as f:
                version = json.load(f)["version"]
        except Exception as e:
            logger.error(f"无法读取版本号: {str(e)}")
            sys.exit(1)

        # 检查版本
        if not version_check(version, min_version="0.45.0"):
            logger.error("版本不符合要求（需 >= 0.45.x）")
            sys.exit(1)

        logger.info("版本检查通过，准备修改文件")

        # 备份文件
        if not backup_files(pkg_path, main_path):
            logger.error("文件备份失败，终止操作")
            sys.exit(1)

        # 修改文件
        if not await modify_main_js(main_path):
            sys.exit(1)


    except Exception as e:
        logger.error(f"执行过程中发生错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
