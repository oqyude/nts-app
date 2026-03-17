@echo off
setlocal

set ROOT=%~dp0
set VENV=%ROOT%.venv-build
set PYTHON=%VENV%\Scripts\python.exe

if not exist "%PYTHON%" (
  python -m venv "%VENV%"
)

"%PYTHON%" -m pip install -r "%ROOT%requirements-build.txt"
"%PYTHON%" -m nuitka --onefile --windows-console-mode=disable --enable-plugin=tk-inter --output-dir="%ROOT%release" --output-filename=nts-app.exe "%ROOT%main.py"
endlocal
