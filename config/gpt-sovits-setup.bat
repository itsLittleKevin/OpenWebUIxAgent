@echo off
REM GPT-SoVITS Setup Script
REM Installs all dependencies into venv_tts for GPT-SoVITS

setlocal enabledelayexpansion
set "SOVITS_DIR=%~dp0..\vendor\gpt-sovits"
set "VENV_DIR=%SOVITS_DIR%\venv_tts"

if not exist "%SOVITS_DIR%" (
    echo ERROR: GPT-SoVITS not found at %SOVITS_DIR%
    pause
    exit /b 1
)

echo.
echo ========================================
echo   GPT-SoVITS Dependency Installer
echo ========================================
echo.

if not exist "%VENV_DIR%" (
    echo Creating Python virtual environment...
    echo.
    cd /d "%SOVITS_DIR%"
    python -m venv venv_tts
    if %ERRORLEVEL% NEQ 0 (
        echo ERROR: Failed to create venv_tts
        pause
        exit /b 1
    )
)

echo Installing requirements into %VENV_DIR%
echo This may take 5-15 minutes on first run...
echo.

REM Activate venv and install
cd /d "%SOVITS_DIR%"
call venv_tts\Scripts\activate.bat
pip install -r requirements.txt

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo   Installation Complete!
    echo ========================================
    echo.
    echo You can now run:
    echo   .\gpt-sovits-launch.ps1
    echo.
) else (
    echo.
    echo ========================================
    echo   Installation Failed
    echo ========================================
    echo.
    echo Check the errors above and try again.
    echo.
)

pause
