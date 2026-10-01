@echo off
chcp 65001 >nul
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Installer.ps1" %*
if errorlevel 1 (
  echo.
  echo Installation interrompue. Consulte Installation\installation.log puis relance ce fichier.
) else (
  echo.
  echo Installation terminee. Ouvre VOD Atelier.exe.
)
pause
