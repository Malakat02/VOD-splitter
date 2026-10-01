@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "VOD Atelier.exe" (
  powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "Installation\Installer.ps1" -Mode Application
  if errorlevel 1 (
    echo Le lancement a echoue. Consulte Installation\installation.log.
    pause
    exit /b 1
  )
)
start "" "%~dp0VOD Atelier.exe"
