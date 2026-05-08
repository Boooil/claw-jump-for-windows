#!/usr/bin/env bash
set -euo pipefail

echo "=== Claw Jump Agent - PyInstaller Build ==="
echo ""

# Platform-specific settings
case "$(uname -s)" in
    Darwin)
        WINDOWED_FLAG="--windowed"
        EXE_NAME="claw-jump-agent"
        SEP=":"
        ;;
    Linux)
        WINDOWED_FLAG="--windowed"
        EXE_NAME="claw-jump-agent"
        SEP=":"
        ;;
    MINGW*|MSYS*|CYGWIN*)
        WINDOWED_FLAG="--noconsole"
        EXE_NAME="claw-jump-agent.exe"
        SEP=";"
        ;;
    *)
        echo "Unsupported platform: $(uname -s)"
        exit 1
        ;;
esac

# Check pyinstaller
if ! command -v pyinstaller &>/dev/null; then
    echo "Installing PyInstaller + dependencies..."
    pip install pyinstaller pystray Pillow
fi

echo ""
echo "Building ${EXE_NAME}..."

pyinstaller --onefile $WINDOWED_FLAG --name claw-jump-agent \
  --icon claw.ico \
  --add-data "spinner_verbs_filtered.txt${SEP}." \
  --hidden-import tkinter \
  --hidden-import pystray \
  --hidden-import PIL \
  --hidden-import PIL.Image \
  --hidden-import PIL.ImageDraw \
  --exclude-module numpy \
  --exclude-module scipy \
  --exclude-module pandas \
  --exclude-module matplotlib \
  --exclude-module jupyter \
  --exclude-module IPython \
  claw_jump_agent.py

echo ""
echo "=== Build successful! ==="
echo "Output: dist/${EXE_NAME}"
ls -lh "dist/${EXE_NAME}"
