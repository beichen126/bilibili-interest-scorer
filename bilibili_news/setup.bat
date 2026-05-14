@echo off
chcp 65001 >nul
echo === bilibili_news 环境安装 ===
echo.

echo [1/3] 检查 Python...
python --version >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo 请先安装 Python: https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version

echo [2/3] 安装 bilibili-api-python...
pip install bilibili-api-python -q
echo 完成

echo [3/3] 创建数据目录...
if not exist data mkdir data
echo 完成

echo.
echo === 安装完成！===
echo.
echo 首次使用请先登录:
echo   python cli.py login
echo.
echo 获取个性化推荐:
echo   python cli.py recommend --full
echo.
echo 其他命令:
echo   python cli.py check     检查登录状态
echo   python cli.py hot       热门视频
echo   python cli.py list      列出已保存数据
echo.
pause
