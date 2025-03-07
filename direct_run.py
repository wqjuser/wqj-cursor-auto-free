#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cursor Pro 直接启动脚本
此脚本直接运行主程序，不使用PyInstaller打包
"""

import os
import sys
import subprocess
import time
import traceback

def main():
    """主函数"""
    try:
        # 清屏
        os.system("cls" if os.name == "nt" else "clear")
        
        # 打印启动信息
        print("=" * 60)
        print("Cursor Pro 直接启动脚本".center(60))
        print("=" * 60)
        print("正在启动主程序...\n")
        
        # 获取主程序路径
        app_dir = os.path.dirname(os.path.abspath(__file__))
        main_script = os.path.join(app_dir, "cursor_pro_keep_alive.py")
        
        if not os.path.exists(main_script):
            print(f"错误: 找不到主程序脚本: {main_script}")
            return
        
        # 创建日志目录
        log_dir = os.path.join(app_dir, "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 启动主程序
        print(f"启动命令: {sys.executable} {main_script}")
        
        # 使用subprocess运行主程序
        process = subprocess.Popen(
            [sys.executable, main_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
        )
        
        print("主程序已启动，正在等待程序结束...\n")
        
        # 等待程序结束
        stdout, stderr = process.communicate()
        
        # 检查程序是否正常退出
        if process.returncode != 0:
            print(f"\n程序异常退出，返回码: {process.returncode}")
            if stderr:
                print("\n错误信息:")
                print(stderr)
            
            # 保存错误日志
            log_file = os.path.join(log_dir, f"error_{int(time.time())}.log")
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"返回码: {process.returncode}\n\n")
                f.write("标准输出:\n")
                f.write(stdout)
                f.write("\n\n标准错误:\n")
                f.write(stderr)
            
            print(f"\n错误日志已保存到: {log_file}")
        else:
            print("\n程序正常退出")
            if stdout:
                print("\n程序输出:")
                print(stdout)
        
    except Exception as e:
        print(f"\n启动器发生错误: {str(e)}")
        traceback.print_exc()
    
    finally:
        # 确保窗口不会立即关闭
        print("\n" + "=" * 60)
        input("按回车键退出...")

if __name__ == "__main__":
    main() 