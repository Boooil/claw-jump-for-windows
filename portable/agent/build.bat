@echo off
echo === Claw Jump Agent - PyInstaller Build ===
echo.

REM Check pyinstaller
where pyinstaller >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Installing PyInstaller + dependencies...
    pip install pyinstaller pystray Pillow
)

echo.
echo Building claw-jump-agent.exe...

pyinstaller --onefile --noconsole --name claw-jump-agent ^
  --icon claw.ico ^
  --add-data "spinner_verbs_filtered.txt;." ^
  --hidden-import tkinter ^
  --hidden-import pystray ^
  --hidden-import PIL ^
  --hidden-import PIL.Image ^
  --hidden-import PIL.ImageDraw ^
  --exclude-module numpy ^
  --exclude-module scipy ^
  --exclude-module pandas ^
  --exclude-module matplotlib ^
  --exclude-module jupyter ^
  --exclude-module IPython ^
  claw_jump_agent.py

if %ERRORLEVEL% equ 0 (
    echo.
    echo === Build successful! ===
    echo Output: dist\claw-jump-agent.exe
    dir dist\claw-jump-agent.exe
) else (
    echo.
    echo === Build FAILED ===
    exit /b 1
)
