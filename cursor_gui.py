import asyncio
import logging
import os
import platform
import subprocess
import sys
import threading
import time

from PyQt6.QtCore import QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QPalette, QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QTextEdit, QPushButton, QFrame, QDialog, QGridLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QLineEdit, QSizePolicy
)

from browser_utils import BrowserManager
from cursor_pro_keep_alive import sign_in_account, get_user_agent, get_cursor_session_token, update_cursor_auth, \
    receive_verification_code
from refresh_data import batch_register

# 导入Cursor Pro相关功能
try:
    from cursor_pro_keep_alive import (
        check_version, reset_machine_id, restore_machine_id,
        try_register, batch_register, ExitCursor
    )
    import refresh_data
    from config import Config

    CONFIG_IMPORT_FAILED = False
except ImportError:
    # 开发模式下可能暂时无法导入
    CONFIG_IMPORT_FAILED = True


    # 创建一个本地版本的Config类，与导入的区分开
    class LocalConfig:
        @staticmethod
        def get_version():
            return "开发版"

        @staticmethod
        def get_domain():
            return "example.com"

        @staticmethod
        def get_api_accounts_url():
            return "https://api.example.com/accounts"

        def __init__(self):
            pass


# 创建标准输出/错误流重定向类
class StreamRedirector(QObject):
    text_written = pyqtSignal(str)

    def __init__(self, log_handler):
        super().__init__()
        self.log_handler = log_handler

    def write(self, text):
        if text.strip():  # 忽略空白文本
            self.log_handler.info(text.strip())

    def flush(self):
        pass


# 创建自定义日志处理器
class GUILogHandler(logging.Handler):
    def __init__(self, log_handler):
        super().__init__()
        self.log_handler = log_handler
        self.setFormatter(logging.Formatter('%(message)s'))

    def emit(self, record):
        msg = self.format(record)
        level = record.levelname

        if level == 'ERROR' or level == 'CRITICAL':
            self.log_handler.error(msg)
        elif level == 'WARNING':
            self.log_handler.warning(msg)
        elif level == 'DEBUG':
            self.log_handler.debug(msg)
        else:  # INFO
            self.log_handler.info(msg)


# 自定义日志处理类，将日志重定向到GUI
class LogHandler:
    def __init__(self, log_widget):
        self.log_widget = log_widget
        self.emoji = {"ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️", "DEBUG": "🔍"}

    def info(self, message):
        self.log(f"{self.emoji['INFO']} 信息: {message}")

    def error(self, message):
        self.log(f"{self.emoji['ERROR']} 错误: {message}", error=True)

    def warning(self, message):
        self.log(f"{self.emoji['WARNING']} 警告: {message}", warning=True)

    def debug(self, message):
        self.log(f"{self.emoji['DEBUG']} 调试: {message}", debug=True)

    def log(self, message, error=False, warning=False, debug=False):
        # 使用亮色主题的固定颜色
        color = "#FF0000" if error else "#FF8800" if warning else "#888888" if debug else "#000000"

        # 在GUI中显示日志
        self.log_widget.append(f'<span style="color:{color};">{message}</span>')

        # 确保光标在最后
        cursor = self.log_widget.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_widget.setTextCursor(cursor)

        # 自动滚动到底部
        self.log_widget.verticalScrollBar().setValue(self.log_widget.verticalScrollBar().maximum())

        # 立即处理事件，确保日志立即显示
        QApplication.processEvents()


# 后台任务执行线程
class WorkerThread(QThread):
    update_signal = pyqtSignal(str, str)  # 参数：消息, 类型(info, error, warning)
    finished_signal = pyqtSignal(bool)  # 任务完成信号，参数为成功或失败
    verification_code_signal = pyqtSignal(str)  # 验证码信号

    def __init__(self, task_type, params=None):
        super().__init__()
        self.task_type = task_type
        self.params = params or {}
        # 标记是否已经执行过设备重置
        self.device_reset_done = self.params.get("device_reset_done", False)
        # 存储验证码
        self.verification_code = None
        # 验证码事件
        self.verification_code_event = threading.Event()
        # 保存GUI实例引用
        self.gui_instance = CursorProGUI._instance

    def run(self):
        try:
            # 根据不同任务类型执行不同操作
            if self.task_type == "register":
                self.handle_register()
            elif self.task_type == "reset_device":
                self.handle_reset_device()
            elif self.task_type == "restore_device":
                self.handle_restore_device()
            elif self.task_type == "login":
                self.handle_login()
            elif self.task_type == "replace_account":
                self.handle_replace_account()
            elif self.task_type == "batch_register":
                self.handle_batch_register()
            else:
                self.update_signal.emit(f"未知任务类型: {self.task_type}", "error")
                self.finished_signal.emit(False)
                return

        except Exception as e:
            import traceback
            error_msg = f"执行任务时出错: {str(e)}\n{traceback.format_exc()}"
            self.update_signal.emit(error_msg, "error")
            self.finished_signal.emit(False)

    def handle_register(self):
        self.update_signal.emit("开始注册账号流程...", "info")
        browser_manager, is_success = try_register(is_auto_register=False)
        if browser_manager:
            browser_manager.quit()
        self.finished_signal.emit(is_success)

    def handle_reset_device(self, prepare_for_login=False):
        # 如果已经执行过设备重置，则跳过
        if not self.device_reset_done:
            self.update_signal.emit("开始重置设备信息...", "info")
            # 使用事件循环异步运行
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(reset_machine_id())
            finally:
                loop.close()
            self.update_signal.emit("设备信息重置完成", "info")
            return True
        else:
            self.update_signal.emit("设备已重置，跳过重置步骤", "info")
            return True

    def handle_restore_device(self):
        self.update_signal.emit("开始恢复设备信息...", "info")
        # 使用事件循环异步运行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(restore_machine_id())
        finally:
            loop.close()
        self.update_signal.emit("设备信息恢复完成", "info")
        self.finished_signal.emit(True)

    def handle_replace_account(self):
        self.update_signal.emit("开始替换账号...", "info")
        # 检查是否是macOS并且需要管理员权限
        is_macos_admin = self.params.get("macos_admin", False)
        if is_macos_admin:
            self.update_signal.emit("使用管理员权限在macOS上替换账号...", "info")
            # 针对macOS的特殊处理
            self.handle_macos_replace_account()
        else:
            # 使用普通方式
            refresh_data.replace_account()
        self.update_signal.emit("账号替换完成", "info")
        self.finished_signal.emit(True)

    def handle_login(self):
        browser_manager = BrowserManager()
        try:
            # 获取登录信息
            email = self.params.get("email", "")
            password = self.params.get("password", "")
            login_type = self.params.get("login_type", "password")

            if not email:
                self.update_signal.emit("邮箱不能为空", "error")
                self.finished_signal.emit(False)
                return

                # 获取user_agent
            user_agent = get_user_agent()
            if not user_agent:
                logging.error("获取user agent失败，使用默认值")
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            # 剔除user_agent中的"HeadlessChrome"
            user_agent = user_agent.replace("HeadlessChrome", "Chrome")
            browser = browser_manager.init_browser(user_agent=user_agent, randomize_fingerprint=True)  # 使用有头模式
            tab = browser.latest_tab
            is_success = False

            # 根据登录类型处理不同的登录流程
            if login_type == "password":
                if not password:
                    self.update_signal.emit("密码不能为空", "error")
                    self.finished_signal.emit(False)
                    return

                self.update_signal.emit(f"使用密码登录账号: {email}", "info")
                is_success = sign_in_account(tab, email, password, is_gui=True)

            elif login_type == "code":
                self.update_signal.emit(f"使用验证码登录账号: {email}", "info")
                is_success = sign_in_account(tab, email, None, is_gui=True)

            else:
                self.update_signal.emit(f"不支持的登录类型: {login_type}", "error")
                self.finished_signal.emit(False)
                return

            if is_success:
                self.update_signal.emit("正在获取会话令牌...", "info")
                user_id, token = get_cursor_session_token(tab)
                if token:
                    self.update_signal.emit("更新认证信息...", "info")
                    update_cursor_auth(email=email, access_token=token, refresh_token=token, user_id=user_id)
                else:
                    self.update_signal.emit("获取会话令牌失败...", "error")

            self.finished_signal.emit(True)

        except Exception as e:
            import traceback
            if browser_manager:
                browser_manager.quit()
            error_msg = f"登录过程中出错: {str(e)}\n{traceback.format_exc()}"
            self.update_signal.emit(error_msg, "error")
            self.finished_signal.emit(False)

    def handle_batch_register(self):
        num = self.params.get("num", 1)
        self.update_signal.emit(f"开始批量注册 {num} 个账号...", "info")
        refresh_data.batch_register(num)
        self.finished_signal.emit(True)

    def handle_macos_replace_account(self):
        """使用管理员权限在macOS上处理替换账号操作"""
        import platform
        import os
        import json

        # 确认是macOS系统
        if platform.system() != "Darwin":
            self.update_signal.emit("不是macOS系统，使用普通替换方式", "warning")
            refresh_data.replace_account()
            return

        # 获取account.json路径
        account_path = os.path.expanduser("~/Library/Application Support/Cursor/User/globalStorage/account.json")
        self.update_signal.emit(f"macOS account.json路径: {account_path}", "info")

        # 获取可用账号
        accounts = refresh_data.get_available_accounts()
        if not accounts:
            self.update_signal.emit("没有可用的账号，API可能未配置或无可用账号", "warning")
            return

        self.update_signal.emit(f"获取到 {len(accounts)} 个可用账号", "info")

        # 随机选择一个账号
        import random
        account = random.choice(accounts)
        self.update_signal.emit(f"随机选择账号: {account['email']}", "info")

        # 构建account.json内容
        account_data = {
            "email": account["email"],
            "token": account["refresh_token"],
            "user_id": account["user_id"]
        }

        try:
            # 写入临时文件
            temp_path = "/tmp/cursor_account.json"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(account_data, f, indent=2)

            self.update_signal.emit("已创建临时文件", "info")

            # 使用管理员权限复制文件
            import subprocess
            cmd = ['osascript', '-e',
                   f'do shell script "cp \\"{temp_path}\\" \\"{account_path}\\"" with administrator privileges']

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                self.update_signal.emit("成功使用管理员权限替换account.json文件", "info")

                # 设置文件权限
                chmod_cmd = ['osascript', '-e',
                             f'do shell script "chmod 666 \\"{account_path}\\"" with administrator privileges']
                chmod_result = subprocess.run(chmod_cmd, capture_output=True, text=True)

                if chmod_result.returncode == 0:
                    self.update_signal.emit("成功设置account.json文件权限", "info")
                else:
                    self.update_signal.emit(f"设置权限失败: {chmod_result.stderr}", "warning")

                # 标记账号为已使用
                refresh_data.change_account_info(account["email"])
            else:
                self.update_signal.emit(f"复制文件失败: {result.stderr}", "error")
                return

        except Exception as e:
            import traceback
            self.update_signal.emit(f"处理account.json文件时出错: {str(e)}\n{traceback.format_exc()}", "error")
            return

    def get_verification_code_from_ui(self):
        """等待用户输入验证码"""
        logging.info("等待用户输入验证码...")
        try:
            # 使用信号触发GUI显示验证码输入区域
            self.verification_code_signal.emit("")
            # 等待用户输入
            self.verification_code_event.clear()
            self.verification_code_event.wait()
            logging.info(f"获取到验证码: {self.verification_code}")
            return self.verification_code
        except Exception as e:
            logging.error(f"获取验证码时出错: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return None

    def handle_verification_code(self, code):
        """处理验证码输入"""
        self.verification_code = code
        self.verification_code_event.set()
        receive_verification_code(code)

    def handle_verification_cancelled(self):
        """处理验证码输入取消"""
        logging.info("用户取消了验证码输入")
        self.verification_code = None
        self.verification_code_event.set()


# 配置对话框类
class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("环境配置")
        self.setMinimumSize(600, 400)
        self.env_file_path = '.env'

        # 设置对话框为亮色主题
        self.setStyleSheet("""
            QDialog {
                background-color: #F5F5F5;
                color: #333333;
            }
            QLabel {
                color: #333333;
            }
            QTableWidget {
                background-color: white;
                color: #333333;
                border: 1px solid #DDDDDD;
            }
            QTableWidget::item {
                color: #333333;
            }
            QHeaderView::section {
                background-color: #E0E0E0;
                color: #333333;
                border: 1px solid #DDDDDD;
            }
        """)

        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)

        # 添加信息标签区域（将在需要时显示）
        self.info_area = QVBoxLayout()
        layout.addLayout(self.info_area)

        # 创建.env文件配置表格
        self.env_table = QTableWidget(0, 2)
        self.env_table.setHorizontalHeaderLabels(["配置项", "值"])
        header = self.env_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        # 设置表格可编辑
        self.env_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked |
                                       QTableWidget.EditTrigger.EditKeyPressed)
        layout.addWidget(self.env_table)

        # 加载.env文件配置
        self.loadEnvFileConfig()

        # 添加按钮布局
        button_layout = QHBoxLayout()

        # 保存按钮
        save_button = QPushButton("保存配置")
        save_button.clicked.connect(self.saveEnvConfig)
        save_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        button_layout.addWidget(save_button)

        # 关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

        # 添加操作提示
        tip_label = QLabel("提示: 双击值可以进行编辑，编辑后点击保存")
        tip_label.setStyleSheet("color: #666666; font-style: italic;")
        layout.addWidget(tip_label)

    def loadEnvFileConfig(self):
        """加载.env文件中的配置"""
        self.env_vars = []
        self.original_lines = []

        # 清除之前的信息标签
        self._clearInfoLabels()

        # 定义默认的配置项
        default_configs = [
            "DOMAIN",
            "EMAIL_BASE_URL",
            "EMAIL_API_KEY",
            "API_ACCOUNTS_URL",
            "API_BASE_URL",
            "API_AVAILABLE_ACCOUNTS_URL",
            "API_MARK_USED_URL_PREFIX"
        ]

        # 尝试读取.env文件
        try:
            if os.path.exists(self.env_file_path):
                with open(self.env_file_path, 'r', encoding='utf-8') as file:
                    self.original_lines = file.readlines()
                    for line in self.original_lines:
                        # 保存原始行，包括注释和空行
                        line_stripped = line.strip()
                        if not line_stripped or line_stripped.startswith('#'):
                            continue

                        # 分割键值对
                        if '=' in line_stripped:
                            parts = line_stripped.split('=', 1)
                            key = parts[0].strip()
                            # 处理行内注释
                            value_with_comment = parts[1].strip()
                            comment = ""

                            if '#' in value_with_comment and not value_with_comment.startswith(("'", '"')):
                                value_parts = value_with_comment.split('#', 1)
                                value = value_parts[0].strip()
                                comment = "#" + value_parts[1] if len(value_parts) > 1 else ""
                            else:
                                value = value_with_comment

                            # 记录引号情况，以便保存时保持一致
                            quote_type = None
                            if (value.startswith("'") and value.endswith("'")):
                                quote_type = "'"
                                value = value[1:-1]
                            elif (value.startswith('"') and value.endswith('"')):
                                quote_type = '"'
                                value = value[1:-1]

                            # 存储键、值、注释和引号类型
                            self.env_vars.append({
                                "key": key,
                                "value": value,
                                "comment": comment,
                                "quote_type": quote_type
                            })

                            # 从默认配置项中移除已存在的项
                            if key in default_configs:
                                default_configs.remove(key)
            else:
                # 文件不存在，使用提示消息
                self.log_file_not_exist = True
                self.original_lines = []
                info_label = QLabel("文件.env不存在，将在保存时创建")
                info_label.setStyleSheet("color: #ff9800; font-style: italic;")
                self.info_area.addWidget(info_label)
                self.info_labels = [info_label]  # 保存引用以便后续清理

            # 无论文件是否存在，都为每个缺失的默认配置项添加空项
            for key in default_configs:
                self.env_vars.append({
                    "key": key,
                    "value": "",
                    "comment": "",
                    "quote_type": '"'  # 默认使用双引号
                })

        except Exception as e:
            # 发生异常时显示错误但仍显示默认配置项
            error_label = QLabel(f"读取.env文件时出错: {str(e)}")
            error_label.setStyleSheet("color: #f44336; font-style: italic;")
            self.info_area.addWidget(error_label)
            self.info_labels = [error_label]  # 保存引用以便后续清理

            # 出错时也显示默认配置项
            for key in default_configs:
                self.env_vars.append({
                    "key": key,
                    "value": "",
                    "comment": "",
                    "quote_type": '"'
                })

        # 设置表格行数
        self.env_table.setRowCount(len(self.env_vars))

        # 填充表格
        for i, var in enumerate(self.env_vars):
            self.env_table.setItem(i, 0, QTableWidgetItem(var["key"]))
            self.env_table.setItem(i, 1, QTableWidgetItem(var["value"]))

    def _clearInfoLabels(self):
        """清除信息标签"""
        if hasattr(self, 'info_labels') and self.info_labels:
            for label in self.info_labels:
                self.info_area.removeWidget(label)
                label.deleteLater()
            self.info_labels = []

    def saveEnvConfig(self):
        """保存修改后的配置到.env文件"""
        try:
            # 首先从表格获取最新值
            for i in range(self.env_table.rowCount()):
                key_item = self.env_table.item(i, 0)
                value_item = self.env_table.item(i, 1)

                if key_item and value_item and i < len(self.env_vars):
                    self.env_vars[i]["key"] = key_item.text()
                    self.env_vars[i]["value"] = value_item.text()

            # 检查.env文件是否存在，不存在则创建
            file_exists = os.path.exists(self.env_file_path)

            # 如果文件存在，创建备份
            if file_exists:
                import shutil
                backup_path = f"{self.env_file_path}.bak"
                shutil.copy2(self.env_file_path, backup_path)

                # 更新文件内容
                new_lines = []
                env_var_index = 0

                # 遍历原始行，保留注释和格式
                for line in self.original_lines:
                    line_stripped = line.strip()
                    if not line_stripped or line_stripped.startswith('#'):
                        new_lines.append(line)  # 保留空行和注释行
                    elif '=' in line_stripped and env_var_index < len(self.env_vars):
                        # 替换为新值
                        var = self.env_vars[env_var_index]
                        key = var["key"]
                        value = var["value"]
                        comment = var["comment"]
                        quote_type = var["quote_type"]

                        # 如果原来有引号，继续使用相同的引号
                        if quote_type:
                            formatted_value = f"{quote_type}{value}{quote_type}"
                        else:
                            formatted_value = value

                        # 组合新行
                        new_line = f"{key}={formatted_value}"
                        if comment:
                            new_line += f" {comment}"
                        new_line += "\n"

                        new_lines.append(new_line)
                        env_var_index += 1
                    else:
                        new_lines.append(line)  # 保留其他行不变

                # 添加新增的配置项
                for i in range(env_var_index, len(self.env_vars)):
                    var = self.env_vars[i]
                    key = var["key"]
                    value = var["value"]
                    comment = var["comment"]
                    quote_type = var["quote_type"]

                    # 使用引号格式化值
                    if quote_type:
                        formatted_value = f"{quote_type}{value}{quote_type}"
                    else:
                        formatted_value = value

                    # 组合新行
                    new_line = f"{key}={formatted_value}"
                    if comment:
                        new_line += f" {comment}"
                    new_line += "\n"

                    new_lines.append(new_line)
            else:
                # 文件不存在，创建新的.env文件内容
                new_lines = []

                # 添加文件头注释
                new_lines.append("# Cursor Pro 环境配置文件\n")
                new_lines.append("# 创建时间: " + time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
                new_lines.append("\n")

                # 添加所有配置项
                for var in self.env_vars:
                    key = var["key"]
                    value = var["value"]
                    comment = var["comment"]
                    quote_type = var["quote_type"] or '"'  # 默认使用双引号

                    # 使用引号格式化值
                    formatted_value = f"{quote_type}{value}{quote_type}"

                    # 组合新行
                    new_line = f"{key}={formatted_value}"
                    if comment:
                        new_line += f" {comment}"
                    new_line += "\n"

                    new_lines.append(new_line)

            # 写入文件
            with open(self.env_file_path, 'w', encoding='utf-8') as file:
                file.writelines(new_lines)

            # 强制刷新缓存，确保文件内容立即写入磁盘
            try:
                # 在macOS上使用fsync确保文件写入磁盘
                # import os  # 已经在文件顶部导入了，这里不需要再导入
                fd = os.open(self.env_file_path, os.O_RDONLY)
                os.fsync(fd)
                os.close(fd)
            except Exception as fsync_error:
                logging.debug(f"同步文件到磁盘失败: {str(fsync_error)}")
                pass

            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "保存成功", f"配置已成功保存到{self.env_file_path}文件")

            # 清除信息标签并重新加载配置
            self._clearInfoLabels()
            
            # 完全重新加载配置
            self.env_vars = []
            self.original_lines = []
            self.loadEnvFileConfig()

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()

            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "保存失败", f"保存配置时出错: {str(e)}\n\n{error_details}")


# 登录对话框类
class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("登录Cursor账号")
        self.setMinimumSize(400, 250)

        # 设置对话框为亮色主题
        self.setStyleSheet("""
            QDialog {
                background-color: #F5F5F5;
                color: #333333;
            }
            QLabel {
                color: #333333;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: white;
                color: #333333;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)

        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title_label = QLabel("请输入Cursor账号信息")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #333333;")
        layout.addWidget(title_label)

        # 表单布局
        form_layout = QGridLayout()
        form_layout.setSpacing(10)

        # 邮箱输入
        email_label = QLabel("邮箱:")
        email_label.setFont(QFont("Arial", 11))
        self.email_input = QLineEdit()
        self.email_input.setFixedHeight(36)
        self.email_input.setPlaceholderText("输入您的Cursor账号邮箱")
        form_layout.addWidget(email_label, 0, 0)
        form_layout.addWidget(self.email_input, 0, 1)

        # 登录方式选择 - 移到最上方
        login_type_label = QLabel("登录方式:")
        login_type_label.setFont(QFont("Arial", 11))
        self.login_type_combo = QComboBox()
        self.login_type_combo.addItem("密码登录")
        self.login_type_combo.addItem("验证码登录")
        self.login_type_combo.setFixedHeight(36)
        # 修复下拉框文字不可见问题
        self.login_type_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 5px;
                background-color: white;
                color: #333333;
                font-size: 14px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #CCCCCC;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: #333333;
                selection-background-color: #E0E0E0;
                selection-color: #333333;
            }
        """)
        self.login_type_combo.currentIndexChanged.connect(self.toggle_password_visibility)
        # 设置ComboBox填充可用水平空间
        self.login_type_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # 将登录方式放入水平布局使其更美观
        login_type_layout = QHBoxLayout()
        login_type_layout.setContentsMargins(0, 0, 0, 0)
        login_type_layout.setSpacing(10)
        login_type_layout.addWidget(login_type_label)
        login_type_layout.addWidget(self.login_type_combo, 1)  # 加入stretch因子1使其填充剩余空间
        form_layout.addLayout(login_type_layout)

        # 表单布局
        form_layout = QGridLayout()
        form_layout.setSpacing(10)

        # 邮箱输入
        email_label = QLabel("邮箱:")
        email_label.setFont(QFont("Arial", 11))
        self.login_email_input = QLineEdit()
        self.login_email_input.setFixedHeight(36)
        self.login_email_input.setPlaceholderText("输入您的Cursor账号邮箱")
        form_layout.addWidget(email_label, 0, 0)
        form_layout.addWidget(self.login_email_input, 0, 1)

        # 密码输入
        self.login_password_label = QLabel("密码:")
        self.login_password_label.setFont(QFont("Arial", 11))
        self.login_password_label.setStyleSheet("color: #000000;")
        self.login_password_input = QLineEdit()
        self.login_password_input.setFixedHeight(36)
        self.login_password_input.setPlaceholderText("输入您的Cursor账号密码")
        self.login_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addWidget(self.login_password_label, 1, 0)
        form_layout.addWidget(self.login_password_input, 1, 1)

        # 验证码输入区域 - 始终显示，但根据登录方式控制可见性
        self.verification_code_label = QLabel("验证码:")
        self.verification_code_label.setFont(QFont("Arial", 11))
        self.verification_code_label.setStyleSheet("color: #000000;")
        self.verification_code_input = QLineEdit()
        self.verification_code_input.setFixedHeight(36)
        self.verification_code_input.setPlaceholderText("输入收到的验证码")
        self.verification_code_input.textChanged.connect(self.check_verification_code)

        # 修改确定按钮的创建和定位
        self.verification_code_submit = QPushButton("确定")
        self.verification_code_submit.setFixedHeight(36)
        self.verification_code_submit.setFixedWidth(120)  # 设置固定宽度以避免过宽
        self.verification_code_submit.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 5px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        self.verification_code_submit.setVisible(False)
        self.verification_code_submit.clicked.connect(self.submit_verification_code)

        # 创建一个容器用于放置按钮，并控制其对齐方式
        button_panel = QWidget()
        button_panel_layout = QHBoxLayout(button_panel)
        button_panel_layout.setContentsMargins(0, 0, 0, 0)
        button_panel_layout.addStretch(1)  # 添加弹性空间
        button_panel_layout.addWidget(self.verification_code_submit)

        # 将按钮容器添加到表单的第4行第2列
        form_layout.addWidget(button_panel, 3, 1)

        layout.addLayout(form_layout)

        # 按钮布局
        login_button_layout = QHBoxLayout()

        # 登录按钮 - 仅在密码登录时显示
        self.confirm_login_button = QPushButton("登录")
        self.confirm_login_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.confirm_login_button.clicked.connect(self.confirm_login)
        self.confirm_login_button.setVisible(False)  # 默认不显示登录按钮
        login_button_layout.addWidget(self.confirm_login_button)

        layout.addLayout(login_button_layout)

        # 添加登录表单区域到主布局
        left_layout.addWidget(self.login_form_area)

        # 右侧日志面板 - 使用固定颜色
        right_panel = QFrame()
        right_panel.setFrameShape(QFrame.Shape.StyledPanel)
        right_panel.setFrameShadow(QFrame.Shadow.Raised)
        right_panel.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 10px;
                border: 1px solid #dddddd;
            }
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(15, 15, 15, 15)  # 设置内边距
        right_layout.setSpacing(10)  # 设置控件间距
        content_layout.addWidget(right_panel, 2)  # 右侧占2的比例

        # 为了确保布局比例正确，设置水平布局的拉伸因子
        content_layout.setStretch(0, 1)  # 左侧面板比例为1
        content_layout.setStretch(1, 2)  # 右侧面板比例为2

        # 日志标签
        log_label = QLabel("日志信息")
        log_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        log_label.setContentsMargins(0, 5, 0, 5)
        log_label.setStyleSheet("color: #333333;")
        right_layout.addWidget(log_label)

        # 日志文本区域 - 使用固定颜色
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border-radius: 5px;
                border: 1px solid #cccccc;
                padding: 10px;
                color: #333333;
            }
        """)
        right_layout.addWidget(self.log_text)

        # 清除日志按钮
        clear_log_button = QPushButton("清除日志")
        clear_log_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e53935;
            }
            QPushButton:pressed {
                background-color: #d32f2f;
            }
        """)
        clear_log_button.clicked.connect(self.clear_log)
        right_layout.addWidget(clear_log_button)

        # 初始化功能描述
        self.update_function_description(0)

        # 初始化日志处理器
        self.log_handler = LogHandler(self.log_text)

        # 设置日志重定向
        self.setup_logging()

        # 显示版本信息
        self.check_version()

    def setup_logging(self):
        """设置日志重定向系统"""
        # 1. 创建并配置自定义日志处理器
        gui_handler = GUILogHandler(self.log_handler)

        # 2. 配置根日志记录器
        root_logger = logging.getLogger()
        # 移除所有现有处理器以避免重复
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        root_logger.addHandler(gui_handler)
        root_logger.setLevel(logging.INFO)

        # 3. 配置cursor_pro模块的日志记录器
        try:
            cursor_logger = logging.getLogger('cursor_pro_keep_alive')
            for handler in cursor_logger.handlers[:]:
                cursor_logger.removeHandler(handler)
            cursor_logger.addHandler(gui_handler)
            cursor_logger.setLevel(logging.INFO)
            cursor_logger.propagate = False  # 避免日志重复
        except:
            pass

        # 4. 重定向标准输出和标准错误
        self.stdout_backup = sys.stdout
        self.stderr_backup = sys.stderr

        sys.stdout = StreamRedirector(self.log_handler)
        sys.stderr = StreamRedirector(self.log_handler)

    def restore_std_streams(self):
        """恢复标准输出和标准错误流"""
        if hasattr(self, 'stdout_backup') and self.stdout_backup:
            sys.stdout = self.stdout_backup
        if hasattr(self, 'stderr_backup') and self.stderr_backup:
            sys.stderr = self.stderr_backup

    def update_function_description(self, index):
        descriptions = [
            "此功能会自动关闭Cursor，重置设备信息，然后完成注册过程，包括生成随机邮箱、设置密码并登录。完成后需手动重启Cursor。",
            "自动关闭Cursor后仅重置设备信息和修改相关文件，不进行注册和登录操作。适用于已有账号但需要重置设备标识的情况。",
            "自动关闭Cursor后将所有设备信息和文件恢复至修改前的状态。如果遇到问题可使用此选项恢复原始设置。",
            "自动关闭Cursor，重置设备信息后，需要登录已有账号，适用于需要使用自己账号的情况。",
            "自动关闭Cursor，重置设备信息后，直接从API获取并替换为新账号。无需手动登录，适合快速切换账号的场景。",
            "批量自动注册多个Cursor账号并保存至文件。可用于准备备用账号或批量测试。此功能不需要关闭Cursor。"
        ]

        if 0 <= index < len(descriptions):
            self.description_text.setPlainText(descriptions[index])

        # 如果选择了功能4（重置设备并登录已有账号），则显示登录表单
        if index == 3:
            # 显示登录表单区域
            self.login_form_area.setVisible(True)

            # 初始化密码框可见性
            self.toggle_password_visibility(0)

            # 重置登录表单
            self.login_email_input.clear()
            self.login_password_input.clear()
            self.verification_code_input.clear()

            # 确保登录按钮可用
            self.confirm_login_button.setEnabled(True)

            # 修改执行按钮文本和行为
            self.execute_button.setText("继续")

            # 确保执行按钮点击时执行的是正确的操作
            try:
                # 断开所有之前的连接
                self.execute_button.clicked.disconnect()
            except:
                pass  # 如果没有连接，会抛出异常，忽略它

            # 重新连接到特定的登录准备功能
            self.execute_button.clicked.connect(self.prepare_login)

        else:
            # 隐藏登录表单区域
            self.login_form_area.setVisible(False)

            # 恢复执行按钮文本和行为
            self.execute_button.setText("执行")

            # 重新连接到默认的执行功能
            try:
                self.execute_button.clicked.disconnect()
            except:
                pass

            self.execute_button.clicked.connect(self.execute_function)

    # 添加一个新方法专门处理登录准备
    def prepare_login(self):
        try:
            # 获取登录信息
            email = self.login_email_input.text().strip()
            password = self.login_password_input.text().strip()
            login_type = "password" if self.login_type_combo.currentIndex() == 0 else "code"

            # 验证基本输入
            if not email:
                self.log_handler.error("邮箱不能为空")
                return

            if login_type == "password" and not password:
                self.log_handler.error("密码不能为空")
                return

            # 禁用按钮防止重复点击
            self.execute_button.setEnabled(False)

            # 执行登录任务
            self.execute_task("login", {
                "email": email,
                "password": password,
                "login_type": login_type,
                "device_reset_done": False  # 需要先重置设备
            })

        except Exception as e:
            import traceback
            error_msg = f"准备登录时出错: {str(e)}\n{traceback.format_exc()}"
            self.log_handler.error(error_msg)
            self.execute_button.setEnabled(True)

    def execute_function(self):
        # 获取选中的功能索引
        index = self.function_combo.currentIndex()

        # 禁用执行按钮
        self.execute_button.setEnabled(False)

        # 对于功能1-5，首先需要验证权限（在macOS上）
        if index < 5 and self.is_macos and not self.has_permission:
            self.log_handler.info("正在请求管理员权限...")
            if not self.request_macos_permission():
                self.log_handler.error("未获得管理员权限，无法执行此操作")
                self.execute_button.setEnabled(True)
                return
        if index < 5:  # 前5个功能需要先退出Cursor
            self.log_handler.info("正在检查并关闭Cursor...")
            try:
                # 使用更直接的方式捕获ExitCursor的输出
                import io
                import contextlib
                import sys
                import logging

                # 确保最新的日志立即显示
                QApplication.processEvents()

                # 创建一个特殊的日志处理器来捕获ExitCursor的日志
                class ExitCursorLogHandler(logging.Handler):
                    def __init__(self, log_func):
                        super().__init__()
                        self.log_func = log_func

                    def emit(self, record):
                        msg = self.format(record)
                        self.log_func(f"Cursor退出: {msg}")

                # 配置日志记录器来捕获ExitCursor的日志
                exit_logger = logging.getLogger('cursor_pro_keep_alive')
                original_handlers = exit_logger.handlers.copy()
                exit_logger.handlers.clear()  # 清除现有处理器

                # 添加我们的自定义处理器
                exit_handler = ExitCursorLogHandler(self.log_handler.info)
                exit_handler.setFormatter(logging.Formatter('%(message)s'))
                exit_logger.addHandler(exit_handler)
                exit_logger.setLevel(logging.INFO)
                exit_logger.propagate = False  # 防止日志传播

                # 使用StringIO捕获标准输出和标准错误
                stdout_capture = io.StringIO()
                stderr_capture = io.StringIO()

                # 备份当前的标准输出和标准错误
                old_stdout = sys.stdout
                old_stderr = sys.stderr

                # 将标准输出和标准错误重定向到我们的捕获对象
                sys.stdout = stdout_capture
                sys.stderr = stderr_capture

                try:
                    # 执行ExitCursor操作，在macOS上可能需要特殊处理
                    QApplication.processEvents()

                    if self.is_macos and self.has_permission:
                        # macOS下使用管理员权限退出Cursor
                        success, cursor_path = self.exit_cursor_macos()
                    else:
                        # 其他平台使用普通方式
                        success, cursor_path = ExitCursor()

                    # 捕获标准输出中的日志信息
                    stdout_log = stdout_capture.getvalue()
                    stderr_log = stderr_capture.getvalue()

                    # 将捕获的日志显示在GUI中
                    if stdout_log:
                        for line in stdout_log.splitlines():
                            if line.strip():
                                self.log_handler.info(f"Cursor退出: {line.strip()}")
                                QApplication.processEvents()  # 确保UI更新

                    if stderr_log:
                        for line in stderr_log.splitlines():
                            if line.strip():
                                self.log_handler.error(f"Cursor退出错误: {line.strip()}")
                                QApplication.processEvents()  # 确保UI更新

                finally:
                    # 恢复标准输出和标准错误
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr

                    # 恢复原来的日志处理器
                    exit_logger.handlers.clear()
                    for handler in original_handlers:
                        exit_logger.addHandler(handler)

                # 根据ExitCursor的结果继续操作
                if not success:
                    self.log_handler.error("无法自动关闭Cursor，请手动关闭后重试")
                    self.execute_button.setEnabled(True)
                    return
                else:
                    # 保存cursor_path以便后续使用
                    self.cursor_path = cursor_path if success else ""
                    QApplication.processEvents()  # 确保UI更新

                    # 对于功能1、4、5，需要立即执行重置设备信息
                    if index in [0, 3, 4]:
                        # 再次设置日志捕获，这次捕获重置设备信息的日志
                        QApplication.processEvents()

                        # 创建一个特殊的日志处理器来捕获重置设备信息的日志
                        class ResetDeviceLogHandler(logging.Handler):
                            def __init__(self, log_func):
                                super().__init__()
                                self.log_func = log_func

                            def emit(self, record):
                                msg = self.format(record)
                                self.log_func(f"设备重置: {msg}")

                        # 配置日志记录器
                        reset_logger = logging.getLogger('cursor_pro_keep_alive')
                        original_reset_handlers = reset_logger.handlers.copy()
                        reset_logger.handlers.clear()

                        # 添加自定义处理器
                        reset_handler = ResetDeviceLogHandler(self.log_handler.info)
                        reset_handler.setFormatter(logging.Formatter('%(message)s'))
                        reset_logger.addHandler(reset_handler)

                        # 捕获标准输出和标准错误
                        reset_stdout_capture = io.StringIO()
                        reset_stderr_capture = io.StringIO()

                        # 备份当前的标准输出和标准错误
                        old_stdout = sys.stdout
                        old_stderr = sys.stderr

                        # 重定向输出
                        sys.stdout = reset_stdout_capture
                        sys.stderr = reset_stderr_capture

                        try:
                            # 执行重置设备信息操作
                            import asyncio
                            self.log_handler.info("正在执行设备重置...")
                            QApplication.processEvents()

                            # 使用事件循环异步运行
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                if self.is_macos and self.has_permission:
                                    # macOS下使用管理员权限重置设备ID
                                    loop.run_until_complete(self.reset_machine_id_macos())
                                else:
                                    # 其他平台使用普通方式
                                    loop.run_until_complete(reset_machine_id())
                            finally:
                                loop.close()

                            # 捕获标准输出中的日志信息
                            reset_stdout_log = reset_stdout_capture.getvalue()
                            reset_stderr_log = reset_stderr_capture.getvalue()

                            # 将捕获的日志显示在GUI中
                            if reset_stdout_log:
                                for line in reset_stdout_log.splitlines():
                                    if line.strip():
                                        self.log_handler.info(f"设备重置: {line.strip()}")
                                        QApplication.processEvents()

                            if reset_stderr_log:
                                for line in reset_stderr_log.splitlines():
                                    if line.strip():
                                        self.log_handler.error(f"设备重置错误: {line.strip()}")
                                        QApplication.processEvents()

                            self.log_handler.info("设备信息重置完成")
                            QApplication.processEvents()

                        except Exception as e:
                            self.log_handler.error(f"重置设备信息时出错: {str(e)}")
                            import traceback
                            self.log_handler.error(traceback.format_exc())
                            self.execute_button.setEnabled(True)
                            return
                        finally:
                            # 恢复标准输出和标准错误
                            sys.stdout = old_stdout
                            sys.stderr = old_stderr

                            # 恢复原来的日志处理器
                            reset_logger.handlers.clear()
                            for handler in original_reset_handlers:
                                reset_logger.addHandler(handler)

            except Exception as e:
                self.log_handler.error(f"关闭Cursor过程出错: {str(e)}")
                import traceback
                self.log_handler.error(traceback.format_exc())
                self.execute_button.setEnabled(True)
                return

                # 根据不同功能执行不同的任务
        if index == 0:  # 一键注册
            self.execute_task("register", {"device_reset_done": True})
        elif index == 1:  # 修改设备信息
            self.execute_task("reset_device")
        elif index == 2:  # 恢复设备信息
            self.execute_task("restore_device")
        # elif index == 3:  # 重置设备并登录
        # 登录表单区域已在update_function_description中显示
        # 这里直接执行设备重置

        elif index == 4:  # 重置设备并直接替换账号
            self.execute_task("replace_account", {"device_reset_done": True})
        elif index == 5:  # 批量注册
            # 获取批量注册数量
            try:
                from PyQt6.QtWidgets import QInputDialog
                num, ok = QInputDialog.getInt(self, "批量注册", "请输入要注册的账号数量:", 1, 1, 100, 1)
                if ok:
                    self.execute_task("batch_register", {"num": num})
                else:
                    self.execute_button.setEnabled(True)
            except Exception as e:
                self.log_handler.error(f"获取注册数量时出错: {str(e)}")
                self.execute_button.setEnabled(True)

    def execute_task(self, task_type, params=None):
        try:
            # 处理任务前确保日志显示正常
            QApplication.processEvents()

            # 禁用相关按钮，防止重复点击
            if hasattr(self, 'execute_button') and self.execute_button:
                self.execute_button.setEnabled(False)
            if hasattr(self, 'confirm_login_button') and self.confirm_login_button:
                self.confirm_login_button.setEnabled(False)
            # 创建并启动工作线程
            self.worker = WorkerThread(task_type, params)
            self.worker.update_signal.connect(self.update_log)
            self.worker.finished_signal.connect(self.task_finished)
            self.worker.verification_code_signal.connect(self.show_verification_dialog)
            self.worker.start()
        except Exception as e:
            import traceback
            error_msg = f"启动任务时出错: {str(e)}\n{traceback.format_exc()}"
            self.log_handler.error(error_msg)

            # 重新启用按钮
            if hasattr(self, 'execute_button') and self.execute_button:
                self.execute_button.setEnabled(True)
            if hasattr(self, 'confirm_login_button') and self.confirm_login_button:
                self.confirm_login_button.setEnabled(True)

    def update_log(self, message, msg_type):
        if msg_type == "info":
            self.log_handler.info(message)
        elif msg_type == "error":
            self.log_handler.error(message)
        elif msg_type == "warning":
            self.log_handler.warning(message)
        else:
            self.log_handler.debug(message)

        # 确保日志立即显示
        QApplication.processEvents()

    def task_finished(self, success):
        if success:
            self.log_handler.info("任务完成")

            # 对于已完成的任务，提示重启Cursor（如果适用）
            if hasattr(self, 'cursor_path') and self.cursor_path:
                self.log_handler.info("任务已完成，请手动重新启动Cursor")
        else:
            self.log_handler.error("任务失败")

        # 确保日志立即显示
        QApplication.processEvents()

        # 重新启用执行按钮
        self.execute_button.setEnabled(True)

    def closeEvent(self, event):
        """窗口关闭事件，恢复标准输出和标准错误流"""
        self.restore_std_streams()
        event.accept()

    def show_settings(self):
        """显示设置对话框"""
        dialog = ConfigDialog(self)
        dialog.exec()

    def exit_cursor_macos(self):
        """在macOS系统上使用管理员权限关闭Cursor"""
        try:
            self.log_handler.info("在macOS上使用管理员权限关闭Cursor...")

            # 找到Cursor进程并关闭
            cmd = ['osascript', '-e', 'tell application "Cursor" to quit']
            subprocess.run(cmd, check=True)

            # 等待进程完全退出
            time.sleep(2)

            # 检查Cursor是否已关闭
            check_cmd = ['pgrep', 'Cursor']
            result = subprocess.run(check_cmd, capture_output=True)

            if result.returncode == 0:
                self.log_handler.warning("Cursor未能完全关闭，尝试强制关闭...")
                kill_cmd = ['pkill', '-9', 'Cursor']
                subprocess.run(kill_cmd)
                time.sleep(1)

            # 获取Cursor应用程序路径
            cursor_app_path = ""
            possible_paths = [
                "/Applications/Cursor.app",
                os.path.expanduser("~/Applications/Cursor.app")
            ]

            for path in possible_paths:
                if os.path.exists(path):
                    cursor_app_path = path
                    break

            if not cursor_app_path:
                self.log_handler.error("找不到Cursor应用程序路径")
                return False, ""

            return True, cursor_app_path

        except Exception as e:
            self.log_handler.error(f"退出Cursor时出错: {str(e)}")
            return False, ""

    async def reset_machine_id_macos(self):
        """在macOS系统上使用管理员权限重置设备ID"""
        try:
            self.log_handler.info("在macOS上使用管理员权限重置设备ID...")

            # 使用MachineIDResetter的reset_machine_ids方法
            # 但可能需要特殊处理以获取足够权限
            await reset_machine_id()

            return True
        except Exception as e:
            self.log_handler.error(f"重置设备ID时出错: {str(e)}")
            return False

    @staticmethod
    def get_verification_code():
        """等待用户输入验证码并返回

        Returns:
            str: 用户输入的验证码或None
        """
        logging.info("请求验证码输入...")

        if CursorProGUI._instance:
            logging.info("找到GUI实例，准备显示验证码输入区域")
            try:
                # 显示验证码输入区域
                CursorProGUI._instance.show_verification_dialog()
                # 等待用户输入
                if CursorProGUI._instance.worker:
                    logging.info("找到worker实例，准备获取验证码")
                    code = CursorProGUI._instance.worker.get_verification_code_from_ui()
                    return code
                else:
                    logging.error("未找到worker实例")
            except Exception as e:
                logging.error(f"获取验证码过程中出错: {str(e)}")
                import traceback
                logging.error(traceback.format_exc())
        else:
            logging.error("未找到GUI实例，无法显示验证码输入区域")
        return None

    # 添加确认登录的方法
    def confirm_login(self):
        """确认登录操作"""
        # 获取登录信息
        email = self.login_email_input.text().strip()
        password = self.login_password_input.text().strip()
        login_type = "password" if self.login_type_combo.currentIndex() == 0 else "code"

        # 验证输入
        if not email:
            self.log_handler.error("邮箱不能为空")
            return

        if login_type == "password" and not password:
            self.log_handler.error("密码不能为空")
            return

        self.log_handler.info(f"准备使用账号 {email} 登录")

        # 禁用执行按钮
        self.confirm_login_button.setEnabled(False)
        self.back_button.setEnabled(False)

        # 创建登录任务
        self.execute_task("login", {
            "device_reset_done": True,
            "email": email,
            "password": password if login_type == "password" else None,
            "login_type": login_type
        })

        # 完成后自动返回功能选择界面
        self.back_to_functions()

    def back_to_functions(self):
        """返回功能选择界面"""
        self.login_widget.setVisible(False)
        self.function_selection_widget.setVisible(True)

    def submit_verification_code(self):
        """提交验证码"""
        code = self.verification_code_input.text().strip()
        if code:
            self.worker.handle_verification_code(code)
            # 清空输入但不隐藏组件
            self.verification_code_input.clear()
            # 隐藏提交按钮直到有新输入
            self.verification_code_submit.setVisible(False)
            self.execute_function()
        else:
            self.log_handler.error("验证码不能为空")

    # 添加验证码输入检查方法
    def check_verification_code(self, text):
        """检查验证码输入并控制确认按钮显示"""
        login_type = "password" if self.login_type_combo.currentIndex() == 0 else "code"
        if login_type == "code" and text.strip():
            self.verification_code_submit.setVisible(True)
        else:
            self.verification_code_submit.setVisible(False)

    # 添加切换密码可见性的方法
    def toggle_password_visibility(self, index):
        """根据登录方式显示或隐藏密码框和相关控件"""
        if index == 0:  # 密码登录
            self.login_password_input.setVisible(True)
            self.login_password_label.setVisible(True)
            self.verification_code_label.setVisible(False)
            self.verification_code_input.setVisible(False)
            self.verification_code_submit.setVisible(False)
            # 密码登录时不需要显示登录按钮
            self.confirm_login_button.setVisible(False)
        else:  # 验证码登录
            self.login_password_input.setVisible(False)
            self.login_password_label.setVisible(False)
            self.verification_code_label.setVisible(True)
            self.verification_code_input.setVisible(True)
            self.verification_code_submit.setVisible(False)  # 初始不显示，等有输入时再显示
            self.confirm_login_button.setVisible(False)

    def clear_log(self):
        """清除日志内容"""
        self.log_text.clear()

    def check_version(self):
        """检查版本信息"""
        # 尝试调用check_version函数
        self.log_handler.info("正在检查版本...")
        try:
            # 捕获check_version函数的输出
            check_version()
            self.log_handler.info("版本检查完成")
        except Exception as e:
            self.log_handler.error(f"检查版本出错: {str(e)}")

    def show_verification_dialog(self):
        """显示验证码输入区域"""
        logging.info("显示验证码输入区域...")
        try:
            # 显示验证码输入区域
            self.verification_code_label.setVisible(True)
            self.verification_code_input.setVisible(True)
            self.verification_code_submit.setVisible(True)
            self.verification_code_submit.setEnabled(True)

            # 清空之前的输入
            self.verification_code_input.clear()

            # 给验证码输入框焦点
            self.verification_code_input.setFocus()

            self.log_handler.info("请在验证码输入框中输入您收到的验证码")

        except Exception as e:
            logging.error(f"显示验证码输入区域时出错: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())


class VerificationCodeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("输入验证码")
        self.setMinimumSize(300, 150)

        # 设置对话框为亮色主题
        self.setStyleSheet("""
            QDialog {
                background-color: #F5F5F5;
                color: #333333;
            }
            QLabel {
                color: #333333;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: white;
                color: #333333;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)

        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title_label = QLabel("请输入验证码")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #333333;")
        layout.addWidget(title_label)

        # 验证码输入框
        self.code_input = QLineEdit()
        self.code_input.setFixedHeight(36)
        self.code_input.setPlaceholderText("输入收到的验证码")
        layout.addWidget(self.code_input)

        # 提示信息
        info_label = QLabel("请查看邮箱获取验证码")
        info_label.setStyleSheet("color: #666666; font-style: italic;")
        layout.addWidget(info_label)

        # 按钮布局
        button_layout = QHBoxLayout()

        # 确认按钮
        confirm_button = QPushButton("确认")
        confirm_button.clicked.connect(self.accept)
        button_layout.addWidget(confirm_button)

        # 取消按钮
        cancel_button = QPushButton("取消")
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
            }
            QPushButton:hover {
                background-color: #e53935;
            }
        """)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def get_code(self):
        """获取输入的验证码"""
        return self.code_input.text().strip()


class CursorProGUI(QMainWindow):
    # 添加一个类变量来存储实例引用
    _instance = None

    def __init__(self):
        super().__init__()
        # 保存实例引用
        self.cursor_path = None
        CursorProGUI._instance = self

        # 获取版本号
        try:
            # 使用正确的Config类
            if CONFIG_IMPORT_FAILED:
                self.config = LocalConfig()
            else:
                self.config = Config()
            self.version = self.config.get_version()
        except:
            self.version = "未知版本"

        # 检测操作系统并初始化权限状态
        self.is_macos = platform.system() == 'Darwin'
        self.has_permission = not self.is_macos  # 非macOS默认有权限

        # 设置标题中包含版本号
        self.setWindowTitle(f"Cursor Pro - {self.version}")

        # 确保窗口使用亮色模式 
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
        self.setPalette(palette)

        self.init_ui()

        # 如果是macOS，检查权限
        if self.is_macos:
            self.check_macos_permission()

        # 初始化验证码对话框
        self.verification_dialog = None

        # 初始化worker
        self.worker = None

        # 确保窗口显示在最前面
        self.raise_()
        self.activateWindow()

        logging.info("CursorProGUI初始化完成")

    def check_macos_permission(self):
        """检查在macOS上是否有足够的权限"""
        try:
            # 尝试获取Cursor的安装路径
            cursor_app_path = ""
            possible_paths = [
                "/Applications/Cursor.app",
                os.path.expanduser("~/Applications/Cursor.app")
            ]

            for path in possible_paths:
                if os.path.exists(path):
                    cursor_app_path = path
                    break

            if not cursor_app_path:
                self.log_handler.warning("找不到Cursor应用程序，请确保已安装Cursor")
                return

            # 尝试写入测试文件来检查权限
            test_file_path = os.path.join(cursor_app_path, "Contents", "Resources", ".permission_test")
            try:
                with open(test_file_path, 'w') as f:
                    f.write("permission test")
                os.remove(test_file_path)
                self.has_permission = True
                self.log_handler.info("已获取足够权限来修改Cursor文件")
            except (PermissionError, OSError):
                self.has_permission = False
                self.show_permission_warning()
        except Exception as e:
            self.log_handler.error(f"检查权限时出错: {str(e)}")
            self.has_permission = False

    def show_permission_warning(self):
        """显示macOS权限警告对话框"""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("需要权限")
        msg.setText("此程序需要修改Cursor应用程序文件")
        msg.setInformativeText("为了正常运行，本程序需要管理员权限来修改Cursor的文件。\n\n"
                               "当执行功能时，系统会提示您输入管理员密码。\n\n"
                               "如不授权，程序部分功能将无法正常工作。")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def request_macos_permission(self):
        """请求macOS管理员权限"""
        if not self.is_macos or self.has_permission:
            return True

        try:
            # 使用osascript提示输入管理员密码
            command = ["osascript", "-e",
                       'do shell script "echo Permission granted" with administrator privileges']
            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode == 0:
                self.has_permission = True
                self.log_handler.info("成功获取管理员权限")
                return True
            else:
                self.log_handler.error(f"获取权限失败: {result.stderr}")
                return False
        except Exception as e:
            self.log_handler.error(f"请求权限时出错: {str(e)}")
            return False

    def init_ui(self):
        # 设置窗口基本属性
        self.setMinimumSize(1000, 700)

        # 创建中央窗口部件
        central_widget = QWidget()
        central_widget.setStyleSheet("background-color: #FFFFFF;")  # 将背景色从 #F0F0F0 改为 #FFFFFF（白色）
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 创建标题布局
        title_layout = QHBoxLayout()

        # 添加弹性空间，使标题居中
        title_layout.addStretch(1)

        # 标题标签
        title_label = QLabel("Cursor Pro 自动化工具")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #333333;")
        title_layout.addWidget(title_label)

        # 添加版本标签
        version_label = QLabel(f"v{self.version}")
        version_label.setFont(QFont("Arial", 10))
        version_label.setStyleSheet("color: #666666;")
        title_layout.addWidget(version_label)

        # 设置按钮 - 使用文本而不是图标，确保在所有平台都能显示
        settings_button = QPushButton("⚙")
        settings_button.setToolTip("查看环境设置")
        settings_button.setFont(QFont("Arial", 14))
        settings_button.setMaximumSize(36, 36)
        settings_button.clicked.connect(self.show_settings)
        settings_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #555555;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                border-radius: 18px;
            }
        """)
        title_layout.addWidget(settings_button)

        # 添加弹性空间，使标题居中
        title_layout.addStretch(1)

        main_layout.addLayout(title_layout)

        # 内容区域 - 使用水平布局
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        main_layout.addLayout(content_layout)

        # 左侧功能面板 - 使用固定颜色
        left_panel = QFrame()
        left_panel.setFrameShape(QFrame.Shape.StyledPanel)
        left_panel.setFrameShadow(QFrame.Shadow.Raised)
        left_panel.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 10px;
                border: 1px solid #dddddd;
            }
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(15, 15, 15, 15)  # 设置内边距
        left_layout.setSpacing(10)  # 设置控件间距
        left_panel.setFixedWidth(350)  # 设置固定宽度
        content_layout.addWidget(left_panel, 1)  # 设置拉伸因子为1

        # 功能标签
        function_label = QLabel("功能选择")
        function_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        function_label.setContentsMargins(0, 5, 0, 5)
        function_label.setStyleSheet("color: #333333;")
        left_layout.addWidget(function_label)

        # 重置功能下拉菜单，使用最简单的实现
        functions = [
            "1.一键注册并且享用Cursor",
            "2.仅仅修改文件或设备信息",
            "3.恢复原始文件或设备信息",
            "4.重置设备并登录已有账号",
            "5.重置设备并直接替换账号",
            "6.随机批量注册账号"
        ]

        self.function_combo = QComboBox()
        for func in functions:
            self.function_combo.addItem(func)

        # 使用亮色主题样式
        self.function_combo.setStyleSheet("""
            QComboBox {
                background-color: white;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 4px;
                color: #333333;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #cccccc;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: #333333;
                border: 1px solid #cccccc;
                selection-background-color: #4CAF50;
                selection-color: white;
            }
        """)
        self.function_combo.setFixedHeight(36)
        self.function_combo.setMinimumWidth(320)
        self.function_combo.currentIndexChanged.connect(self.update_function_description)
        left_layout.addWidget(self.function_combo)

        # 执行按钮
        self.execute_button = QPushButton("执行")
        self.execute_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.execute_button.clicked.connect(self.execute_function)
        left_layout.addWidget(self.execute_button)

        # 功能描述
        description_label = QLabel("功能描述")
        description_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        description_label.setContentsMargins(0, 5, 0, 5)
        description_label.setStyleSheet("color: #333333;")
        left_layout.addWidget(description_label)

        self.description_text = QTextEdit()
        self.description_text.setReadOnly(True)
        self.description_text.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border-radius: 5px;
                border: 1px solid #cccccc;
                padding: 10px;
                color: #333333;
            }
        """)
        left_layout.addWidget(self.description_text)

        # 登录表单区域 - 直接添加在功能描述下方
        self.login_form_area = QWidget()
        self.login_form_area.setVisible(False)  # 初始隐藏
        login_layout = QVBoxLayout(self.login_form_area)
        login_layout.setContentsMargins(0, 10, 0, 0)
        login_layout.setSpacing(15)
        # 确保在暗色模式下可见
        self.login_form_area.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
            }
            QLabel {
                color: #000000;
            }
        """)

        # 登录方式选择 - 移到最上方
        login_type_label = QLabel("登录方式:")
        login_type_label.setFont(QFont("Arial", 11))
        login_type_label.setStyleSheet("color: #000000;")
        self.login_type_combo = QComboBox()
        self.login_type_combo.addItem("密码登录")
        self.login_type_combo.addItem("验证码登录")
        self.login_type_combo.setFixedHeight(36)
        self.login_type_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # 修复下拉框文字不可见问题
        self.login_type_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 5px;
                background-color: white;
                color: #000000;
                font-size: 14px;
                min-width: 200px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #CCCCCC;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: #000000;
                selection-background-color: #E0E0E0;
                selection-color: #000000;
            }
        """)
        self.login_type_combo.currentIndexChanged.connect(self.toggle_password_visibility)

        # 将登录方式放入水平布局使其更美观
        login_type_layout = QHBoxLayout()
        login_type_layout.setContentsMargins(0, 0, 0, 0)
        login_type_layout.setSpacing(10)
        login_type_layout.addWidget(login_type_label)
        login_type_layout.addWidget(self.login_type_combo, 1)  # 添加拉伸因子1使ComboBox填充剩余空间
        login_layout.addLayout(login_type_layout)

        # 表单布局
        form_layout = QGridLayout()
        form_layout.setSpacing(10)

        # 邮箱输入
        email_label = QLabel("邮箱:")
        email_label.setFont(QFont("Arial", 11))
        email_label.setStyleSheet("color: #000000;")
        self.login_email_input = QLineEdit()
        self.login_email_input.setFixedHeight(36)
        self.login_email_input.setPlaceholderText("输入您的Cursor账号邮箱")
        self.login_email_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: white;
                color: #000000;
            }
        """)
        form_layout.addWidget(email_label, 0, 0)
        form_layout.addWidget(self.login_email_input, 0, 1)

        # 密码输入
        self.login_password_label = QLabel("密码:")
        self.login_password_label.setFont(QFont("Arial", 11))
        self.login_password_label.setStyleSheet("color: #000000;")
        self.login_password_input = QLineEdit()
        self.login_password_input.setFixedHeight(36)
        self.login_password_input.setPlaceholderText("输入您的Cursor账号密码")
        self.login_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_password_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: white;
                color: #000000;
            }
        """)
        form_layout.addWidget(self.login_password_label, 1, 0)
        form_layout.addWidget(self.login_password_input, 1, 1)

        # 验证码输入区域 - 始终显示，但根据登录方式控制可见性
        self.verification_code_label = QLabel("验证码:")
        self.verification_code_label.setFont(QFont("Arial", 11))
        self.verification_code_label.setStyleSheet("color: #000000;")
        self.verification_code_input = QLineEdit()
        self.verification_code_input.setFixedHeight(36)
        self.verification_code_input.setPlaceholderText("输入收到的验证码")
        self.verification_code_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: white;
                color: #000000;
            }
        """)
        self.verification_code_input.textChanged.connect(self.check_verification_code)
        self.verification_code_submit = QPushButton("确定")
        self.verification_code_submit.setFixedHeight(36)
        self.verification_code_submit.setMinimumWidth(120)  # 设置最小宽度
        self.verification_code_submit.setMaximumWidth(120)  # 设置最大宽度
        self.verification_code_submit.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 5px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        self.verification_code_submit.setVisible(False)  # 初始不显示，仅在有验证码输入时显示
        self.verification_code_submit.clicked.connect(self.submit_verification_code)
        form_layout.addWidget(self.verification_code_label, 2, 0)
        form_layout.addWidget(self.verification_code_input, 2, 1)

        # 验证码按钮布局 - 使用QHBoxLayout控制对齐方式
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch(1)  # 添加弹性空间将按钮推向右侧
        button_layout.addWidget(self.verification_code_submit)

        # 将按钮布局添加到第4行
        verify_button_container = QWidget()
        verify_button_container.setLayout(button_layout)
        form_layout.addWidget(verify_button_container, 3, 1, 1, 1)

        login_layout.addLayout(form_layout)

        # 按钮布局
        login_button_layout = QHBoxLayout()

        # 登录按钮 - 仅在密码登录时显示
        self.confirm_login_button = QPushButton("登录")
        self.confirm_login_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.confirm_login_button.clicked.connect(self.confirm_login)
        self.confirm_login_button.setVisible(False)  # 默认不显示登录按钮
        login_button_layout.addWidget(self.confirm_login_button)

        login_layout.addLayout(login_button_layout)

        # 添加登录表单区域到主布局
        left_layout.addWidget(self.login_form_area)

        # 右侧日志面板 - 使用固定颜色
        right_panel = QFrame()
        right_panel.setFrameShape(QFrame.Shape.StyledPanel)
        right_panel.setFrameShadow(QFrame.Shadow.Raised)
        right_panel.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 10px;
                border: 1px solid #dddddd;
            }
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(15, 15, 15, 15)  # 设置内边距
        right_layout.setSpacing(10)  # 设置控件间距
        content_layout.addWidget(right_panel, 2)  # 右侧占2的比例

        # 为了确保布局比例正确，设置水平布局的拉伸因子
        content_layout.setStretch(0, 1)  # 左侧面板比例为1
        content_layout.setStretch(1, 2)  # 右侧面板比例为2

        # 日志标签
        log_label = QLabel("日志信息")
        log_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        log_label.setContentsMargins(0, 5, 0, 5)
        log_label.setStyleSheet("color: #333333;")
        right_layout.addWidget(log_label)

        # 日志文本区域 - 使用固定颜色
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border-radius: 5px;
                border: 1px solid #cccccc;
                padding: 10px;
                color: #333333;
            }
        """)
        right_layout.addWidget(self.log_text)

        # 清除日志按钮
        clear_log_button = QPushButton("清除日志")
        clear_log_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e53935;
            }
            QPushButton:pressed {
                background-color: #d32f2f;
            }
        """)
        clear_log_button.clicked.connect(self.clear_log)
        right_layout.addWidget(clear_log_button)

        # 初始化功能描述
        self.update_function_description(0)

        # 初始化日志处理器
        self.log_handler = LogHandler(self.log_text)

        # 设置日志重定向
        self.setup_logging()

        # 显示版本信息
        self.check_version()

    def setup_logging(self):
        """设置日志重定向系统"""
        # 1. 创建并配置自定义日志处理器
        gui_handler = GUILogHandler(self.log_handler)

        # 2. 配置根日志记录器
        root_logger = logging.getLogger()
        # 移除所有现有处理器以避免重复
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        root_logger.addHandler(gui_handler)
        root_logger.setLevel(logging.INFO)

        # 3. 配置cursor_pro模块的日志记录器
        try:
            cursor_logger = logging.getLogger('cursor_pro_keep_alive')
            for handler in cursor_logger.handlers[:]:
                cursor_logger.removeHandler(handler)
            cursor_logger.addHandler(gui_handler)
            cursor_logger.setLevel(logging.INFO)
            cursor_logger.propagate = False  # 避免日志重复
        except:
            pass

        # 4. 重定向标准输出和标准错误
        self.stdout_backup = sys.stdout
        self.stderr_backup = sys.stderr

        sys.stdout = StreamRedirector(self.log_handler)
        sys.stderr = StreamRedirector(self.log_handler)

    def restore_std_streams(self):
        """恢复标准输出和标准错误流"""
        if hasattr(self, 'stdout_backup') and self.stdout_backup:
            sys.stdout = self.stdout_backup
        if hasattr(self, 'stderr_backup') and self.stderr_backup:
            sys.stderr = self.stderr_backup

    def update_function_description(self, index):
        descriptions = [
            "此功能会自动关闭Cursor，重置设备信息，然后完成注册过程，包括生成随机邮箱、设置密码并登录。完成后需手动重启Cursor。",
            "自动关闭Cursor后仅重置设备信息和修改相关文件，不进行注册和登录操作。适用于已有账号但需要重置设备标识的情况。",
            "自动关闭Cursor后将所有设备信息和文件恢复至修改前的状态。如果遇到问题可使用此选项恢复原始设置。",
            "自动关闭Cursor，重置设备信息后，需要登录已有账号，适用于需要使用自己账号的情况。",
            "自动关闭Cursor，重置设备信息后，直接从API获取并替换为新账号。无需手动登录，适合快速切换账号的场景。",
            "批量自动注册多个Cursor账号并保存至文件。可用于准备备用账号或批量测试。此功能不需要关闭Cursor。"
        ]

        if 0 <= index < len(descriptions):
            self.description_text.setPlainText(descriptions[index])

        # 如果选择了功能4（重置设备并登录已有账号），则显示登录表单
        if index == 3:
            # 显示登录表单区域
            self.login_form_area.setVisible(True)

            # 初始化密码框可见性
            self.toggle_password_visibility(0)

            # 重置登录表单
            self.login_email_input.clear()
            self.login_password_input.clear()
            self.verification_code_input.clear()

            # 确保登录按钮可用
            self.confirm_login_button.setEnabled(True)

            # 修改执行按钮文本和行为
            self.execute_button.setText("继续")

            # 确保执行按钮点击时执行的是正确的操作
            try:
                # 断开所有之前的连接
                self.execute_button.clicked.disconnect()
            except:
                pass  # 如果没有连接，会抛出异常，忽略它

            # 重新连接到特定的登录准备功能
            self.execute_button.clicked.connect(self.prepare_login)

        else:
            # 隐藏登录表单区域
            self.login_form_area.setVisible(False)

            # 恢复执行按钮文本和行为
            self.execute_button.setText("执行")

            # 重新连接到默认的执行功能
            try:
                self.execute_button.clicked.disconnect()
            except:
                pass

            self.execute_button.clicked.connect(self.execute_function)

    # 添加一个新方法专门处理登录准备
    def prepare_login(self):
        try:
            # 获取登录信息
            email = self.login_email_input.text().strip()
            password = self.login_password_input.text().strip()
            login_type = "password" if self.login_type_combo.currentIndex() == 0 else "code"

            # 验证基本输入
            if not email:
                self.log_handler.error("邮箱不能为空")
                return

            if login_type == "password" and not password:
                self.log_handler.error("密码不能为空")
                return

            # 禁用按钮防止重复点击
            self.execute_button.setEnabled(False)

            # 执行登录任务
            self.execute_task("login", {
                "email": email,
                "password": password,
                "login_type": login_type,
                "device_reset_done": False  # 需要先重置设备
            })

        except Exception as e:
            import traceback
            error_msg = f"准备登录时出错: {str(e)}\n{traceback.format_exc()}"
            self.log_handler.error(error_msg)
            self.execute_button.setEnabled(True)

    def execute_function(self):
        # 获取选中的功能索引
        index = self.function_combo.currentIndex()

        # 禁用执行按钮
        self.execute_button.setEnabled(False)

        # 对于功能1-5，首先需要验证权限（在macOS上）
        if index < 5 and self.is_macos and not self.has_permission:
            self.log_handler.info("正在请求管理员权限...")
            if not self.request_macos_permission():
                self.log_handler.error("未获得管理员权限，无法执行此操作")
                self.execute_button.setEnabled(True)
                return
        if index < 5:  # 前5个功能需要先退出Cursor
            self.log_handler.info("正在检查并关闭Cursor...")
            try:
                # 使用更直接的方式捕获ExitCursor的输出
                import io
                import contextlib
                import sys
                import logging

                # 确保最新的日志立即显示
                QApplication.processEvents()

                # 创建一个特殊的日志处理器来捕获ExitCursor的日志
                class ExitCursorLogHandler(logging.Handler):
                    def __init__(self, log_func):
                        super().__init__()
                        self.log_func = log_func

                    def emit(self, record):
                        msg = self.format(record)
                        self.log_func(f"Cursor退出: {msg}")

                # 配置日志记录器来捕获ExitCursor的日志
                exit_logger = logging.getLogger('cursor_pro_keep_alive')
                original_handlers = exit_logger.handlers.copy()
                exit_logger.handlers.clear()  # 清除现有处理器

                # 添加我们的自定义处理器
                exit_handler = ExitCursorLogHandler(self.log_handler.info)
                exit_handler.setFormatter(logging.Formatter('%(message)s'))
                exit_logger.addHandler(exit_handler)
                exit_logger.setLevel(logging.INFO)
                exit_logger.propagate = False  # 防止日志传播

                # 使用StringIO捕获标准输出和标准错误
                stdout_capture = io.StringIO()
                stderr_capture = io.StringIO()

                # 备份当前的标准输出和标准错误
                old_stdout = sys.stdout
                old_stderr = sys.stderr

                # 将标准输出和标准错误重定向到我们的捕获对象
                sys.stdout = stdout_capture
                sys.stderr = stderr_capture

                try:
                    # 执行ExitCursor操作，在macOS上可能需要特殊处理
                    QApplication.processEvents()

                    if self.is_macos and self.has_permission:
                        # macOS下使用管理员权限退出Cursor
                        success, cursor_path = self.exit_cursor_macos()
                    else:
                        # 其他平台使用普通方式
                        success, cursor_path = ExitCursor()

                    # 捕获标准输出中的日志信息
                    stdout_log = stdout_capture.getvalue()
                    stderr_log = stderr_capture.getvalue()

                    # 将捕获的日志显示在GUI中
                    if stdout_log:
                        for line in stdout_log.splitlines():
                            if line.strip():
                                self.log_handler.info(f"Cursor退出: {line.strip()}")
                                QApplication.processEvents()  # 确保UI更新

                    if stderr_log:
                        for line in stderr_log.splitlines():
                            if line.strip():
                                self.log_handler.error(f"Cursor退出错误: {line.strip()}")
                                QApplication.processEvents()  # 确保UI更新

                finally:
                    # 恢复标准输出和标准错误
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr

                    # 恢复原来的日志处理器
                    exit_logger.handlers.clear()
                    for handler in original_handlers:
                        exit_logger.addHandler(handler)

                # 根据ExitCursor的结果继续操作
                if not success:
                    self.log_handler.error("无法自动关闭Cursor，请手动关闭后重试")
                    self.execute_button.setEnabled(True)
                    return
                else:
                    # 保存cursor_path以便后续使用
                    self.cursor_path = cursor_path if success else ""
                    QApplication.processEvents()  # 确保UI更新

                    # 对于功能1、4、5，需要立即执行重置设备信息
                    if index in [0, 3, 4]:
                        # 再次设置日志捕获，这次捕获重置设备信息的日志
                        QApplication.processEvents()

                        # 创建一个特殊的日志处理器来捕获重置设备信息的日志
                        class ResetDeviceLogHandler(logging.Handler):
                            def __init__(self, log_func):
                                super().__init__()
                                self.log_func = log_func

                            def emit(self, record):
                                msg = self.format(record)
                                self.log_func(f"设备重置: {msg}")

                        # 配置日志记录器
                        reset_logger = logging.getLogger('cursor_pro_keep_alive')
                        original_reset_handlers = reset_logger.handlers.copy()
                        reset_logger.handlers.clear()

                        # 添加自定义处理器
                        reset_handler = ResetDeviceLogHandler(self.log_handler.info)
                        reset_handler.setFormatter(logging.Formatter('%(message)s'))
                        reset_logger.addHandler(reset_handler)

                        # 捕获标准输出和标准错误
                        reset_stdout_capture = io.StringIO()
                        reset_stderr_capture = io.StringIO()

                        # 备份当前的标准输出和标准错误
                        old_stdout = sys.stdout
                        old_stderr = sys.stderr

                        # 重定向输出
                        sys.stdout = reset_stdout_capture
                        sys.stderr = reset_stderr_capture

                        try:
                            # 执行重置设备信息操作
                            import asyncio
                            self.log_handler.info("正在执行设备重置...")
                            QApplication.processEvents()

                            # 使用事件循环异步运行
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                if self.is_macos and self.has_permission:
                                    # macOS下使用管理员权限重置设备ID
                                    loop.run_until_complete(self.reset_machine_id_macos())
                                else:
                                    # 其他平台使用普通方式
                                    loop.run_until_complete(reset_machine_id())
                            finally:
                                loop.close()

                            # 捕获标准输出中的日志信息
                            reset_stdout_log = reset_stdout_capture.getvalue()
                            reset_stderr_log = reset_stderr_capture.getvalue()

                            # 将捕获的日志显示在GUI中
                            if reset_stdout_log:
                                for line in reset_stdout_log.splitlines():
                                    if line.strip():
                                        self.log_handler.info(f"设备重置: {line.strip()}")
                                        QApplication.processEvents()

                            if reset_stderr_log:
                                for line in reset_stderr_log.splitlines():
                                    if line.strip():
                                        self.log_handler.error(f"设备重置错误: {line.strip()}")
                                        QApplication.processEvents()

                            self.log_handler.info("设备信息重置完成")
                            QApplication.processEvents()

                        except Exception as e:
                            self.log_handler.error(f"重置设备信息时出错: {str(e)}")
                            import traceback
                            self.log_handler.error(traceback.format_exc())
                            self.execute_button.setEnabled(True)
                            return
                        finally:
                            # 恢复标准输出和标准错误
                            sys.stdout = old_stdout
                            sys.stderr = old_stderr

                            # 恢复原来的日志处理器
                            reset_logger.handlers.clear()
                            for handler in original_reset_handlers:
                                reset_logger.addHandler(handler)

            except Exception as e:
                self.log_handler.error(f"关闭Cursor过程出错: {str(e)}")
                import traceback
                self.log_handler.error(traceback.format_exc())
                self.execute_button.setEnabled(True)
                return

                # 根据不同功能执行不同的任务
        if index == 0:  # 一键注册
            self.execute_task("register", {"device_reset_done": True})
        elif index == 1:  # 修改设备信息
            self.execute_task("reset_device")
        elif index == 2:  # 恢复设备信息
            self.execute_task("restore_device")
        # elif index == 3:  # 重置设备并登录
        # 登录表单区域已在update_function_description中显示
        # 这里直接执行设备重置

        elif index == 4:  # 重置设备并直接替换账号
            self.execute_task("replace_account", {"device_reset_done": True})
        elif index == 5:  # 批量注册
            # 获取批量注册数量
            try:
                from PyQt6.QtWidgets import QInputDialog
                num, ok = QInputDialog.getInt(self, "批量注册", "请输入要注册的账号数量:", 1, 1, 100, 1)
                if ok:
                    self.execute_task("batch_register", {"num": num})
                else:
                    self.execute_button.setEnabled(True)
            except Exception as e:
                self.log_handler.error(f"获取注册数量时出错: {str(e)}")
                self.execute_button.setEnabled(True)

    def execute_task(self, task_type, params=None):
        try:
            # 处理任务前确保日志显示正常
            QApplication.processEvents()

            # 禁用相关按钮，防止重复点击
            if hasattr(self, 'execute_button') and self.execute_button:
                self.execute_button.setEnabled(False)
            if hasattr(self, 'confirm_login_button') and self.confirm_login_button:
                self.confirm_login_button.setEnabled(False)
            # 创建并启动工作线程
            self.worker = WorkerThread(task_type, params)
            self.worker.update_signal.connect(self.update_log)
            self.worker.finished_signal.connect(self.task_finished)
            self.worker.verification_code_signal.connect(self.show_verification_dialog)
            self.worker.start()
        except Exception as e:
            import traceback
            error_msg = f"启动任务时出错: {str(e)}\n{traceback.format_exc()}"
            self.log_handler.error(error_msg)

            # 重新启用按钮
            if hasattr(self, 'execute_button') and self.execute_button:
                self.execute_button.setEnabled(True)
            if hasattr(self, 'confirm_login_button') and self.confirm_login_button:
                self.confirm_login_button.setEnabled(True)

    def update_log(self, message, msg_type):
        if msg_type == "info":
            self.log_handler.info(message)
        elif msg_type == "error":
            self.log_handler.error(message)
        elif msg_type == "warning":
            self.log_handler.warning(message)
        else:
            self.log_handler.debug(message)

        # 确保日志立即显示
        QApplication.processEvents()

    def task_finished(self, success):
        if success:
            self.log_handler.info("任务完成")

            # 对于已完成的任务，提示重启Cursor（如果适用）
            if hasattr(self, 'cursor_path') and self.cursor_path:
                self.log_handler.info("任务已完成，请手动重新启动Cursor")
        else:
            self.log_handler.error("任务失败")

        # 确保日志立即显示
        QApplication.processEvents()

        # 重新启用执行按钮
        self.execute_button.setEnabled(True)

    def closeEvent(self, event):
        """窗口关闭事件，恢复标准输出和标准错误流"""
        self.restore_std_streams()
        event.accept()

    def show_settings(self):
        """显示设置对话框"""
        dialog = ConfigDialog(self)
        dialog.exec()

    def exit_cursor_macos(self):
        """在macOS系统上使用管理员权限关闭Cursor"""
        try:
            self.log_handler.info("在macOS上使用管理员权限关闭Cursor...")

            # 找到Cursor进程并关闭
            cmd = ['osascript', '-e', 'tell application "Cursor" to quit']
            subprocess.run(cmd, check=True)

            # 等待进程完全退出
            time.sleep(2)

            # 检查Cursor是否已关闭
            check_cmd = ['pgrep', 'Cursor']
            result = subprocess.run(check_cmd, capture_output=True)

            if result.returncode == 0:
                self.log_handler.warning("Cursor未能完全关闭，尝试强制关闭...")
                kill_cmd = ['pkill', '-9', 'Cursor']
                subprocess.run(kill_cmd)
                time.sleep(1)

            # 获取Cursor应用程序路径
            cursor_app_path = ""
            possible_paths = [
                "/Applications/Cursor.app",
                os.path.expanduser("~/Applications/Cursor.app")
            ]

            for path in possible_paths:
                if os.path.exists(path):
                    cursor_app_path = path
                    break

            if not cursor_app_path:
                self.log_handler.error("找不到Cursor应用程序路径")
                return False, ""

            return True, cursor_app_path

        except Exception as e:
            self.log_handler.error(f"退出Cursor时出错: {str(e)}")
            return False, ""

    async def reset_machine_id_macos(self):
        """在macOS系统上使用管理员权限重置设备ID"""
        try:
            self.log_handler.info("在macOS上使用管理员权限重置设备ID...")

            # 使用MachineIDResetter的reset_machine_ids方法
            # 但可能需要特殊处理以获取足够权限
            await reset_machine_id()

            return True
        except Exception as e:
            self.log_handler.error(f"重置设备ID时出错: {str(e)}")
            return False

    @staticmethod
    def get_verification_code():
        """等待用户输入验证码并返回

        Returns:
            str: 用户输入的验证码或None
        """
        logging.info("请求验证码输入...")

        if CursorProGUI._instance:
            logging.info("找到GUI实例，准备显示验证码输入区域")
            try:
                # 显示验证码输入区域
                CursorProGUI._instance.show_verification_dialog()
                # 等待用户输入
                if CursorProGUI._instance.worker:
                    logging.info("找到worker实例，准备获取验证码")
                    code = CursorProGUI._instance.worker.get_verification_code_from_ui()
                    return code
                else:
                    logging.error("未找到worker实例")
            except Exception as e:
                logging.error(f"获取验证码过程中出错: {str(e)}")
                import traceback
                logging.error(traceback.format_exc())
        else:
            logging.error("未找到GUI实例，无法显示验证码输入区域")
        return None

    # 添加确认登录的方法
    def confirm_login(self):
        """确认登录操作"""
        # 获取登录信息
        email = self.login_email_input.text().strip()
        password = self.login_password_input.text().strip()
        login_type = "password" if self.login_type_combo.currentIndex() == 0 else "code"

        # 验证输入
        if not email:
            self.log_handler.error("邮箱不能为空")
            return

        if login_type == "password" and not password:
            self.log_handler.error("密码不能为空")
            return

        self.log_handler.info(f"准备使用账号 {email} 登录")

        # 禁用执行按钮
        self.confirm_login_button.setEnabled(False)
        self.back_button.setEnabled(False)

        # 创建登录任务
        self.execute_task("login", {
            "device_reset_done": True,
            "email": email,
            "password": password if login_type == "password" else None,
            "login_type": login_type
        })

        # 完成后自动返回功能选择界面
        self.back_to_functions()

    def back_to_functions(self):
        """返回功能选择界面"""
        self.login_widget.setVisible(False)
        self.function_selection_widget.setVisible(True)

    def submit_verification_code(self):
        """提交验证码"""
        code = self.verification_code_input.text().strip()
        if code:
            self.worker.handle_verification_code(code)
            # 清空输入但不隐藏组件
            self.verification_code_input.clear()
            # 隐藏提交按钮直到有新输入
            self.verification_code_submit.setVisible(False)
            self.execute_function()
        else:
            self.log_handler.error("验证码不能为空")

    # 添加验证码输入检查方法
    def check_verification_code(self, text):
        """检查验证码输入并控制确认按钮显示"""
        login_type = "password" if self.login_type_combo.currentIndex() == 0 else "code"
        if login_type == "code" and text.strip():
            self.verification_code_submit.setVisible(True)
        else:
            self.verification_code_submit.setVisible(False)

    # 添加切换密码可见性的方法
    def toggle_password_visibility(self, index):
        """根据登录方式显示或隐藏密码框和相关控件"""
        if index == 0:  # 密码登录
            self.login_password_input.setVisible(True)
            self.login_password_label.setVisible(True)
            self.verification_code_label.setVisible(False)
            self.verification_code_input.setVisible(False)
            self.verification_code_submit.setVisible(False)
            # 密码登录时不需要显示登录按钮
            self.confirm_login_button.setVisible(False)
        else:  # 验证码登录
            self.login_password_input.setVisible(False)
            self.login_password_label.setVisible(False)
            self.verification_code_label.setVisible(True)
            self.verification_code_input.setVisible(True)
            self.verification_code_submit.setVisible(False)  # 初始不显示，等有输入时再显示
            self.confirm_login_button.setVisible(False)

    def clear_log(self):
        """清除日志内容"""
        self.log_text.clear()

    def check_version(self):
        """检查版本信息"""
        # 尝试调用check_version函数
        self.log_handler.info("正在检查版本...")
        try:
            # 捕获check_version函数的输出
            check_version()
            self.log_handler.info("版本检查完成")
        except Exception as e:
            self.log_handler.error(f"检查版本出错: {str(e)}")

    def show_verification_dialog(self):
        """显示验证码输入区域"""
        logging.info("显示验证码输入区域...")
        try:
            # 显示验证码输入区域
            self.verification_code_label.setVisible(True)
            self.verification_code_input.setVisible(True)
            self.verification_code_submit.setVisible(True)
            self.verification_code_submit.setEnabled(True)

            # 清空之前的输入
            self.verification_code_input.clear()

            # 给验证码输入框焦点
            self.verification_code_input.setFocus()

            self.log_handler.info("请在验证码输入框中输入您收到的验证码")

        except Exception as e:
            logging.error(f"显示验证码输入区域时出错: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())


if __name__ == "__main__":
    # 在应用启动前设置基本日志配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )

    # 创建一个测试日志记录器
    test_logger = logging.getLogger('test_logger')

    # 强制使用亮色模式，禁用暗色模式
    os.environ["QT_QPA_PLATFORM"] = "windows:darkmode=0"

    app = QApplication(sys.argv)

    # 设置应用样式为亮色Fusion主题
    app.setStyle("Fusion")

    # 强制使用亮色调色板
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
    palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Link, QColor(0, 0, 255))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)

    window = CursorProGUI()
    window.show()
    sys.exit(app.exec())
