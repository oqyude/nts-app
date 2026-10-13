@echo off
REM Build NTS Calculator as a single Windows executable.
REM Thin wrapper around build.py — see build.py for the actual logic.
REM
REM Usage:
REM    build.bat                 full build (vcvars -> venv -> deps -> tests -> nuitka)
REM    build.bat /SKIP-TESTS    skip pytest sanity pass
REM    build.bat /ASSUME-YES    auto-accept Nuitka downloads (Dependency Walker)
REM    build.bat /CLEAN         remove .venv-build and release/ before building

setlocal

set "ARGS="
set "DO_CLEAN=0"
:parseargs
if "%~1"=="" goto endparse
if /I "%~1"=="/SKIP-TESTS" set "ARGS=%ARGS% --skip-tests"
if /I "%~1"=="/ASSUME-YES" set "ARGS=%ARGS% --assume-yes"
if /I "%~1"=="/CLEAN" set "DO_CLEAN=1"
if /I "%~1"=="/PYTHON" (
    shift
    set "ARGS=%ARGS% --python %~1"
)
shift
goto parseargs
:endparse

if "%DO_CLEAN%"=="1" (
    echo [clean] Removing .venv-build and release
    if exist .venv-build rmdir /s /q .venv-build
    if exist release rmdir /s /q release
)

python build.py %ARGS%
if errorlevel 1 exit /b 1

if exist "release\nts-app.exe" (
    for %%F in ("release\nts-app.exe") do @echo [OK] nts-app.exe: %%~zF bytes
)

endlocal

