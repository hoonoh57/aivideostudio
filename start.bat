@echo off
chcp 65001 >nul
title AIVideoStudio Launcher
color 0A

echo ╔══════════════════════════════════════════╗
echo ║       AIVideoStudio Launcher v1.0        ║
echo ╚══════════════════════════════════════════╝
echo.

cd /d D:\aivideostudio

:: ─── 1. Python check ───
echo [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.12+ from python.org
    pause
    exit /b 1
)
echo       Python OK

:: ─── 2. venv check & create ───
echo [2/5] Checking virtual environment...
if not exist ".venv\Scripts\activate.bat" (
    echo       Creating venv...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo       Installing dependencies...
    pip install --upgrade pip >nul
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
    pip install PyQt6 ffmpeg-python loguru appdirs psutil edge-tts python-mpv openai-whisper pysubs2 requests
    echo       Dependencies installed!
) else (
    call .venv\Scripts\activate.bat
    echo       venv OK
)

:: ─── 3. FFmpeg check ───
echo [3/5] Checking FFmpeg...
set FFMPEG_FOUND=0
if exist "D:\ffmpeg\bin\ffmpeg.exe" set FFMPEG_FOUND=1
where ffmpeg >nul 2>&1 && set FFMPEG_FOUND=1
if "%FFMPEG_FOUND%"=="0" (
    echo       WARNING: FFmpeg not found. Export may not work.
    echo       Download from https://www.gyan.dev/ffmpeg/builds/
) else (
    echo       FFmpeg OK
)

:: ─── 4. GPT-SoVITS server ───
echo [4/5] Checking GPT-SoVITS server...
set SOVITS_DIR=D:\GPT-SoVITS
set SOVITS_RUNNING=0

:: Check if server is already running on port 9880
curl -s http://127.0.0.1:9880/tts >nul 2>&1 && set SOVITS_RUNNING=1

if "%SOVITS_RUNNING%"=="1" (
    echo       GPT-SoVITS server already running
) else (
    if exist "%SOVITS_DIR%\runtime\python.exe" (
        if exist "%SOVITS_DIR%\api_v2.py" (
            echo       Starting GPT-SoVITS server in background...
            start "GPT-SoVITS Server" /min cmd /c "cd /d %SOVITS_DIR% && .\runtime\python api_v2.py -a 127.0.0.1 -p 9880"
            echo       Waiting for server startup...
            timeout /t 15 /nobreak >nul
            curl -s http://127.0.0.1:9880/tts >nul 2>&1
            if errorlevel 1 (
                echo       WARNING: Server may still be loading. TTS panel will show status.
            ) else (
                echo       GPT-SoVITS server started!
            )
        ) else (
            echo       GPT-SoVITS not installed. Edge-TTS will be used.
            echo       To install: download from huggingface.co/lj1995/GPT-SoVITS-windows-package
        )
    ) else (
        echo       GPT-SoVITS not installed. Edge-TTS will be used.
    )
)

:: ─── 5. Launch AIVideoStudio ───
echo [5/5] Starting AIVideoStudio...
echo.
echo ╔══════════════════════════════════════════╗
echo ║         Launching Application...         ║
echo ╚══════════════════════════════════════════╝
echo.

python -m aivideostudio.main

:: ─── Cleanup: stop GPT-SoVITS on exit ───
echo.
echo Shutting down...
curl -s "http://127.0.0.1:9880/control?command=exit" >nul 2>&1
echo Done. Press any key to close.
pause >nul
