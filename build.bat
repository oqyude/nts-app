@echo off
setlocal

set ROOT=%~dp0
set VENV=%ROOT%.venv-build
set PYTHON=%VENV%\Scripts\python.exe

if not exist "%PYTHON%" (
  python -m venv "%VENV%"
)

"%PYTHON%" -m pip install -r "%ROOT%requirements-build.txt"
"%PYTHON%" -m nuitka --onefile --windows-disable-console --enable-plugin=tk-inter --output-dir="%ROOT%release" --output-filename=nts-app.exe "%ROOT%main.py"

if "%NTS_USE_UPX%"=="1" (
  where upx >nul 2>nul
  if not errorlevel 1 (
    upx -9 "%ROOT%release\nts-app.exe"
  )
)
endlocal
