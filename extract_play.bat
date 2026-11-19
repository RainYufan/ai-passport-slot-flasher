@echo off
chcp 65001 >nul
cd /d "%~dp0"
set /p URL=请输入玩法链接(回车提交): 
if "%URL%"=="" (
  echo 没有输入链接。
  pause
  exit /b 1
)
python extract_play.py "%URL%"
if errorlevel 1 (
  echo.
  echo 若提示 python 不是内部或外部命令,请先安装 Python 3:
  echo   https://www.python.org/downloads/
)
echo.
pause
