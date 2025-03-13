#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import logging
import traceback
import platform
from PyQt6.QtCore import Qt
import time

def setup_logging():
    """设置基本的日志系统，确保在GUI启动前捕获所有日志"""
    try:
        # 确保logs目录存在
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 配置日志系统
        log_file = os.path.join(log_dir, "cursor_gui.log")
        
        # 创建基本的日志配置
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        # 捕获未处理的异常
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
            else:
                logging.error("未捕获的异常:", exc_info=(exc_type, exc_value, exc_traceback))
        
        sys.excepthook = handle_exception
        
    except Exception as e:
        print(f"设置日志系统时出错: {str(e)}")
        traceback.print_exc()

def main():
    """启动GUI应用程序"""
    try:
        # 获取应用程序包的路径
        if getattr(sys, 'frozen', False):
            # 如果是打包后的应用
            application_path = os.path.dirname(sys.executable)
            if platform.system() == 'Darwin':
                # macOS下需要特殊处理路径
                application_path = os.path.normpath(os.path.join(
                    application_path,
                    '..',
                    'Resources'
                ))
        else:
            # 如果是开发环境
            application_path = os.path.dirname(os.path.abspath(__file__))

        # 切换到正确的工作目录
        os.chdir(application_path)
        
        # 设置Qt环境变量来解决样式问题
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        os.environ["QT_SCALE_FACTOR"] = "1"
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
        
        # macOS特定设置
        if platform.system() == 'Darwin':
            os.environ["QT_MAC_WANTS_LAYER"] = "1"
            os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
            os.environ["QT_MAC_WANTS_WINDOW"] = "1"
            os.environ["QT_MAC_WANTS_FOCUS"] = "1"
            os.environ["QT_MAC_WANTS_ACTIVATE"] = "1"
            
            # 设置PATH环境变量
            os_path = os.environ.get('PATH', '')
            if '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin' not in os_path:
                os.environ['PATH'] = '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:' + os_path
        
        # 首先设置日志系统
        setup_logging()
        
        # 添加应用程序路径到Python路径
        if application_path not in sys.path:
            sys.path.insert(0, application_path)
        
        # 记录启动信息
        logging.info(f"启动Cursor Pro GUI应用")
        logging.info(f"应用程序路径: {application_path}")
        logging.info(f"当前工作目录: {os.getcwd()}")
        logging.info(f"Python路径: {sys.path}")
        
        # 导入GUI模块
        from cursor_gui import CursorProGUI, QApplication
        
        # 创建并启动应用
        app = QApplication(sys.argv)
        
        # macOS特定设置
        if platform.system() == 'Darwin':
            app.setQuitOnLastWindowClosed(False)  # 防止最后一个窗口关闭时退出应用
            
            # 设置应用程序名称
            app.setApplicationName("Cursor Pro GUI")
            app.setApplicationDisplayName("Cursor Pro GUI")
            
            # 确保应用程序在Dock中显示
            app.setProperty("DOCK_ICON_VISIBLE", True)
        
        # 创建主窗口
        window = CursorProGUI()
        
        # 显示窗口并确保它在最前面
        window.show()
        window.raise_()
        window.activateWindow()
        
        # 运行应用主循环
        return app.exec()
        
    except Exception as e:
        logging.error(f"启动GUI时出错: {str(e)}")
        logging.error(traceback.format_exc())
        
        # 在控制台显示错误信息
        print(f"\n程序启动失败: {str(e)}")
        print("\n详细错误信息:")
        traceback.print_exc()
        
        # 如果是打包后的应用，保存错误日志到桌面
        if getattr(sys, 'frozen', False):
            desktop_path = os.path.expanduser("~/Desktop")
            error_log_path = os.path.join(desktop_path, "cursor_pro_error.log")
            try:
                with open(error_log_path, "w", encoding="utf-8") as f:
                    f.write(f"启动失败时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"错误信息: {str(e)}\n")
                    f.write("\n详细错误信息:\n")
                    f.write(traceback.format_exc())
            except:
                pass
        
        return 1

if __name__ == "__main__":
    sys.exit(main()) 