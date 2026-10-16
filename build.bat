@echo off
REM Build NTS Calculator as a single Windows executable.
REM Thin wrapper around build.py — see build.py for the actual logic.
REM
REM Usage:
REM    build.bat                       full build, nts-app.exe (vcvars -> venv -> deps -> tests -> nuitka)
REM    build.bat /VARIANT reverse      full build, nts-app-reverse.exe (self-check GUI)
REM    build.bat /SKIP-TESTS           skip pytest sanity pass
REM    build.bat /ASSUME-YES           auto-accept Nuitka downloads (Dependency Walker)
REM    build.bat /CLEAN                remove .venv-build and release/ before building

setlocal

set "ARGS="
set "DO_CLEAN=0"
set "VARIANT=app"
:parseargs
if "%~1"=="" goto endparse
if /I "%~1"=="/VARIANT" (
    set "VARIANT=%~2"
    set "ARGS=%ARGS% --variant %~2"
    shift
)
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

if /I "%VARIANT%"=="reverse" (
    set "EXE_NAME=nts-app-reverse.exe"
) else (
    set "EXE_NAME=nts-app.exe"
)
if exist "release\%EXE_NAME%" (
    for %%F in ("release\%EXE_NAME%") do @echo [OK] %EXE_NAME%: %%~zF bytes
)

endlocal

