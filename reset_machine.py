import hashlib
import json
import os
import sys
import uuid
import asyncio
import logging

from colorama import Fore, Style, init

import patch_cursor_get_machine_id 

# 初始化colorama
init()

# 定义emoji和颜色常量
EMOJI = {
    "FILE": "📄",
    "BACKUP": "💾",
    "SUCCESS": "✅",
    "ERROR": "❌",
    "INFO": "ℹ️",
    "RESET": "🔄",
}


class MachineIDResetter:
    def __init__(self):
        # 判断操作系统
        if sys.platform == "win32":  # Windows
            appdata = os.getenv("APPDATA")
            if appdata is None:
                raise EnvironmentError("APPDATA 环境变量未设置")
            self.db_path = os.path.join(
                appdata, "Cursor", "User", "globalStorage", "storage.json"
            )
        elif sys.platform == "darwin":  # macOS
            self.db_path = os.path.abspath(
                os.path.expanduser(
                    "~/Library/Application Support/Cursor/User/globalStorage/storage.json"
                )
            )
        elif sys.platform == "linux":  # Linux 和其他类Unix系统
            self.db_path = os.path.abspath(
                os.path.expanduser("~/.config/Cursor/User/globalStorage/storage.json")
            )
        else:
            raise NotImplementedError(f"不支持的操作系统: {sys.platform}")

    def generate_new_ids(self):
        """生成新的机器ID"""
        # 生成新的UUID
        dev_device_id = str(uuid.uuid4())

        # 生成新的machineId (64个字符的十六进制)
        machine_id = hashlib.sha256(os.urandom(32)).hexdigest()

        # 生成新的macMachineId (128个字符的十六进制)
        mac_machine_id = hashlib.sha512(os.urandom(64)).hexdigest()

        # 生成新的sqmId
        sqm_id = "{" + str(uuid.uuid4()).upper() + "}"

        return {
            "telemetry.devDeviceId": dev_device_id,
            "telemetry.macMachineId": mac_machine_id,
            "telemetry.machineId": machine_id,
            "telemetry.sqmId": sqm_id,
        }

    async def reset_machine_ids(self):
        """重置机器ID并备份原始文件"""
        try:
            pkg_path, _ = await patch_cursor_get_machine_id.get_cursor_paths()
            
            # 获取版本号
            try:
                with open(pkg_path, "r", encoding="utf-8") as f:
                    version = json.load(f)["version"]
                    logging.info(f"当前 Cursor 版本: {version}")
            except Exception as e:
                sys.exit(1)
            
            is_045_version = patch_cursor_get_machine_id.version_check(version, min_version="0.45.0")

            # 检查文件是否存在
            if not os.path.exists(self.db_path):
                logging.info(f"配置文件不存在: {self.db_path}")
                return False

            # 检查文件权限
            if not os.access(self.db_path, os.R_OK | os.W_OK):
                logging.info(f"无法读写配置文件，请检查文件权限！")
                logging.info(f"如果你使用过 go-cursor-help 来修改 ID; 请修改文件只读权限 {self.db_path} ")
                return False

            # 读取现有配置
            with open(self.db_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            # 只在备份文件不存在时创建备份
            backup_path = f"{self.db_path}.backup"
            if not os.path.exists(backup_path):
                with open(backup_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=4)

            # 生成新的ID
            new_ids = self.generate_new_ids()

            # 更新配置
            config.update(new_ids)

            # 保存新配置
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)

            # 在所有操作完成后，按顺序打印日志
            logging.info(f"正在检查配置文件...")
            logging.info(f"读取当前配置...")
            if not os.path.exists(backup_path):
                logging.info(f"创建配置文件备份...")
                logging.info(f"备份文件已保存至: {backup_path}")
            else:
                logging.info(f"storage.json已存在备份文件，跳过备份步骤")
            logging.info(f"生成新的机器标识...")
            logging.info(f"保存新配置...")
            logging.info(f"机器标识重置成功！")

            if is_045_version:
                await patch_cursor_get_machine_id.main(restore_mode=False)
            return True

        except PermissionError as e:
            logging.info(f"权限错误: {str(e)}")
            logging.info(f"请尝试以管理员身份运行此程序")
            return False
        except Exception as e:
            logging.info(f"重置过程出错: {str(e)}")
            return False

    async def restore_machine_ids(self):
        """从备份文件恢复机器ID"""
        try:
            pkg_path, _ = await patch_cursor_get_machine_id.get_cursor_paths()
            # 获取版本号
            try:
                with open(pkg_path, "r", encoding="utf-8") as f:
                    version = json.load(f)["version"]
            except Exception as e:
                sys.exit(1)
            
            is_045_version = patch_cursor_get_machine_id.version_check(version, min_version="0.45.0")
            backup_path = f"{self.db_path}.backup"

            # 检查备份文件是否存在
            if not os.path.exists(backup_path):
                logging.info(f"备份文件不存在: {backup_path}")
                return False

            # 检查备份文件权限
            if not os.access(backup_path, os.R_OK):
                logging.info(f"无法读取备份文件，请检查文件权限！")
                return False

            # 读取备份配置
            logging.info(f"读取备份配置...")
            with open(backup_path, "r", encoding="utf-8") as f:
                backup_config = json.load(f)

            # 检查原始文件权限
            if not os.access(self.db_path, os.W_OK):
                logging.info(f"无法写入配置文件，请检查文件权限！")
                return False

            # 恢复配置
            logging.info(f"正在恢复配置...")
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(backup_config, f, indent=4)

            logging.info(f"{Fore.GREEN}{EMOJI['SUCCESS']} 机器标识已恢复！")

            if is_045_version:
                await patch_cursor_get_machine_id.main(restore_mode=True)
                
            return True
            
        except json.JSONDecodeError:
            logging.info(f"备份文件格式错误")
            return False
        except Exception as e:
            logging.info(f"恢复过程出错: {str(e)}")
            return False


if __name__ == "__main__":
    logging.info(f"\n{'=' * 50}")
    logging.info(f"Cursor 机器标识重置工具")
    logging.info(f"{'=' * 50}")

    resetter = MachineIDResetter()
    
    # 添加命令行参数支持并使用事件循环运行异步函数
    if len(sys.argv) > 1 and sys.argv[1] == '--restore':
        asyncio.run(resetter.restore_machine_ids())
    else:
        asyncio.run(resetter.reset_machine_ids())

    logging.info(f"\n{'=' * 50}")
    input(f"按回车键退出...")
