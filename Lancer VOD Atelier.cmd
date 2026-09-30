@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" launch.py
) else (
  if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
    "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" launch.py
  ) else (
    py -3 launch.py
  )
)
if errorlevel 1 (
  echo.
  echo Le lancement a echoue. Python 3.12 et FFmpeg sont necessaires.
  pause
)
