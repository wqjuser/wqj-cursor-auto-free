#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import logging
import traceback

def setup_logging():
    """设置基本的日志系统，确保在GUI启动前捕获所有日志"""
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

def main():
    """启动GUI应用程序"""
    try:
        # 设置Qt环境变量来解决样式问题
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        os.environ["QT_SCALE_FACTOR"] = "1"
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
        
        # 首先设置日志系统
        setup_logging()
        
        # 添加当前目录到Python路径
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        # 导入GUI模块
        from cursor_gui import CursorProGUI, QApplication
        
        # 记录启动信息
        logging.info("启动Cursor Pro GUI应用")
        
        # 创建并启动应用
        app = QApplication(sys.argv)
        window = CursorProGUI()
        window.show()
        
        # 运行应用主循环
        sys.exit(app.exec())
        
    except Exception as e:
        # 捕获并记录所有未处理的异常
        error_msg = f"应用启动失败: {str(e)}\n{traceback.format_exc()}"
        logging.critical(error_msg)
        
        # 如果GUI已启动，则显示错误对话框
        try:
            from PyQt6.QtWidgets import QMessageBox
            error_dialog = QMessageBox()
            error_dialog.setIcon(QMessageBox.Icon.Critical)
            error_dialog.setWindowTitle("启动错误")
            error_dialog.setText("应用启动失败")
            error_dialog.setDetailedText(error_msg)
            error_dialog.exec()
        except:
            # 如果GUI无法显示错误对话框，则在控制台显示错误
            print(error_msg)
        
        sys.exit(1)

if __name__ == "__main__":
    main() 