import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QPushButton, QLabel, QStackedWidget, QFrame,
                            QHBoxLayout, QSpacerItem, QSizePolicy, QComboBox,
                            QTextEdit, QScrollArea)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QFont, QPalette, QColor, QTextCursor
import cursor_pro_keep_alive as main_logic
import asyncio
import logging
import queue
from threading import Thread, Lock
import time

# 创建一个全局的日志队列
log_queue = queue.Queue()

class StreamToLogger:
    def __init__(self, log_signal):
        self.log_signal = log_signal

    def write(self, text):
        if text.strip():  # 只处理非空文本
            self.log_signal.log_signal.emit(text.strip())

    def flush(self):
        pass

class ModernButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(40)
        self.setFont(QFont("Microsoft YaHei", 10))
        self.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
        """)

class ModernLabel(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Microsoft YaHei", 12))
        self.setStyleSheet("color: #333333;")

class ModernFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 10px;
                border: 1px solid #E0E0E0;
            }
        """)

class ModernComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Microsoft YaHei", 10))
        self.setStyleSheet("""
            QComboBox {
                border: 1px solid #E0E0E0;
                border-radius: 5px;
                padding: 5px;
                background-color: white;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: url(down_arrow.png);
                width: 12px;
                height: 12px;
            }
        """)

class LogTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Microsoft YaHei", 10))
        self.setReadOnly(True)
        self.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #E0E0E0;
                border-radius: 5px;
                padding: 10px;
            }
        """)

class QTextEditLogger(logging.Handler):
    def __init__(self, parent):
        super().__init__()
        self.widget = LogTextEdit(parent)
        self.widget.setReadOnly(True)

    def emit(self, record):
        msg = self.format(record)
        self.widget.append(msg)
        self.widget.moveCursor(QTextCursor.MoveOperation.End)

# 创建一个自定义的日志处理器
class GuiLogHandler(logging.Handler):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    def emit(self, record):
        msg = self.format(record)
        self.signal.log_signal.emit(msg)

# 创建一个信号类
class LogSignal(QObject):
    log_signal = pyqtSignal(str)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cursor 工具")
        self.setMinimumSize(1200, 800)
        
        # 创建日志信号
        self.log_signal = LogSignal()
        self.log_signal.log_signal.connect(self.update_log)
        
        # 重定向标准输出和标准错误到GUI
        sys.stdout = StreamToLogger(self.log_signal)
        sys.stderr = StreamToLogger(self.log_signal)
        
        # 设置窗口样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F5F5F5;
            }
        """)
        
        # 创建主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # 创建标题
        title = ModernLabel("Cursor 工具")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        title.setStyleSheet("color: #1976D2; margin: 20px;")
        main_layout.addWidget(title)
        
        # 创建内容区域
        content_layout = QHBoxLayout()
        
        # 左侧功能区
        left_frame = ModernFrame()
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(15)
        
        # 功能选择下拉框
        function_label = ModernLabel("功能")
        left_layout.addWidget(function_label)
        
        self.function_combo = ModernComboBox()
        self.function_combo.addItems([
            "一键注册并且享用Cursor",
            "仅仅修改文件或设备信息",
            "恢复原始文件或设备信息",
            "重置设备并登录已有账号",
            "重置设备并直接替换账号",
            "随机批量注册账号"
        ])
        left_layout.addWidget(self.function_combo)
        
        # 功能描述
        description_label = ModernLabel("功能描述")
        left_layout.addWidget(description_label)
        
        self.description_text = QTextEdit()
        self.description_text.setReadOnly(True)
        self.description_text.setFont(QFont("Microsoft YaHei", 10))
        self.description_text.setStyleSheet("""
            QTextEdit {
                background-color: #F8F9FA;
                border: 1px solid #E0E0E0;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        left_layout.addWidget(self.description_text)
        
        # 执行按钮
        execute_button = ModernButton("执行")
        execute_button.clicked.connect(self.execute_function)
        left_layout.addWidget(execute_button)
        
        content_layout.addWidget(left_frame, 1)
        
        # 右侧日志区域
        right_frame = ModernFrame()
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(20, 20, 20, 20)
        
        log_label = ModernLabel("日志显示区域")
        right_layout.addWidget(log_label)
        
        # 创建日志文本框
        self.log_text = LogTextEdit()
        right_layout.addWidget(self.log_text)
        
        # 设置日志处理器
        self.setup_logger()
        
        content_layout.addWidget(right_frame, 2)
        main_layout.addLayout(content_layout)
        
        # 添加底部信息
        footer = ModernLabel("© 2024 Cursor Tool")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: #666666; margin-top: 20px;")
        main_layout.addWidget(footer)
        
        # 设置窗口图标
        self.setWindowIcon(QIcon("icon.png"))
        
        # 连接功能选择信号
        self.function_combo.currentIndexChanged.connect(self.update_description)
        self.update_description()

    def setup_logger(self):
        # 创建日志处理器
        gui_handler = GuiLogHandler(self.log_signal)
        gui_handler.setFormatter(logging.Formatter('%(message)s'))
        
        # 获取根日志记录器
        logger = logging.getLogger()
        
        # 移除所有现有的处理器
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # 添加GUI处理器
        logger.addHandler(gui_handler)
        logger.setLevel(logging.INFO)
        
        # 设置主程序的日志处理器
        main_logger = logging.getLogger('cursor_pro_keep_alive')
        for handler in main_logger.handlers[:]:
            main_logger.removeHandler(handler)
        main_logger.addHandler(gui_handler)
        main_logger.setLevel(logging.INFO)
        
        # 禁用主程序的文件日志
        main_logger.propagate = True

    def update_log(self, message):
        if message.strip():  # 只处理非空消息
            self.log_text.append(message)
            # 确保光标在最后
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log_text.setTextCursor(cursor)
            # 滚动到最新内容
            scrollbar = self.log_text.verticalScrollBar()
            if scrollbar:
                scrollbar.setValue(scrollbar.maximum())
            QApplication.processEvents()

    def update_description(self):
        descriptions = {
            0: "一键完成Cursor账号注册和配置过程，让你快速开始使用Cursor。",
            1: "仅修改必要的文件和设备信息，不进行账号操作。",
            2: "将所有文件和设备信息恢复到原始状态。",
            3: "重置设备信息后，使用已有账号登录Cursor。",
            4: "重置设备信息并自动替换当前账号。",
            5: "自动批量注册多个Cursor账号。"
        }
        current_index = self.function_combo.currentIndex()
        self.description_text.setText(descriptions.get(current_index, ""))
    
    async def run_async_function(self, func, *args):
        try:
            # 清空日志显示
            self.log_text.clear()
            await func(*args)
        except Exception as e:
            logging.error(f"执行异步函数时出错: {str(e)}")
    
    def execute_function(self):
        functions = [
            self.register_and_use,
            self.modify_device_info,
            self.restore_device_info,
            self.reset_and_login,
            self.reset_and_replace,
            self.batch_register
        ]
        current_index = self.function_combo.currentIndex()
        if 0 <= current_index < len(functions):
            functions[current_index]()
    
    def register_and_use(self):
        asyncio.run(self.run_async_function(main_logic.main))
    
    def modify_device_info(self):
        asyncio.run(self.run_async_function(main_logic.main, 2))
    
    def restore_device_info(self):
        asyncio.run(self.run_async_function(main_logic.main, 3))
    
    def reset_and_login(self):
        asyncio.run(self.run_async_function(main_logic.main, 4))
    
    def reset_and_replace(self):
        asyncio.run(self.run_async_function(main_logic.main, 5))
    
    def batch_register(self):
        asyncio.run(self.run_async_function(main_logic.main, 6))

def main():
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle("Fusion")
    
    # 创建并显示主窗口
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 