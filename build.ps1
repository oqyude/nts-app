$ErrorActionPreference = "Stop"

# Thin wrapper around build.py — see build.py for the actual build logic.
# Usage:
#   .\build.ps1                              full build (vcvars -> venv -> deps -> tests -> nuitka)
#   .\build.ps1 -SkipTests                   skip pytest sanity pass
#   .\build.ps1 -AssumeYes                   auto-accept Nuitka downloads (Dependency Walker)
#   .\build.ps1 -Clean                       remove .venv-build and release/ before building
#   .\build.ps1 -Python C:\path\to\python.exe build with a different Python

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($Clean) {
    Write-Host "[clean] Removing .venv-build and release"
    foreach ($d in @("$root\.venv-build", "$root\release")) {
        if (Test-Path $d) { Remove-Item -Recurse -Force $d }
    }
}

$args = @()
if ($SkipTests) { $args += "--skip-tests" }
if ($AssumeYes) { $args += "--assume-yes" }
if ($Python)   { $args += @("--python", $Python) }

python (Join-Path $root "build.py") @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$exePath = Join-Path $root "release\nts-app.exe"
if (Test-Path $exePath) {
    $size = (Get-Item $exePath).Length
    Write-Host ("[OK] nts-app.exe: {0} bytes" -f $size)
}
