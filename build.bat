@echo off

REM --- create venv if missing ---
if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)

set PYTHON=.venv\Scripts\python.exe

REM --- upgrade pip ---
%PYTHON% -m pip install --upgrade pip

REM --- install deps only if requirements.txt exists ---
if exist requirements.txt (
    echo Installing dependencies...
    %PYTHON% -m pip install -r requirements.txt
) else (
    echo requirements.txt not found, skipping dependencies
)

REM --- ensure pyinstaller ---
%PYTHON% -m pip install pyinstaller

REM --- build exe ---
%PYTHON% -m PyInstaller ^
    --onefile ^
    --noconsole ^
    -n nts-app ^
    --distpath release ^
    --workpath build ^
    --specpath build ^
    main.py

echo Build finished.