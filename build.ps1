$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $root ".venv-build"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $python)) {
  python -m venv $venv
}

& $python -m pip install -r (Join-Path $root "requirements-build.txt")
& $python -m nuitka --onefile --windows-console-mode=disable --enable-plugin=tk-inter --output-dir=(Join-Path $root "release") --output-filename=nts-app.exe (Join-Path $root "main.py")
