$ErrorActionPreference = "Stop"

# Thin wrapper around build.py — see build.py for the actual build logic.
# Usage:
#   .\build.ps1                              full build, nts-app.exe (vcvars -> venv -> deps -> tests -> nuitka)
#   .\build.ps1 -Variant reverse             full build, nts-app-reverse.exe (self-check GUI)
#   .\build.ps1 -SkipTests                   skip pytest sanity pass
#   .\build.ps1 -AssumeYes                   auto-accept Nuitka downloads (Dependency Walker)
#   .\build.ps1 -Clean                       remove .venv-build and release/ before building
#   .\build.ps1 -Python C:\path\to\python.exe build with a different Python

param(
    [switch]$SkipTests,
    [switch]$AssumeYes,
    [switch]$Clean,
    [string]$Variant = "app",
    [string]$Python
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($Clean) {
    Write-Host "[clean] Removing .venv-build and release"
    foreach ($d in @("$root\.venv-build", "$root\release")) {
        if (Test-Path $d) { Remove-Item -Recurse -Force $d }
    }
}

$args = @()
if ($Variant -ne "app") { $args += @("--variant", $Variant) }
if ($SkipTests) { $args += "--skip-tests" }
if ($AssumeYes) { $args += "--assume-yes" }
if ($Python)   { $args += @("--python", $Python) }

python (Join-Path $root "build.py") @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$exeName = if ($Variant -eq "reverse") { "nts-app-reverse.exe" } else { "nts-app.exe" }
$exePath = Join-Path $root "release\$exeName"
if (Test-Path $exePath) {
    $size = (Get-Item $exePath).Length
    Write-Host ("[OK] {0}: {1} bytes" -f $exeName, $size)
}
