#!/usr/bin/env python3
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
