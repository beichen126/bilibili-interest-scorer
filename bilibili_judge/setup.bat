@echo off
chcp 65001 >nul
echo === bilibili_judge 环境安装 ===
echo.
echo [1/3] 检查 Python...
python --version >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo 请先安装 Python: https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version
echo [2/3] 安装依赖...
pip install bilibili-api-python requests -q
echo 完成
echo [3/3] 创建数据目录...
if not exist data mkdir data
echo.
echo === 安装完成！===
echo.
echo 使用前需要先登录 bilibili_news:
echo   cd ..\bilibili_news
echo   python cli.py login
echo.
echo 然后回到本模块使用:
echo   cd ..\bilibili_judge
echo   python cli.py profile
echo   python cli.py config --api-key sk-xxx
echo   python cli.py judge ..\bilibili_news\data\recommend_xxx.json
echo.
pause
