@echo off
echo ======================================
echo Cursor Pro 启动脚本
echo ======================================
echo.
echo 正在启动程序...
echo.

REM 检查CursorPro.exe是否存在
if exist "CursorPro.exe" (
    echo 找到主程序: CursorPro.exe
    echo 正在启动...
    echo.
    CursorPro.exe
) else if exist "dist\windows\CursorPro.exe" (
    echo 找到主程序: dist\windows\CursorPro.exe
    echo 正在启动...
    echo.
    dist\windows\CursorPro.exe
) else if exist "dist\win32\CursorPro.exe" (
    echo 找到主程序: dist\win32\CursorPro.exe
    echo 正在启动...
    echo.
    dist\win32\CursorPro.exe
) else if exist "dist\CursorPro.exe" (
    echo 找到主程序: dist\CursorPro.exe
    echo 正在启动...
    echo.
    dist\CursorPro.exe
) else (
    echo 错误: 找不到CursorPro.exe
    echo 请确保在正确的目录中运行此脚本
)

echo.
echo 程序已退出
echo 按任意键关闭此窗口...
pause > nul 