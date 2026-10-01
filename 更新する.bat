@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

where py > nul 2>&1
if not errorlevel 1 goto use_py
where python > nul 2>&1
if not errorlevel 1 goto use_python

echo Python が見つかりません。
echo Microsoft Store で「Python」を検索してインストールしてから、もう一度実行してください。
goto end

:use_py
py build.py
goto end

:use_python
python build.py

:end
echo.
pause
