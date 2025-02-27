#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cursor 应用程序补丁工具 - 优化版本
该脚本用于修改 Cursor 应用程序的 getMachineId 函数行为
"""

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
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any, Union, Callable
import asyncio
import aiofiles
import aiofiles.os
import aiofiles.tempfile
from contextlib import contextmanager

# 仅在 Windows 系统上导入 winreg
if platform.system() == "Windows":
    import winreg


class CursorPatcher:
    """Cursor 应用程序补丁工具类"""
    
    def __init__(self, log_level: int = logging.INFO):
        """
        初始化补丁工具
        
        Args:
            log_level: 日志级别，默认为 INFO
        """
        self.logger = self._setup_logging(log_level)
        self.system = platform.system()
        self._cursor_exe_path: Optional[str] = None
        self._package_json_path: Optional[str] = None
        self._main_js_path: Optional[str] = None

    def _setup_logging(self, log_level: int) -> logging.Logger:
        """
        配置并返回日志记录器
        
        Args:
            log_level: 日志级别
            
        Returns:
            logging.Logger: 配置好的日志记录器
        """
        logger = logging.getLogger("cursor_patcher")
        
        # 清除所有已存在的处理器
        logger.handlers.clear()
        
        # 防止日志重复
        logger.propagate = False
        
        # 设置日志级别
        logger.setLevel(log_level)
        
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger

    @contextmanager
    def _error_handler(self, operation: str, exit_on_error: bool = False):
        """
        错误处理上下文管理器
        
        Args:
            operation: 操作名称
            exit_on_error: 错误时是否退出程序
        """
        try:
            yield
        except Exception as e:
            self.logger.error(f"{operation}失败: {str(e)}")
            if exit_on_error:
                sys.exit(1)
            raise

    async def _get_windows_registry_install_location(self) -> Optional[str]:
        """
        从 Windows 注册表中查找 Cursor 的安装位置
        
        Returns:
            Optional[str]: Cursor.exe 的路径，未找到则返回 None
        """
        if self.system != "Windows":
            return None
            
        self.logger.debug("开始从注册表查找 Cursor 安装位置...")
        registry_paths = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{DADADADA-ADAD-ADAD-ADAD-ADADADADADAD}}_is1"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\62625861-8486-5be9-9e46-1da50df5f8ff")
        ]

        for hkey, path in registry_paths:
            try:
                with winreg.OpenKey(hkey, path) as key:
                    try:
                        cursor_exe = winreg.QueryValueEx(key, "DisplayIcon")[0]
                        if cursor_exe and os.path.isfile(cursor_exe):
                            self.logger.info(f"从注册表找到 Cursor 安装位置: {cursor_exe}")
                            return cursor_exe
                    except WindowsError:
                        continue
            except WindowsError:
                continue
        
        return None

    def _get_cursor_process_path(self) -> Optional[str]:
        """
        通过进程查找正在运行的 Cursor
        
        Returns:
            Optional[str]: Cursor 进程的路径，未找到则返回 None
        """
        try:
            for proc in psutil.process_iter(['name', 'exe']):
                try:
                    proc_name = proc.info['name'].lower()
                    if proc_name == 'cursor.exe' or proc_name == 'cursor':
                        exe_path = proc.info['exe']
                        self.logger.info(f"从运行进程找到 Cursor: {exe_path}")
                        return exe_path
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as e:
            self.logger.debug(f"查找进程时出错: {str(e)}")
        return None

    def _get_windows_drives(self) -> List[str]:
        """
        获取 Windows 系统的所有驱动器
        
        Returns:
            List[str]: 驱动器列表
        """
        import string
        from ctypes import windll
        
        drives = []
        bitmask = windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drives.append(f"{letter}:")
            bitmask >>= 1
        return drives

    async def _find_cursor_exe_windows(self) -> Optional[str]:
        """
        在 Windows 系统上查找 Cursor.exe
        
        Returns:
            Optional[str]: Cursor.exe 的路径，未找到则返回 None
        """
        # 1. 从注册表查找
        cursor_exe = await self._get_windows_registry_install_location()
        if cursor_exe:
            return cursor_exe
            
        # 2. 从运行进程中查找
        cursor_exe = self._get_cursor_process_path()
        if cursor_exe:
            return cursor_exe

        # 3. 检查环境变量定义的路径
        env_paths = [
            Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "Cursor",
            Path(os.getenv("PROGRAMFILES", "")) / "Cursor",
            Path(os.getenv("PROGRAMFILES(X86)", "")) / "Cursor",
            Path(os.getenv("APPDATA", "")) / "Programs" / "Cursor",
            Path(os.getenv("USERPROFILE", "")) / "AppData" / "Local" / "Programs" / "Cursor"
        ]
        
        self.logger.info("检查环境变量定义的路径...")
        for base_path in env_paths:
            if base_path.exists():
                cursor_path = base_path / "Cursor.exe"
                if cursor_path.is_file():
                    self.logger.info(f"找到 Cursor.exe: {cursor_path}")
                    return str(cursor_path)
        
        # 4. 检查所有驱动器下的常见安装位置
        common_install_dirs = [
            "Cursor",
            os.path.join("Program Files", "Cursor"),
            os.path.join("Program Files (x86)", "Cursor"),
            os.path.join("Users", os.getenv("USERNAME", ""), "AppData", "Local", "Programs", "Cursor")
        ]
        
        for drive in self._get_windows_drives():
            for install_dir in common_install_dirs:
                full_path = Path(drive) / install_dir / "Cursor.exe"
                if full_path.is_file():
                    self.logger.info(f"找到 Cursor.exe: {full_path}")
                    return str(full_path)
        
        # 5. 检查环境变量PATH中的所有目录
        if "PATH" in os.environ:
            for path_dir in os.environ["PATH"].split(os.pathsep):
                location = Path(path_dir) / "Cursor.exe"
                if location.is_file():
                    self.logger.info(f"在 PATH 中找到 Cursor.exe: {location}")
                    return str(location)
        
        # 6. 使用where命令
        try:
            import subprocess
            result = subprocess.run(["where", "Cursor.exe"], 
                                  capture_output=True, 
                                  text=True, 
                                  check=False)
            if result.returncode == 0:
                paths = result.stdout.strip().split('\n')
                if paths:
                    self.logger.info(f"使用 where 命令找到 Cursor.exe: {paths[0]}")
                    return paths[0]
        except Exception as e:
            self.logger.debug(f"使用 where 命令搜索失败: {str(e)}")
            
        return None

    async def _find_cursor_exe_macos(self) -> Optional[str]:
        """
        在 macOS 系统上查找 Cursor
        
        Returns:
            Optional[str]: Cursor 的路径，未找到则返回 None
        """
        # 在 macOS 上查找 Cursor.app
        common_paths = [
            "/Applications/Cursor.app/Contents/MacOS/Cursor",
            os.path.expanduser("~/Applications/Cursor.app/Contents/MacOS/Cursor")
        ]
        
        for path in common_paths:
            if os.path.isfile(path):
                self.logger.info(f"在 macOS 上找到 Cursor: {path}")
                return path
                
        # 从运行进程中查找
        cursor_exe = self._get_cursor_process_path()
        if cursor_exe:
            return cursor_exe
            
        return None

    async def _find_cursor_exe_linux(self) -> Optional[str]:
        """
        在 Linux 系统上查找 Cursor
        
        Returns:
            Optional[str]: Cursor 的路径，未找到则返回 None
        """
        # 在 Linux 上查找 Cursor
        common_paths = [
            "/usr/bin/cursor",
            "/usr/local/bin/cursor",
            "/opt/Cursor/cursor",
            "/usr/share/cursor/cursor"
        ]
        
        for path in common_paths:
            if os.path.isfile(path):
                self.logger.info(f"在 Linux 上找到 Cursor: {path}")
                return path
                
        # 从运行进程中查找
        cursor_exe = self._get_cursor_process_path()
        if cursor_exe:
            return cursor_exe
            
        return None

    async def find_cursor_exe(self) -> Optional[str]:
        """
        查找 Cursor 可执行文件
        
        Returns:
            Optional[str]: Cursor 可执行文件的路径，未找到则返回 None
        """
        # 使用缓存的路径（如果存在）
        if self._cursor_exe_path:
            return self._cursor_exe_path
            
        self.logger.info("开始搜索 Cursor 可执行文件...")
        
        # 根据不同操作系统使用不同的查找方法
        finder_map = {
            "Windows": self._find_cursor_exe_windows,
            "Darwin": self._find_cursor_exe_macos,
            "Linux": self._find_cursor_exe_linux
        }
        
        finder = finder_map.get(self.system)
        if not finder:
            self.logger.error(f"不支持的操作系统: {self.system}")
            return None
            
        cursor_exe = await finder()
        
        # 如果自动查找失败，提示用户手动输入
        if not cursor_exe:
            self.logger.warning(f"未找到 Cursor 可执行文件，请手动输入完整路径")
            time.sleep(1)
            user_path = input("请输入Cursor可执行文件的完整路径: ").strip()
            if os.path.isfile(user_path):
                cursor_exe = user_path
                self.logger.info(f"使用用户提供的路径: {user_path}")
        
        # 缓存找到的路径
        if cursor_exe:
            self._cursor_exe_path = cursor_exe
            
        return cursor_exe

    async def get_cursor_app_path(self) -> Optional[str]:
        """
        获取 Cursor 应用程序的安装根目录
        
        Returns:
            Optional[str]: Cursor 应用程序的安装根目录，未找到则返回 None
        """
        cursor_exe = await self.find_cursor_exe()
        if not cursor_exe:
            return None
            
        return os.path.dirname(cursor_exe)

    async def get_cursor_paths(self) -> Tuple[Optional[str], Optional[str]]:
        """
        获取 Cursor 应用程序的关键文件路径
        
        Returns:
            Tuple[Optional[str], Optional[str]]: (package.json 路径, main.js 路径) 的元组
        """
        # 使用缓存的路径（如果存在）
        if self._package_json_path and self._main_js_path:
            return self._package_json_path, self._main_js_path
            
        self.logger.info(f"获取 Cursor 关键文件路径...")
        
        path_finders = {
            "Windows": self._get_windows_paths,
            "Darwin": self._get_macos_paths,
            "Linux": self._get_linux_paths
        }
        
        finder = path_finders.get(self.system)
        if not finder:
            self.logger.error(f"不支持的操作系统: {self.system}")
            return None, None
            
        pkg_path, main_path = await finder()
        
        # 缓存找到的路径
        if pkg_path and main_path:
            self._package_json_path = pkg_path
            self._main_js_path = main_path
            
        return pkg_path, main_path

    async def _get_windows_paths(self) -> Tuple[Optional[str], Optional[str]]:
        """
        获取 Windows 系统上的 Cursor 关键文件路径
        
        Returns:
            Tuple[Optional[str], Optional[str]]: (package.json 路径, main.js 路径) 的元组
        """
        # 首先尝试查找实际安装路径
        app_path = await self.get_cursor_app_path()
        if app_path:
            resources_path = os.path.join(app_path, "resources", "app")
            if os.path.exists(resources_path):
                pkg_path = os.path.join(resources_path, "package.json")
                main_path = os.path.join(resources_path, "out", "main.js")
                if os.path.isfile(pkg_path) and os.path.isfile(main_path):
                    return pkg_path, main_path
        
        # 如果找不到，使用默认路径
        base = os.path.join(os.getenv("LOCALAPPDATA", ""), "Programs", "Cursor", "resources", "app")
        pkg_path = os.path.join(base, "package.json")
        main_path = os.path.join(base, "out", "main.js")
        
        return pkg_path, main_path

    async def _get_macos_paths(self) -> Tuple[Optional[str], Optional[str]]:
        """
        获取 macOS 系统上的 Cursor 关键文件路径
        
        Returns:
            Tuple[Optional[str], Optional[str]]: (package.json 路径, main.js 路径) 的元组
        """
        base_path = "/Applications/Cursor.app/Contents/Resources/app"
        pkg_path = os.path.join(base_path, "package.json")
        main_path = os.path.join(base_path, "out", "main.js")
        
        return pkg_path, main_path

    async def _get_linux_paths(self) -> Tuple[Optional[str], Optional[str]]:
        """
        获取 Linux 系统上的 Cursor 关键文件路径
        
        Returns:
            Tuple[Optional[str], Optional[str]]: (package.json 路径, main.js 路径) 的元组
        """
        bases = ["/opt/Cursor/resources/app", "/usr/share/cursor/resources/app"]
        
        for base in bases:
            pkg_path = os.path.join(base, "package.json")
            if os.path.exists(pkg_path):
                main_path = os.path.join(base, "out", "main.js")
                return pkg_path, main_path
                
        return None, None

    def check_system_requirements(self, pkg_path: str, main_path: str) -> bool:
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
                self.logger.error(f"文件不存在: {file_path}")
                return False

            if not os.access(file_path, os.W_OK):
                self.logger.error(f"没有文件写入权限: {file_path}")
                return False

        return True

    def check_version(self, version: str, min_version: str = "", max_version: str = "") -> bool:
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
        
        with self._error_handler("版本检查"):
            if not re.match(version_pattern, version):
                self.logger.error(f"无效的版本号格式: {version}")
                return False

            def parse_version(ver: str) -> Tuple[int, ...]:
                return tuple(map(int, ver.split(".")))

            current = parse_version(version)

            if min_version and current < parse_version(min_version):
                self.logger.error(f"版本号 {version} 小于最小要求 {min_version}")
                return False

            if max_version and current > parse_version(max_version):
                self.logger.error(f"版本号 {version} 大于最大要求 {max_version}")
                return False

            return True

    def backup_files(self, main_path: str) -> bool:
        """
        备份原始文件
        
        Args:
            main_path: main.js 文件路径
            
        Returns:
            bool: 备份是否成功
        """
        try:
            # 只备份 main.js
            backup_main = f"{main_path}.bak"
            if os.path.exists(backup_main):
                self.logger.info(f"main.js已存在备份文件，跳过备份步骤")
                return True
                
            if os.path.exists(main_path):
                shutil.copy2(main_path, backup_main)
                self.logger.info(f"已备份 main.js: {backup_main}")

            return True
        except Exception as e:
            self.logger.error(f"备份文件失败: {str(e)}")
            return False

    def restore_backup_files(self, main_path: str) -> bool:
        """
        恢复备份文件
        
        Args:
            main_path: main.js 文件路径
            
        Returns:
            bool: 恢复是否成功
        """
        try:
            # 只恢复 main.js
            backup_main = f"{main_path}.bak"
            if os.path.exists(backup_main):
                shutil.copy2(backup_main, main_path)
                self.logger.info(f"已恢复 main.js")
                return True

            self.logger.error("未找到备份文件")
            return False
        except Exception as e:
            self.logger.error(f"恢复备份失败: {str(e)}")
            return False

    async def modify_main_js(self, main_path: str) -> bool:
        """
        修改 main.js 文件
        
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

            # 创建临时文件
            async with aiofiles.tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
                # 读取原始文件内容
                async with aiofiles.open(main_path, "r", encoding="utf-8") as main_file:
                    content = await main_file.read()

                # 执行替换
                patterns = {
                    r"async getMachineId\(\)\{return [^??]+\?\?([^}]+)\}": r"async getMachineId(){return \1}",
                    r"async getMacMachineId\(\)\{return [^??]+\?\?([^}]+)\}": r"async getMacMachineId(){return \1}"
                }

                modified = False
                for pattern, replacement in patterns.items():
                    new_content = re.sub(pattern, replacement, content)
                    if new_content != content:
                        content = new_content
                        modified = True

                if not modified:
                    self.logger.warning("未找到需要修改的模式，文件保持不变")
                    return False

                # 写入修改后的内容到临时文件
                await tmp_file.write(content)
                tmp_path = tmp_file.name

            # 使用 shutil.move 移动文件
            shutil.move(tmp_path, main_path)

            # 恢复原始文件的权限和所有者
            os.chmod(main_path, original_mode)
            if os.name != 'nt':  # 在非Windows系统上设置所有者
                os.chown(main_path, original_uid, original_gid)

            self.logger.info("main.js文件修改成功")
            return True

        except Exception as e:
            self.logger.error(f"修改文件时发生错误: {str(e)}")
            return False

    async def get_version(self, pkg_path: str) -> Optional[str]:
        """
        从 package.json 文件中获取版本号
        
        Args:
            pkg_path: package.json 文件路径
            
        Returns:
            Optional[str]: 版本号，获取失败则返回 None
        """
        try:
            async with aiofiles.open(pkg_path, "r", encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)
                return data.get("version")
        except Exception as e:
            self.logger.error(f"获取版本号失败: {str(e)}")
            return None

    async def patch(self) -> bool:
        """
        应用补丁
        
        Returns:
            bool: 是否成功应用补丁
        """
        try:
            # 获取路径
            pkg_path, main_path = await self.get_cursor_paths()
            if not pkg_path or not main_path:
                self.logger.error("无法获取 Cursor 文件路径")
                return False

            # 检查系统要求
            if not self.check_system_requirements(pkg_path, main_path):
                self.logger.error("系统要求检查失败")
                return False

            # 获取版本号
            version = await self.get_version(pkg_path)
            if not version:
                self.logger.error("无法获取版本号")
                return False

            # 检查版本
            if not self.check_version(version, min_version="0.45.0"):
                self.logger.error("版本不符合要求（需 >= 0.45.0）")
                return False

            self.logger.info(f"Cursor 版本 {version} 检查通过，准备修改文件")

            # 备份文件
            if not self.backup_files(main_path):
                self.logger.error("文件备份失败，终止操作")
                return False

            # 修改文件
            if not await self.modify_main_js(main_path):
                self.logger.error("修改文件失败")
                return False

            self.logger.info("补丁应用成功！")
            return True

        except Exception as e:
            self.logger.error(f"应用补丁失败: {str(e)}")
            return False

    async def restore(self) -> bool:
        """
        恢复原始文件
        
        Returns:
            bool: 是否成功恢复
        """
        try:
            # 获取路径
            pkg_path, main_path = await self.get_cursor_paths()
            if not pkg_path or not main_path:
                self.logger.error("无法获取 Cursor 文件路径")
                return False

            # 恢复备份
            if not self.restore_backup_files(main_path):
                self.logger.error("恢复备份失败")
                return False

            self.logger.info("备份恢复完成")
            return True

        except Exception as e:
            self.logger.error(f"恢复原始文件失败: {str(e)}")
            return False


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Cursor 应用程序补丁工具")
    parser.add_argument("--restore", action="store_true", help="恢复原始文件")
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    args = parser.parse_args()
    
    log_level = logging.DEBUG if args.debug else logging.INFO
    patcher = CursorPatcher(log_level=log_level)
    
    if args.restore:
        success = await patcher.restore()
    else:
        success = await patcher.patch()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main()) 