import os
import sys
import subprocess

def install_dependencies():
    """安装运行GUI所需的依赖"""
    print("正在安装必要的依赖...")
    
    # 要安装的依赖列表
    dependencies = [
        "PyQt6",
        "requests",
        "psutil",
        "asyncio"
    ]
    
    # 使用pip安装
    for dep in dependencies:
        print(f"正在安装 {dep}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
            print(f"{dep} 安装成功!")
        except Exception as e:
            print(f"{dep} 安装失败: {str(e)}")
    
    print("\n所有依赖安装完成!")
    print("现在您可以运行 'python cursor_gui.py' 启动GUI界面")

if __name__ == "__main__":
    install_dependencies()
    input("\n按回车键退出...") 