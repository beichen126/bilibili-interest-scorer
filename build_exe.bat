@echo off
chcp 65001 >nul
echo === B站工具箱 打包脚本 ===
echo.

cd /d "%~dp0"

pyinstaller --onefile --noconsole ^
    --name "B站工具箱" ^
    --add-data "bilibili_news;bilibili_news" ^
    --add-data "bilibili_judge;bilibili_judge" ^
    --collect-all bilibili_api ^
    --hidden-import requests ^
    --hidden-import bilibili_news ^
    --hidden-import bilibili_judge ^
    --hidden-import config ^
    --noconfirm ^
    gui.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] 打包成功！
    echo 输出: dist\B站工具箱.exe
) else (
    echo.
    echo [失败] 打包出错，请检查上面的日志
)

pause
