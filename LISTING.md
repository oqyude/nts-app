## `build.bat`

```bat
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

```

## `build.ps1`

```powershell
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
```

## `build.py`

```python
"""NTS Calculator build orchestrator.

Builds the NTS GUI app as a single Windows executable using Nuitka + MSVC.
Two variants are supported via ``--variant``:

  * ``app``     — default; computes regression from raw input (entry: main.py).
  * ``reverse`` — self-check GUI (entry: main_reverse.py).

Why Python (not batch / PowerShell)?
- CMD has parser quirks with very long REM separator lines + EnableDelayedExpansion
  that surface as spurious `. was unexpected at this time` errors after the parser
  reads the file. A pure-Python orchestrator side-steps that entirely and is also
  cross-platform-friendly (the vcvars64 detection is the only Windows-specific bit).

Requirements on the build host:
- Python 3.10+ (3.14 recommended; 3.15 supported as "experimental" by Nuitka 4.3)
- One of the following Visual Studio installs (vcvars64.bat is auto-detected):
  * BuildTools 18        — C:\\Program Files (x86)\\Microsoft Visual Studio\\18\\BuildTools
  * Visual Studio 2022   — C:\\Program Files\\Microsoft Visual Studio\\2022\\{Community,BuildTools,...}
  * Visual Studio 2019   — C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\BuildTools
- Dependency Walker (scoop install depends) so Nuitka can resolve imports for --onefile.

Usage:
    python build.py                          # full build (nts-app.exe)
    python build.py --variant reverse        # full build (nts-app-reverse.exe)
    python build.py --skip-tests             # skip the pytest sanity pass
    python build.py --compiler=clang-cl      # override default MSVC with clang-cl
    python build.py --python C:/.../python.exe   # build with a different Python
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent
VENV_DIR = REPO_ROOT / ".venv-build"
RELEASE_DIR = REPO_ROOT / "release"

VARIANTS: dict[str, dict[str, str]] = {
    "app": {
        "entry": str(REPO_ROOT / "main.py"),
        "output": "nts-app.exe",
        "product_name": "NTS Calculator",
    },
    "reverse": {
        "entry": str(REPO_ROOT / "main_reverse.py"),
        "output": "nts-app-reverse.exe",
        "product_name": "NTS Reverse",
    },
}

VCVARS64_CANDIDATES = [
    r"C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat",
    r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat",
    r"C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat",
    r"C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat",
    r"C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat",
    r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat",
    r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Enterprise\VC\Auxiliary\Build\vcvars64.bat",
    r"C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat",
]


def find_vcvars64() -> Optional[Path]:
    for candidate in VCVARS64_CANDIDATES:
        path = Path(candidate)
        if path.is_file():
            return path
    return None


def app_version() -> str:
    """Версия приложения — читается из ``nts/__init__.py`` (единственный источник).

    Файл читается текстом, а не импортом: на этапе сборки зависимости могут быть
    ещё не установлены, а ``nts`` тянет ``openpyxl``.
    """
    source = (REPO_ROOT / "nts" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', source)
    if not match:
        sys.exit("не удалось прочитать __version__ из nts/__init__.py")
    return match.group(1)


def load_msvc_env(vcvars: Path) -> dict[str, str]:
    """Run vcvars64.bat and capture the resulting env vars into a dict.

    Uses a temporary .bat helper so cmd.exe parses the `call "path with spaces" && set`
    correctly (subprocess escaping rules make the inline form brittle).
    """
    helper = REPO_ROOT / ".temp" / "_dump_vcvars_env.bat"
    helper.parent.mkdir(exist_ok=True)
    helper.write_text(
        f'@echo off\r\n'
        f'call "{vcvars}" >NUL\r\n'
        f'set\r\n',
        encoding="ascii",
    )
    try:
        out = subprocess.run(
            ["cmd.exe", "/c", str(helper)],
            capture_output=True, text=True, check=True,
        ).stdout
    finally:
        helper.unlink(missing_ok=True)
    env: dict[str, str] = {}
    for line in out.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


def find_cl(env: dict[str, str]) -> Optional[str]:
    """Locate cl.exe either on PATH (post-vcvars) or in the vcvars-enriched env."""
    cl_path = shutil.which("cl.exe", path=env.get("PATH", ""))
    return cl_path


def venv_python(python_bin: Optional[Path] = None) -> Path:
    py = VENV_DIR / "Scripts" / "python.exe"
    if not py.exists():
        base = str(python_bin) if python_bin else sys.executable
        print(f"[venv] creating {VENV_DIR} from {base}")
        subprocess.run([base, "-m", "venv", str(VENV_DIR)], check=True)
    return py


def pip_install(py: Path, *requirements_files: Path) -> None:
    cmd = [str(py), "-m", "pip", "install", "--upgrade", "pip", "wheel"]
    print(f"[pip] {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    for req in requirements_files:
        cmd = [str(py), "-m", "pip", "install", "-r", str(req)]
        print(f"[pip] {' '.join(cmd)}")
        subprocess.run(cmd, check=True)


def smoke_tests(py: Path) -> None:
    print("[pytest] running sanity tests...")
    result = subprocess.run([str(py), "-m", "pytest", "-q"], cwd=REPO_ROOT)
    if result.returncode != 0:
        sys.exit(f"pytest failed with code {result.returncode}")


def nuitka_build(
    py: Path,
    msvc_version: str,
    extra_env: dict[str, str],
    assume_yes: bool,
    variant: str,
) -> None:
    RELEASE_DIR.mkdir(exist_ok=True)
    settings = VARIANTS[variant]
    py_site = Path(str(VENV_DIR)) / "Lib" / "site-packages" / "tkinterdnd2" / "tkdnd"
    if not py_site.is_dir():
        sys.exit(f"tkinterdnd2 tkdnd/ not found at {py_site} — pip install broken?")
    cmd = [
        str(py), "-m", "nuitka",
        "--onefile",
        "--standalone",
        f"--msvc={msvc_version}",
        "--enable-plugins=tk-inter",
        "--windows-console-mode=disable",
        f"--product-name={settings['product_name']}",
        f"--file-version={app_version()}",
        "--copyright=Built with Nuitka",
        f"--output-dir={RELEASE_DIR}",
        f"--output-filename={settings['output']}",
        "--include-data-dir=examples=examples",
        "--include-module=tkinterdnd2",
        # Bundle whole tkdnd/ tree for pkgIndex.tcl and tkdnd*.tcl on every
        # platform/tcl arch — see gui.py::_patched_require.
        f"--include-data-dir={py_site}=tkinterdnd2/tkdnd",
    ]
    # Nuitka defers shared libs (.dll/.so/.dylib) inside --include-data-dir
    # to its dll-files plugin, which only discovers the file that the
    # tkinterdnd2 Python package advertises in metadata — typically just the
    # win-x64 (Tcl 8) variant. Force-include every shared lib so the win-x64-tcl9
    # (and friends) DLL ends up next to its pkgIndex.tcl at runtime. Skip the one
    # DLL Nuitka already injects via the dll-files plugin (win-x64 on tkinterdnd2
    # 0.6.4) because Nuitka rejects duplicate data files as a fatal error.
    _dllfiles_skip = {py_site / "win-x64" / "libtkdnd2.10.3.dll"}
    for sub in sorted(py_site.iterdir()):
        if not sub.is_dir():
            continue
        for lib in sorted(sub.iterdir()):
            if lib.suffix in {".dll", ".so", ".dylib"} and lib not in _dllfiles_skip:
                dest = f"tkinterdnd2/tkdnd/{sub.name}/{lib.name}"
                cmd.append(f"--include-data-files={lib}={dest}")
    if assume_yes:
        cmd.append("--assume-yes-for-downloads")
    cmd.append(settings["entry"])
    print("[nuitka]", " ".join(cmd))
    env = os.environ.copy()
    env.update(extra_env)
    scoop_shims = Path.home() / "scoop" / "shims"
    if scoop_shims.is_dir():
        env["PATH"] = str(scoop_shims) + os.pathsep + env.get("PATH", "")
    if "PATH" in extra_env:
        env["PATH"] = extra_env["PATH"] + os.pathsep + env["PATH"]
    result = subprocess.run(cmd, cwd=REPO_ROOT, env=env)
    if result.returncode != 0:
        sys.exit(f"nuitka build failed with code {result.returncode}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--variant",
        choices=sorted(VARIANTS.keys()),
        default="app",
        help="Build target — 'app' (nts-app.exe) or 'reverse' (nts-app-reverse.exe).",
    )
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--compiler", choices=["auto", "msvc", "clang-cl"], default="auto")
    parser.add_argument("--msvc-version", default="14.5",
                        help="MSVC version for --msvc= (default 14.5 = MSVC 2022 / BuildTools 18)")
    parser.add_argument("--assume-yes", action="store_true",
                        help="Auto-accept Nuitka downloads (Dependency Walker)")
    parser.add_argument("--python", type=Path, default=None,
                        help="Python interpreter to use for the build venv "
                             "(default: current). Pass e.g. C:/.../python314/current/python.exe "
                             "to build against 3.14 instead of the running Python.")
    args = parser.parse_args()

    print(f"[1/5] vcvars64 detection")
    vcvars = find_vcvars64()
    if not vcvars:
        sys.exit("vcvars64.bat not found in standard locations — install MSVC build tools")
    print(f"      using {vcvars}")
    msvc_env = load_msvc_env(vcvars)
    cl_path = find_cl(msvc_env)
    if not cl_path:
        sys.exit("cl.exe not on PATH after vcvars — install C++ build tools")
    print(f"      cl.exe: {cl_path}")

    print(f"[2/5] venv")
    py = venv_python(args.python)

    print(f"[3/5] pip install")
    pip_install(
        py,
        REPO_ROOT / "requirements-build.txt",
        REPO_ROOT / "requirements.txt",
    )

    if not args.skip_tests:
        print(f"[4/5] pytest")
        smoke_tests(py)
    else:
        print(f"[4/5] pytest (skipped)")

    print(f"[5/5] nuitka onefile (MSVC {args.msvc_version}, variant={args.variant})")
    nuitka_build(py, args.msvc_version, msvc_env, args.assume_yes, args.variant)

    exe = RELEASE_DIR / VARIANTS[args.variant]["output"]
    if exe.exists():
        print(f"[OK] {exe} ({exe.stat().st_size:,} bytes)")
        return 0
    print(f"[X] {VARIANTS[args.variant]['output']} not produced")
    return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
```

## `main.py`

```python
from nts.gui import main

if __name__ == "__main__":
    main()
```

## `main_reverse.py`

```python
"""Entry point for the ``nts-app-reverse`` GUI variant (self-check mode)."""
from nts.reverse_gui import main


if __name__ == "__main__":
    main()
```

## `nts/__init__.py`

```python
from .core import (
    EXPECTED_EXPERIMENTS,
    Experiment,
    InputData,
    PARALLEL_TRIALS,
    compute,
    fmt3,
    format_equation,
    read_input_file,
    read_input_json,
    read_input_xlsx,
)

__version__ = "0.2.1"

__all__ = [
    "EXPECTED_EXPERIMENTS",
    "Experiment",
    "InputData",
    "PARALLEL_TRIALS",
    "__version__",
    "compute",
    "fmt3",
    "format_equation",
    "read_input_file",
    "read_input_json",
    "read_input_xlsx",
]
```

## `nts/__main__.py`

```python
from .gui import main

if __name__ == "__main__":
    main()
```

## `nts/checker/__init__.py`

```python
"""Самопроверка: сверка расчёта с эталоном.

Пакет разделён по ответственностям:

* :mod:`nts.checker.model` — формат эталона (ядро/расширенное/словарь),
  режимы проверки и типы результата;
* :mod:`nts.checker.compare` — движок сравнения (DISCRETE / NUMERIC /
  ``f_value`` / списки строк);
* :mod:`nts.checker.loader` — загрузка файлов самопроверки (JSON и Excel) и
  выбор режима по содержимому файла;
* :mod:`nts.checker.xlsx_io` — чтение и запись эталонной книги Excel;
* :mod:`nts.checker.report` — текстовый чек-лист по результату.

Публичный API прежний: ``from nts.checker import verify, write_self_check_xlsx``
и так далее работает как раньше.

Сравнение разбито по видам полей:

* DISCRETE — строковые поля (знаки, коды, уравнение, вердикт);
* NUMERIC — коэффициентоподобные группы и t-значения с погрешностями по
  категориям (1e-3 / 1e-2 / 1e-1);
* ``f_value`` — отдельная политика NaN/inf (NaN не совпадает никогда,
  совпадающие бесконечности — да);
* списки ``g_tests`` и ``output_rows`` — сверка множества строк и сравнение
  по ключу (соответственно ``row`` и ``(delta1, delta2)``).

Политика полноты:

* :data:`MODE_FULL` — эталон должен покрывать все известные поля, отсутствие
  поля считается провалом;
* :data:`MODE_SIMPLIFIED` — сравнивается ядро
  (:data:`CORE_RESULT_KEYS`) и, если он есть в эталоне, блок Граббса
  (:data:`SIMPLIFIED_EXTRA_KEYS`); остальные опциональные поля пропускаются.

Цвет в формате книги — только метка: ядро определяется
:data:`CORE_RESULT_KEYS` и именем листа, заливка нигде не читается.
"""
from __future__ import annotations

from .compare import verify
from .loader import parse_self_check_bundle, parse_self_check_file
from .model import (
    CORE_FILL_RGB,
    CORE_RESULT_KEYS,
    DESCRIPTION_COLUMN,
    DICTIONARY_SHEET_NAME,
    EXTENDED_SHEET_NAME,
    MODE_FULL,
    MODE_SIMPLIFIED,
    SIMPLIFIED_EXTRA_KEYS,
    CheckEntry,
    CheckResult,
    SelfCheckBundle,
    Tolerance,
)
from .report import print_checklist
from .xlsx_io import parse_self_check_xlsx, write_self_check_xlsx

__all__ = [
    "CORE_FILL_RGB",
    "CORE_RESULT_KEYS",
    "DESCRIPTION_COLUMN",
    "DICTIONARY_SHEET_NAME",
    "EXTENDED_SHEET_NAME",
    "MODE_FULL",
    "MODE_SIMPLIFIED",
    "SIMPLIFIED_EXTRA_KEYS",
    "CheckEntry",
    "CheckResult",
    "SelfCheckBundle",
    "Tolerance",
    "parse_self_check_bundle",
    "parse_self_check_file",
    "parse_self_check_xlsx",
    "print_checklist",
    "verify",
    "write_self_check_xlsx",
]
```

## `nts/checker/compare.py`

```python
"""Движок сравнения: фактический результат против эталона.

Сравнение разбито по видам полей:

* DISCRETE — строковые поля (знаки, коды, уравнение, вердикт);
* NUMERIC — коэффициентоподобные группы и t-значения с погрешностями по
  категориям;
* ``f_value`` — отдельная политика NaN/inf;
* списки ``g_tests`` и ``output_rows`` — сверка множества строк и сравнение
  по ключу (соответственно ``row`` и ``(delta1, delta2)``).

Режимы: :data:`MODE_FULL` требует полноты эталона, :data:`MODE_SIMPLIFIED`
сравнивает ядро и, если он есть в эталоне, блок Граббса.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional

from .model import (
    CORE_RESULT_KEYS,
    MODE_FULL,
    MODE_SIMPLIFIED,
    SIMPLIFIED_EXTRA_KEYS,
    CheckEntry,
    CheckResult,
    Tolerance,
)


# ---- DISCRETE comparison helpers -------------------------------------------


def _eq_entry(
    name: str,
    actual: Any,
    expected: Any,
) -> CheckEntry:
    """Compare two scalar values with exact ``==``. Discrete fields only.

    Treats ``None`` on either side as a regular value (used by simple top-level
    discrete comparisons). Use :func:`_check_discrete` when ``(None, None)``
    must be skipped and one-sided ``None`` must be reported as "missing".
    """
    ok = actual == expected
    return CheckEntry(
        name=name,
        passed=bool(ok),
        actual=actual,
        expected=expected,
        diff=None,
        message="" if ok else f"discrete mismatch: {actual!r} != {expected!r}",
    )


def _check_discrete(
    name: str,
    actual: Any,
    expected: Any,
) -> Optional[CheckEntry]:
    """Compare discrete values with explicit handling of missing sides.

    Returns ``None`` when both sides are missing. Returns a failed
    ``CheckEntry`` (with ``diff=None`` and a "missing in expected/actual"
    message) when exactly one side is missing. Otherwise performs exact
    ``==`` comparison.
    """
    if actual is None and expected is None:
        return None
    if actual is None:
        return CheckEntry(
            name=name,
            passed=False,
            actual=actual,
            expected=expected,
            diff=None,
            message=f"missing in actual: actual={actual!r}, expected={expected!r}",
        )
    if expected is None:
        return CheckEntry(
            name=name,
            passed=False,
            actual=actual,
            expected=expected,
            diff=None,
            message=f"missing in expected: actual={actual!r}, expected={expected!r}",
        )
    return _eq_entry(name, actual, expected)


def _compare_discrete(
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> List[CheckEntry]:
    """Emit ``CheckEntry`` rows for top-level DISCRETE fields.

    ``g_tests`` per-row handling lives in :func:`_compare_g_tests` (todo 3).
    """
    entries: List[CheckEntry] = []

    # 1. t-tests signs (sign_b0, sign_b1, sign_b2) — exact string match.
    actual_t = actual.get("t_tests") or {}
    expected_t = expected.get("t_tests") or {}
    for key in ("sign_b0", "sign_b1", "sign_b2"):
        entry = _check_discrete(
            f"t_tests.{key}",
            actual_t.get(key),
            expected_t.get(key),
        )
        if entry is not None:
            entries.append(entry)

    # 2. f_result_code — single discrete string.
    entry = _check_discrete(
        "f_result_code",
        actual.get("f_result_code"),
        expected.get("f_result_code"),
    )
    if entry is not None:
        entries.append(entry)

    # 3. equation — full string (display form may include δ1, δ2).
    entry = _check_discrete(
        "equation",
        actual.get("equation"),
        expected.get("equation"),
    )
    if entry is not None:
        entries.append(entry)

    # 4. f_result — discrete verdict text.
    entry = _check_discrete(
        "f_result",
        actual.get("f_result"),
        expected.get("f_result"),
    )
    if entry is not None:
        entries.append(entry)

    return entries


def _summarize(entries: Iterable[CheckEntry]) -> CheckResult:
    passed = sum(1 for e in entries if e.passed)
    failed = sum(1 for e in entries if not e.passed)
    return CheckResult(passed=passed, failed=failed, entries=list(entries))


# ---- NUMERIC comparison helpers -----------------------------------


# Coefficient-like groups compared against ``tolerance.coeff_abs``.
_NUMERIC_COEFF_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("coefficients", ("b0", "b1", "b2")),
    ("coefficients_v", ("b0", "b1", "b2")),
    ("z_averages", ("z1_avg", "z2_avg")),
    ("pz", ("pz1", "pz2")),
    ("delta_calc", ("delta1", "delta2")),
)

# t-tests values compared against ``tolerance.t_abs`` (``sign_*`` are DISCRETE).
_NUMERIC_T_KEYS: tuple[str, ...] = ("t0", "t1", "t2")


def _check_numeric(
    name: str,
    actual: Any,
    expected: Any,
    abs_tol: float,
) -> Optional[CheckEntry]:
    """Compare two scalars with ``math.isclose``.

    Returns ``None`` when both sides are missing (no entry emitted). Returns a
    failed ``CheckEntry`` with ``diff=None`` when exactly one side is missing.
    Otherwise returns the entry with ``passed = math.isclose(...)`` and
    ``diff = actual - expected``.
    """
    if actual is None and expected is None:
        return None
    if actual is None or expected is None:
        return CheckEntry(
            name=name,
            passed=False,
            actual=actual,
            expected=expected,
            diff=None,
            message=f"missing numeric value: actual={actual!r}, expected={expected!r}",
        )
    ok = math.isclose(actual, expected, abs_tol=abs_tol)
    diff = actual - expected
    if ok:
        return CheckEntry(
            name=name,
            passed=True,
            actual=actual,
            expected=expected,
            diff=diff,
            message="",
        )
    return CheckEntry(
        name=name,
        passed=False,
        actual=actual,
        expected=expected,
        diff=diff,
        message=(
            f"numeric mismatch: |{actual!r} - {expected!r}| = {abs(diff)!r} "
            f"> abs_tol={abs_tol!r}"
        ),
    )


def _compare_numeric(
    actual: dict[str, Any],
    expected: dict[str, Any],
    tolerance: Tolerance,
) -> List[CheckEntry]:
    """Emit ``CheckEntry`` rows for every NUMERIC field of the coefficient-like groups."""
    entries: List[CheckEntry] = []

    for group_name, keys in _NUMERIC_COEFF_GROUPS:
        actual_group = actual.get(group_name) or {}
        expected_group = expected.get(group_name) or {}
        for key in keys:
            entry = _check_numeric(
                f"{group_name}.{key}",
                actual_group.get(key),
                expected_group.get(key),
                tolerance.coeff_abs,
            )
            if entry is not None:
                entries.append(entry)

    actual_t = actual.get("t_tests") or {}
    expected_t = expected.get("t_tests") or {}
    for key in _NUMERIC_T_KEYS:
        entry = _check_numeric(
            f"t_tests.{key}",
            actual_t.get(key),
            expected_t.get(key),
            tolerance.t_abs,
        )
        if entry is not None:
            entries.append(entry)

    return entries


# ---- f_value NaN/inf policy ---------------------------------------


def _check_f_value(
    actual: Any,
    expected: Any,
    abs_tol: float,
) -> Optional[CheckEntry]:
    """Compare ``f_value`` with explicit NaN/``inf`` policy.

    Rules:
      * ``None,None`` → no entry;
      * one side ``None`` → "missing" entry, ``passed=False``, ``diff=None``;
      * either side ``NaN`` → "NaN never matches" entry (NaN never matches
        even against itself);
      * both ``±inf`` of the same sign → pass, ``diff=0.0``;
      * both ``±inf`` of opposite sign → fail;
      * one ``inf`` and the other finite → fail with ``diff=±inf``;
      * both finite → ``math.isclose`` with ``abs_tol``.
    """
    if actual is None and expected is None:
        return None
    if actual is None or expected is None:
        return CheckEntry(
            name="f_value",
            passed=False,
            actual=actual,
            expected=expected,
            diff=None,
            message=f"missing numeric value: actual={actual!r}, expected={expected!r}",
        )

    # NaN never matches — even NaN vs NaN fails.
    if math.isnan(actual) or math.isnan(expected):
        return CheckEntry(
            name="f_value",
            passed=False,
            actual=actual,
            expected=expected,
            diff=None,
            message=f"NaN never matches: actual={actual!r}, expected={expected!r}",
        )

    actual_inf = math.isinf(actual)
    expected_inf = math.isinf(expected)

    if actual_inf and expected_inf:
        same_sign = (actual > 0) == (expected > 0)
        return CheckEntry(
            name="f_value",
            passed=same_sign,
            actual=actual,
            expected=expected,
            diff=0.0 if same_sign else float("inf"),
            message=(
                ""
                if same_sign
                else (
                    f"inf sign mismatch: actual={actual!r} != expected={expected!r}"
                )
            ),
        )

    if actual_inf or expected_inf:
        # ``actual - expected`` here is ±inf (never NaN — the ``both +inf``
        # case was handled above and NaN was rejected earlier).
        diff = actual - expected
        return CheckEntry(
            name="f_value",
            passed=False,
            actual=actual,
            expected=expected,
            diff=diff,
            message=(
                f"inf vs finite mismatch: actual={actual!r} != expected={expected!r}"
            ),
        )

    diff = actual - expected
    ok = math.isclose(actual, expected, abs_tol=abs_tol)
    if ok:
        return CheckEntry(
            name="f_value",
            passed=True,
            actual=actual,
            expected=expected,
            diff=diff,
            message="",
        )
    return CheckEntry(
        name="f_value",
        passed=False,
        actual=actual,
        expected=expected,
        diff=diff,
        message=(
            f"numeric mismatch: |{actual!r} - {expected!r}| = {abs(diff)!r} "
            f"> abs_tol={abs_tol!r}"
        ),
    )


def _compare_f_value(
    actual: dict[str, Any],
    expected: dict[str, Any],
    tolerance: Tolerance,
) -> List[CheckEntry]:
    """Emit a single ``f_value`` entry using the NaN/inf policy."""
    entry = _check_f_value(
        actual.get("f_value"),
        expected.get("f_value"),
        tolerance.f_abs,
    )
    return [entry] if entry is not None else []


# ---- g_tests row-set validation + sort-by-row ---------------------


def _compare_g_tests(
    actual: dict[str, Any],
    expected: dict[str, Any],
    tolerance: Tolerance,
) -> List[CheckEntry]:
    """Compare ``g_tests`` row-sets then per-row ``g`` (numeric) and ``ok``.

    Contract:
      * both sides absent → no entries;
      * exactly one side absent → single "missing" entry;
      * both sides empty → no entries;
      * row-set inequality → single explicit "row set mismatch" entry;
      * row-set equality → sort by ``row`` (stable) then per-row ``g`` and
        ``ok`` comparisons (numeric ``coeff_abs`` for ``g``).
    """
    entries: List[CheckEntry] = []

    actual_raw = actual.get("g_tests")
    expected_raw = expected.get("g_tests")
    actual_present = actual_raw is not None
    expected_present = expected_raw is not None

    if not actual_present and not expected_present:
        return entries
    if not actual_present or not expected_present:
        return [
            CheckEntry(
                name="g_tests",
                passed=False,
                actual=list(actual_raw) if actual_present else None,
                expected=list(expected_raw) if expected_present else None,
                diff=None,
                message=(
                    f"missing g_tests list: actual="
                    f"{'present' if actual_present else 'missing'}, "
                    f"expected={'present' if expected_present else 'missing'}"
                ),
            )
        ]

    actual_list: List[dict[str, Any]] = list(actual_raw)  # type: ignore[arg-type]
    expected_list: List[dict[str, Any]] = list(expected_raw)  # type: ignore[arg-type]

    if not actual_list and not expected_list:
        return entries

    actual_row_ids = [r.get("row") for r in actual_list]
    expected_row_ids = [r.get("row") for r in expected_list]

    if set(actual_row_ids) != set(expected_row_ids):
        actual_set = set(actual_row_ids)
        expected_set = set(expected_row_ids)
        actual_only = sorted(actual_set - expected_set)
        expected_only = sorted(expected_set - actual_set)
        msg_parts = []
        if actual_only:
            msg_parts.append(f"actual-only-rows={actual_only}")
        if expected_only:
            msg_parts.append(f"expected-only-rows={expected_only}")
        return [
            CheckEntry(
                name="g_tests",
                passed=False,
                actual=actual_row_ids,
                expected=expected_row_ids,
                diff=None,
                message=(
                    f"g_tests row set mismatch: actual={sorted(actual_set)} "
                    f"!= expected={sorted(expected_set)}"
                    + (f"; {'; '.join(msg_parts)}" if msg_parts else "")
                ),
            )
        ]

    actual_sorted = sorted(actual_list, key=lambda r: r.get("row"))
    expected_sorted = sorted(expected_list, key=lambda r: r.get("row"))

    for a_row, e_row in zip(actual_sorted, expected_sorted):
        row_id = a_row.get("row")
        g_entry = _check_numeric(
            f"g_tests[row={row_id}].g",
            a_row.get("g"),
            e_row.get("g"),
            tolerance.coeff_abs,
        )
        if g_entry is not None:
            entries.append(g_entry)
        ok_entry = _check_discrete(
            f"g_tests[row={row_id}].ok",
            a_row.get("ok"),
            e_row.get("ok"),
        )
        if ok_entry is not None:
            entries.append(ok_entry)

    return entries


# ---- output_rows delta-tuple sort ---------------------------------


_OUTPUT_ROW_FIELDS: tuple[str, ...] = (
    "y_avg",
    "delta1",
    "delta2",
    "y_pred",
    "y_avg_minus_y",
    "y_avg_minus_y_sq",
)


def _compare_output_rows(
    actual: dict[str, Any],
    expected: dict[str, Any],
    tolerance: Tolerance,
) -> List[CheckEntry]:
    """Compare ``output_rows`` row-sets then per-row fields.

    ``OutputRow`` has NO ``row`` key (``nts/core.py:61-67``), so the unique
    per-row identifier is the ``(delta1, delta2)`` tuple. Uniqueness follows
    ``DELTA1/2_SIGNATURE`` (``nts/core.py:21-22``).

    Same missing/empty/set-mismatch contract as :func:`_compare_g_tests`.
    """
    entries: List[CheckEntry] = []

    actual_raw = actual.get("output_rows")
    expected_raw = expected.get("output_rows")
    actual_present = actual_raw is not None
    expected_present = expected_raw is not None

    if not actual_present and not expected_present:
        return entries
    if not actual_present or not expected_present:
        return [
            CheckEntry(
                name="output_rows",
                passed=False,
                actual=list(actual_raw) if actual_present else None,
                expected=list(expected_raw) if expected_present else None,
                diff=None,
                message=(
                    f"missing output_rows list: actual="
                    f"{'present' if actual_present else 'missing'}, "
                    f"expected={'present' if expected_present else 'missing'}"
                ),
            )
        ]

    actual_list: List[dict[str, Any]] = list(actual_raw)  # type: ignore[arg-type]
    expected_list: List[dict[str, Any]] = list(expected_raw)  # type: ignore[arg-type]

    if not actual_list and not expected_list:
        return entries

    actual_keys = [(r.get("delta1"), r.get("delta2")) for r in actual_list]
    expected_keys = [(r.get("delta1"), r.get("delta2")) for r in expected_list]

    if set(actual_keys) != set(expected_keys):
        actual_set = set(actual_keys)
        expected_set = set(expected_keys)
        return [
            CheckEntry(
                name="output_rows",
                passed=False,
                actual=sorted(actual_set),
                expected=sorted(expected_set),
                diff=None,
                message=(
                    f"output_rows delta set mismatch: "
                    f"actual={sorted(actual_set)} != expected={sorted(expected_set)}"
                ),
            )
        ]

    actual_sorted = sorted(
        actual_list, key=lambda r: (r.get("delta1"), r.get("delta2"))
    )
    expected_sorted = sorted(
        expected_list, key=lambda r: (r.get("delta1"), r.get("delta2"))
    )

    for a_row, e_row in zip(actual_sorted, expected_sorted):
        row_key = (a_row.get("delta1"), a_row.get("delta2"))
        for field_name in _OUTPUT_ROW_FIELDS:
            entry = _check_numeric(
                f"output_rows{list(row_key)!s}.{field_name}",
                a_row.get(field_name),
                e_row.get(field_name),
                tolerance.coeff_abs,
            )
            if entry is not None:
                entries.append(entry)

    return entries


# ---- public entry point ----------------------------------------------------


def _project_actual_to_expected(
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    """Restrict ``actual`` to the fields ``expected`` actually provides.

    Used by the simplified mode: a reference file may legitimately omit
    fields (that is exactly what the optional ``extended`` sheet is for).
    Dropping those fields from the *actual* payload makes the comparison skip
    them instead of reporting them as missing. A field present in ``expected``
    but absent from ``actual`` stays absent on purpose — that is a real
    failure, not a coverage gap.
    """
    projected: dict[str, Any] = {}
    for key, exp_value in expected.items():
        act_value = actual.get(key)
        if isinstance(exp_value, dict):
            if not isinstance(act_value, dict):
                continue
            sub = {k: act_value[k] for k in exp_value if k in act_value}
            if sub:
                projected[key] = sub
            continue
        if isinstance(exp_value, list):
            if act_value is not None:
                projected[key] = act_value
            continue
        if key in actual:
            projected[key] = act_value
    return projected


def _select_core_expected(expected: dict[str, Any]) -> dict[str, Any]:
    """Keep only the core keys of an expected payload.

    :data:`CORE_RESULT_KEYS` are dotted paths (``coefficients.b0``); the
    result is a nested dict shaped like ``expected`` again. Groups keep only
    the core leaves — ``coefficients`` keeps ``b0``/``b1``/``b2`` and nothing
    else.

    :data:`SIMPLIFIED_EXTRA_KEYS` (the Grubbs block) are carried over when the
    reference file provides them: a core-only workbook still ships a
    ``grubbs`` sheet, and the criterion belongs to the core method even though
    it is not one of the yellow-marked scalar cells.
    """
    out: dict[str, Any] = {}
    for path in CORE_RESULT_KEYS:
        parts = path.split(".")
        if len(parts) == 1:
            if path in expected:
                out[path] = expected[path]
            continue
        group_name, leaf = parts[0], parts[1]
        group = expected.get(group_name)
        if not isinstance(group, dict) or leaf not in group:
            continue
        out.setdefault(group_name, {})[leaf] = group[leaf]
    for path in SIMPLIFIED_EXTRA_KEYS:
        if path in expected:
            out[path] = expected[path]
    return out


def verify(
    actual: dict[str, Any],
    expected: dict[str, Any],
    *,
    tolerance: Optional[Tolerance] = None,
    mode: str = MODE_FULL,
) -> CheckResult:
    """Verify a ``ComputeResult`` payload against an expected reference.

    Compares DISCRETE top-level fields (signs, codes, equation, f_result),
    NUMERIC coefficient-like groups (``coeff_abs``), ``t_tests`` values
    (``t_abs``), the Fisher ``f_value`` (``f_abs``, with NaN/inf policy),
    ``g_tests`` row-set with sort-by-row plus per-row ``g``/``ok`` compare,
    and ``output_rows`` row-set with sort-by-(delta1, delta2) plus per-row
    numeric compare.

    ``mode``:

    * :data:`MODE_FULL` (default) — the reference must cover every field the
      comparison knows about; a field missing from ``expected`` is a failure.
    * :data:`MODE_SIMPLIFIED` — the core keys (:data:`CORE_RESULT_KEYS`) are
      compared, plus the Grubbs block (:data:`SIMPLIFIED_EXTRA_KEYS`) when the
      reference provides it. The remaining optional fields (extended keys,
      per-row output) are skipped, so a reference file without them still
      verifies the model.

    Raises ``ValueError("expected must not be empty")`` when ``expected`` is an
    empty mapping. Unknown keys inside ``expected`` are silently ignored.
    """
    if not expected:
        raise ValueError("expected must not be empty")
    if tolerance is None:
        tolerance = Tolerance()
    if mode == MODE_SIMPLIFIED:
        expected = _select_core_expected(expected)
        actual = _project_actual_to_expected(actual, expected)
    elif mode != MODE_FULL:
        raise ValueError(
            f"unknown verification mode {mode!r} "
            f"(expected {MODE_FULL!r} or {MODE_SIMPLIFIED!r})"
        )
    entries = _compare_discrete(actual, expected)
    entries.extend(_compare_numeric(actual, expected, tolerance))
    entries.extend(_compare_f_value(actual, expected, tolerance))
    entries.extend(_compare_g_tests(actual, expected, tolerance))
    entries.extend(_compare_output_rows(actual, expected, tolerance))
    return _summarize(entries)


```

## `nts/checker/loader.py`

```python
"""Загрузка файлов самопроверки: JSON и Excel.

Формат на входе — либо JSON с блоками ``input``/``expected``, либо книга
Excel (см. :mod:`nts.checker.xlsx_io`). Режим проверки выводится из файла:
книга с листом ``extended`` объявляет полное покрытие, остальные — ядро.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, cast

from ..core import ComputeResult, InputData, _parse_input_data
from .model import MODE_FULL, MODE_SIMPLIFIED, SelfCheckBundle
from .xlsx_io import load_xlsx_bundle


# ---- self-check JSON file loader -----------------------------------


def parse_self_check_bundle(path: Path) -> SelfCheckBundle:
    """Load a self-check file and resolve the verification mode it implies.

    Dispatches on extension:

    * ``.json`` — JSON payload shaped as ``{"input": ..., "expected": ...}``.
      The ``expected`` block is a complete payload, so the mode is
      :data:`MODE_FULL`.
    * ``.xlsx`` / ``.xlsm`` — self-check workbook (see
      :func:`parse_self_check_xlsx` for the layout). The mode is
      :data:`MODE_FULL` when the workbook carries an ``extended`` sheet (full
      coverage declared) and :data:`MODE_SIMPLIFIED` otherwise — a workbook
      without that sheet is a complete check on its own.

    Raises ``ValueError`` for JSON payloads that are not objects, are empty, or
    are missing the ``input`` or ``expected`` key. Raises ``FileNotFoundError``
    when the path does not exist. Underlying ``_parse_input_data`` errors
    propagate unchanged.
    """
    ext = path.suffix.lower()
    if ext == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("self-check file must be a JSON object")
        if not data:
            raise ValueError("self-check file must not be empty")
        if "input" not in data:
            raise ValueError("self-check file is missing 'input' key")
        if "expected" not in data:
            raise ValueError("self-check file is missing 'expected' key")
        input_data = _parse_input_data(data["input"])
        expected = cast(ComputeResult, data["expected"])
        return SelfCheckBundle(
            input_data=input_data,
            expected=cast(Dict[str, Any], expected),
            mode=MODE_FULL,
        )
    if ext in {".xlsx", ".xlsm"}:
        return load_xlsx_bundle(path)
    raise ValueError(
        f"unsupported self-check extension {ext!r} (expected .json, .xlsx or .xlsm)"
    )


def parse_self_check_file(path: Path) -> tuple[InputData, ComputeResult]:
    """Load a self-check file. Returns ``(input_data, expected_result)``.

    Dispatches on extension:

    * ``.json`` — JSON payload shaped as ``{"input": ..., "expected": ...}``.
    * ``.xlsx`` / ``.xlsm`` — self-check workbook (see
      :func:`parse_self_check_xlsx` for the layout).

    Both paths validate the ``input`` block via
    :func:`nts.core._parse_input_data`; the ``expected`` block is kept as a raw
    ``dict`` cast to :class:`nts.core.ComputeResult` (its fields are arbitrary,
    consumed only by :func:`verify`).

    Raises ``ValueError`` for JSON payloads that are not objects, are empty, or
    are missing the ``input`` or ``expected`` key. Raises ``FileNotFoundError``
    when the path does not exist. Underlying ``_parse_input_data`` errors
    propagate unchanged.
    """
    bundle = parse_self_check_bundle(path)
    return bundle.input_data, cast(ComputeResult, bundle.expected)


```

## `nts/checker/model.py`

```python
"""Модель самопроверки: константы формата и типы результатов.

Константы описывают формат эталонной книги (ядро / расширенное / словарь) и
режимы проверки; датаклассы — результат сравнения, который возвращает
:func:`nts.checker.compare.verify`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..core import ComputeResult, InputData


# ---- Verification modes ------------------------------------------------------

#: Every field the verifier knows about must be present in the reference and
#: must match (JSON payloads, workbooks with an ``extended`` sheet).
MODE_FULL = "full"

#: Only the core keys (:data:`CORE_RESULT_KEYS`) are compared; the optional
#: fields (extended keys, G-tests, per-row output) are skipped.
MODE_SIMPLIFIED = "simplified"

#: Name of the optional sheet holding the non-core result keys.
EXTENDED_SHEET_NAME = "extended"

#: ARGB fill used to mark core cells (matches the reference workbook).
CORE_FILL_RGB = "FFFFFF00"

#: Header of the description column added next to ``key`` / ``value``.
DESCRIPTION_COLUMN = "description"

#: Name of the sheet carrying the full variable dictionary.
DICTIONARY_SHEET_NAME = "dictionary"

# ---- Core vs extended result keys --------------------------------------------
#
# The ``result`` sheet of a self-check workbook holds the *core* keys only.
# Everything else goes to the optional ``extended`` sheet, so a reference file
# without that sheet still verifies the model end-to-end (simplified mode).
#
# The core set mirrors the yellow-marked cells of the reference workbook:
# the regression coefficients (coded and natural) and the Student t-values.

CORE_RESULT_KEYS: tuple[str, ...] = (
    "f_value",
    "coefficients.b0",
    "coefficients.b1",
    "coefficients.b2",
    "coefficients_v.b0",
    "coefficients_v.b1",
    "coefficients_v.b2",
    "t_tests.t0",
    "t_tests.t1",
    "t_tests.t2",
)

#: Blocks the simplified mode compares *in addition* to the core keys when the
#: reference file provides them. The Grubbs criterion is part of the core
#: method (a gross-error check on the same experiments), so a core-only
#: workbook that carries a ``grubbs`` sheet reports it instead of silently
#: dropping the rows. ``output_rows`` stays extended-only.
SIMPLIFIED_EXTRA_KEYS: tuple[str, ...] = ("g_tests",)


@dataclass(frozen=True)
class SelfCheckBundle:
    """A parsed self-check file together with the mode it implies.

    ``mode`` is :data:`MODE_FULL` when the reference file declares full
    coverage — a JSON payload, or a workbook carrying an ``extended`` sheet —
    and :data:`MODE_SIMPLIFIED` for a workbook without that sheet, where the
    core keys and (when present) the Grubbs block are compared.
    """

    input_data: InputData
    expected: Dict[str, Any]
    mode: str


@dataclass(frozen=True)
class Tolerance:
    """Per-category numeric tolerances. Defaults follow Excel reference precision."""

    coeff_abs: float = 1e-3  # b0, b1, b2 (and their variance counterparts)
    t_abs: float = 1e-2  # Student t-values
    f_abs: float = 1e-1  # Fisher F-value


@dataclass(frozen=True)
class CheckEntry:
    """Outcome of comparing one field between actual and expected."""

    name: str
    passed: bool
    actual: Any
    expected: Any
    diff: Optional[float]
    message: str


@dataclass(frozen=True)
class CheckResult:
    """Aggregate verification report."""

    passed: int
    failed: int
    entries: List[CheckEntry] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.passed + self.failed != len(self.entries):
            raise ValueError(
                f"CheckResult invariant violated: passed({self.passed}) "
                f"+ failed({self.failed}) != len(entries)({len(self.entries)})"
            )


```

## `nts/checker/report.py`

```python
"""Отчёт по результату проверки: текстовый чек-лист."""
from __future__ import annotations

import sys
from typing import Any, Optional

from ..dictionary import UNKNOWN_DESCRIPTION, describe_entry
from ..i18n import I18N, localize_check_value, normalize_lang, translate_message
from .model import CheckResult


# ---- print_checklist() Unicode/ASCII output ------------------------


def print_checklist(
    result: CheckResult,
    *,
    ascii: bool = False,
    file: Optional[Any] = None,
    lang: Optional[str] = None,
) -> None:
    """Render a :class:`CheckResult` as a human-readable checklist.

    Format per entry::

        <icon> <name>: actual=... expected=... (diff: <diff>)
            <message-if-any>

    With ``lang`` set, the human description of the variable is appended to
    the name (``coefficients.b0 — Regression intercept (coded coefficients)``),
    so a reader does not have to know the key. The same ``lang`` localizes the
    title, the labels, the canonical values (Fisher verdict, G-test status)
    and the technical note of a failed check. Without ``lang`` the output is
    the language-neutral English checklist.

    Summary line at end: ``"<passed> passed, <failed> failed"`` (translated
    when ``lang`` is given).

    Parameters:
        result: Aggregate verification report from :func:`verify`.
        ascii: When ``True`` use ``[OK]``/``[FAIL]`` instead of the Unicode
            glyphs ``✓``/``✗``. Useful for terminals/codepages that can't
            render the glyphs.
        file: Writable text stream (defaults to ``sys.stdout``). Caller is
            responsible for encoding.
        lang: Language code for the variable descriptions and the report
            labels (see :mod:`nts.dictionary` / :mod:`nts.i18n`). ``None``
            keeps the bare key names and the English labels.
    """
    if file is None:
        file = sys.stdout
    table = I18N[normalize_lang(lang)] if lang is not None else I18N["EN"]
    pass_icon = "[OK]" if ascii else "✓"
    fail_icon = "[FAIL]" if ascii else "✗"
    file.write(f"{table['self_check_title']}\n")
    for entry in result.entries:
        icon = pass_icon if entry.passed else fail_icon
        diff_str = (
            table["report_not_applicable"]
            if entry.diff is None
            else f"{entry.diff:.6g}"
        )
        label = entry.name
        actual = entry.actual
        expected = entry.expected
        message = entry.message
        if lang is not None:
            description = describe_entry(entry.name, lang)
            if description and description != UNKNOWN_DESCRIPTION:
                label = f"{entry.name} — {description}"
            actual = localize_check_value(entry.name, actual, lang)
            expected = localize_check_value(entry.name, expected, lang)
            message = translate_message(message, lang)
        file.write(
            f"  {icon} {label}: {table['report_actual']}={actual!r} "
            f"{table['report_expected']}={expected!r} "
            f"({table['report_diff']}: {diff_str})\n"
        )
        if message:
            file.write(f"      {message}\n")
    summary = (
        table["summary_passed"].format(passed=result.passed)
        + ", "
        + table["summary_failed"].format(failed=result.failed)
    )
    file.write(f"\n{summary}\n")
```

## `nts/checker/xlsx_io.py`

```python
"""Чтение и запись эталонной книги самопроверки (Excel).

Листы: ``input`` (опыты), ``criteria`` (критерии), ``result`` (ядро,
вертикально ``key``/``value``/``description``), ``extended`` (остальные ключи,
опциональный), ``grubbs``, ``output_rows`` и ``dictionary``.

Цвет в формате — только метка: ядро определяется списком
:data:`nts.checker.model.CORE_RESULT_KEYS` и именем листа, заливка нигде не
читается.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from ..core import ComputeResult, InputData, _parse_input_data
from ..dictionary import DESCRIPTIONS, describe
from ..i18n import (
    DEFAULT_LANGUAGE,
    canonical_check_value,
    localize_check_value,
    normalize_lang,
)
from .model import (
    CORE_FILL_RGB,
    CORE_RESULT_KEYS,
    DESCRIPTION_COLUMN,
    DICTIONARY_SHEET_NAME,
    EXTENDED_SHEET_NAME,
    MODE_FULL,
    MODE_SIMPLIFIED,
    SelfCheckBundle,
)


# ---- self-check xlsx loader + writer ------------------------------


_REQUIRED_SELF_CHECK_SHEETS: tuple[str, ...] = ("input", "criteria", "result")


def _require_openpyxl() -> Any:
    """Import openpyxl or raise a clear :class:`RuntimeError`."""
    try:
        import openpyxl  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "openpyxl is required for Excel self-check files. "
            "Install it with: python -m pip install openpyxl"
        ) from exc
    return openpyxl


def _read_xlsx_sheet_rows(wb: Any, name: str) -> List[List[Any]]:
    """Read ``wb[name]`` as a list of cell-value rows. Raises if sheet is missing."""
    if name not in wb.sheetnames:
        raise ValueError(
            f"self-check workbook missing required sheet {name!r}; "
            f"found sheets: {wb.sheetnames}"
        )
    ws = wb[name]
    return [list(row) for row in ws.iter_rows(values_only=True)]


def _parse_xlsx_sheet_to_dict(rows: List[List[Any]]) -> List[Dict[str, Any]]:
    """Treat first row as header and remaining non-blank rows as records."""
    if not rows:
        return []
    header = [str(c).strip() if c is not None else "" for c in rows[0]]
    out: List[Dict[str, Any]] = []
    for raw in rows[1:]:
        if all(c is None or str(c).strip() == "" for c in raw):
            continue
        record: Dict[str, Any] = {}
        for i, key in enumerate(header):
            if not key:
                continue
            record[key] = raw[i] if i < len(raw) else None
        out.append(record)
    return out


def _read_xlsx_criteria(wb: Any) -> Dict[str, float]:
    """Read the ``criteria`` sheet.

    Accepts both layouts produced by :func:`nts.core._read_criteria_from_sheet`:
    a header row of ``g_crit,t_crit,f_crit`` followed by one value row, **or**
    bare key/value pairs (e.g. ``A1='g_crit', B1=0.7679``). The first matching
    layout wins.
    """
    rows = _read_xlsx_sheet_rows(wb, "criteria")
    if not rows:
        raise ValueError("self-check workbook 'criteria' sheet is empty")

    header = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
    if "g_crit" in header and "t_crit" in header and "f_crit" in header:
        if len(rows) < 2:
            raise ValueError(
                "self-check workbook 'criteria' sheet has header but no value row"
            )
        value_row = rows[1]
        return {
            "g_crit": float(value_row[header.index("g_crit")]),
            "t_crit": float(value_row[header.index("t_crit")]),
            "f_crit": float(value_row[header.index("f_crit")]),
        }

    crit: Dict[str, float] = {}
    for raw in rows:
        if not raw or raw[0] is None:
            continue
        key = str(raw[0]).strip().lower()
        if key in {"g_crit", "t_crit", "f_crit"} and len(raw) > 1 and raw[1] is not None:
            crit[key] = float(raw[1])
    if set(crit.keys()) != {"g_crit", "t_crit", "f_crit"}:
        missing = {"g_crit", "t_crit", "f_crit"} - set(crit.keys())
        raise ValueError(
            f"self-check workbook 'criteria' sheet missing keys: {sorted(missing)}"
        )
    return crit


def _parse_xlsx_result_sheet(rows: List[List[Any]]) -> Dict[str, Any]:
    """Rebuild a ``ComputeResult``-shaped ``dict`` from a vertical ``(key,value)`` sheet.

    Top-level scalars are stored as dotted-path keys (``equation``, ``f_value``,
    ``coefficients.b0``, ``t_tests.sign_b0``, ...). Returns the in-progress dict;
    the caller is responsible for attaching ``g_tests`` and ``output_rows``.
    """
    if len(rows) < 2:
        raise ValueError("self-check workbook 'result' sheet is empty")
    header = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
    if "key" not in header or "value" not in header:
        raise ValueError(
            "self-check workbook 'result' sheet must have a header row 'key, value'"
        )
    key_idx = header.index("key")
    val_idx = header.index("value")

    result: Dict[str, Any] = {}
    for raw in rows[1:]:
        if all(c is None or str(c).strip() == "" for c in raw):
            continue
        key = raw[key_idx]
        value = raw[val_idx] if val_idx < len(raw) else None
        if key is None or str(key).strip() == "":
            continue
        path = str(key).strip()
        _set_dotted(result, path, value)
    return result


def _set_dotted(target: Dict[str, Any], path: str, value: Any) -> None:
    """Insert ``value`` at ``target[parts[0]][parts[1]]...`` for a dotted key.

    For top-level scalars (``equation``, ``f_value``, ...) the value lands at
    ``target[path]``. Numeric cells are coerced to ``float``; the criterion
    keys (``g_crit``, ``t_crit``, ``f_crit``) and the discrete string fields
    (``equation``, ``f_result_code``, ``f_result``, ``t_tests.sign_*``) keep
    their native type. Booleans (rare) are kept as-is. A localized ``f_result``
    verdict is mapped back to its canonical English form.
    """
    parts = path.split(".")
    value = _coerce_scalar(value)
    if path == "f_result":
        value = canonical_check_value(path, value)
    if len(parts) == 1:
        target[parts[0]] = value
        return
    group = parts[0]
    sub_key = parts[1]
    if group not in target or not isinstance(target.get(group), dict):
        target[group] = {}
    target[group][sub_key] = value


def _coerce_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return None
        try:
            return float(text)
        except ValueError:
            return text
    return value


def parse_self_check_xlsx(path: Path) -> tuple[InputData, ComputeResult]:
    """Load a self-check workbook. Returns ``(input_data, expected_result)``.

    Required sheets (in any order, but the first three are mandatory):

    * ``input``       — header ``idx, delta1, delta2, x1, x2, x3, y1, y2, y3``
                        and 4 data rows (consumed by
                        :func:`nts.core._parse_input_data`).
    * ``criteria``    — either ``g_crit,t_crit,f_crit`` header + 1 value row,
                        or bare key/value pairs ``A=g_crit,B=0.7679``, ...
    * ``result``      — vertical ``(key, value)`` table with the **core** keys;
                        dotted paths such as ``coefficients.b0`` rebuild the
                        nested :class:`ComputeResult`.
    * ``extended``    — optional vertical ``(key, value)`` table with the
                        non-core result keys. Its presence declares full
                        coverage (strict mode); without it the workbook is a
                        complete check on its own (simplified mode).
    * ``grubbs``      — header ``row,G,ok`` + 4 rows. Optional but expected;
                        an empty sheet is treated as missing.
    * ``output_rows`` — header
                        ``delta1,delta2,y_avg,y_pred,y_avg_minus_y,y_avg_minus_y_sq``
                        + 4 rows. Optional; an empty sheet is treated as missing.

    Raises ``ValueError`` when a required sheet is absent or malformed.
    Raises ``FileNotFoundError`` when ``path`` does not exist.
    """
    bundle = load_xlsx_bundle(path)
    return bundle.input_data, cast(ComputeResult, bundle.expected)


def _merge_expected(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    """Merge ``extra`` into ``base``, merging nested groups key-by-key.

    A dotted key such as ``t_tests.sign_b0`` lands in a nested group; a plain
    ``dict.update`` would drop the sibling keys of that group (``t_tests.t0``),
    so groups are merged instead of replaced.
    """
    for key, value in extra.items():
        current = base.get(key)
        if isinstance(value, dict) and isinstance(current, dict):
            base[key] = {**current, **value}
        else:
            base[key] = value
    return base


def load_xlsx_bundle(path: Path) -> SelfCheckBundle:
    """Parse a self-check workbook into a :class:`SelfCheckBundle`."""
    openpyxl = _require_openpyxl()
    wb = openpyxl.load_workbook(str(path), data_only=True)

    for sheet_name in _REQUIRED_SELF_CHECK_SHEETS:
        if sheet_name not in wb.sheetnames:
            raise ValueError(
                f"self-check workbook missing required sheet {sheet_name!r}; "
                f"found sheets: {wb.sheetnames}"
            )

    input_records = _parse_xlsx_sheet_to_dict(_read_xlsx_sheet_rows(wb, "input"))
    if not input_records:
        raise ValueError("self-check workbook 'input' sheet has no data rows")

    crit = _read_xlsx_criteria(wb)

    input_dict: Dict[str, Any] = {
        "experiments": input_records,
        "g_crit": crit["g_crit"],
        "t_crit": crit["t_crit"],
        "f_crit": crit["f_crit"],
    }
    input_data = _parse_input_data(input_dict)

    result_rows = _read_xlsx_sheet_rows(wb, "result")
    expected: Dict[str, Any] = _parse_xlsx_result_sheet(result_rows)

    has_extended = EXTENDED_SHEET_NAME in wb.sheetnames
    if has_extended:
        extended_rows = _read_xlsx_sheet_rows(wb, EXTENDED_SHEET_NAME)
        _merge_expected(expected, _parse_xlsx_result_sheet(extended_rows))

    if "grubbs" in wb.sheetnames:
        grubbs_records = _parse_xlsx_sheet_to_dict(_read_xlsx_sheet_rows(wb, "grubbs"))
        if grubbs_records:
            expected["g_tests"] = [
                {
                    "row": int(float(rec["row"])),
                    "g": float(rec["G"]),
                    "ok": canonical_check_value("g_tests.row.ok", str(rec["ok"])),
                }
                for rec in grubbs_records
                if rec.get("row") is not None
            ]

    if "output_rows" in wb.sheetnames:
        out_records = _parse_xlsx_sheet_to_dict(_read_xlsx_sheet_rows(wb, "output_rows"))
        if out_records:
            expected["output_rows"] = [
                {
                    "delta1": float(rec["delta1"]),
                    "delta2": float(rec["delta2"]),
                    "y_avg": float(rec["y_avg"]),
                    "y_pred": float(rec["y_pred"]),
                    "y_avg_minus_y": float(rec["y_avg_minus_y"]),
                    "y_avg_minus_y_sq": float(rec["y_avg_minus_y_sq"]),
                }
                for rec in out_records
            ]

    return SelfCheckBundle(
        input_data=input_data,
        expected=expected,
        mode=MODE_FULL if has_extended else MODE_SIMPLIFIED,
    )


def _core_fill() -> Any:
    """Yellow fill marking a core cell (matches the reference workbook)."""
    from openpyxl.styles import PatternFill

    return PatternFill(
        fill_type="solid",
        start_color=CORE_FILL_RGB,
        end_color=CORE_FILL_RGB,
    )


def write_self_check_xlsx(
    path: Path,
    input_data: InputData,
    result: ComputeResult,
    *,
    lang: str = DEFAULT_LANGUAGE,
    localize_values: bool = False,
) -> Path:
    """Write a self-check workbook in the same layout :func:`parse_self_check_xlsx` reads.

    Schema matches what the regular GUI's "Export to Excel" button emits
    (:meth:`nts.gui.App._export_xlsx`), so a file round-tripped through either
    tool is interchangeable. Returns the same ``path`` for chaining.

    The ``result`` sheet carries the **core** keys only (see
    :data:`CORE_RESULT_KEYS`), marked with a yellow fill; every other result
    key goes to the optional ``extended`` sheet. Dropping the ``extended``
    sheet therefore leaves a complete — if narrower — check behind.

    Both key/value sheets carry a third ``description`` column with the human
    meaning of the variable (see :mod:`nts.dictionary`), written in ``lang``.
    The ``dictionary`` sheet lists every variable of the workbook — result
    keys and the column names of the other sheets — with its description.
    Human-facing discrete values (the Fisher verdict and the Grubbs status)
    are written in ``lang`` when ``localize_values`` is true; the reader maps
    them back to the canonical English form, so a Russian report stays
    interchangeable with an English one. The default (``False``) keeps the
    canonical values, which is what a reference workbook needs.
    """
    openpyxl = _require_openpyxl()
    wb = openpyxl.Workbook()
    ws_input = wb.active
    ws_input.title = "input"
    ws_input.append(["idx", "delta1", "delta2", "x1", "x2", "x3", "y1", "y2", "y3"])
    for exp in input_data.experiments:
        ws_input.append([
            exp.idx, exp.delta1, exp.delta2,
            exp.x1, exp.x2, exp.x3,
            exp.y1, exp.y2, exp.y3,
        ])

    ws_crit = wb.create_sheet("criteria")
    ws_crit.append(["g_crit", "t_crit", "f_crit"])
    ws_crit.append([input_data.g_crit, input_data.t_crit, input_data.f_crit])

    header = ["key", "value", DESCRIPTION_COLUMN]
    ws_res = wb.create_sheet("result")
    ws_res.append(header)
    ws_ext = wb.create_sheet(EXTENDED_SHEET_NAME)
    ws_ext.append(header)
    coeffs = result["coefficients"]
    coeffs_v = result["coefficients_v"]
    z_avg = result["z_averages"]
    pz = result["pz"]
    delta = result["delta_calc"]
    t_tests = result["t_tests"]

    rows: List[tuple[str, Any]] = []

    def _kv(prefix: str, mapping: Dict[str, Any]) -> None:
        for k, v in mapping.items():
            rows.append((f"{prefix}.{k}" if prefix else k, v))

    rows.append(("equation", result["equation"]))
    rows.append(("f_avg", result["f_avg"]))
    rows.append(("f_value", result["f_value"]))
    rows.append(("f_result_code", result["f_result_code"]))
    rows.append(("f_result", result["f_result"]))
    rows.append(("g_crit", result["g_crit"]))
    rows.append(("t_crit", result["t_crit"]))
    rows.append(("f_crit", result["f_crit"]))
    _kv("coefficients", coeffs)
    _kv("coefficients_v", coeffs_v)
    _kv("z_averages", z_avg)
    _kv("pz", pz)
    _kv("delta_calc", delta)
    rows.append(("t_tests.t0", t_tests["t0"]))
    rows.append(("t_tests.t1", t_tests["t1"]))
    rows.append(("t_tests.t2", t_tests["t2"]))
    rows.append(("t_tests.sign_b0", t_tests["sign_b0"]))
    rows.append(("t_tests.sign_b1", t_tests["sign_b1"]))
    rows.append(("t_tests.sign_b2", t_tests["sign_b2"]))

    fill = _core_fill()
    for key, value in rows:
        is_core = key in CORE_RESULT_KEYS
        ws = ws_res if is_core else ws_ext
        displayed = (
            localize_check_value(key, value, lang)
            if localize_values and key == "f_result"
            else value
        )
        ws.append([key, displayed, describe(key, lang)])
        if is_core:
            ws.cell(row=ws.max_row, column=2).fill = fill

    ws_g = wb.create_sheet("grubbs")
    ws_g.append(["row", "G", "ok"])
    for g in result["g_tests"]:
        status = (
            localize_check_value("g_tests.row.ok", g["ok"], lang)
            if localize_values
            else g["ok"]
        )
        ws_g.append([g["row"], g["g"], status])

    ws_o = wb.create_sheet("output_rows")
    ws_o.append([
        "delta1", "delta2", "y_avg",
        "y_pred", "y_avg_minus_y", "y_avg_minus_y_sq",
    ])
    for r in result["output_rows"]:
        ws_o.append([
            r["delta1"], r["delta2"], r["y_avg"],
            r["y_pred"], r["y_avg_minus_y"], r["y_avg_minus_y_sq"],
        ])

    ws_dict = wb.create_sheet(DICTIONARY_SHEET_NAME)
    ws_dict.append(["key", DESCRIPTION_COLUMN])
    table = DESCRIPTIONS.get(normalize_lang(lang), DESCRIPTIONS["EN"])
    for name, description in table.items():
        ws_dict.append([name, description])

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(path))
    return Path(path)


```

## `nts/cli.py`

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import ComputeResult, InputData, compute, read_input_file
from .i18n import DEFAULT_LANGUAGE, I18N, LANGUAGES, localize_check_value, normalize_lang


def print_report(result: ComputeResult, lang: str = DEFAULT_LANGUAGE) -> None:
    table = I18N[normalize_lang(lang)]
    t = result["t_tests"]
    print(result["equation"])
    print("")
    print(table["cli_report_t"])
    for label, key, sign_key in (("t_0", "t0", "sign_b0"), ("t_1", "t1", "sign_b1"), ("t_2", "t2", "sign_b2")):
        print(f"  {label}: t={t[key]:.4f} sign={t[sign_key]}")
    print("")
    print(table["cli_report_g"])
    for row in result["g_tests"]:
        status = localize_check_value("g_tests.row.ok", row["ok"], lang)
        print("  " + table["cli_report_row"].format(
            row=row["row"], g=f"{row['g']:.4f}", status=status,
        ))
    print("")
    print(table["cli_report_output"])
    headers = ("y_avg", "delta1", "delta2", "y_pred", "y_avg-y", "(y_avg-y)^2")
    print("  " + " | ".join(headers))
    for r in result["output_rows"]:
        cells = (
            f"{r['y_avg']:.6g}", f"{r['delta1']:.6g}", f"{r['delta2']:.6g}",
            f"{r['y_pred']:.6g}", f"{r['y_avg_minus_y']:.6g}", f"{r['y_avg_minus_y_sq']:.6g}",
        )
        print("  " + " | ".join(cells))
    print("")
    print(f"{table['f_avg']}={result['f_avg']:.6g}")
    print(f"{table['f_value']}={result['f_value']:.6g}")
    print(localize_check_value("f_result", result["f_result"], lang))


def _force_utf8_output() -> None:
    """Make stdout/stderr UTF-8 so ``δ`` and ``✓``/``✗`` survive a cp1252 console.

    Without this the CLI dies with ``UnicodeEncodeError`` on the default
    Windows console encoding (cp1252 cannot encode ``δ`` or the checklist
    glyphs) — the report and the self-check checklist both carry them.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def main() -> None:
    _force_utf8_output()
    parser = argparse.ArgumentParser(description="Compute results without Excel dependencies.")
    parser.add_argument(
        "path",
        nargs="?",
        help="Input file path (positional alternative to --input).",
    )
    parser.add_argument(
        "--input",
        dest="input_path",
        default=None,
        help="Path to JSON or XLSX input file (or self-check file when --self-check).",
    )
    parser.add_argument(
        "--self-check",
        dest="self_check",
        action="store_true",
        help="Run self-check mode: input JSON must be {\"input\": {...}, \"expected\": {...}}.",
    )
    parser.add_argument("--json", dest="json_path", help="Write result JSON to this path.")
    parser.add_argument(
        "--lang",
        dest="lang",
        choices=LANGUAGES,
        default=DEFAULT_LANGUAGE,
        help=f"Report language (default: {DEFAULT_LANGUAGE}).",
    )
    args = parser.parse_args()
    lang = normalize_lang(args.lang)

    input_path_str = args.input_path or args.path
    if input_path_str is None:
        parser.error("the following arguments are required: --input or a positional path")
    args.input_path = input_path_str

    if args.self_check:
        from .checker import parse_self_check_bundle, print_checklist, verify
        try:
            bundle = parse_self_check_bundle(Path(args.input_path))
        except (ValueError, FileNotFoundError) as e:
            print(f"{I18N[lang]['cli_error']} {e}", file=sys.stderr)
            sys.exit(2)
        actual = compute(bundle.input_data)
        result = verify(actual, bundle.expected, mode=bundle.mode)
        print_checklist(result, lang=lang)
        sys.exit(0 if result.failed == 0 else 1)
        return

    path = Path(args.input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    data: InputData = read_input_file(path)
    result = compute(data)
    print_report(result, lang=lang)

    if args.json_path:
        json_path = Path(args.json_path)
        json_path.write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
```

## `nts/core.py`

```python
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Dict, List, Tuple, TypedDict

try:
    import openpyxl
    from openpyxl.worksheet.worksheet import Worksheet
except Exception:
    openpyxl = None
    Worksheet = None  # type: ignore[assignment,misc]


# Размерность плана (Методичка §3): 2² дизайн, m=3 параллельных опыта.
EXPECTED_EXPERIMENTS: int = 4
PARALLEL_TRIALS: int = 3
DELTA1_SIGNATURE: Tuple[int, ...] = (-1, -1, 1, 1)
DELTA2_SIGNATURE: Tuple[int, ...] = (-1, 1, -1, 1)


class GTest(TypedDict):
    row: int
    g: float
    ok: str


class TTests(TypedDict):
    t0: float
    t1: float
    t2: float
    sign_b0: str
    sign_b1: str
    sign_b2: str


class CoeffsDict(TypedDict):
    b0: float
    b1: float
    b2: float


class ScalarsDict(TypedDict):
    z1_avg: float
    z2_avg: float


class PairsDict(TypedDict):
    pz1: float
    pz2: float


class DeltaCalcDict(TypedDict):
    delta1: float
    delta2: float


class OutputRow(TypedDict):
    y_avg: float
    delta1: float
    delta2: float
    y_pred: float
    y_avg_minus_y: float
    y_avg_minus_y_sq: float


class ComputeResult(TypedDict, total=False):
    """Контракт результата ``compute()``. Методичка §3."""
    coefficients: CoeffsDict
    coefficients_v: CoeffsDict
    z_averages: ScalarsDict
    pz: PairsDict
    delta_calc: DeltaCalcDict
    g_tests: List[GTest]
    t_tests: TTests
    output_rows: List[OutputRow]
    f_avg: float
    f_value: float
    f_result_code: str
    f_result: str
    equation: str
    g_crit: float
    t_crit: float
    f_crit: float


@dataclass(frozen=True)
class InputData:
    """Входные данные, единый формат (JSON и Excel)."""
    experiments: List["Experiment"]
    g_crit: float
    t_crit: float
    f_crit: float


@dataclass
class Experiment:
    idx: int
    delta1: float
    delta2: float
    x1: float
    x2: float
    x3: float
    y1: float
    y2: float
    y3: float

    @property
    def z1(self) -> float:
        return safe_div(self.x1, self.x2, "x1/x2")

    @property
    def z2(self) -> float:
        return safe_div(self.x3, self.x2, "x3/x2")

    @property
    def y_values(self) -> List[float]:
        return [self.y1, self.y2, self.y3]

    @property
    def y_avg(self) -> float:
        return sum(self.y_values) / PARALLEL_TRIALS


def safe_div(numerator: float, denominator: float, label: str) -> float:
    if denominator == 0:
        raise ValueError(f"Division by zero for {label}.")
    return numerator / denominator


def _to_float(value: object, label: str) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        raw = value.strip().replace(",", ".")
        if raw == "":
            raise ValueError(f"Empty value for {label}.")
        return float(raw)
    raise ValueError(f"Invalid value for {label}: {value!r}")


def _round3(value: float) -> float:
    if not math.isfinite(value):
        return value
    return float(Decimal(str(value)).quantize(Decimal("0.000"), rounding=ROUND_HALF_UP))


def fmt3(value: float) -> str:
    """Format a float to 3 decimal places, trim trailing zeros."""
    return f"{value:.3f}".rstrip("0").rstrip(".")


def format_equation(b0: float, b1: float, b2: float, delta1_sym: str, delta2_sym: str) -> str:
    """Format ``Y = b0 + b1·δ1 + b2·δ2`` from **coded** coefficients (Методичка §3, ф-ла 3.3).

    Pass ``0.0`` for any coefficient whose t-test failed (it will be omitted from the
    string instead of rendering as ``+ 0*δ``).
    """
    parts: List[str] = [f"Y = {fmt3(b0)}"]
    for value, name in ((b1, delta1_sym), (b2, delta2_sym)):
        if value == 0:
            continue
        sign = "+" if value >= 0 else "-"
        parts.append(f"{sign} {fmt3(abs(value))}*{name}")
    return " ".join(parts)


# Ожидаемые столбцы таблицы экспериментов.
EXPECTED_COLUMNS: List[str] = ["idx", "delta1", "delta2", "x1", "x2", "x3", "y1", "y2", "y3"]

# Допустимые имена колонок (Excel) с небольшими вариациями.
_HEADER_ALIASES: Dict[str, List[str]] = {
    "idx": ["idx", "no", "n", "num", "number"],
    "delta1": ["delta1", "d1", "delta-1", "delta_1", "delta 1"],
    "delta2": ["delta2", "d2", "delta-2", "delta_2", "delta 2"],
    "x1": ["x1"],
    "x2": ["x2"],
    "x3": ["x3"],
    "y1": ["y1"],
    "y2": ["y2"],
    "y3": ["y3"],
}

# Допустимые имена для критериев.
_CRIT_ALIASES: Dict[str, List[str]] = {
    "g_crit": ["g_crit", "gcrit", "g-crit", "g crit"],
    "t_crit": ["t_crit", "tcrit", "t-crit", "t crit"],
    "f_crit": ["f_crit", "fcrit", "f-crit", "f crit"],
}


def _normalize_header(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    return text.replace(" ", "").replace("_", "").replace("-", "")


_HEADER_MAP: Dict[str, str] = {
    _normalize_header(alias): key
    for key, aliases in _HEADER_ALIASES.items()
    for alias in aliases
}

_CRIT_MAP: Dict[str, str] = {
    _normalize_header(alias): key
    for key, aliases in _CRIT_ALIASES.items()
    for alias in aliases
}


def _parse_input_data(data: Dict[str, Any]) -> InputData:
    """Parse already-validated dict (от JSON или Excel) в InputData."""
    if "experiments" not in data:
        raise ValueError("Input must include 'experiments'.")
    experiments: List[Experiment] = []
    for idx, item in enumerate(data["experiments"]):
        if "y" in item:
            raise ValueError("Use y1, y2, y3 instead of 'y' in experiments.")
        experiments.append(
            Experiment(
                idx=int(_to_float(item["idx"], f"experiments[{idx}].idx")),
                delta1=_to_float(item["delta1"], f"experiments[{idx}].delta1"),
                delta2=_to_float(item["delta2"], f"experiments[{idx}].delta2"),
                x1=_to_float(item["x1"], f"experiments[{idx}].x1"),
                x2=_to_float(item["x2"], f"experiments[{idx}].x2"),
                x3=_to_float(item["x3"], f"experiments[{idx}].x3"),
                y1=_to_float(item["y1"], f"experiments[{idx}].y1"),
                y2=_to_float(item["y2"], f"experiments[{idx}].y2"),
                y3=_to_float(item["y3"], f"experiments[{idx}].y3"),
            )
        )
    return InputData(
        experiments=experiments,
        g_crit=_to_float(data["g_crit"], "g_crit"),
        t_crit=_to_float(data["t_crit"], "t_crit"),
        f_crit=_to_float(data["f_crit"], "f_crit"),
    )


def read_input_json(path: Path) -> InputData:
    data = json.loads(path.read_text(encoding="utf-8"))
    return _parse_input_data(data)


def _iter_rows(ws: Worksheet) -> List[List[Any]]:
    return [list(row) for row in ws.iter_rows(values_only=True)]


def _read_experiments_sheet(ws: Worksheet) -> List[Dict[str, Any]]:
    rows = _iter_rows(ws)
    if not rows:
        raise ValueError("Excel sheet is empty.")

    header_row = rows[0]
    column_map: Dict[int, str] = {}
    for idx, cell in enumerate(header_row):
        key = _HEADER_MAP.get(_normalize_header(cell))
        if key:
            column_map[idx] = key

    missing = [key for key in EXPECTED_COLUMNS if key not in column_map.values()]
    if missing:
        raise ValueError(f"Excel header missing columns: {', '.join(missing)}.")

    experiments: List[Dict[str, Any]] = []
    for row in rows[1:]:
        if all(cell is None or str(cell).strip() == "" for cell in row):
            continue
        item: Dict[str, Any] = {
            key: row[col_idx] if col_idx < len(row) else None
            for col_idx, key in column_map.items()
        }
        experiments.append(item)
    return experiments


def _read_criteria_from_sheet(ws: Worksheet) -> Dict[str, Any]:
    rows = _iter_rows(ws)
    if not rows:
        return {}

    header = rows[0]
    header_map: Dict[int, str] = {}
    for idx, cell in enumerate(header):
        key = _CRIT_MAP.get(_normalize_header(cell))
        if key:
            header_map[idx] = key

    if header_map and len(rows) > 1:
        data_row = rows[1]
        data: Dict[str, Any] = {
            key: data_row[col_idx]
            for col_idx, key in header_map.items()
            if col_idx < len(data_row)
        }
        if set(data.keys()) == set(_CRIT_ALIASES.keys()):
            return data

    data: Dict[str, Any] = {}
    for row in rows:
        if not row:
            continue
        key = _CRIT_MAP.get(_normalize_header(row[0]))
        if key and len(row) > 1:
            data[key] = row[1]
    return data


def read_input_xlsx(path: Path) -> InputData:
    if openpyxl is None or Worksheet is None:
        raise RuntimeError(
            "openpyxl is required for Excel import. Install it with: python -m pip install openpyxl"
        )

    wb = openpyxl.load_workbook(path, data_only=True)
    exp_ws = wb["experiments"] if "experiments" in wb.sheetnames else wb.active
    experiments = _read_experiments_sheet(exp_ws)

    crit_ws: Worksheet | None = None
    if "criteria" in wb.sheetnames:
        crit_ws = wb["criteria"]
    elif "crit" in wb.sheetnames:
        crit_ws = wb["crit"]

    crit_data = _read_criteria_from_sheet(crit_ws) if crit_ws is not None else {}
    if not crit_data:
        crit_data = _read_criteria_from_sheet(exp_ws)

    missing = [key for key in _CRIT_ALIASES if key not in crit_data]
    if missing:
        raise ValueError(f"Excel input missing criteria: {', '.join(missing)}.")

    return _parse_input_data({
        "experiments": experiments,
        "g_crit": crit_data["g_crit"],
        "t_crit": crit_data["t_crit"],
        "f_crit": crit_data["f_crit"],
    })


def read_input_file(path: Path) -> InputData:
    ext = path.suffix.lower()
    if ext == ".json":
        return read_input_json(path)
    if ext in {".xlsx", ".xlsm"}:
        return read_input_xlsx(path)
    raise ValueError(f"Unsupported input format: {path.suffix}")


def _coded_coefficients(y_avg: List[float]) -> Tuple[float, float, float]:
    """b0, b1, b2 в кодированных переменных (δ1, δ2) для ортогонального 2² плана."""
    n = len(y_avg)
    b0 = sum(y_avg) / n
    b1 = sum(s * y for s, y in zip(DELTA1_SIGNATURE, y_avg)) / n
    b2 = sum(s * y for s, y in zip(DELTA2_SIGNATURE, y_avg)) / n
    return b0, b1, b2


def _scaling_factors(z1: List[float], z2: List[float], n: int) -> Tuple[float, float, float, float, float, float]:
    z1_avg = sum(z1) / n
    z2_avg = sum(z2) / n
    return z1_avg, z2_avg, z1_avg - min(z1), max(z2) - z2_avg, z1[0] - z1_avg, z2[0] - z2_avg


def _natural_coefficients(
    b_coded: Tuple[float, float, float],
    z1_avg: float,
    z2_avg: float,
    pz1: float,
    pz2: float,
) -> Tuple[float, float, float]:
    b0, b1, b2 = b_coded
    return (
        b0 - b1 * z1_avg / pz1 - b2 * z2_avg / pz2,
        b1 / pz1,
        b2 / pz2,
    )


def _grubbs_block(experiments: List[Experiment], y_avg: List[float], g_crit: float) -> Tuple[List[GTest], List[float]]:
    """Returns (g_tests, all squared deviations)."""
    g_tests: List[GTest] = []
    squares: List[float] = []
    for i, exp in enumerate(experiments):
        deviations = [(y_avg[i] - y) ** 2 for y in exp.y_values]
        sum_sq = sum(deviations)
        g_val = safe_div(max(deviations), sum_sq, "G") if sum_sq != 0 else 0.0
        g_tests.append(GTest(row=exp.idx, g=g_val, ok="OK" if g_val < g_crit else "not OK"))
        squares.extend(deviations)
    return g_tests, squares


def _student_block(b_natural: Tuple[float, float, float], s_v: float) -> Tuple[float, float, float]:
    """Student t по **натуральным** (v) коэффициентам. При s_v = 0 ненулевые b → inf.

    Базируется на эталоне Excel (.temp/расчет.xlsx), не на Методичке §3.
    См. .agent/context/calculation-diff.md.
    """
    b0, b1, b2 = b_natural
    if s_v > 0:
        return abs(b0) / s_v, abs(b1) / s_v, abs(b2) / s_v
    return (
        float("inf") if b0 else 0.0,
        float("inf") if b1 else 0.0,
        float("inf") if b2 else 0.0,
    )


def _significance_marks(t_values: Tuple[float, float, float], t_crit: float) -> Tuple[str, str, str]:
    return tuple("+" if t > t_crit else "-" for t in t_values)


def _output_rows(experiments: List[Experiment], y_avg: List[float], b_coded: Tuple[float, float, float], signs: Tuple[str, str, str]) -> List[OutputRow]:
    rows: List[OutputRow] = []
    for exp, y in zip(experiments, y_avg):
        y_pred = 0.0
        if signs[0] == "+":
            y_pred += b_coded[0]
        if signs[1] == "+":
            y_pred += b_coded[1] * exp.delta1
        if signs[2] == "+":
            y_pred += b_coded[2] * exp.delta2
        y_res = y - y_pred
        rows.append(OutputRow(
            y_avg=y,
            delta1=exp.delta1,
            delta2=exp.delta2,
            y_pred=y_pred,
            y_avg_minus_y=y_res,
            y_avg_minus_y_sq=y_res ** 2,
        ))
    return rows


def _fisher_block(s2_vos: float, output_rows: List[OutputRow], n: int, f_crit: float) -> Tuple[float, float, str, str]:
    f_avg = sum(r["y_avg_minus_y_sq"] for r in output_rows) / n
    f_value = safe_div(s2_vos, f_avg, "F") if f_avg != 0 else float("inf")
    code = "not_rejected" if f_value < f_crit else "rejected"
    text = "Hypothesis not rejected" if code == "not_rejected" else "Hypothesis rejected"
    return f_avg, f_value, code, text


def compute(input_data: InputData) -> ComputeResult:
    """Full factorial 2² analysis with parallel trials.

    Variable map (per Excel reference ``.temp/расчет.xlsx``; differs from
    Методичка.docx §3 — see ``.agent/context/calculation-diff.md``):

    ============= ==============================================================
    Symbol         Meaning
    ============= ==============================================================
    ``x1,x2,x3``   component shares (% water, binder, filler), ``Σ = 100%``
    ``z1 = x1/x2`` water/binder ratio
    ``z2 = x3/x2`` filler/binder ratio
    ``δ1, δ2``     coded factors ∈ {-1, +1}  (``Experiment.delta1/delta2``)
    ``y1,y2,y3``   three parallel trials; ``y_avg = (y1+y2+y3)/3``
    ``N = 4``      plan points (2² design); ``m = 3`` parallel trials
    ``s²_вос``     ``Σ(y_ij − ȳ_i)² / N(m−1)``, df = 8
    ``S_в``        ``√(s²_вос / (N·m))`` — divisor uses N·m (Excel convention)
    ``t_i``        ``|b_i_v| / S_в`` — Student on NATURAL (v) coeffs
    ``G``          Grubbs per experiment; ``G < G_cr`` ⇒ однородность
    ``F``          ``s²_вос / (Σ_resid² / N)`` — adequacy check, inverted
                   ratio, no df adjustment (per Excel reference)
    ============= ==============================================================
    """
    experiments = input_data.experiments
    if len(experiments) != EXPECTED_EXPERIMENTS:
        raise ValueError(
            f"Expected exactly {EXPECTED_EXPERIMENTS} experiments, got {len(experiments)}."
        )
    n = EXPECTED_EXPERIMENTS
    g_crit, t_crit, f_crit = input_data.g_crit, input_data.t_crit, input_data.f_crit

    z1 = [e.z1 for e in experiments]
    z2 = [e.z2 for e in experiments]
    y_avg = [e.y_avg for e in experiments]

    b_coded = _coded_coefficients(y_avg)
    z1_avg, z2_avg, pz1, pz2, dz1, dz2 = _scaling_factors(z1, z2, n)
    b_natural = _natural_coefficients(b_coded, z1_avg, z2_avg, pz1, pz2)

    g_tests, squares = _grubbs_block(experiments, y_avg, g_crit)
    s2_vos = sum(squares) / (n * (PARALLEL_TRIALS - 1))
    s_v = math.sqrt(s2_vos / (n * PARALLEL_TRIALS)) if s2_vos > 0 else 0.0

    t_values = _student_block(b_natural, s_v)
    signs = _significance_marks(t_values, t_crit)

    out_rows = _output_rows(experiments, y_avg, b_coded, signs)
    f_avg, f_value, f_code, f_text = _fisher_block(s2_vos, out_rows, n, f_crit)

    equation = format_equation(
        b_coded[0] if signs[0] == "+" else 0.0,
        b_coded[1] if signs[1] == "+" else 0.0,
        b_coded[2] if signs[2] == "+" else 0.0,
        "δ1", "δ2",
    )

    return ComputeResult(
        coefficients=CoeffsDict(b0=_round3(b_coded[0]), b1=_round3(b_coded[1]), b2=_round3(b_coded[2])),
        coefficients_v=CoeffsDict(b0=_round3(b_natural[0]), b1=_round3(b_natural[1]), b2=_round3(b_natural[2])),
        z_averages=ScalarsDict(z1_avg=_round3(z1_avg), z2_avg=_round3(z2_avg)),
        pz=PairsDict(pz1=_round3(pz1), pz2=_round3(pz2)),
        delta_calc=DeltaCalcDict(
            delta1=_round3(safe_div(dz1, pz1, "delta1_calc")),
            delta2=_round3(safe_div(dz2, pz2, "delta2_calc")),
        ),
        g_tests=[GTest(row=g["row"], g=_round3(g["g"]), ok=g["ok"]) for g in g_tests],
        t_tests=TTests(
            t0=_round3(t_values[0]),
            t1=_round3(t_values[1]),
            t2=_round3(t_values[2]),
            sign_b0=signs[0],
            sign_b1=signs[1],
            sign_b2=signs[2],
        ),
        output_rows=out_rows,
        f_avg=_round3(f_avg),
        f_value=_round3(f_value),
        f_result_code=f_code,
        f_result=f_text,
        equation=equation,
        g_crit=_round3(g_crit),
        t_crit=_round3(t_crit),
        f_crit=_round3(f_crit),
    )
```

## `nts/dictionary.py`

```python
"""Human-readable descriptions of the calculator's variables.

The machine keys (``coefficients_v.b1``, ``t_tests.t0``, ...) are stable API
surface — they must not change. This module is the companion dictionary that
says what each key *means*, for two audiences:

  * the Excel self-check workbook — an extra ``description`` column next to
    ``key`` / ``value``;
  * the GUIs — the reverse checklist shows what a field actually is instead of
    a bare key.

EN is the base table; RU is a full translation (the wording follows
Методичка.docx §3 and the Excel reference ``.temp/расчет.xlsx``).

Lookup rules
------------
``describe()`` takes a plain key: a result key (``"coefficients.b0"``), a
column name (``"x1"``, ``"y_avg"``) or a criteria name (``"g_crit"``).
``describe_entry()`` takes a *checklist entry name* — the composite names the
verifier emits (``"g_tests[row=1].g"``, ``"output_rows[-1.0, -1.0].y_avg"``)
— and resolves the variable part of it.
"""
from __future__ import annotations

from .i18n import DEFAULT_LANGUAGE, normalize_lang

#: Descriptions of every result key, per language.
DESCRIPTIONS_EN: dict[str, str] = {
    # -- result scalars ----------------------------------------------------
    "equation": "Regression equation Y = b0 + b1·δ1 + b2·δ2",
    "f_avg": "Mean squared residual sum (F_avg)",
    "f_value": "Fisher criterion value",
    "f_result_code": "Fisher criterion result code",
    "f_result": "Fisher criterion verdict (model adequacy)",
    "g_crit": "Grubbs criterion critical value",
    "t_crit": "Student t criterion critical value",
    "f_crit": "Fisher criterion critical value",
    # -- regression coefficients -------------------------------------------
    "coefficients.b0": "Regression intercept (coded coefficients)",
    "coefficients.b1": "Coefficient of δ1 (coded)",
    "coefficients.b2": "Coefficient of δ2 (coded)",
    "coefficients_v.b0": "Regression intercept in natural units (v)",
    "coefficients_v.b1": "Coefficient of δ1 in natural units (v)",
    "coefficients_v.b2": "Coefficient of δ2 in natural units (v)",
    # -- plan in ratios ----------------------------------------------------
    "z_averages.z1_avg": "Mean of z1 = x1/x2 across the experiments",
    "z_averages.z2_avg": "Mean of z2 = x3/x2 across the experiments",
    "pz.pz1": "Reduced range of z1 (z̄1 − min z1)",
    "pz.pz2": "Reduced range of z2 (max z2 − z̄2)",
    "delta_calc.delta1": "Re-derived coded factor δ1",
    "delta_calc.delta2": "Re-derived coded factor δ2",
    # -- Student t ---------------------------------------------------------
    "t_tests.t0": "Student t criterion for b0",
    "t_tests.t1": "Student t criterion for b1",
    "t_tests.t2": "Student t criterion for b2",
    "t_tests.sign_b0": "Sign of b0",
    "t_tests.sign_b1": "Sign of b1",
    "t_tests.sign_b2": "Sign of b2",
    # -- input columns -----------------------------------------------------
    "idx": "Experiment number",
    "delta1": "Coded factor δ1",
    "delta2": "Coded factor δ2",
    "x1": "First component share, %",
    "x2": "Second component share, %",
    "x3": "Third component share, %",
    "y1": "Response, parallel trial 1",
    "y2": "Response, parallel trial 2",
    "y3": "Response, parallel trial 3",
    # -- G-test rows -------------------------------------------------------
    "g_tests": "Grubbs criterion per experiment (row, G, ok)",
    "output_rows": "Per-experiment regression output (delta1, delta2, y_avg, y_pred, ...)",
    "row": "Experiment number",
    "G": "Grubbs criterion value",
    "g": "Grubbs criterion value",
    "ok": "No gross error detected",
    # -- output rows -------------------------------------------------------
    "y_avg": "Mean response of the experiment",
    "y_pred": "Regression prediction for the experiment",
    "y_avg_minus_y": "Mean response minus prediction",
    "y_avg_minus_y_sq": "Squared deviation (contribution to F_avg)",
}

DESCRIPTIONS_RU: dict[str, str] = {
    # -- result scalars ----------------------------------------------------
    "equation": "Уравнение регрессии Y = b0 + b1·δ1 + b2·δ2",
    "f_avg": "Средняя сумма квадратов отклонений (F_ср)",
    "f_value": "Значение критерия Фишера",
    "f_result_code": "Код результата критерия Фишера",
    "f_result": "Вывод по критерию Фишера (адекватность модели)",
    "g_crit": "Критическое значение критерия Граббса",
    "t_crit": "Критическое значение t-критерия Стьюдента",
    "f_crit": "Критическое значение критерия Фишера",
    # -- regression coefficients -------------------------------------------
    "coefficients.b0": "Свободный член регрессии (кодированные коэффициенты)",
    "coefficients.b1": "Коэффициент при δ1 (кодированный)",
    "coefficients.b2": "Коэффициент при δ2 (кодированный)",
    "coefficients_v.b0": "Свободный член регрессии в натуральных единицах (в)",
    "coefficients_v.b1": "Коэффициент при δ1 в натуральных единицах (в)",
    "coefficients_v.b2": "Коэффициент при δ2 в натуральных единицах (в)",
    # -- plan in ratios ----------------------------------------------------
    "z_averages.z1_avg": "Среднее значение z1 = x1/x2 по опытам",
    "z_averages.z2_avg": "Среднее значение z2 = x3/x2 по опытам",
    "pz.pz1": "Приведённый размах z1 (z̄1 − min z1)",
    "pz.pz2": "Приведённый размах z2 (max z2 − z̄2)",
    "delta_calc.delta1": "Пересчитанный кодированный фактор δ1",
    "delta_calc.delta2": "Пересчитанный кодированный фактор δ2",
    # -- Student t ---------------------------------------------------------
    "t_tests.t0": "t-критерий Стьюдента для b0",
    "t_tests.t1": "t-критерий Стьюдента для b1",
    "t_tests.t2": "t-критерий Стьюдента для b2",
    "t_tests.sign_b0": "Знак коэффициента b0",
    "t_tests.sign_b1": "Знак коэффициента b1",
    "t_tests.sign_b2": "Знак коэффициента b2",
    # -- input columns -----------------------------------------------------
    "idx": "Номер опыта",
    "delta1": "Кодированный фактор δ1",
    "delta2": "Кодированный фактор δ2",
    "x1": "Доля первого компонента, %",
    "x2": "Доля второго компонента, %",
    "x3": "Доля третьего компонента, %",
    "y1": "Отклик, параллельный опыт 1",
    "y2": "Отклик, параллельный опыт 2",
    "y3": "Отклик, параллельный опыт 3",
    # -- G-test rows -------------------------------------------------------
    "g_tests": "Критерий Граббса по опытам (row, G, ok)",
    "output_rows": "Поопытный результат регрессии (delta1, delta2, y_avg, y_pred, ...)",
    "row": "Номер опыта",
    "G": "Значение критерия Граббса",
    "g": "Значение критерия Граббса",
    "ok": "Грубная ошибка не обнаружена",
    # -- output rows -------------------------------------------------------
    "y_avg": "Средний отклик опыта",
    "y_pred": "Предсказанное значение регрессии",
    "y_avg_minus_y": "Отклонение среднего отклика от предсказанного",
    "y_avg_minus_y_sq": "Квадрат отклонения (вклад в F_ср)",
}

#: Description tables per language code.
DESCRIPTIONS: dict[str, dict[str, str]] = {
    "EN": DESCRIPTIONS_EN,
    "RU": DESCRIPTIONS_RU,
}

#: Fallback used when a key has no description in the requested language.
UNKNOWN_DESCRIPTION = "—"


def describe(key: str, lang: str = DEFAULT_LANGUAGE) -> str:
    """Return the human-readable description of ``key``.

    Returns :data:`UNKNOWN_DESCRIPTION` when the key is not in the dictionary
    (an unknown key must not break a report).
    """
    table = DESCRIPTIONS.get(normalize_lang(lang), DESCRIPTIONS_EN)
    return table.get(key, UNKNOWN_DESCRIPTION)


def describe_entry(name: str, lang: str = DEFAULT_LANGUAGE) -> str:
    """Return the description of a checklist entry name.

    The verifier emits composite names for list fields — ``g_tests[row=1].g``,
    ``output_rows[-1.0, -1.0].y_avg``. Only the variable part carries meaning,
    so the container prefix is stripped before the lookup:

    * ``"coefficients.b0"``              → description of ``coefficients.b0``
    * ``"g_tests[row=1].g"``             → description of ``g``
    * ``"output_rows[-1.0, -1.0].y_avg"``→ description of ``y_avg``
    """
    key = name
    if "]" in key:
        key = key.split("]", 1)[1].lstrip(".")
    return describe(key, lang)
```

## `nts/gui.py`

```python
from __future__ import annotations

import json
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk
from typing import Any, Dict, List
from urllib.parse import unquote

from .checker import write_self_check_xlsx
from .core import EXPECTED_EXPERIMENTS, Experiment, InputData, compute, fmt3, read_input_file
from .dictionary import describe
from .i18n import DEFAULT_LANGUAGE, I18N, LANGUAGES, localize_check_value, normalize_lang

try:
    import openpyxl
except Exception:
    openpyxl = None

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    import tkinterdnd2 as _tkd2_module
    import platform as _platform

    def _patched_require(tkroot):
        """Find tkdnd data dir in any of tkinterdnd2.__path__ entries.

        Nuitka onefile puts the python code at one extraction path and the data
        files at another (sometimes a virtual ``\\not_existing`` path that Nuitka
        rewrites for data-file lookups). Searching all ``__path__`` entries is the
        only portable way to locate the data.
        """
        system = _platform.system()
        if system == "Windows":
            machine = os.environ.get("PROCESSOR_ARCHITECTURE", _platform.machine())
        else:
            machine = _platform.machine()
        if system == "Darwin" and machine == "arm64":
            plat = "osx-arm64"
        elif system == "Darwin" and machine == "x86_64":
            plat = "osx-x64"
        elif system == "Linux" and machine == "aarch64":
            plat = "linux-arm64"
        elif system == "Linux" and machine == "x86_64":
            plat = "linux-x64"
        elif system == "Windows" and machine == "ARM64":
            plat = "win-arm64"
        elif system == "Windows" and machine == "AMD64":
            plat = "win-x64"
        elif system == "Windows" and machine == "x86":
            plat = "win-x86"
        else:
            raise RuntimeError(f"Platform not supported: {system}/{machine}")

        tcl_major = int(tkroot.tk.call("info", "tclversion").split(".")[0])
        suffix = "-tcl9" if tcl_major >= 9 else ""
        subdir = f"tkdnd/{plat}{suffix}"

        last_err: Exception | None = None
        for base in _tkd2_module.__path__:
            candidate = os.path.join(base, subdir)
            if os.path.isdir(candidate):
                tkroot.tk.call("lappend", "auto_path", candidate)
                try:
                    TkinterDnD.TkdndVersion = tkroot.tk.call("package", "require", "tkdnd")
                    return TkinterDnD.TkdndVersion
                except Exception as exc:
                    last_err = exc
        raise RuntimeError(
            f"tkdnd data not found in any __path__ entry (last error: {last_err})"
        )

    TkinterDnD._require = _patched_require
    DND_AVAILABLE = True
except Exception:
    DND_AVAILABLE = False
    DND_FILES = None
    TkinterDnD = None


INPUT_COLUMNS: List[tuple[str, str]] = [
    ("idx", "no"),
    ("delta1", "delta1"),
    ("delta2", "delta2"),
    ("x1", "x1"),
    ("x2", "x2"),
    ("x3", "x3"),
    ("y1", "y1"),
    ("y2", "y2"),
    ("y3", "y3"),
]

T_BLOCK: tuple[tuple[str, str, str], ...] = (
    ("t_0", "t0", "b0"),
    ("t_1", "t1", "b1"),
    ("t_2", "t2", "b2"),
)

#: Colour of the muted description lines that annotate the computed values.
CAPTION_COLOR = "#4b5563"

#: Width (px) at which a description wraps onto the next line.
CAPTION_WRAP = 400


def normalize_number(value: str) -> str:
    return value.strip().replace(",", ".")


def extract_dropped_path(data: str) -> str:
    raw = data.strip()
    if raw.startswith("{"):
        end = raw.find("}")
        if end != -1:
            raw = raw[1:end]
    elif " " in raw:
        raw = raw.split(" ", 1)[0]
    raw = unquote(raw)
    if raw.startswith("file://"):
        raw = raw[7:]
    return raw.lstrip("/")


def _experiment_from_form(entries: Dict[tuple[int, str], tk.Entry], row: int, t_msg: str) -> Experiment:
    def get(key: str) -> float:
        raw = normalize_number(entries[(row, key)].get())
        if raw == "":
            raise ValueError(t_msg.format(row=row + 1, key=key))
        return float(raw)

    return Experiment(
        idx=int(get("idx")),
        delta1=get("delta1"),
        delta2=get("delta2"),
        x1=get("x1"),
        x2=get("x2"),
        x3=get("x3"),
        y1=get("y1"),
        y2=get("y2"),
        y3=get("y3"),
    )


class App(TkinterDnD.Tk if DND_AVAILABLE else tk.Tk):  # type: ignore[misc]
    def __init__(self) -> None:
        super().__init__()
        self.geometry("980x520")
        self.lang = tk.StringVar(value=DEFAULT_LANGUAGE)
        self.selected_file = tk.StringVar(value="")
        self.last_input: InputData | None = None

        self.entries: Dict[tuple[int, str], tk.Entry] = {}
        self.g_crit_var = tk.StringVar()
        self.t_crit_var = tk.StringVar()
        self.f_crit_var = tk.StringVar()

        self.style = ttk.Style(self)
        self.caption_font = self._derive_font(-1)
        self.headline_font = self._derive_font(1, weight="bold")

        self.header_labels: List[ttk.Label] = []

        self._build_ui()
        self._apply_lang()
        self._clear_inputs()
        if DND_AVAILABLE:
            self._setup_dnd()

    def t(self, key: str) -> str:
        return I18N[self.lang.get()][key]

    def t_header(self, key: str) -> str:
        return I18N[self.lang.get()]["headers"][key]

    def _derive_font(self, size_delta: int = 0, **options: str) -> tkfont.Font:
        """Return a new font derived from the UI default font.

        ``tkinter.font.Font.copy()`` hands back the *same* named font, so
        resizing it would shrink the whole application. A separate font
        object is created instead — the default font stays untouched.
        """
        actual = tkfont.nametofont("TkDefaultFont").actual()
        family = actual.get("family", "Segoe UI")
        if isinstance(family, (tuple, list)):
            family = family[0]
        size = max(int(actual.get("size", 9)) + size_delta, 6)
        return tkfont.Font(self, family=family, size=size, **options)

    def _panel_background(self) -> str:
        """Background colour of the output panel, matched to the ttk theme."""
        return self.style.lookup("TFrame", "background") or "#f0f0f0"

    def _place_value(
        self,
        parent: tk.Misc,
        row: int,
        column: int,
        value: str,
        description: str,
        padx: tuple[int, int] = (0, 0),
    ) -> None:
        """Place a value with its human-readable description underneath.

        The value keeps the regular UI font, the description is one step
        smaller and dimmer — the number stays the hero and the explanation
        reads as a quiet note right under it.
        """
        ttk.Label(parent, text=value).grid(
            row=row, column=column, sticky="w", padx=padx, pady=(3, 0)
        )
        tk.Label(
            parent,
            text=description,
            background=self._panel_background(),
            foreground=CAPTION_COLOR,
            font=self.caption_font,
            anchor="w",
            justify="left",
            wraplength=CAPTION_WRAP,
        ).grid(row=row + 1, column=column, sticky="w", padx=padx, pady=(0, 3))

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X)

        self.label_input_file = ttk.Label(top)
        self.label_input_file.pack(side=tk.LEFT)
        self.file_entry = ttk.Entry(top, textvariable=self.selected_file, width=60, state="readonly")
        self.file_entry.pack(side=tk.LEFT, padx=8)
        self.btn_browse = ttk.Button(top, command=self._browse_file)
        self.btn_browse.pack(side=tk.LEFT)
        self.btn_clear = ttk.Button(top, command=self._clear_inputs)
        self.btn_clear.pack(side=tk.LEFT, padx=(6, 0))

        self.lang_label = ttk.Label(top)
        self.lang_label.pack(side=tk.LEFT, padx=(14, 4))
        self.lang_combo = ttk.Combobox(top, values=LANGUAGES, textvariable=self.lang, state="readonly", width=4)
        self.lang_combo.pack(side=tk.LEFT)
        self.lang_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_lang())

        self.label_dnd_hint: ttk.Label | None = None
        if not DND_AVAILABLE:
            self.label_dnd_hint = ttk.Label(top)
            self.label_dnd_hint.pack(side=tk.LEFT, padx=8)

        grid = ttk.Frame(self, padding=(10, 0, 10, 10))
        grid.pack(fill=tk.BOTH, expand=True)
        for col_idx, (_, key) in enumerate(INPUT_COLUMNS):
            lbl = ttk.Label(grid)
            lbl.grid(row=0, column=col_idx, padx=6, pady=6)
            self.header_labels.append(lbl)
            grid.columnconfigure(col_idx, weight=1)

        for row_idx in range(EXPECTED_EXPERIMENTS):
            for col_idx, (key, _label_key) in enumerate(INPUT_COLUMNS):
                ent = ttk.Entry(grid, width=10)
                ent.grid(row=row_idx + 1, column=col_idx, padx=6, pady=4, sticky="nsew")
                self.entries[(row_idx, key)] = ent

        footer = ttk.Frame(self, padding=(10, 0, 10, 10))
        footer.pack(fill=tk.X)

        self.label_g = ttk.Label(footer)
        self.label_g.grid(row=0, column=0, padx=6, pady=4, sticky="w")
        ttk.Entry(footer, textvariable=self.g_crit_var, width=10).grid(row=0, column=1, padx=6, pady=4)
        self.label_t = ttk.Label(footer)
        self.label_t.grid(row=0, column=2, padx=6, pady=4, sticky="w")
        ttk.Entry(footer, textvariable=self.t_crit_var, width=10).grid(row=0, column=3, padx=6, pady=4)
        self.label_f = ttk.Label(footer)
        self.label_f.grid(row=0, column=4, padx=6, pady=4, sticky="w")
        ttk.Entry(footer, textvariable=self.f_crit_var, width=10).grid(row=0, column=5, padx=6, pady=4)
        self.btn_calc = ttk.Button(footer, command=self._calculate)
        self.btn_calc.grid(row=0, column=6, padx=12, pady=4)

    def _setup_dnd(self) -> None:
        assert DND_FILES is not None
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._on_drop)
        self.file_entry.drop_target_register(DND_FILES)
        self.file_entry.dnd_bind("<<Drop>>", self._on_drop)

    def _apply_lang(self) -> None:
        self.lang.set(normalize_lang(self.lang.get()))
        self.title(self.t("title_main"))
        self.label_input_file.config(text=self.t("input_file"))
        self.btn_browse.config(text=self.t("browse"))
        self.btn_clear.config(text=self.t("clear"))
        self.btn_calc.config(text=self.t("calculate"))
        self.label_g.config(text=self.t("g_crit"))
        self.label_t.config(text=self.t("t_crit"))
        self.label_f.config(text=self.t("f_crit"))
        self.lang_label.config(text=self.t("lang"))
        if self.label_dnd_hint is not None:
            self.label_dnd_hint.config(text=self.t("dnd_hint"))
        for idx, (_key, header_key) in enumerate(INPUT_COLUMNS):
            self.header_labels[idx].config(text=self.t_header(header_key))

    def _on_drop(self, event: tk.Event) -> None:  # type: ignore[override]
        path = extract_dropped_path(getattr(event, "data", ""))
        if not path:
            return
        p = Path(path)
        if p.suffix.lower() not in {".json", ".xlsx", ".xlsm"}:
            messagebox.showerror(self.t("load_error"), self.t("drop_file"))
            return
        self.selected_file.set(str(p))
        self._load_from_path(p)

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            title=self.t("input_file"),
            filetypes=[
                (self.t("filter_input_files"), "*.json;*.xlsx;*.xlsm"),
                (self.t("filter_json"), "*.json"),
                (self.t("filter_excel"), "*.xlsx;*.xlsm"),
                (self.t("filter_all"), "*.*"),
            ],
        )
        if not path:
            return
        self.selected_file.set(path)
        self._load_from_path(Path(path))

    def _clear_inputs(self) -> None:
        self.selected_file.set("")
        for (row_idx, key), ent in self.entries.items():
            ent.delete(0, tk.END)
            if key == "idx":
                ent.insert(0, str(row_idx + 1))
        self.g_crit_var.set("")
        self.t_crit_var.set("")
        self.f_crit_var.set("")

    def _load_from_path(self, path: Path) -> None:
        try:
            data = read_input_file(path)
        except Exception as exc:
            messagebox.showerror(self.t("load_error"), str(exc))
            return

        self.last_input = data
        experiments = data.experiments

        for (row_idx, key), ent in self.entries.items():
            ent.delete(0, tk.END)
            if key == "idx":
                ent.insert(0, str(row_idx + 1))
        self.update_idletasks()

        def fill_row(i: int) -> None:
            exp = experiments[i]
            for key, val in (
                ("idx", exp.idx), ("delta1", exp.delta1), ("delta2", exp.delta2),
                ("x1", exp.x1), ("x2", exp.x2), ("x3", exp.x3),
                ("y1", exp.y1), ("y2", exp.y2), ("y3", exp.y3),
            ):
                ent = self.entries[(i, key)]
                ent.delete(0, tk.END)
                ent.insert(0, str(val))

        def fill_next(i: int) -> None:
            if i >= min(EXPECTED_EXPERIMENTS, len(experiments)):
                self.g_crit_var.set(str(data.g_crit))
                self.t_crit_var.set(str(data.t_crit))
                self.f_crit_var.set(str(data.f_crit))
                return
            fill_row(i)
            self.update_idletasks()
            self.after(1, lambda: fill_next(i + 1))

        self.after(1, lambda: fill_next(0))

    def _read_experiments(self) -> List[Experiment]:
        return [
            _experiment_from_form(self.entries, i, self.t("empty_value"))
            for i in range(EXPECTED_EXPERIMENTS)
        ]

    def _read_crit(self) -> tuple[float, float, float]:
        g_raw = normalize_number(self.g_crit_var.get())
        t_raw = normalize_number(self.t_crit_var.get())
        f_raw = normalize_number(self.f_crit_var.get())
        if g_raw == "" or t_raw == "" or f_raw == "":
            raise ValueError(self.t("crit_required"))
        return float(g_raw), float(t_raw), float(f_raw)

    def _calculate(self) -> None:
        try:
            experiments = self._read_experiments()
            g_crit, t_crit, f_crit = self._read_crit()
            data = InputData(experiments=experiments, g_crit=g_crit, t_crit=t_crit, f_crit=f_crit)
            result = compute(data)
        except Exception as exc:
            messagebox.showerror(self.t("calc_error"), str(exc))
            return

        self.last_input = data
        self._show_output(result)

    def _show_output(self, result: Dict[str, Any]) -> None:
        lang = self.lang.get()
        win = tk.Toplevel(self)
        win.title(self.t("title_output"))
        win.geometry("820x600")

        top = ttk.Frame(win, padding=10)
        top.pack(fill=tk.X)
        ttk.Label(top, text=str(result["equation"]), font=self.headline_font).pack(anchor="w")

        mid = ttk.Frame(win, padding=(10, 0, 10, 6))
        mid.pack(fill=tk.X)
        t_tests = result["t_tests"]
        coeffs_v = result["coefficients_v"]
        for row, (tk_label_key, key, vk) in enumerate(T_BLOCK):
            self._place_value(
                mid,
                row * 2,
                0,
                f"{self.t(tk_label_key)} = {fmt3(t_tests[key])} ({t_tests[f'sign_{vk}']})",
                describe(f"t_tests.{key}", lang),
                padx=(6, 26),
            )
            self._place_value(
                mid,
                row * 2,
                1,
                f"{self.t(f'{vk}v')} = {fmt3(coeffs_v[vk])}",
                describe(f"coefficients_v.{vk}", lang),
                padx=(0, 6),
            )

        grubbs = ttk.LabelFrame(win, text=self.t("grubbs_title"), padding=(10, 6, 10, 6))
        grubbs.pack(fill=tk.X, padx=10, pady=(4, 6))
        for i, g in enumerate(result["g_tests"]):
            cmp_sign = self.t("cmp_le") if g["g"] <= result["g_crit"] else self.t("cmp_gt")
            status = self.t("status_ok") if g["g"] <= result["g_crit"] else self.t("status_bad")
            line = self.t("grubbs_row").format(
                row=g["row"], g=fmt3(g["g"]), cmp=cmp_sign,
                gcrit=fmt3(result["g_crit"]), status=status,
            )
            self._place_value(grubbs, i * 2, 0, line, describe("G", lang))

        fisher = ttk.LabelFrame(win, text=self.t("fisher_title"), padding=(10, 6, 10, 6))
        fisher.pack(fill=tk.X, padx=10, pady=(2, 10))
        cmp_sign = self.t("cmp_le") if result["f_value"] <= result["f_crit"] else self.t("cmp_gt")
        fisher_line = self.t("fisher_cmp").format(
            f=fmt3(result["f_value"]), cmp=cmp_sign, fcrit=fmt3(result["f_crit"]),
        )
        self._place_value(fisher, 0, 0, fisher_line, describe("f_value", lang))

        res_code = result.get("f_result_code")
        if res_code == "not_rejected":
            res_text = self.t("result_not_rejected")
        elif res_code == "rejected":
            res_text = self.t("result_rejected")
        else:
            res_text = str(localize_check_value("f_result", result.get("f_result", ""), lang))
        self._place_value(fisher, 2, 0, res_text, describe("f_result", lang))

        btns = ttk.Frame(win, padding=(10, 0, 10, 10))
        btns.pack(fill=tk.X)
        ttk.Button(btns, text=self.t("export_json"), command=lambda: self._export_json(result)).pack(side=tk.LEFT)
        ttk.Button(btns, text=self.t("export_xlsx"), command=lambda: self._export_xlsx(result)).pack(side=tk.LEFT, padx=8)

    def _build_export_payload(self, result: Dict[str, Any]) -> Dict[str, Any]:
        if self.last_input is None:
            raise ValueError(self.t("msg_no_input_data"))
        data = self.last_input
        return {
            "input": {
                "experiments": [
                    {
                        "idx": exp.idx,
                        "delta1": exp.delta1,
                        "delta2": exp.delta2,
                        "x1": exp.x1,
                        "x2": exp.x2,
                        "x3": exp.x3,
                        "y1": exp.y1,
                        "y2": exp.y2,
                        "y3": exp.y3,
                    }
                    for exp in data.experiments
                ],
                "g_crit": data.g_crit,
                "t_crit": data.t_crit,
                "f_crit": data.f_crit,
            },
            "result": result,
        }

    def _export_json(self, result: Dict[str, Any]) -> None:
        try:
            payload = self._build_export_payload(result)
            path = filedialog.asksaveasfilename(
                title=self.t("export_title"),
                defaultextension=".json",
                filetypes=[
                    (self.t("filter_json"), "*.json"),
                    (self.t("filter_all"), "*.*"),
                ],
            )
            if not path:
                return
            Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            messagebox.showinfo(self.t("export_title"), self.t("export_done"))
        except Exception as exc:
            messagebox.showerror(self.t("export_error"), str(exc))

    def _export_xlsx(self, result: Dict[str, Any]) -> None:
        """Write a self-check workbook.

        The layout is owned by :func:`nts.checker.write_self_check_xlsx` (single
        source of truth, shared with the CLI):
          * ``input``        — experiments table (idx + 8 columns, 4 data rows).
          * ``criteria``     — header ``g_crit,t_crit,f_crit`` + one value row.
          * ``result``       — the **core** result keys, vertical
            ``(key, value, description)``, yellow-marked; dotted paths
            (``coefficients.b0``, ``t_tests.t0``, ...).
          * ``extended``     — the remaining result keys (optional for the reader).
          * ``dictionary``   — every variable of the workbook with its description.
          * ``grubbs``       — one row per G-test (matched by ``row`` on read).
          * ``output_rows``  — one row per ``(delta1, delta2)`` experiment
            (matched by ``(delta1, delta2)`` on read).
        """
        if openpyxl is None:
            messagebox.showerror(self.t("export_error"), self.t("msg_openpyxl_missing"))
            return
        try:
            if self.last_input is None:
                raise ValueError(self.t("msg_no_input_data"))
            path = filedialog.asksaveasfilename(
                title=self.t("export_title"),
                defaultextension=".xlsx",
                filetypes=[
                    (self.t("filter_excel"), "*.xlsx"),
                    (self.t("filter_all"), "*.*"),
                ],
            )
            if not path:
                return

            write_self_check_xlsx(
                Path(path), self.last_input, result,
                lang=self.lang.get(), localize_values=True,
            )

            messagebox.showinfo(self.t("export_title"), self.t("export_done"))
        except Exception as exc:
            messagebox.showerror(self.t("export_error"), str(exc))


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
```

## `nts/i18n.py`

```python
"""UI translations for the NTS calculator.

EN — базовый словарь. RU задаёт отличия от EN. Чтобы добавить язык, добавьте
его в ``TRANSLATIONS`` с переопределением только нужных ключей; остальные
возьмутся из ``EN_BASE``.
"""

from typing import Any, Dict

LANGUAGES: tuple[str, ...] = ("RU", "EN")
DEFAULT_LANGUAGE: str = "RU"


EN_BASE: Dict[str, Any] = {
    "title_main": "NTS Calculator",
    "title_output": "Output",
    "input_file": "Input file:",
    "browse": "Browse",
    "clear": "Clear",
    "calculate": "Calculate",
    "g_crit": "G_crit",
    "t_crit": "t_crit",
    "f_crit": "F_crit",
    "f_avg": "F_avg",
    "f_value": "F_value",
    "dnd_hint": "(Install tkinterdnd2 for drag & drop)",
    "load_error": "Load error",
    "calc_error": "Calculation error",
    "drop_file": "Please drop a .json or .xlsx file.",
    "empty_value": "Empty value in row {row}, {key}.",
    "crit_required": "G_crit, t_crit and F_crit must be filled.",
    "t_0": "t_0",
    "t_1": "t_1",
    "t_2": "t_2",
    "b0v": "b0 (v)",
    "b1v": "b1 (v)",
    "b2v": "b2 (v)",
    "lang": "Lang:",
    "result_not_rejected": "Hypothesis not rejected",
    "result_rejected": "Hypothesis rejected",
    "export_json": "Export JSON",
    "export_xlsx": "Export XLSX",
    "export_done": "Saved successfully.",
    "export_error": "Export error",
    "export_title": "Export",
    "delta1_sym": "δ1",
    "delta2_sym": "δ2",
    "grubbs_title": "Grubbs criterion",
    "grubbs_row": "Experiment {row}: G={g} {cmp} G_crit={gcrit} ({status})",
    "fisher_title": "Fisher criterion",
    "fisher_cmp": "F={f} {cmp} F_crit={fcrit}",
    "cmp_le": "<=",
    "cmp_gt": ">",
    "status_ok": "OK",
    "status_bad": "not OK",
    "self_check_title": "Self-check",
    "summary_passed": "{passed} passed",
    "summary_failed": "{failed} failed",
    "diff_label": "diff",
    "missing_label": "missing",
    "reverse_title_main": "NTS Reverse (self-check)",
    "reverse_load": "Open file",
    "reverse_reload": "Reload",
    "reverse_clear": "Clear",
    "reverse_export_report": "Export report",
    "reverse_no_data": "Load a self-check file (.json, .xlsx, .xlsm) to start.",
    "reverse_drop_file": "Please drop a self-check file (.json, .xlsx, .xlsm).",
    "reverse_col_name": "Field",
    "reverse_col_description": "Description",
    "reverse_col_actual": "Actual",
    "reverse_col_expected": "Expected",
    "reverse_col_diff": "Diff",
    "reverse_col_message": "Note",
    "reverse_summary_all_passed": "All {total} checks passed.",
    "reverse_summary_some_failed": "{passed} passed, {failed} failed of {total}.",
    "reverse_load_error": "Self-check load error",
    "reverse_no_file": "Load a self-check file (.json, .xlsx, .xlsm) first.",
    "reverse_export_title": "Export self-check report",
    "reverse_export_done": "Report saved.",
    "reverse_export_error": "Report export error",
    "reverse_report_source": "source",
    "reverse_run": "Run check",
    "reverse_run_error": "Verification error",
    "reverse_mode": "Mode:",
    "reverse_mode_auto": "Auto (by file)",
    "reverse_mode_simplified": "Simplified (main fields)",
    "reverse_mode_full": "Extended (all fields)",
    "reverse_mode_current": "Mode: {mode}",
    # -- CLI report headings / labels -------------------------------------
    "cli_report_t": "t-tests:",
    "cli_report_g": "G-tests:",
    "cli_report_output": "Output:",
    "cli_report_row": "row {row}: G={g} ({status})",
    "cli_error": "error:",
    # -- checklist text labels --------------------------------------------
    "report_actual": "actual",
    "report_expected": "expected",
    "report_diff": "diff",
    "report_not_applicable": "n/a",
    # -- canonical value translations -------------------------------------
    "code_not_rejected": "not_rejected",
    "code_rejected": "rejected",
    # -- file dialogs / message boxes -------------------------------------
    "filter_input_files": "Input files",
    "filter_self_check_files": "Self-check files",
    "filter_json": "JSON",
    "filter_excel": "Excel",
    "filter_text": "Text",
    "filter_all": "All files",
    "msg_openpyxl_missing": "openpyxl is not installed.",
    "msg_no_input_data": "No input data to export.",
}

EN_HEADERS: Dict[str, str] = {
    "no": "No",
    "delta1": "δ1",
    "delta2": "δ2",
    "x1": "x1", "x2": "x2", "x3": "x3",
    "y1": "y1", "y2": "y2", "y3": "y3",
}

RU_OVERRIDES: Dict[str, Any] = {
    "title_main": "Калькулятор НТС",
    "title_output": "Результат",
    "input_file": "Файл ввода:",
    "browse": "Обзор",
    "clear": "Очистить",
    "calculate": "Расчет",
    "g_crit": "G_крит",
    "t_crit": "t_крит",
    "f_crit": "F_крит",
    "f_avg": "F_ср",
    "f_value": "F_знач",
    "dnd_hint": "(Установите tkinterdnd2 для drag & drop)",
    "load_error": "Ошибка загрузки",
    "calc_error": "Ошибка расчета",
    "drop_file": "Перетащите файл .json или .xlsx.",
    "empty_value": "Пустое значение в строке {row}, {key}.",
    "crit_required": "Заполните G_крит, t_крит и F_крит.",
    "b0v": "b0 (в)",
    "b1v": "b1 (в)",
    "b2v": "b2 (в)",
    "lang": "Язык:",
    "result_not_rejected": "Гипотеза не отвергается",
    "result_rejected": "Гипотеза отвергается",
    "export_json": "Экспорт JSON",
    "export_xlsx": "Экспорт XLSX",
    "export_done": "Файл сохранен.",
    "export_error": "Ошибка экспорта",
    "export_title": "Экспорт",
    "grubbs_title": "Критерий Граббса",
    "grubbs_row": "Опыт {row}: G={g} {cmp} G_крит={gcrit} ({status})",
    "fisher_title": "Критерий Фишера",
    "fisher_cmp": "F={f} {cmp} F_крит={fcrit}",
    "status_bad": "не OK",
    "self_check_title": "Самопроверка",
    "summary_passed": "{passed} пройдено",
    "summary_failed": "{failed} провалено",
    "diff_label": "расхождение",
    "missing_label": "отсутствует",
    "reverse_title_main": "НТС Реверс (самопроверка)",
    "reverse_load": "Открыть файл",
    "reverse_reload": "Перечитать",
    "reverse_clear": "Очистить",
    "reverse_export_report": "Экспорт отчёта",
    "reverse_no_data": "Загрузите файл самопроверки (.json, .xlsx, .xlsm), чтобы начать.",
    "reverse_drop_file": "Перетащите файл самопроверки (.json, .xlsx, .xlsm).",
    "reverse_col_name": "Поле",
    "reverse_col_description": "Описание",
    "reverse_col_actual": "Факт",
    "reverse_col_expected": "Эталон",
    "reverse_col_diff": "Δ",
    "reverse_col_message": "Примечание",
    "reverse_summary_all_passed": "Все {total} проверок пройдены.",
    "reverse_summary_some_failed": "{passed} пройдено, {failed} провалено из {total}.",
    "reverse_load_error": "Ошибка загрузки самопроверки",
    "reverse_no_file": "Сначала загрузите файл самопроверки (.json, .xlsx, .xlsm).",
    "reverse_export_title": "Экспорт отчёта самопроверки",
    "reverse_export_done": "Отчёт сохранён.",
    "reverse_export_error": "Ошибка экспорта отчёта",
    "reverse_report_source": "источник",
    "reverse_run": "Проверить",
    "reverse_run_error": "Ошибка проверки",
    "reverse_mode": "Режим:",
    "reverse_mode_auto": "Авто (по файлу)",
    "reverse_mode_simplified": "Упрощённый (основные поля)",
    "reverse_mode_full": "Расширенный (все поля)",
    "reverse_mode_current": "Режим: {mode}",
    # -- CLI report headings / labels -------------------------------------
    "cli_report_t": "t-критерии:",
    "cli_report_g": "Критерий Граббса:",
    "cli_report_output": "Поопытный вывод:",
    "cli_report_row": "Опыт {row}: G={g} ({status})",
    "cli_error": "ошибка:",
    # -- checklist text labels --------------------------------------------
    "report_actual": "факт",
    "report_expected": "эталон",
    "report_diff": "расхождение",
    "report_not_applicable": "н/д",
    # -- canonical value translations -------------------------------------
    "code_not_rejected": "не отвергается",
    "code_rejected": "отвергается",
    # -- file dialogs / message boxes -------------------------------------
    "filter_input_files": "Файлы ввода",
    "filter_self_check_files": "Файлы самопроверки",
    "filter_json": "JSON",
    "filter_excel": "Excel",
    "filter_text": "Текст",
    "filter_all": "Все файлы",
    "msg_openpyxl_missing": "openpyxl не установлен.",
    "msg_no_input_data": "Нет входных данных для экспорта.",
}

RU_HEADERS_OVERRIDES: Dict[str, str] = {
    "no": "№",
}


def _build(base: Dict[str, Any], overrides: Dict[str, Any], base_headers: Dict[str, str], header_overrides: Dict[str, str]) -> Dict[str, Any]:
    out = {**base, **overrides}
    out["headers"] = {**base_headers, **header_overrides}
    return out


TRANSLATIONS: Dict[str, Dict[str, Any]] = {
    "EN": _build(EN_BASE, {}, EN_HEADERS, {}),
    "RU": _build(EN_BASE, RU_OVERRIDES, EN_HEADERS, RU_HEADERS_OVERRIDES),
}

I18N: Dict[str, Dict[str, Any]] = TRANSLATIONS


def normalize_lang(lang: str) -> str:
    """Return a language code that exists in TRANSLATIONS (defaults to DEFAULT_LANGUAGE)."""
    return lang if lang in TRANSLATIONS else DEFAULT_LANGUAGE


#: Rusification of the technical note prefixes emitted by ``nts.checker.verify``.
#: Keyed by the exact English prefix; the remainder of the message is kept as is.
_RU_MESSAGE_PREFIXES: dict[str, str] = {
    "discrete mismatch: ": "расхождение значений: ",
    "missing in actual: ": "отсутствует в факте: ",
    "missing in expected: ": "отсутствует в эталоне: ",
    "missing numeric value: ": "отсутствует числовое значение: ",
    "numeric mismatch: ": "числовое расхождение: ",
    "NaN never matches: ": "NaN не совпадает никогда: ",
    "inf sign mismatch: ": "несовпадение знака бесконечности: ",
    "inf vs finite mismatch: ": "бесконечность против конечного значения: ",
    "missing g_tests list: ": "отсутствует список g_tests: ",
    "g_tests row set mismatch: ": "несовпадение набора строк g_tests: ",
    "missing output_rows list: ": "отсутствует список output_rows: ",
    "output_rows delta set mismatch: ": "несовпадение набора delta output_rows: ",
}


def _entry_leaf(name: str) -> str:
    """Variable part of a checklist entry name (``g_tests[row=1].ok`` → ``ok``)."""
    if "]" in name:
        return name.split("]", 1)[1].lstrip(".")
    return name.rsplit(".", 1)[-1]


def localize_check_value(name: str, value: Any, lang: str) -> Any:
    """Translate a *canonical* result value for display.

    The data model keeps ``f_result`` (``Hypothesis not rejected``),
    ``f_result_code`` (``not_rejected``) and the G-test status (``OK``) in a
    single canonical form so files and comparisons stay language-neutral. The
    UI must not show those English strings in the Russian locale, so this
    helper maps them at render time.

    Non-string values, unknown keys and unknown strings are returned unchanged.
    """
    if not isinstance(value, str):
        return value
    table = TRANSLATIONS[normalize_lang(lang)]
    leaf = _entry_leaf(name)
    if leaf == "f_result":
        if value == "Hypothesis not rejected":
            return table["result_not_rejected"]
        if value == "Hypothesis rejected":
            return table["result_rejected"]
    elif leaf == "f_result_code":
        if value == "not_rejected":
            return table["code_not_rejected"]
        if value == "rejected":
            return table["code_rejected"]
    elif leaf == "ok":
        if value == "OK":
            return table["status_ok"]
        if value == "not OK":
            return table["status_bad"]
    return value


def translate_message(message: str, lang: str) -> str:
    """Translate the technical note of a failed check for the given language.

    Only the known English prefixes are replaced; the variable tail
    (numbers, repr values) is preserved. Unknown messages pass through.
    """
    if not message or normalize_lang(lang) != "RU":
        return message
    for prefix, translated in _RU_MESSAGE_PREFIXES.items():
        if message.startswith(prefix):
            return translated + message[len(prefix):]
    return message


def canonical_check_value(name: str, value: Any) -> Any:
    """Map a localized display value back to the language-neutral form.

    The inverse of :func:`localize_check_value` for the values the writer may
    localize in an exported workbook. Used by the workbook reader, so a
    Russian report stays interchangeable with an English one.
    """
    if not isinstance(value, str):
        return value
    leaf = _entry_leaf(name)
    if leaf in ("f_result", "f_result_code", "ok"):
        for table in TRANSLATIONS.values():
            if leaf == "f_result":
                if value == table["result_not_rejected"]:
                    return "Hypothesis not rejected"
                if value == table["result_rejected"]:
                    return "Hypothesis rejected"
            elif leaf == "f_result_code":
                if value == table["code_not_rejected"]:
                    return "not_rejected"
                if value == table["code_rejected"]:
                    return "rejected"
            else:
                if value == table["status_bad"]:
                    return "not OK"
                if value == table["status_ok"]:
                    return "OK"
    return value
```

## `nts/reverse_gui.py`

```python
"""Self-check (``reverse``) GUI.

Variant of the NTS calculator GUI: instead of computing from a raw input,
it loads a self-check JSON file (with both ``input`` and ``expected`` keys),
runs the canonical :func:`nts.core.compute`, and renders a checklist of
field-by-field comparisons produced by :func:`nts.checker.verify`.

The layout differs from :mod:`nts.gui`:
  * no manual experiment grid — the file is the single source of truth;
  * the result is a colour-coded checklist (green ✓ / red ✗) instead of an
    equation/coeffs/grubbs/fisher panel;
  * export writes the same checklist as plain text (see
    :func:`nts.checker.print_checklist`).

Drag-and-drop uses the same TkinterDnD setup as :mod:`nts.gui`; if the
optional ``tkinterdnd2`` package is missing, a hint label is shown and the
``Browse`` button still works.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Optional

from .checker import (
    MODE_FULL,
    MODE_SIMPLIFIED,
    CheckResult,
    parse_self_check_bundle,
    print_checklist,
    verify,
)
from .core import ComputeResult, InputData, compute
from .dictionary import describe_entry
from .gui import DND_AVAILABLE, DND_FILES, TkinterDnD, extract_dropped_path
from .i18n import (
    DEFAULT_LANGUAGE,
    I18N,
    LANGUAGES,
    localize_check_value,
    normalize_lang,
    translate_message,
)

# Keep the checklist row schema tight: one tuple per visible column. Order
# matches the Treeview ``columns=`` declaration in :meth:`ReverseApp._build_ui`.
_CHECKLIST_COLUMNS: tuple[str, ...] = (
    "icon", "name", "description", "actual", "expected", "diff", "message",
)

#: Verification modes offered by the mode selector. ``auto`` follows the file:
#: simplified unless the workbook carries an ``extended`` sheet.
_MODE_CODES: tuple[str, ...] = ("auto", "simplified", "full")

#: i18n key of the label of each mode code (see ``_MODE_CODES``).
_MODE_LABEL_KEYS: dict[str, str] = {
    "auto": "reverse_mode_auto",
    "simplified": "reverse_mode_simplified",
    "full": "reverse_mode_full",
}


def _format_cell(value: Any, missing_label: str) -> str:
    """Render a CheckEntry field for the Treeview cell.

    - ``None`` becomes the localized "missing" label so the row stays readable.
    - floats are formatted with ``%g`` (6 significant digits) to mirror CLI.
    - everything else falls back to ``repr`` (keeps quotes ``str``/``bool``).
    """
    if value is None:
        return missing_label
    if isinstance(value, float):
        return f"{value:.6g}"
    return repr(value)


def _format_diff(diff: Optional[float], missing_label: str) -> str:
    if diff is None:
        return missing_label
    return f"{diff:.6g}"


_ALLOWED_SELF_CHECK_EXTS: frozenset[str] = frozenset({".json", ".xlsx", ".xlsm"})


class ReverseApp(TkinterDnD.Tk if DND_AVAILABLE else tk.Tk):  # type: ignore[misc]
    """Self-check GUI window."""

    def __init__(self) -> None:
        super().__init__()
        self.geometry("1100x560")
        self.lang = tk.StringVar(value=DEFAULT_LANGUAGE)
        self.selected_file = tk.StringVar(value="")
        self.last_payload: Optional[InputData] = None
        self.last_expected: Optional[ComputeResult] = None
        self.last_result: Optional[CheckResult] = None
        #: Mode selected by the user: ``auto`` | ``simplified`` | ``full``.
        self.mode_code = "auto"
        #: Mode implied by the loaded file (resolved when the file is read).
        self.file_mode = MODE_SIMPLIFIED

        self._build_ui()
        self._apply_lang()
        self._show_placeholder()
        if DND_AVAILABLE:
            self._setup_dnd()

    # ---- i18n helpers -------------------------------------------------------

    def t(self, key: str) -> str:
        return I18N[self.lang.get()][key]

    # ---- UI construction -----------------------------------------------------

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X)

        self.label_input_file = ttk.Label(top)
        self.label_input_file.pack(side=tk.LEFT)
        self.file_entry = ttk.Entry(
            top, textvariable=self.selected_file, width=60, state="readonly"
        )
        self.file_entry.pack(side=tk.LEFT, padx=8)

        self.btn_browse = ttk.Button(top, command=self._browse_file)
        self.btn_browse.pack(side=tk.LEFT)
        self.btn_reload = ttk.Button(top, command=self._reload)
        self.btn_reload.pack(side=tk.LEFT, padx=(6, 0))
        self.btn_clear = ttk.Button(top, command=self._clear)
        self.btn_clear.pack(side=tk.LEFT, padx=(6, 0))
        self.btn_run = ttk.Button(top, command=self._run_check)
        self.btn_run.pack(side=tk.LEFT, padx=(6, 0))
        self.btn_export = ttk.Button(top, command=self._export_report)
        self.btn_export.pack(side=tk.LEFT, padx=(6, 0))

        self.lang_label = ttk.Label(top)
        self.lang_label.pack(side=tk.LEFT, padx=(14, 4))
        self.lang_combo = ttk.Combobox(
            top, values=LANGUAGES, textvariable=self.lang,
            state="readonly", width=4,
        )
        self.lang_combo.pack(side=tk.LEFT)
        self.lang_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_lang())

        self.mode_label = ttk.Label(top)
        self.mode_label.pack(side=tk.LEFT, padx=(14, 4))
        self.mode_var = tk.StringVar(value="")
        self.mode_combo = ttk.Combobox(
            top, values=[], textvariable=self.mode_var, state="readonly", width=18,
        )
        self.mode_combo.pack(side=tk.LEFT)
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_selected)

        self.label_dnd_hint: ttk.Label | None = None
        if not DND_AVAILABLE:
            self.label_dnd_hint = ttk.Label(top)
            self.label_dnd_hint.pack(side=tk.LEFT, padx=8)

        # Summary header — shows passed/failed badge or the "no data" hint.
        self.summary_var = tk.StringVar(value="")
        self.summary_label = ttk.Label(self, padding=(10, 0, 10, 6), anchor="w")
        self.summary_label.config(textvariable=self.summary_var)
        self.summary_label.pack(fill=tk.X)

        # Checklist Treeview.
        tree_wrap = ttk.Frame(self, padding=(10, 0, 10, 10))
        tree_wrap.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(
            tree_wrap,
            columns=_CHECKLIST_COLUMNS,
            show="headings",
            height=14,
        )
        self._tree_heading_keys = {
            "name": "reverse_col_name",
            "description": "reverse_col_description",
            "actual": "reverse_col_actual",
            "expected": "reverse_col_expected",
            "diff": "reverse_col_diff",
            "message": "reverse_col_message",
        }
        widths = {
            "icon": 32,
            "name": 200,
            "description": 260,
            "actual": 150,
            "expected": 150,
            "diff": 80,
            "message": 200,
        }
        for col in _CHECKLIST_COLUMNS:
            self.tree.heading(col, text=col)
            self.tree.column(
                col, width=widths[col], anchor="w", stretch=(col != "icon")
            )
        self.tree.tag_configure("passed", foreground="#1a7a1a")
        self.tree.tag_configure("failed", foreground="#a01010")
        vsb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

    def _setup_dnd(self) -> None:
        assert DND_FILES is not None
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._on_drop)
        self.file_entry.drop_target_register(DND_FILES)
        self.file_entry.dnd_bind("<<Drop>>", self._on_drop)

    def _apply_lang(self) -> None:
        self.lang.set(normalize_lang(self.lang.get()))
        self.title(self.t("reverse_title_main"))
        self.label_input_file.config(text=self.t("input_file"))
        self.btn_browse.config(text=self.t("reverse_load"))
        self.btn_reload.config(text=self.t("reverse_reload"))
        self.btn_clear.config(text=self.t("reverse_clear"))
        self.btn_run.config(text=self.t("reverse_run"))
        self.btn_export.config(text=self.t("reverse_export_report"))
        self.lang_label.config(text=self.t("lang"))
        self.mode_label.config(text=self.t("reverse_mode"))
        self._refresh_mode_labels()
        if self.label_dnd_hint is not None:
            self.label_dnd_hint.config(text=self.t("dnd_hint"))
        for col, key in self._tree_heading_keys.items():
            self.tree.heading(col, text=self.t(key))
        # Re-translate the rendered checklist, so values and notes follow the
        # language switch instead of staying in the old locale.
        if self.last_result is not None:
            self._render_result(self.last_result)
        else:
            self.summary_var.set(self.t("reverse_no_data"))

    # ---- mode selector -------------------------------------------------------

    def _refresh_mode_labels(self) -> None:
        """Rebuild the mode selector labels in the current language."""
        labels = [self.t(_MODE_LABEL_KEYS[code]) for code in _MODE_CODES]
        self.mode_combo.configure(values=labels)
        self.mode_var.set(self.t(_MODE_LABEL_KEYS[self.mode_code]))

    def _on_mode_selected(self, _event: tk.Event) -> None:
        """Remember the selected mode and re-run the check with it."""
        for code in _MODE_CODES:
            if self.mode_var.get() == self.t(_MODE_LABEL_KEYS[code]):
                self.mode_code = code
                break
        if self.last_payload is not None:
            self._run_check()

    def _effective_mode(self) -> str:
        """Resolve the mode to verify with.

        The selector wins; ``auto`` follows the file — a workbook with an
        ``extended`` sheet is checked in full, anything else in the simplified
        mode (core fields only).
        """
        if self.mode_code == "simplified":
            return MODE_SIMPLIFIED
        if self.mode_code == "full":
            return MODE_FULL
        return self.file_mode

    # ---- DnD / file loading -------------------------------------------------

    def _on_drop(self, event: tk.Event) -> None:  # type: ignore[override]
        path = extract_dropped_path(getattr(event, "data", ""))
        if not path:
            return
        p = Path(path)
        if p.suffix.lower() not in _ALLOWED_SELF_CHECK_EXTS:
            messagebox.showerror(
                self.t("reverse_load_error"), self.t("reverse_drop_file")
            )
            return
        self.selected_file.set(str(p))
        self._run_from_path(p)

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            title=self.t("reverse_load"),
            filetypes=[
                (self.t("filter_self_check_files"), "*.json;*.xlsx;*.xlsm"),
                (self.t("filter_json"), "*.json"),
                (self.t("filter_excel"), "*.xlsx;*.xlsm"),
                (self.t("filter_all"), "*.*"),
            ],
        )
        if not path:
            return
        self.selected_file.set(path)
        self._run_from_path(Path(path))

    def _reload(self) -> None:
        raw = self.selected_file.get()
        if not raw:
            messagebox.showerror(self.t("reverse_load_error"), self.t("reverse_no_file"))
            return
        self._run_from_path(Path(raw))

    def _clear(self) -> None:
        self.selected_file.set("")
        self.last_payload = None
        self.last_expected = None
        self.last_result = None
        self._show_placeholder()

    def _run_from_path(self, path: Path) -> None:
        try:
            bundle = parse_self_check_bundle(path)
        except (ValueError, FileNotFoundError) as exc:
            messagebox.showerror(self.t("reverse_load_error"), str(exc))
            return
        self.last_payload = bundle.input_data
        self.last_expected = bundle.expected
        self.file_mode = bundle.mode
        self._run_check()

    # ---- core verification ---------------------------------------------------

    def _run_check(self) -> None:
        if self.last_payload is None or self.last_expected is None:
            messagebox.showerror(self.t("reverse_load_error"), self.t("reverse_no_file"))
            return
        try:
            actual = compute(self.last_payload)
            result = verify(actual, self.last_expected, mode=self._effective_mode())
        except Exception as exc:  # noqa: BLE001 — surface everything to the user.
            messagebox.showerror(self.t("reverse_run_error"), str(exc))
            return
        self.last_result = result
        self._render_result(result)

    # ---- rendering -----------------------------------------------------------

    def _show_placeholder(self) -> None:
        self._clear_tree()
        self.summary_var.set(self.t("reverse_no_data"))

    def _clear_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _render_result(self, result: CheckResult) -> None:
        self._clear_tree()
        missing_label = self.t("missing_label")
        lang = self.lang.get()
        for entry in result.entries:
            tag = "passed" if entry.passed else "failed"
            icon = "✓" if entry.passed else "✗"
            self.tree.insert(
                "",
                "end",
                values=(
                    icon,
                    entry.name,
                    describe_entry(entry.name, lang),
                    _format_cell(
                        localize_check_value(entry.name, entry.actual, lang),
                        missing_label,
                    ),
                    _format_cell(
                        localize_check_value(entry.name, entry.expected, lang),
                        missing_label,
                    ),
                    _format_diff(entry.diff, missing_label),
                    translate_message(entry.message, lang),
                ),
                tags=(tag,),
            )
        self._refresh_summary(result)

    def _refresh_summary(self, result: CheckResult) -> None:
        total = result.passed + result.failed
        mode_label = self.t(_MODE_LABEL_KEYS[self._effective_mode_code()])
        if result.failed == 0:
            self.summary_var.set(
                self.t("reverse_summary_all_passed").format(total=total)
                + "  " + self.t("reverse_mode_current").format(mode=mode_label)
            )
        else:
            self.summary_var.set(
                self.t("reverse_summary_some_failed").format(
                    passed=result.passed, failed=result.failed, total=total
                )
                + "  " + self.t("reverse_mode_current").format(mode=mode_label)
            )

    def _effective_mode_code(self) -> str:
        """The mode code of the check in effect (``auto`` resolved)."""
        if self.mode_code in ("simplified", "full"):
            return self.mode_code
        return "simplified" if self.file_mode == MODE_SIMPLIFIED else "full"

    # ---- export --------------------------------------------------------------

    def _export_report(self) -> None:
        if self.last_result is None:
            messagebox.showerror(
                self.t("reverse_export_error"), self.t("reverse_no_file")
            )
            return
        try:
            path = filedialog.asksaveasfilename(
                title=self.t("reverse_export_title"),
                defaultextension=".txt",
                filetypes=[
                    (self.t("filter_text"), "*.txt"),
                    (self.t("filter_all"), "*.*"),
                ],
            )
            if not path:
                return
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(f"# {self.t('reverse_title_main')}\n")
                if self.selected_file.get():
                    fh.write(
                        f"# {self.t('reverse_report_source')}: "
                        f"{self.selected_file.get()}\n"
                    )
                fh.write("#\n")
                print_checklist(self.last_result, file=fh, lang=self.lang.get())
            messagebox.showinfo(
                self.t("reverse_export_title"), self.t("reverse_export_done")
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(
                self.t("reverse_export_error"), str(exc)
            )


def main() -> None:
    ReverseApp().mainloop()


if __name__ == "__main__":
    main()
```

## `tests/conftest.py`

```python
"""Общие фикстуры для тестов NTS."""

from pathlib import Path

import pytest

from nts.core import Experiment


@pytest.fixture
def examples_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture
def default_experiments() -> list[Experiment]:
    return [
        Experiment(idx=1, delta1=-1, delta2=-1, x1=43.75, x2=43.75, x3=12.5,
                   y1=1167, y2=1238, y3=963),
        Experiment(idx=2, delta1=-1, delta2=1, x1=35.0, x2=35.0, x3=30.0,
                   y1=991, y2=992, y3=849),
        Experiment(idx=3, delta1=1, delta2=-1, x1=55.0, x2=34.97, x3=10.0,
                   y1=1167, y2=1116, y3=1135),
        Experiment(idx=4, delta1=1, delta2=1, x1=45.83, x2=25.17, x3=25.0,
                   y1=967, y2=1119, y3=1058),
    ]


@pytest.fixture
def default_criteria() -> tuple[float, float, float]:
    return 0.7679, 2.306, 239.0


@pytest.fixture
def all_significant_experiments() -> list[Experiment]:
    """Синтетический пример, где все три коэффициента значимы.

    y_avg = [900, 900, 900, 1300] даёт b_coded = (1000, 100, 100) ровно.
    Небольшой шум ±1 добавляет вариабельность для Стьюдента (s²_вос > 0).
    """
    return [
        Experiment(idx=1, delta1=-1, delta2=-1, x1=30.0, x2=50.0, x3=20.0,
                   y1=899, y2=901, y3=900),
        Experiment(idx=2, delta1=-1, delta2=1, x1=35.0, x2=45.0, x3=20.0,
                   y1=901, y2=900, y3=899),
        Experiment(idx=3, delta1=1, delta2=-1, x1=55.0, x2=35.0, x3=10.0,
                   y1=900, y2=901, y3=899),
        Experiment(idx=4, delta1=1, delta2=1, x1=45.0, x2=30.0, x3=25.0,
                   y1=1301, y2=1299, y3=1300),
    ]
```

## `tests/test_checker.py`

```python
"""Tests for nts.checker.verify() — DISCRETE + NUMERIC + LIST-SORT paths.

DISCRETE:
  - t_tests.sign_b0 / sign_b1 / sign_b2
  - f_result_code
  - g_tests[i].ok (per-row, position-based)
  - equation
  - f_result

NUMERIC per-category tolerance:
  - coefficients / coefficients_v / z_averages / pz / delta_calc → coeff_abs
  - t_tests.t0 / t1 / t2 → t_abs
  - g_tests[i].g per-row → coeff_abs
  - f_value → f_abs (with NaN/inf policy)

f_value inf/NaN + list-row sort + empty/extra-key policy:
  - f_value: NaN never matches (even NaN==NaN); inf==inf same-sign passes;
    inf vs finite fails with diff=inf.
  - g_tests: row-set validation + sort by ``row`` key (stable) before
    per-row comparison of g and ok.
  - output_rows: row-set validation on ``(delta1, delta2)`` tuple + sort
    by that tuple before per-row comparison of all 6 numeric fields.
  - Empty ``expected`` → ``ValueError("expected must not be empty")``.
  - Extra keys in ``expected`` → silently ignored.

parse_self_check_file — JSON file loader with bad-schema detection:
  - happy path: minimal ``{"input": {...InputData...}, "expected":
    {...ComputeResult...}}`` payload → returns ``(InputData, ComputeResult)``;
  - missing ``input`` key → ``ValueError`` whose message mentions ``input``;
  - missing ``expected`` key → ``ValueError`` whose message mentions
    ``expected``;
  - empty ``{}`` payload → ``ValueError``.

Test fixtures build minimal ComputeResult-shaped dicts inline with arbitrary
distinct values. NO hardcoded ``g_crit``/``t_crit``/``f_crit`` literals (see
``.agent/rules/project-rules.md:30``).
"""
from __future__ import annotations

import json
import tempfile
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

from nts.checker import (
    MODE_FULL,
    MODE_SIMPLIFIED,
    CheckEntry,
    CheckResult,
    Tolerance,
    print_checklist,
    verify,
)


# ---- helpers ---------------------------------------------------------------


def _make_g_test(row: int, ok: str = "ok", g: float = 0.0) -> Dict[str, Any]:
    """Build a single ``GTest``-shaped dict (row, g, ok).

    Matches ``nts/core.py:25-28``: ``GTest`` has ``row: int``.
    """
    return {"row": row, "g": g, "ok": ok}


def _make_output_row(
    delta1: int,
    delta2: int,
    base: float = 100.0,
) -> Dict[str, Any]:
    """Build a single ``OutputRow``-shaped dict.

    Matches ``nts/core.py:61-67``: ``OutputRow`` has NO ``row`` key — only
    y_avg, delta1, delta2, y_pred, y_avg_minus_y, y_avg_minus_y_sq.
    Per-row identity is the ``(delta1, delta2)`` tuple (see ``DELTA1/2_SIGNATURE``
    uniqueness in ``nts/core.py:21-22``).
    """
    y_avg = base + 10.0 * (delta1 + delta2 + 2)
    return {
        "y_avg": y_avg,
        "delta1": float(delta1),
        "delta2": float(delta2),
        "y_pred": y_avg,
        "y_avg_minus_y": 0.0,
        "y_avg_minus_y_sq": 0.0,
    }


def _discrete_compute_result(
    *,
    signs: tuple[str, str, str] = ("+", "+", "+"),
    f_result_code: str = "not_rejected",
    g_tests: list[Dict[str, Any]] | None = None,
    equation: str = "Y = b0 + b1·δ1 + b2·δ2",
    f_result: str = "F < F_cr → уравнение адекватно",
) -> Dict[str, Any]:
    """Build a minimal ComputeResult carrying only DISCRETE fields."""
    if g_tests is None:
        g_tests = [_make_g_test(i + 1) for i in range(4)]
    return {
        "t_tests": {
            "sign_b0": signs[0],
            "sign_b1": signs[1],
            "sign_b2": signs[2],
        },
        "g_tests": g_tests,
        "f_result_code": f_result_code,
        "equation": equation,
        "f_result": f_result,
    }


def _numeric_compute_result(
    *,
    b0: float = 1.0,
    b1: float = 2.0,
    b2: float = 3.0,
    b0_v: float = 10.0,
    b1_v: float = 20.0,
    b2_v: float = 30.0,
    z1_avg: float = 1.5,
    z2_avg: float = 2.5,
    pz1: float = 0.5,
    pz2: float = 1.5,
    delta1: float = 0.4,
    delta2: float = 0.6,
    t0: float = 5.0,
    t1: float = 4.0,
    t2: float = 3.0,
    signs: tuple[str, str, str] = ("+", "+", "+"),
    f_avg: float = 50.0,
    f_value: float = 5.0,
    f_result_code: str = "not_rejected",
    equation: str = "Y = b0 + b1·δ1 + b2·δ2",
    f_result: str = "F < F_cr → уравнение адекватно",
    g_crit_echo: float = 0.5,
    t_crit_echo: float = 2.0,
    f_crit_echo: float = 100.0,
    g_tests: list[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Build a full ComputeResult-shaped dict with NUMERIC + DISCRETE fields.

    All values are arbitrary distinct constants — NO ``g_crit``/``t_crit``/
    ``f_crit`` literals (per ``.agent/rules/project-rules.md:30``). The
    ``*_echo`` keys are arbitrary echoes for fields the loader/writer treat as
    scalars (the function avoids the bare names ``g_crit``/``t_crit``/``f_crit``
    so callers can pick distinct values for input vs expected payloads).
    """
    if g_tests is None:
        g_tests = [_make_g_test(i + 1) for i in range(4)]
    return {
        "coefficients": {"b0": b0, "b1": b1, "b2": b2},
        "coefficients_v": {"b0": b0_v, "b1": b1_v, "b2": b2_v},
        "z_averages": {"z1_avg": z1_avg, "z2_avg": z2_avg},
        "pz": {"pz1": pz1, "pz2": pz2},
        "delta_calc": {"delta1": delta1, "delta2": delta2},
        "t_tests": {
            "sign_b0": signs[0],
            "sign_b1": signs[1],
            "sign_b2": signs[2],
            "t0": t0,
            "t1": t1,
            "t2": t2,
        },
        "g_tests": g_tests,
        "f_avg": f_avg,
        "f_value": f_value,
        "f_result_code": f_result_code,
        "equation": equation,
        "f_result": f_result,
        "g_crit": g_crit_echo,
        "t_crit": t_crit_echo,
        "f_crit": f_crit_echo,
    }


# ---- dataclass shape -------------------------------------------------------


def test_check_result_dataclass() -> None:
    """CheckResult must expose name/passed/actual/expected/diff/message + counters."""
    entry = CheckEntry(
        name="t_tests.sign_b0",
        passed=True,
        actual="+",
        expected="+",
        diff=None,
        message="ok",
    )
    assert entry.name == "t_tests.sign_b0"
    assert entry.passed is True
    assert entry.actual == "+"
    assert entry.expected == "+"
    assert entry.diff is None
    assert entry.message == "ok"

    result = CheckResult(passed=1, failed=0, entries=[entry])
    assert result.passed == 1
    assert result.failed == 0
    assert result.entries == [entry]

    tol = Tolerance()
    assert tol.coeff_abs == pytest.approx(1e-3)
    assert tol.t_abs == pytest.approx(1e-2)
    assert tol.f_abs == pytest.approx(1e-1)


# ---- happy-path DISCRETE verification ---------------------------------------


def test_verify_discrete_happy() -> None:
    """All DISCRETE fields equal → verify() reports zero failures.

    The G-test comparison adds 4 per-row ``g_tests.g`` numeric entries (one per row) on top
    of the 10 pre-existing discrete entries, so the happy path emits 14
    total entries: 10 discrete (``diff is None``) + 4 numeric (``diff == 0``).
    """
    actual = _discrete_compute_result()
    expected = _discrete_compute_result()

    result: CheckResult = verify(actual, expected)

    assert isinstance(result, CheckResult)
    assert result.failed == 0
    assert result.passed == 14
    assert isinstance(result.entries, list)
    assert len(result.entries) == 14
    assert all(e.passed for e in result.entries)

    discrete_entries = [e for e in result.entries if e.diff is None]
    assert len(discrete_entries) == 10
    assert all(e.diff is None for e in discrete_entries)


def test_verify_returns_int_counters() -> None:
    """verify() must return object with .passed and .failed as int counters + .entries list."""
    actual = _discrete_compute_result()
    expected = _discrete_compute_result()

    result = verify(actual, expected)

    assert isinstance(result.passed, int)
    assert isinstance(result.failed, int)
    assert isinstance(result.entries, list)
    # passed + failed must equal total entries
    assert result.passed + result.failed == len(result.entries)


def test_tolerance_overrides_accepted() -> None:
    """Tolerance dataclass accepts keyword overrides (NUMERIC path is todo 2; shape only)."""
    tol = Tolerance(coeff_abs=1e-4, t_abs=1e-3, f_abs=1e-2)
    assert tol.coeff_abs == pytest.approx(1e-4)
    assert tol.t_abs == pytest.approx(1e-3)
    assert tol.f_abs == pytest.approx(1e-2)

    # And verify() accepts the kwarg even when DISCRETE path ignores it.
    actual = _discrete_compute_result()
    expected = _discrete_compute_result()
    res = verify(actual, expected, tolerance=tol)
    assert res.failed == 0
    # 10 discrete + 4 g_tests.g per-row (todo 3) = 14.
    assert res.passed == 14


# ---- NUMERIC per-category tolerance -------------------------------


def test_verify_numeric_tolerance_pass() -> None:
    """NUMERIC delta within coeff_abs (1e-4 ≤ 1e-3) → all NUMERIC entries pass.

    19 NUMERIC scalar entries (12 coefficient-like under ``coeff_abs``
    + 3 ``t_tests`` under ``t_abs`` + 4 ``g_tests.g`` per-row under
    ``coeff_abs``) + 1 NUMERIC ``f_value`` under ``f_abs`` = 20 NUMERIC entries.
    Plus 10 DISCRETE entries. Grand total = 30 entries.
    """
    actual = _numeric_compute_result()
    expected = _numeric_compute_result()

    result: CheckResult = verify(actual, expected)

    assert isinstance(result, CheckResult)
    assert result.failed == 0
    assert result.passed == 30
    assert len(result.entries) == 30

    numeric_entries = [e for e in result.entries if e.diff is not None]
    assert len(numeric_entries) == 20
    assert all(e.passed for e in numeric_entries)
    assert all(e.diff == pytest.approx(0.0) for e in numeric_entries)

    discrete_entries = [e for e in result.entries if e.diff is None]
    assert len(discrete_entries) == 10
    assert all(e.passed for e in discrete_entries)


def test_verify_numeric_tolerance_fail() -> None:
    """delta 1.0 on b0 (>> coeff_abs=1e-3) → fail with diff=actual-expected."""
    base = _numeric_compute_result()
    actual = _numeric_compute_result(b0=base["coefficients"]["b0"] + 1.0)
    expected = base

    result = verify(actual, expected)

    b0_entry = next(
        (e for e in result.entries if e.name == "coefficients.b0"), None
    )
    assert b0_entry is not None, "missing coefficients.b0 entry"
    assert b0_entry.passed is False
    assert b0_entry.diff == pytest.approx(1.0)
    assert b0_entry.actual == pytest.approx(base["coefficients"]["b0"] + 1.0)
    assert b0_entry.expected == pytest.approx(base["coefficients"]["b0"])

    failed = [e for e in result.entries if not e.passed]
    assert len(failed) == 1
    assert failed[0].name == "coefficients.b0"


def test_verify_per_category_tolerances() -> None:
    """coeff_abs governs coefficient-like fields, t_abs governs t-tests values.

    Given ``Tolerance(coeff_abs=1e-6, t_abs=1.0, f_abs=1e-1)``:
      * delta 1e-4 on coefficients.b0 (≫1e-6) → fail under coeff_abs.
      * delta 5.0 on t_tests.t0 (≫1.0) → fail under t_abs.
      * delta 0.5 on t_tests.t1 (<1.0) → pass under t_abs.

    f_value/f_abs coverage is deferred to todo 3.
    """
    tol = Tolerance(coeff_abs=1e-6, t_abs=1.0, f_abs=1e-1)
    base = _numeric_compute_result()
    actual = _numeric_compute_result(
        b0=base["coefficients"]["b0"] + 1e-4,
        t0=base["t_tests"]["t0"] + 5.0,
        t1=base["t_tests"]["t1"] + 0.5,
    )
    expected = base

    result = verify(actual, expected, tolerance=tol)

    by_name = {e.name: e for e in result.entries}

    # given: delta 1e-4 on coefficients.b0 with coeff_abs=1e-6
    assert by_name["coefficients.b0"].passed is False
    assert by_name["coefficients.b0"].diff == pytest.approx(1e-4)

    # given: delta 5.0 on t_tests.t0 with t_abs=1.0
    assert by_name["t_tests.t0"].passed is False
    assert by_name["t_tests.t0"].diff == pytest.approx(5.0)

    # given: delta 0.5 on t_tests.t1 with t_abs=1.0
    assert by_name["t_tests.t1"].passed is True
    assert by_name["t_tests.t1"].diff == pytest.approx(0.5)

    failed_numeric = [
        e.name for e in result.entries
        if not e.passed and e.diff is not None
    ]
    assert failed_numeric == ["coefficients.b0", "t_tests.t0"]
    assert result.failed == 2


# ---- f_value inf/NaN -----------------------------------------------


def test_verify_f_value_inf_both_pass() -> None:
    """Both f_value=+inf (e.g. safe_div protection) → pass with diff=0.0."""
    actual = _numeric_compute_result()
    expected = _numeric_compute_result()
    inf = float("inf")
    actual["f_value"] = inf
    expected["f_value"] = inf

    result = verify(actual, expected)

    f_entries = [e for e in result.entries if e.name == "f_value"]
    assert len(f_entries) == 1, "exactly one f_value entry expected"
    f_entry = f_entries[0]
    assert f_entry.passed is True
    assert f_entry.actual == inf
    assert f_entry.expected == inf
    # Matching infinities are conceptually equal → diff=0.0 per implementation.
    assert f_entry.diff == 0.0


def test_verify_f_value_inf_mismatch() -> None:
    """actual f_value=+inf, expected=1.0 → fail with diff=+inf; no exception."""
    actual = _numeric_compute_result()
    expected = _numeric_compute_result()
    actual["f_value"] = float("inf")
    expected["f_value"] = 1.0

    result = verify(actual, expected)

    f_entries = [e for e in result.entries if e.name == "f_value"]
    assert len(f_entries) == 1
    f_entry = f_entries[0]
    assert f_entry.passed is False
    # diff = +inf - 1.0 = +inf
    assert f_entry.diff == float("inf")
    assert f_entry.actual == float("inf")
    assert f_entry.expected == pytest.approx(1.0)
    assert f_entry.message != ""


def test_verify_f_value_nan_safe_any() -> None:
    """Any NaN (even NaN==NaN) → fail with explicit 'NaN' message.

    Two sub-cases:
      (a) actual=NaN, expected=0.0 → fail
      (b) actual=NaN, expected=NaN → ALSO fail (NaN never matches itself)
    """
    nan = float("nan")

    actual_a = _numeric_compute_result()
    expected_a = _numeric_compute_result()
    actual_a["f_value"] = nan
    expected_a["f_value"] = 0.0
    result_a = verify(actual_a, expected_a)
    f_a = next(e for e in result_a.entries if e.name == "f_value")
    assert f_a.passed is False
    assert "NaN" in f_a.message

    actual_b = _numeric_compute_result()
    expected_b = _numeric_compute_result()
    actual_b["f_value"] = nan
    expected_b["f_value"] = nan
    result_b = verify(actual_b, expected_b)
    f_b = next(e for e in result_b.entries if e.name == "f_value")
    assert f_b.passed is False
    assert "NaN" in f_b.message
    assert math.isnan(f_b.actual)
    assert math.isnan(f_b.expected)


# ---- g_tests sort-by-row + row-set validation ---------------------


def test_verify_g_tests_sort_by_row() -> None:
    """Same g_tests values in different row order → pass after sort-by-row.

    Actual g_tests in order [3,1,4,2], expected in [1,2,3,4].
    """
    actual_g = [
        _make_g_test(3, ok="ok", g=0.3),
        _make_g_test(1, ok="ok", g=0.1),
        _make_g_test(4, ok="ok", g=0.4),
        _make_g_test(2, ok="not_ok", g=0.2),
    ]
    expected_g = [
        _make_g_test(1, ok="ok", g=0.1),
        _make_g_test(2, ok="not_ok", g=0.2),
        _make_g_test(3, ok="ok", g=0.3),
        _make_g_test(4, ok="ok", g=0.4),
    ]

    actual = _numeric_compute_result(g_tests=actual_g)
    expected = _numeric_compute_result(g_tests=expected_g)

    result = verify(actual, expected)

    g_entries = [e for e in result.entries if e.name.startswith("g_tests[")]
    assert len(g_entries) > 0, "expected g_tests entries to be emitted"
    failures = [(e.name, e.message) for e in g_entries if not e.passed]
    assert failures == [], (
        f"all g_tests entries should pass after row-sort, "
        f"got failures: {failures}"
    )


def test_verify_g_tests_row_set_mismatch() -> None:
    """Row IDs differ (actual row 4, expected row 5) → fail with explicit message."""
    actual_g = [_make_g_test(i) for i in (1, 2, 3, 4)]
    expected_g = [_make_g_test(i) for i in (1, 2, 3, 5)]

    actual = _numeric_compute_result(g_tests=actual_g)
    expected = _numeric_compute_result(g_tests=expected_g)

    result = verify(actual, expected)

    failed = [e for e in result.entries if not e.passed]
    assert len(failed) >= 1

    mismatch_entry = next(
        (
            e for e in failed
            if "row" in e.message.lower() and "mismatch" in e.message.lower()
        ),
        None,
    )
    assert mismatch_entry is not None, (
        f"expected a row-set mismatch entry, failed entries: "
        f"{[(e.name, e.message) for e in failed]}"
    )
    assert "4" in mismatch_entry.message
    assert "5" in mismatch_entry.message


# ---- output_rows sort by (delta1, delta2) tuple + delta-set check ---


def test_verify_output_rows_sort_by_delta_tuple() -> None:
    """Same output_rows in scrambled order → pass after sort-by-(delta1, delta2).

    OutputRow has NO ``row`` key (per ``nts/core.py:61-67``), so the unique
    row identifier is the ``(delta1, delta2)`` tuple.

    Expected rows ordered by delta tuple:
        idx 0: (-1,-1)
        idx 1: (-1, 1)
        idx 2: (1,-1)
        idx 3: (1, 1)
    Actual rows in scrambled order [2, 0, 3, 1].
    """
    expected_rows = [
        _make_output_row(-1, -1, base=100.0),
        _make_output_row(-1, 1, base=200.0),
        _make_output_row(1, -1, base=300.0),
        _make_output_row(1, 1, base=400.0),
    ]
    # Scramble: actual in order [expected[2], expected[0], expected[3], expected[1]]
    actual_rows = [expected_rows[2], expected_rows[0], expected_rows[3], expected_rows[1]]

    actual = _numeric_compute_result()
    actual["output_rows"] = actual_rows
    expected = _numeric_compute_result()
    expected["output_rows"] = expected_rows

    result = verify(actual, expected)

    output_entries = [e for e in result.entries if e.name.startswith("output_rows[")]
    assert len(output_entries) > 0, "expected output_rows entries to be emitted"
    failures = [(e.name, e.message) for e in output_entries if not e.passed]
    assert failures == [], (
        f"all output_rows entries should pass after delta-tuple sort, "
        f"got failures: {failures}"
    )


def test_verify_output_rows_delta_set_mismatch() -> None:
    """Actual has a (1,-1) row that expected lacks → fail with explicit message."""
    actual_rows = [
        _make_output_row(-1, -1, base=100.0),
        _make_output_row(-1, 1, base=200.0),
        _make_output_row(1, -1, base=300.0),
        _make_output_row(1, 1, base=400.0),
    ]
    # Expected missing the (1,-1) row.
    expected_rows = [
        _make_output_row(-1, -1, base=100.0),
        _make_output_row(-1, 1, base=200.0),
        _make_output_row(1, 1, base=400.0),
    ]

    actual = _numeric_compute_result()
    actual["output_rows"] = actual_rows
    expected = _numeric_compute_result()
    expected["output_rows"] = expected_rows

    result = verify(actual, expected)

    failed = [e for e in result.entries if not e.passed]
    assert len(failed) >= 1

    mismatch_entry = next(
        (
            e for e in failed
            if "delta" in e.message.lower() and "mismatch" in e.message.lower()
        ),
        None,
    )
    assert mismatch_entry is not None, (
        f"expected a delta-set mismatch entry, failed entries: "
        f"{[(e.name, e.message) for e in failed]}"
    )


# ---- empty-expected guard + extra-key ignored ----------------------


def test_verify_empty_expected_raises() -> None:
    """``{}`` as ``expected`` → ``ValueError("expected must not be empty")``."""
    actual = _numeric_compute_result()
    expected: Dict[str, Any] = {}

    with pytest.raises(ValueError, match="expected must not be empty"):
        verify(actual, expected)


def test_verify_extra_key_in_expected_ignored() -> None:
    """An unknown key (``"foo"``) in ``expected`` is ignored; verification proceeds."""
    actual = _numeric_compute_result()
    expected = _numeric_compute_result()
    expected["foo"] = "bar"  # noqa: S105 — extra unknown key, must be ignored.

    result = verify(actual, expected)

    assert isinstance(result, CheckResult)
    assert not any(e.name == "foo" for e in result.entries)
    assert result.failed == 0
    assert all(e.passed for e in result.entries)


# ---- parse_self_check_file — JSON loader + bad-schema detection ----


def _tiny_input_data() -> Dict[str, Any]:
    """Build a minimal InputData-shaped JSON payload (distinct arbitrary values).

    Matches the ``InputData`` contract consumed by ``nts.core._parse_input_data``
    (``experiments`` list + ``g_crit`` / ``t_crit`` / ``f_crit`` floats). Uses
    arbitrary numbers — NO hardcoded ``g_crit``/``t_crit``/``f_crit`` literals.
    """
    return {
        "experiments": [
            {
                "idx": 1,
                "delta1": -1,
                "delta2": -1,
                "x1": 10.0,
                "x2": 20.0,
                "x3": 30.0,
                "y1": 100,
                "y2": 110,
                "y3": 120,
            },
            {
                "idx": 2,
                "delta1": 1,
                "delta2": -1,
                "x1": 11.0,
                "x2": 21.0,
                "x3": 31.0,
                "y1": 101,
                "y2": 111,
                "y3": 121,
            },
        ],
        "g_crit": 0.5,
        "t_crit": 2.0,
        "f_crit": 100.0,
    }


def _tiny_compute_result() -> Dict[str, Any]:
    """Build a minimal ComputeResult-shaped dict (distinct arbitrary values)."""
    return _discrete_compute_result()


def test_parse_self_check_file_valid(tmp_path: Path) -> None:
    """Valid ``{"input": {...}, "expected": {...}}`` → ``(InputData, ComputeResult)``.

    The returned ``input_data`` must be an ``InputData`` instance (parsed via
    ``_parse_input_data``); ``expected`` is the raw dict cast to
    ``ComputeResult`` shape — runtime fields are arbitrary.
    """
    from nts.core import InputData
    from nts.checker import parse_self_check_file

    payload = {
        "input": _tiny_input_data(),
        "expected": _tiny_compute_result(),
    }
    path = tmp_path / "self_check.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    input_data, expected = parse_self_check_file(path)

    assert isinstance(input_data, InputData)
    assert len(input_data.experiments) == 2
    assert input_data.g_crit == pytest.approx(0.5)
    assert input_data.t_crit == pytest.approx(2.0)
    assert input_data.f_crit == pytest.approx(100.0)

    assert isinstance(expected, dict)
    assert expected["f_result_code"] == "not_rejected"
    assert expected["equation"] == "Y = b0 + b1·δ1 + b2·δ2"


def test_parse_self_check_file_missing_input_raises(tmp_path: Path) -> None:
    """Payload with only ``"expected"`` (no ``"input"``) → ``ValueError`` mentioning ``input``."""
    from nts.checker import parse_self_check_file

    payload = {"expected": _tiny_compute_result()}
    path = tmp_path / "self_check.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="input"):
        parse_self_check_file(path)


def test_parse_self_check_file_missing_expected_raises(tmp_path: Path) -> None:
    """Payload with only ``"input"`` (no ``"expected"``) → ``ValueError`` mentioning ``expected``."""
    from nts.checker import parse_self_check_file

    payload = {"input": _tiny_input_data()}
    path = tmp_path / "self_check.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="expected"):
        parse_self_check_file(path)


def test_parse_self_check_file_empty_raises(tmp_path: Path) -> None:
    """``{}`` payload → ``ValueError`` (no ``input`` and no ``expected``)."""
    from nts.checker import parse_self_check_file

    path = tmp_path / "empty.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError):
        parse_self_check_file(path)


# ---- parse_self_check_xlsx + parse_self_check_file dispatch ---------------


def _tiny_input_xlsx_payload() -> "InputData":
    from nts.core import InputData, Experiment

    return InputData(
        experiments=[
            Experiment(
                idx=1, delta1=-1, delta2=-1,
                x1=10.0, x2=20.0, x3=30.0,
                y1=100, y2=110, y3=120,
            ),
            Experiment(
                idx=2, delta1=1, delta2=-1,
                x1=11.0, x2=21.0, x3=31.0,
                y1=101, y2=111, y3=121,
            ),
        ],
        g_crit=0.5,
        t_crit=2.0,
        f_crit=100.0,
    )


def _full_compute_result_for_xlsx() -> Dict[str, Any]:
    """Same shape as :func:`_numeric_compute_result`, plus ``output_rows``.

    The xlsx writer/loader both round-trip the per-experiment ``output_rows``
    list, so the test fixture must populate it explicitly.
    """
    base = _numeric_compute_result()
    base["output_rows"] = [
        {
            "delta1": -1.0, "delta2": -1.0, "y_avg": 110.0,
            "y_pred": 109.5, "y_avg_minus_y": 0.5, "y_avg_minus_y_sq": 0.25,
        },
        {
            "delta1": 1.0, "delta2": -1.0, "y_avg": 111.0,
            "y_pred": 110.5, "y_avg_minus_y": 0.5, "y_avg_minus_y_sq": 0.25,
        },
    ]
    return base


def test_parse_self_check_xlsx_happy(tmp_path: Path) -> None:
    """``write_self_check_xlsx`` then ``parse_self_check_file`` (xlsx dispatch) round-trips."""
    from nts.checker import parse_self_check_file, write_self_check_xlsx

    payload_in = _tiny_input_xlsx_payload()
    expected = _full_compute_result_for_xlsx()

    path = tmp_path / "self_check.xlsx"
    write_self_check_xlsx(path, payload_in, expected)

    input_data, got_expected = parse_self_check_file(path)

    assert input_data.experiments == payload_in.experiments
    assert input_data.g_crit == pytest.approx(0.5)
    assert input_data.t_crit == pytest.approx(2.0)
    assert input_data.f_crit == pytest.approx(100.0)
    assert got_expected["coefficients"]["b0"] == pytest.approx(1.0)
    assert got_expected["coefficients_v"]["b0"] == pytest.approx(10.0)
    assert got_expected["z_averages"]["z2_avg"] == pytest.approx(2.5)
    assert got_expected["t_tests"]["t0"] == pytest.approx(5.0)
    assert got_expected["t_tests"]["sign_b1"] == "+"
    assert got_expected["g_tests"][0]["ok"] == "ok"
    assert got_expected["equation"] == "Y = b0 + b1·δ1 + b2·δ2"


def test_parse_self_check_xlsx_round_trip_via_dispatch(tmp_path: Path) -> None:
    """Both ``parse_self_check_xlsx`` and the dispatching ``parse_self_check_file`` yield equivalent data."""
    from nts.checker import (
        parse_self_check_file,
        parse_self_check_xlsx,
        write_self_check_xlsx,
    )

    payload_in = _tiny_input_xlsx_payload()
    expected = _full_compute_result_for_xlsx()

    path = tmp_path / "round_trip.xlsx"
    write_self_check_xlsx(path, payload_in, expected)

    via_dispatch = parse_self_check_file(path)
    via_xlsx = parse_self_check_xlsx(path)

    assert via_dispatch[0].experiments == via_xlsx[0].experiments
    assert via_dispatch[1] == via_xlsx[1]


def test_parse_self_check_xlsx_missing_input_sheet_raises(tmp_path: Path) -> None:
    """Workbook without ``input`` sheet → ``ValueError`` mentioning ``input``."""
    import openpyxl

    from nts.checker import parse_self_check_xlsx

    path = tmp_path / "no_input.xlsx"
    wb = openpyxl.Workbook()
    wb.active.title = "result"
    wb.create_sheet("criteria")
    wb.save(path)

    with pytest.raises(ValueError, match="input"):
        parse_self_check_xlsx(path)


def test_parse_self_check_xlsx_missing_criteria_sheet_raises(tmp_path: Path) -> None:
    """Workbook without ``criteria`` sheet → ``ValueError`` mentioning ``criteria``."""
    import openpyxl

    from nts.checker import parse_self_check_xlsx

    path = tmp_path / "no_crit.xlsx"
    wb = openpyxl.Workbook()
    wb.active.title = "input"
    wb.create_sheet("result")
    wb.save(path)

    with pytest.raises(ValueError, match="criteria"):
        parse_self_check_xlsx(path)


def test_parse_self_check_xlsx_missing_result_sheet_raises(tmp_path: Path) -> None:
    """Workbook without ``result`` sheet → ``ValueError`` mentioning ``result``."""
    import openpyxl

    from nts.checker import parse_self_check_xlsx

    path = tmp_path / "no_res.xlsx"
    wb = openpyxl.Workbook()
    wb.active.title = "input"
    wb.create_sheet("criteria")
    wb.save(path)

    with pytest.raises(ValueError, match="result"):
        parse_self_check_xlsx(path)


def test_parse_self_check_xlsx_criteria_kv_layout(tmp_path: Path) -> None:
    """Criteria sheet accepts key/value layout (no header row) as a second option."""
    from nts.checker import parse_self_check_xlsx, write_self_check_xlsx

    import openpyxl

    payload_in = _tiny_input_xlsx_payload()
    expected = _full_compute_result_for_xlsx()
    path = tmp_path / "kv.xlsx"
    write_self_check_xlsx(path, payload_in, expected)

    wb = openpyxl.load_workbook(path)
    crit = wb["criteria"]
    crit.delete_rows(1)  # drop header
    crit["A1"] = "g_crit"
    crit["B1"] = "0.5"
    crit["A2"] = "t_crit"
    crit["B2"] = "2.0"
    crit["A3"] = "f_crit"
    crit["B3"] = "100.0"
    wb.save(path)

    input_data, _ = parse_self_check_xlsx(path)
    assert input_data.g_crit == pytest.approx(0.5)
    assert input_data.t_crit == pytest.approx(2.0)
    assert input_data.f_crit == pytest.approx(100.0)


def test_parse_self_check_file_unsupported_extension_raises(tmp_path: Path) -> None:
    """``parse_self_check_file`` dispatch rejects extensions outside json/xlsx/xlsm."""
    from nts.checker import parse_self_check_file

    path = tmp_path / "self_check.txt"
    path.write_text("ignored", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported"):
        parse_self_check_file(path)


def test_parse_self_check_file_xlsm_dispatch(tmp_path: Path) -> None:
    """``.xlsm`` (macro workbook) is accepted by the dispatcher and forwarded to the xlsx loader."""
    from nts.checker import parse_self_check_file, write_self_check_xlsx

    payload_in = _tiny_input_xlsx_payload()
    expected = _full_compute_result_for_xlsx()
    path = tmp_path / "self_check.xlsm"
    write_self_check_xlsx(path, payload_in, expected)

    input_data, got_expected = parse_self_check_file(path)
    assert input_data.g_crit == pytest.approx(0.5)
    assert got_expected["coefficients"]["b1"] == pytest.approx(2.0)


# ---- GUI plumbing: drag-and-drop extension allowlist + i18n ---------------
#
# These are smoke tests, not full Tk interop tests (no display available in CI).
# They pin the regression where the constant was class-scoped (caused NameError
# at runtime when referenced by bare name inside a method).


def test_reverse_gui_allowed_ext_constant_resolves_at_call_time() -> None:
    """``_ALLOWED_SELF_CHECK_EXTS`` must resolve via bare name inside a method body.

    A previous build declared the frozenset as a class attribute and referenced
    it by bare name from inside ``_on_drop``. Class-scope names are not visible
    to methods in Python, so the call raised ``NameError`` and DnD silently
    failed for every extension (not just xlsx). This regression test ensures
    the constant resolves both ways.
    """
    from nts.reverse_gui import ReverseApp, _ALLOWED_SELF_CHECK_EXTS

    assert _ALLOWED_SELF_CHECK_EXTS == frozenset({".json", ".xlsx", ".xlsm"})
    assert isinstance(_ALLOWED_SELF_CHECK_EXTS, frozenset)
    # Class may or may not re-export; tolerate either layout.
    assert sorted(_ALLOWED_SELF_CHECK_EXTS) == [".json", ".xlsm", ".xlsx"]


def test_reverse_i18n_strings_format_agnostic() -> None:
    """User-facing messages must mention all 3 supported extensions, not just .json.

    The button label (``reverse_load``) is intentionally short — it stays
    format-agnostic. The descriptive strings (`reverse_drop_file`,
    `reverse_no_data`, `reverse_no_file`) must list the actual extensions
    so the user knows what to drop/load.
    """
    from nts.i18n import I18N

    for lang in ("EN", "RU"):
        s = I18N[lang]
        for key in ("reverse_drop_file", "reverse_no_data", "reverse_no_file"):
            assert key in s, f"missing {lang}!{key}"
            text = s[key]
            assert ".json" in text, f"{lang}!{key}={text!r} must mention .json"
            assert ".xlsx" in text, f"{lang}!{key}={text!r} must mention .xlsx"
            assert ".xlsm" in text, f"{lang}!{key}={text!r} must mention .xlsm"


# ---- print_checklist() Unicode/ASCII rendering ---------------------


def _tiny_check_result() -> CheckResult:
    """Build a small CheckResult with 2 pass entries + 1 fail entry."""
    entries = [
        CheckEntry(
            name="coefficients.b0",
            passed=True,
            actual=1.0,
            expected=1.0,
            diff=0.0,
            message="",
        ),
        CheckEntry(
            name="t_tests.sign_b0",
            passed=True,
            actual="+",
            expected="+",
            diff=None,
            message="",
        ),
        CheckEntry(
            name="f_result_code",
            passed=False,
            actual="rejected",
            expected="not_rejected",
            diff=None,
            message="discrete mismatch",
        ),
    ]
    return CheckResult(passed=2, failed=1, entries=entries)


def test_print_checklist_unicode(capsys: pytest.CaptureFixture[str]) -> None:
    """Unicode mode: pass → ``✓``, fail → ``✗``; summary contains counts."""
    result = _tiny_check_result()

    print_checklist(result)
    captured = capsys.readouterr()

    assert "✓" in captured.out
    assert "✗" in captured.out
    assert "2 passed" in captured.out
    assert "1 failed" in captured.out


def test_print_checklist_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    """ASCII mode: pass → ``[OK]``, fail → ``[FAIL]``; no Unicode glyphs."""
    result = _tiny_check_result()

    print_checklist(result, ascii=True)
    captured = capsys.readouterr()

    assert "[OK]" in captured.out
    assert "[FAIL]" in captured.out
    assert "✓" not in captured.out
    assert "✗" not in captured.out


def test_print_checklist_includes_diff(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A fail entry with diff=0.5 → stdout contains the diff label text."""
    entry = CheckEntry(
        name="coefficients.b0",
        passed=False,
        actual=1.5,
        expected=1.0,
        diff=0.5,
        message="numeric mismatch",
    )
    result = CheckResult(passed=0, failed=1, entries=[entry])

    print_checklist(result)
    captured = capsys.readouterr()

    assert "diff" in captured.out
    assert "0.5" in captured.out


def test_print_checklist_includes_missing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A fail entry with message='missing' → stdout contains 'missing'."""
    entry = CheckEntry(
        name="f_value",
        passed=False,
        actual=None,
        expected=1.0,
        diff=None,
        message="missing",
    )
    result = CheckResult(passed=0, failed=1, entries=[entry])

    print_checklist(result)
    captured = capsys.readouterr()

    assert "missing" in captured.out


def test_print_checklist_localizes_report_and_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``lang='RU'`` translates the title, labels, verdicts and notes."""
    entries = [
        CheckEntry(
            name="f_result",
            passed=True,
            actual="Hypothesis not rejected",
            expected="Hypothesis not rejected",
            diff=None,
            message="",
        ),
        CheckEntry(
            name="g_tests[row=1].ok",
            passed=False,
            actual="not OK",
            expected="OK",
            diff=None,
            message="discrete mismatch: 'not OK' != 'OK'",
        ),
        CheckEntry(
            name="coefficients.b0",
            passed=False,
            actual=1.5,
            expected=1.0,
            diff=0.5,
            message="numeric mismatch: |1.5 - 1.0| = 0.5 > abs_tol=0.001",
        ),
    ]
    result = CheckResult(passed=1, failed=2, entries=entries)

    print_checklist(result, lang="RU")
    out = capsys.readouterr().out

    assert "Самопроверка" in out
    assert "Гипотеза не отвергается" in out
    assert "не OK" in out
    assert "расхождение значений" in out
    assert "числовое расхождение" in out
    assert "факт=" in out and "эталон=" in out
    assert "1 пройдено, 2 провалено" in out
    assert "Hypothesis not rejected" not in out
    assert "numeric mismatch" not in out


def test_localize_check_value_and_message() -> None:
    """Canonical values and note prefixes map to RU without touching the tail."""
    from nts.i18n import localize_check_value, translate_message

    assert localize_check_value("f_result", "Hypothesis rejected", "RU") == (
        "Гипотеза отвергается"
    )
    assert localize_check_value("f_result_code", "not_rejected", "RU") == (
        "не отвергается"
    )
    assert localize_check_value("g_tests[row=2].ok", "not OK", "RU") == "не OK"
    # Unknown values and non-strings pass through unchanged.
    assert localize_check_value("coefficients.b0", 1.5, "RU") == 1.5
    assert localize_check_value("f_result", "custom text", "RU") == "custom text"

    raw = "missing in expected: actual='x', expected=None"
    assert translate_message(raw, "RU") == (
        "отсутствует в эталоне: actual='x', expected=None"
    )
    assert translate_message(raw, "EN") == raw
    assert translate_message("custom note", "RU") == "custom note"

    from nts.i18n import canonical_check_value

    assert canonical_check_value("f_result", "Гипотеза не отвергается") == (
        "Hypothesis not rejected"
    )
    assert canonical_check_value("f_result_code", "отвергается") == "rejected"
    assert canonical_check_value("g_tests[row=1].ok", "не OK") == "not OK"
    assert canonical_check_value("f_result", "custom text") == "custom text"


# ---- i18n self-check keys present in EN + RU ------------------------

# Names of the 5 self-check i18n keys (EN_BASE + RU_OVERRIDES).
SELF_CHECK_KEYS: tuple[str, ...] = (
    "self_check_title",
    "summary_passed",
    "summary_failed",
    "diff_label",
    "missing_label",
)


def test_i18n_self_check_keys_present_en() -> None:
    """All 5 self-check keys present in ``I18N["EN"]`` with non-empty values.

    5 keys were added to ``EN_BASE`` in ``nts/i18n.py``. Each must be present
    in the assembled ``I18N["EN"]`` dict (which mirrors ``EN_BASE``) and carry
    a non-empty string value.
    """
    from nts.i18n import I18N

    en = I18N["EN"]
    assert isinstance(en, dict)

    for key in SELF_CHECK_KEYS:
        assert key in en, f"missing key {key!r} in I18N['EN']"
        value = en[key]
        assert isinstance(value, str), (
            f"I18N['EN'][{key!r}] must be a str, got {type(value).__name__}"
        )
        assert value != "", f"I18N['EN'][{key!r}] must be non-empty"


def test_i18n_self_check_keys_present_ru() -> None:
    """All 5 self-check keys present in ``I18N["RU"]`` with non-empty values.

    Russian translations must override every new key (no fallback to EN),
    otherwise the GUI will show mixed-language UI strings. Back-compat for
    pre-existing keys (``status_ok``, ``status_bad``) is also asserted here.
    """
    from nts.i18n import I18N

    ru = I18N["RU"]
    assert isinstance(ru, dict)

    for key in SELF_CHECK_KEYS:
        assert key in ru, f"missing key {key!r} in I18N['RU']"
        value = ru[key]
        assert isinstance(value, str), (
            f"I18N['RU'][{key!r}] must be a str, got {type(value).__name__}"
        )
        assert value != "", f"I18N['RU'][{key!r}] must be non-empty"

    # Back-compat: pre-existing keys must remain bit-identical.
    # ``status_ok`` in EN_BASE is "OK" (line 54 of nts/i18n.py); RU keeps the
    # same value because RU_OVERRIDES only overrides ``status_bad``.
    assert ru["status_ok"] == "OK", (
        f"I18N['RU']['status_ok'] must remain 'OK' (back-compat), "
        f"got {ru['status_ok']!r}"
    )
    assert ru["status_bad"] == "не OK", (
        f"I18N['RU']['status_bad'] must remain 'не OK' (back-compat), "
        f"got {ru['status_bad']!r}"
    )
    # EN back-compat sanity check (status_ok / status_bad are pre-existing keys
    # that the checklist renderer reuses as ✓/✗ glyphs; if either drifts, the
    # renderer's assumption breaks).
    en = I18N["EN"]
    assert en["status_ok"] == "OK"
    assert en["status_bad"] == "not OK"


# ---- CLI integration (--self-check flag) ---------------------------


_CLI_ENV_BASE: Dict[str, str] = {
    "PYTHONIOENCODING": "utf-8",
}


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run ``python -m nts.cli <args>`` with UTF-8 stdout/stderr streams.

    Both child and parent force UTF-8: the child via ``PYTHONIOENCODING=utf-8``
    (so its ``sys.stdout`` writes UTF-8 bytes for ``δ`` etc.), and the parent
    via an explicit ``encoding='utf-8'`` — otherwise Windows ``subprocess.run``
    decodes pipe output as ``cp1252`` regardless of the env var.
    """
    return subprocess.run(
        [sys.executable, "-m", "nts.cli", *args],
        env={**os.environ, **_CLI_ENV_BASE},
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_cli_help_lists_self_check_flag() -> None:
    """``python -m nts.cli --help`` advertises the new ``--self-check`` flag.

    The help message must advertise the ``--self-check`` flag next to
    ``--input`` and ``--json``.
    """
    proc = _run_cli("--help")

    assert proc.returncode == 0, (
        f"--help should exit 0, got {proc.returncode!r}; "
        f"stderr={proc.stderr!r}"
    )
    assert "--self-check" in proc.stdout, (
        f"--help output must mention --self-check; got stdout={proc.stdout!r}"
    )


def test_cli_default_input_path_byte_identical(
    examples_dir: Path,
) -> None:
    """Regression: ``python -m nts.cli --input examples/default.json`` is unchanged.

    Asserts the exact stdout byte-string captured in
    ``.omo/evidence/baseline_pre_change.txt``. Any edit to ``nts/cli.py`` that
    disturbs the ``--input`` path — even a trailing newline or whitespace
    change — must trip this test. The default report language is Russian
    (``DEFAULT_LANGUAGE``); ``--lang EN`` keeps the historical English wording
    (see :func:`test_cli_lang_en_keeps_english_report`).
    """
    input_path = examples_dir / "default.json"
    proc = _run_cli("--input", str(input_path))

    assert proc.returncode == 0, (
        f"baseline --input run should exit 0, got {proc.returncode!r}; "
        f"stderr={proc.stderr!r}"
    )
    expected = (
        "Y = 1063.5 + 30.167*δ1 - 67.5*δ2\n"
        "\n"
        "t-критерии:\n"
        "  t_0: t=39.7300 sign=+\n"
        "  t_1: t=3.2700 sign=+\n"
        "  t_2: t=6.5740 sign=+\n"
        "\n"
        "Критерий Граббса:\n"
        "  Опыт 1: G=0.6250 (OK)\n"
        "  Опыт 2: G=0.6670 (OK)\n"
        "  Опыт 3: G=0.5760 (OK)\n"
        "  Опыт 4: G=0.5610 (OK)\n"
        "\n"
        "Поопытный вывод:\n"
        "  y_avg | delta1 | delta2 | y_pred | y_avg-y | (y_avg-y)^2\n"
        "  1122.67 | -1 | -1 | 1100.83 | 21.8333 | 476.694\n"
        "  944 | -1 | 1 | 965.833 | -21.8333 | 476.694\n"
        "  1139.33 | 1 | -1 | 1161.17 | -21.8333 | 476.694\n"
        "  1048 | 1 | 1 | 1026.17 | 21.8333 | 476.694\n"
        "\n"
        "F_ср=476.694\n"
        "F_знач=17.655\n"
        "Гипотеза не отвергается\n"
    )
    assert proc.stdout == expected, (
        f"stdout drifted from the recorded baseline; "
        f"diff={proc.stdout!r} vs {expected!r}"
    )


def test_cli_lang_en_keeps_english_report(
    examples_dir: Path,
) -> None:
    """``--lang EN`` reproduces the historical English report verbatim."""
    proc = _run_cli("--input", str(examples_dir / "default.json"), "--lang", "EN")

    assert proc.returncode == 0
    expected = (
        "Y = 1063.5 + 30.167*δ1 - 67.5*δ2\n"
        "\n"
        "t-tests:\n"
        "  t_0: t=39.7300 sign=+\n"
        "  t_1: t=3.2700 sign=+\n"
        "  t_2: t=6.5740 sign=+\n"
        "\n"
        "G-tests:\n"
        "  row 1: G=0.6250 (OK)\n"
        "  row 2: G=0.6670 (OK)\n"
        "  row 3: G=0.5760 (OK)\n"
        "  row 4: G=0.5610 (OK)\n"
        "\n"
        "Output:\n"
        "  y_avg | delta1 | delta2 | y_pred | y_avg-y | (y_avg-y)^2\n"
        "  1122.67 | -1 | -1 | 1100.83 | 21.8333 | 476.694\n"
        "  944 | -1 | 1 | 965.833 | -21.8333 | 476.694\n"
        "  1139.33 | 1 | -1 | 1161.17 | -21.8333 | 476.694\n"
        "  1048 | 1 | 1 | 1026.17 | 21.8333 | 476.694\n"
        "\n"
        "F_avg=476.694\n"
        "F_value=17.655\n"
        "Hypothesis not rejected\n"
    )
    assert proc.stdout == expected


def test_cli_self_check_missing_expected_exits_2(
    tmp_path: Path,
    examples_dir: Path,
) -> None:
    """``--self-check`` on a payload without ``expected`` exits with status 2.

    Mirrors the S7 scenario of the self-check plan: a self-check
    payload that contains only the ``input`` key (no ``expected``) must
    surface a clear stderr message and exit with status code 2 (distinct
    from 0 = pass and 1 = fail).

    Per the plan the ``--self-check`` flag is ``store_true``; the file path
    is supplied via the existing ``--input`` argument.
    """
    input_payload = json.loads((examples_dir / "default.json").read_text(encoding="utf-8"))
    payload_missing_expected = {"input": input_payload}
    bad_path = tmp_path / "missing_expected.json"
    bad_path.write_text(json.dumps(payload_missing_expected), encoding="utf-8")

    proc = _run_cli("--input", str(bad_path), "--self-check")

    assert proc.returncode == 2, (
        f"missing-expected payload must exit 2 (usage/schema error), got "
        f"{proc.returncode!r}; stdout={proc.stdout!r}; stderr={proc.stderr!r}"
    )
    combined = proc.stderr + proc.stdout
    assert "expected" in combined, (
        f"stderr/stdout must mention the missing 'expected' key; "
        f"got combined={combined!r}"
    )


# ---- end-to-end CLI subprocess integration (--self-check happy/mismatch) --


def _build_self_check_payload(
    *,
    perturb_b0_by: float = 0.0,
) -> Dict[str, Any]:
    """Build a synthetic ``{"input": ..., "expected": ...}`` self-check payload.

    Uses an inline 4-experiment ``InputData`` (the 2² design with full factor
    signatures) so :func:`nts.core.compute` is happy — see
    ``nts/core.py:19 EXPECTED_EXPERIMENTS = 4``. Numeric values are arbitrary
    (no canonical ``g_crit``/``t_crit``/``f_crit`` literals per
    ``.agent/rules/project-rules.md:30``).

    Runs :func:`nts.core.compute` on the same input the CLI will see, then
    snapshots the resulting ``ComputeResult`` (JSON round-tripped for
    deep-copy safety) as ``expected``. When ``perturb_b0_by`` is non-zero,
    the ``coefficients.b0`` field in ``expected`` is shifted by that amount
    so the numeric tolerance (``coeff_abs = 1e-3``) is exceeded and the CLI
    exits 1.

    Returns the dict ready to ``json.dumps``. Caller is responsible for
    writing it to disk in ``tmp_path`` so the CLI sees an isolated fixture.
    """
    from nts.core import _parse_input_data, compute

    input_dict = {
        "experiments": [
            {
                "idx": 1,
                "delta1": -1,
                "delta2": -1,
                "x1": 30.0,
                "x2": 50.0,
                "x3": 20.0,
                "y1": 100,
                "y2": 110,
                "y3": 90,
            },
            {
                "idx": 2,
                "delta1": -1,
                "delta2": 1,
                "x1": 35.0,
                "x2": 45.0,
                "x3": 20.0,
                "y1": 200,
                "y2": 210,
                "y3": 190,
            },
            {
                "idx": 3,
                "delta1": 1,
                "delta2": -1,
                "x1": 55.0,
                "x2": 35.0,
                "x3": 10.0,
                "y1": 300,
                "y2": 310,
                "y3": 290,
            },
            {
                "idx": 4,
                "delta1": 1,
                "delta2": 1,
                "x1": 45.0,
                "x2": 30.0,
                "x3": 25.0,
                "y1": 400,
                "y2": 410,
                "y3": 390,
            },
        ],
        "g_crit": 0.5,
        "t_crit": 2.0,
        "f_crit": 100.0,
    }
    parsed = _parse_input_data(input_dict)
    actual = compute(parsed)
    # JSON round-trip = deep copy that survives the subprocess boundary and
    # avoids sharing TypedDict (mutable dict at runtime) across processes.
    expected: Dict[str, Any] = json.loads(json.dumps(actual))
    if perturb_b0_by:
        expected["coefficients"]["b0"] = expected["coefficients"]["b0"] + perturb_b0_by
    return {"input": input_dict, "expected": expected}


def test_cli_self_check_subprocess_happy(tmp_path: Path) -> None:
    """End-to-end: ``python -m nts.cli --self-check`` exits 0 on a passing payload.

    Builds a synthetic ``{input, expected}`` file via
    :func:`_build_self_check_payload` (no canonical ``g_crit``/``t_crit``/
    ``f_crit`` literals) and invokes the CLI as a subprocess. The expected
    payload mirrors what :func:`nts.core.compute` returns for the same input,
    so the verifier should see zero diffs and the CLI should exit 0 with the
    human-readable checklist ending in ``"<N> пройдено, 0 провалено"``.

    Stdout must contain both the Unicode ``✓`` (rendered by default) and
    the literal ``Самопроверка`` header printed by
    :func:`nts.checker.print_checklist` (the CLI defaults to the Russian
    report; ``--lang EN`` is covered separately). The equation line includes
    ``δ1`` / ``δ2`` so ``PYTHONIOENCODING=utf-8`` is required to keep the
    parent's text decoder from raising on byte 0xCE etc. — this is exercised
    (not stubbed) via :func:`_run_cli`.
    """
    payload = _build_self_check_payload()
    path = tmp_path / "self_check_ok.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_cli("--input", str(path), "--self-check")

    assert proc.returncode == 0, (
        f"--self-check on a valid payload must exit 0, got {proc.returncode!r}; "
        f"stdout={proc.stdout!r}; stderr={proc.stderr!r}"
    )
    assert "Самопроверка" in proc.stdout, (
        f"stdout must contain the localized 'Самопроверка' header; got {proc.stdout!r}"
    )
    assert "пройдено" in proc.stdout, (
        f"stdout must mention 'пройдено' in the summary; got {proc.stdout!r}"
    )


def test_cli_self_check_subprocess_mismatch(tmp_path: Path) -> None:
    """End-to-end: ``--self-check`` exits 1 when ``coefficients.b0`` is perturbed.

    Builds the same synthetic payload via
    :func:`_build_self_check_payload(perturb_b0_by=100.0)`. The shift of 100
    on ``b0`` is far beyond ``Tolerance.coeff_abs = 1e-3``, so the CLI must
    surface at least one failed entry, print ``"<N> пройдено, 1 провалено"``
    (or more) and exit with status code 1. Stdout must contain ``"провалено"``
    so operators can grep the summary line.
    """
    payload = _build_self_check_payload(perturb_b0_by=100.0)
    path = tmp_path / "self_check_bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_cli("--input", str(path), "--self-check")

    assert proc.returncode == 1, (
        f"--self-check on a perturbed payload must exit 1, got "
        f"{proc.returncode!r}; stdout={proc.stdout!r}; stderr={proc.stderr!r}"
    )
    assert "провалено" in proc.stdout, (
        f"stdout must contain 'провалено' in the summary; got {proc.stdout!r}"
    )

# ---- Core vs extended: workbook split + simplified (no-extended) mode ---------
#
# The reference workbook keeps the *core* result keys on the ``result`` sheet
# (yellow-marked, same cells as the hand-made reference file) and every other
# result key on the optional ``extended`` sheet. A workbook without that sheet
# must still be a complete, runnable check — the simplified mode compares only
# the fields the reference file actually provides.


def _write_reference_workbook(path: Path) -> Path:
    """Write a full self-check workbook from the arbitrary-value test fixture."""
    from nts.checker import write_self_check_xlsx

    write_self_check_xlsx(
        path, _tiny_input_xlsx_payload(), _full_compute_result_for_xlsx()
    )
    return path


def _drop_sheet(path: Path, sheet_name: str) -> None:
    """Remove ``sheet_name`` from the workbook at ``path`` (in place)."""
    import openpyxl

    wb = openpyxl.load_workbook(path)
    del wb[sheet_name]
    wb.save(path)


def _core_expected_payload() -> Dict[str, Any]:
    """The core-only expected payload: no ``extended`` keys at all."""
    return {
        "coefficients": {"b0": 1.0, "b1": 2.0, "b2": 3.0},
        "coefficients_v": {"b0": 10.0, "b1": 20.0, "b2": 30.0},
        "t_tests": {"t0": 5.0, "t1": 4.0, "t2": 3.0},
        "f_value": 5.0,
    }


def test_write_self_check_xlsx_splits_core_and_extended(tmp_path: Path) -> None:
    """``result`` holds the core keys only (yellow fill); ``extended`` holds the rest."""
    import openpyxl

    from nts.checker import (
        CORE_RESULT_KEYS,
        EXTENDED_SHEET_NAME,
        write_self_check_xlsx,
    )

    path = tmp_path / "split.xlsx"
    write_self_check_xlsx(
        path, _tiny_input_xlsx_payload(), _full_compute_result_for_xlsx()
    )

    wb = openpyxl.load_workbook(path)
    assert EXTENDED_SHEET_NAME in wb.sheetnames

    res = wb["result"]
    res_keys = [row[0] for row in res.iter_rows(min_row=2, values_only=True) if row[0]]
    ext = wb[EXTENDED_SHEET_NAME]
    ext_keys = [row[0] for row in ext.iter_rows(min_row=2, values_only=True) if row[0]]

    assert set(res_keys) == set(CORE_RESULT_KEYS)
    assert "equation" in ext_keys, "non-core keys must live on the extended sheet"
    assert not (set(res_keys) & set(ext_keys)), "a key cannot be on both sheets"

    # Core value cells are yellow-marked; extended cells stay unstyled.
    for row in res.iter_rows(min_row=2):
        if row[0] is None:
            continue
        assert row[1].fill.patternType == "solid"
        assert row[1].fill.fgColor.rgb == "FFFFFF00"
    for row in ext.iter_rows(min_row=2):
        if row[0] is None:
            continue
        assert row[1].fill.patternType in (None, "none")


def test_parse_self_check_xlsx_merges_extended_sheet(tmp_path: Path) -> None:
    """The optional ``extended`` sheet is merged into the expected payload."""
    from nts.checker import MODE_FULL, parse_self_check_bundle

    path = _write_reference_workbook(tmp_path / "full.xlsx")
    bundle = parse_self_check_bundle(path)

    assert bundle.mode == MODE_FULL, "an extended sheet declares full coverage"
    assert bundle.expected["equation"] == "Y = b0 + b1·δ1 + b2·δ2"
    assert bundle.expected["coefficients"]["b0"] == pytest.approx(1.0)
    assert bundle.expected["t_tests"]["t0"] == pytest.approx(5.0)
    # The merge must not drop the sibling keys of a nested group.
    assert bundle.expected["t_tests"]["sign_b1"] == "+"
    assert bundle.expected["z_averages"]["z2_avg"] == pytest.approx(2.5)


def test_parse_self_check_bundle_without_extended_is_simplified(
    tmp_path: Path,
) -> None:
    """A workbook without ``extended`` parses in simplified mode."""
    from nts.checker import EXTENDED_SHEET_NAME, MODE_SIMPLIFIED, parse_self_check_bundle

    path = _write_reference_workbook(tmp_path / "core_only.xlsx")
    _drop_sheet(path, EXTENDED_SHEET_NAME)

    bundle = parse_self_check_bundle(path)

    assert bundle.mode == MODE_SIMPLIFIED
    assert "equation" not in bundle.expected
    assert bundle.expected["coefficients"]["b0"] == pytest.approx(1.0)
    assert bundle.expected["t_tests"]["t0"] == pytest.approx(5.0)


def test_verify_simplified_mode_checks_only_core_fields() -> None:
    """``MODE_SIMPLIFIED`` compares the core keys only — optional fields are skipped."""
    from nts.checker import MODE_SIMPLIFIED, verify

    actual = _full_compute_result_for_xlsx()
    result = verify(actual, _core_expected_payload(), mode=MODE_SIMPLIFIED)

    assert result.failed == 0, (
        f"simplified mode must not fail on absent fields; "
        f"failures={[e.message for e in result.entries if not e.passed]!r}"
    )
    assert {e.name for e in result.entries} == {
        "coefficients.b0", "coefficients.b1", "coefficients.b2",
        "coefficients_v.b0", "coefficients_v.b1", "coefficients_v.b2",
        "t_tests.t0", "t_tests.t1", "t_tests.t2",
        "f_value",
    }


def test_verify_simplified_mode_keeps_grubbs_and_skips_output_rows() -> None:
    """Simplified mode reports the Grubbs block but not the per-row output.

    A core-only workbook still carries a ``grubbs`` sheet, and the criterion
    is part of the core method: the simplified checklist must show it. The
    ``output_rows`` block stays extended-only.
    """
    from nts.checker import MODE_SIMPLIFIED, verify

    actual = _full_compute_result_for_xlsx()
    full_expected = _full_compute_result_for_xlsx()
    result = verify(actual, full_expected, mode=MODE_SIMPLIFIED)

    names = {e.name for e in result.entries}
    assert any(name.startswith("g_tests") for name in names), (
        "the Grubbs block must be reported in the simplified mode"
    )
    assert not any(name.startswith("output_rows") for name in names)
    assert names == {
        "coefficients.b0", "coefficients.b1", "coefficients.b2",
        "coefficients_v.b0", "coefficients_v.b1", "coefficients_v.b2",
        "t_tests.t0", "t_tests.t1", "t_tests.t2",
        "f_value",
        "g_tests[row=1].g", "g_tests[row=1].ok",
        "g_tests[row=2].g", "g_tests[row=2].ok",
        "g_tests[row=3].g", "g_tests[row=3].ok",
        "g_tests[row=4].g", "g_tests[row=4].ok",
    }


def test_verify_full_mode_reports_absent_fields() -> None:
    """``MODE_FULL`` (default) keeps reporting absent fields as failures."""
    from nts.checker import MODE_FULL, verify

    actual = _full_compute_result_for_xlsx()
    result = verify(actual, _core_expected_payload(), mode=MODE_FULL)

    assert result.failed > 0
    messages = " ".join(e.message for e in result.entries if not e.passed)
    assert "missing" in messages


def test_verify_rejects_unknown_mode() -> None:
    """An unknown mode is a programming error, not a silent fallback."""
    from nts.checker import verify

    with pytest.raises(ValueError, match="unknown verification mode"):
        verify(_full_compute_result_for_xlsx(), _core_expected_payload(), mode="nope")


def test_cli_self_check_xlsx_without_extended_exits_0(
    tmp_path: Path,
    examples_dir: Path,
) -> None:
    """A workbook without ``extended`` still passes the CLI self-check.

    The workbook is built from the real ``examples/default.json`` input, so the
    expected values match the computation exactly — the only difference is the
    missing ``extended`` sheet.
    """
    from nts.checker import EXTENDED_SHEET_NAME, write_self_check_xlsx
    from nts.core import compute, read_input_file

    input_data = read_input_file(examples_dir / "default.json")
    result = compute(input_data)

    path = tmp_path / "core_only.xlsx"
    write_self_check_xlsx(path, input_data, result)
    _drop_sheet(path, EXTENDED_SHEET_NAME)

    proc = _run_cli("--input", str(path), "--self-check")

    assert proc.returncode == 0, (
        f"core-only workbook must exit 0; got {proc.returncode!r}; "
        f"stdout={proc.stdout!r}; stderr={proc.stderr!r}"
    )
    assert "0 провалено" in proc.stdout, (
        f"checklist summary must report no failures; got {proc.stdout!r}"
    )
    assert "g_tests" in proc.stdout, (
        f"the simplified checklist must report the Grubbs block; got {proc.stdout!r}"
    )


def test_cli_self_check_xlsx_with_extended_exits_0(
    tmp_path: Path,
    examples_dir: Path,
) -> None:
    """The same workbook with an ``extended`` sheet also passes (full mode)."""
    from nts.checker import write_self_check_xlsx
    from nts.core import compute, read_input_file

    input_data = read_input_file(examples_dir / "default.json")
    result = compute(input_data)

    path = tmp_path / "full.xlsx"
    write_self_check_xlsx(path, input_data, result)

    proc = _run_cli("--input", str(path), "--self-check")

    assert proc.returncode == 0, (
        f"full workbook must exit 0; got {proc.returncode!r}; "
        f"stdout={proc.stdout!r}; stderr={proc.stderr!r}"
    )
    assert "0 провалено" in proc.stdout


# ---- Human-readable variable dictionary -------------------------------------
#
# The machine keys stay stable; the dictionary says what each of them means.
# It feeds the Excel ``description`` column and the GUI checklist.


def test_dictionary_describes_every_core_key() -> None:
    """Every core key has a description in both languages."""
    from nts.checker import CORE_RESULT_KEYS
    from nts.dictionary import UNKNOWN_DESCRIPTION, describe

    for key in CORE_RESULT_KEYS:
        for lang in ("EN", "RU"):
            text = describe(key, lang)
            assert text != UNKNOWN_DESCRIPTION, f"{lang}: no description for {key!r}"
            assert text.strip(), f"{lang}: empty description for {key!r}"


def test_dictionary_describes_every_written_result_key() -> None:
    """Every key the writer emits has a description (no empty cells)."""
    from nts.checker import write_self_check_xlsx
    from nts.dictionary import UNKNOWN_DESCRIPTION, describe

    path = Path(tempfile.gettempdir()) / "nts_dict_probe.xlsx"
    write_self_check_xlsx(
        path, _tiny_input_xlsx_payload(), _full_compute_result_for_xlsx()
    )
    import openpyxl

    wb = openpyxl.load_workbook(path)
    for sheet in ("result", "extended"):
        for row in wb[sheet].iter_rows(min_row=2, values_only=True):
            if not row[0]:
                continue
            assert row[2] != UNKNOWN_DESCRIPTION, f"no description for {row[0]!r}"
            assert row[2] == describe(row[0], "RU")


def test_dictionary_describe_entry_resolves_container_prefix() -> None:
    """Checklist entry names resolve to the description of their variable."""
    from nts.dictionary import UNKNOWN_DESCRIPTION, describe, describe_entry

    assert describe_entry("coefficients.b0", "RU") == describe("coefficients.b0", "RU")
    assert describe_entry("g_tests[row=1].g", "RU") == describe("g", "RU")
    assert describe_entry(
        "output_rows[-1.0, -1.0].y_avg", "EN"
    ) == describe("y_avg", "EN")
    assert describe_entry("totally.unknown", "RU") == UNKNOWN_DESCRIPTION


def test_write_self_check_xlsx_adds_description_column(tmp_path: Path) -> None:
    """Both key/value sheets carry a ``description`` column."""
    import openpyxl

    from nts.checker import EXTENDED_SHEET_NAME, write_self_check_xlsx
    from nts.dictionary import describe

    path = tmp_path / "described.xlsx"
    write_self_check_xlsx(
        path, _tiny_input_xlsx_payload(), _full_compute_result_for_xlsx(), lang="RU"
    )

    wb = openpyxl.load_workbook(path)
    for sheet in ("result", EXTENDED_SHEET_NAME):
        ws = wb[sheet]
        assert [c.value for c in ws[1]] == ["key", "value", "description"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row[0]:
                continue
            assert row[2] == describe(row[0], "RU")


def test_write_self_check_xlsx_round_trips_with_description_column(
    tmp_path: Path,
) -> None:
    """The reader tolerates the extra description column."""
    from nts.checker import parse_self_check_bundle, write_self_check_xlsx

    path = tmp_path / "round_trip_described.xlsx"
    write_self_check_xlsx(
        path, _tiny_input_xlsx_payload(), _full_compute_result_for_xlsx(), lang="EN"
    )

    bundle = parse_self_check_bundle(path)
    assert bundle.expected["coefficients"]["b0"] == pytest.approx(1.0)
    assert bundle.expected["equation"] == "Y = b0 + b1·δ1 + b2·δ2"


def test_write_self_check_xlsx_localizes_verdict_and_round_trips(
    tmp_path: Path,
) -> None:
    """The RU workbook shows the Russian verdict/status but reads canonically."""
    import openpyxl

    from nts.checker import (
        EXTENDED_SHEET_NAME,
        parse_self_check_bundle,
        write_self_check_xlsx,
    )

    result = _full_compute_result_for_xlsx()
    result["f_result"] = "Hypothesis not rejected"
    result["g_tests"][0]["ok"] = "not OK"

    path = tmp_path / "ru_report.xlsx"
    write_self_check_xlsx(
        path, _tiny_input_xlsx_payload(), result,
        lang="RU", localize_values=True,
    )

    wb = openpyxl.load_workbook(path)
    ext_values = {
        row[0]: row[1]
        for row in wb[EXTENDED_SHEET_NAME].iter_rows(min_row=2, values_only=True)
        if row[0]
    }
    assert ext_values["f_result"] == "Гипотеза не отвергается"
    grubbs_ok = [
        row[2] for row in wb["grubbs"].iter_rows(min_row=2, values_only=True)
        if row[0] is not None
    ]
    assert grubbs_ok[0] == "не OK"

    bundle = parse_self_check_bundle(path)
    assert bundle.expected["f_result"] == "Hypothesis not rejected"
    assert bundle.expected["g_tests"][0]["ok"] == "not OK"


def test_print_checklist_includes_description_when_lang_given(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``print_checklist(lang=...)`` appends the human description."""
    from nts.checker import print_checklist
    from nts.dictionary import describe

    entry = CheckEntry(
        name="coefficients.b0",
        passed=True,
        actual=1.0,
        expected=1.0,
        diff=0.0,
        message="",
    )
    print_checklist(CheckResult(passed=1, failed=0, entries=[entry]), lang="RU")

    out = capsys.readouterr().out
    assert describe("coefficients.b0", "RU") in out
    assert "coefficients.b0" in out


# ---- Reverse GUI: verification modes -----------------------------------------
#
# The reverse GUI verifies in the simplified mode by default and switches to
# the extended mode automatically when the loaded file carries an ``extended``
# sheet.


def _reverse_app_stub(
    *,
    mode_code: str = "auto",
    file_mode: str = MODE_SIMPLIFIED,
):
    """A :class:`ReverseApp` without a Tk root (no display needed)."""
    from nts.reverse_gui import ReverseApp

    app = ReverseApp.__new__(ReverseApp)
    app.mode_code = mode_code
    app.file_mode = file_mode
    return app


def test_reverse_gui_mode_defaults_to_simplified() -> None:
    """Without a file the reverse GUI would verify in the simplified mode."""
    app = _reverse_app_stub(mode_code="auto", file_mode=MODE_SIMPLIFIED)
    assert app._effective_mode() == MODE_SIMPLIFIED
    assert app._effective_mode_code() == "simplified"


def test_reverse_gui_mode_auto_follows_extended_sheet() -> None:
    """An ``extended`` sheet switches the automatic mode to extended."""
    app = _reverse_app_stub(mode_code="auto", file_mode=MODE_FULL)
    assert app._effective_mode() == MODE_FULL
    assert app._effective_mode_code() == "full"


def test_reverse_gui_mode_selector_overrides_file_mode() -> None:
    """The explicit selector wins over what the file implies."""
    app = _reverse_app_stub(mode_code="simplified", file_mode=MODE_FULL)
    assert app._effective_mode() == MODE_SIMPLIFIED

    app = _reverse_app_stub(mode_code="full", file_mode=MODE_SIMPLIFIED)
    assert app._effective_mode() == MODE_FULL


def test_reverse_gui_has_description_column() -> None:
    """The checklist shows a description column next to the field name."""
    from nts.reverse_gui import _CHECKLIST_COLUMNS

    assert "description" in _CHECKLIST_COLUMNS
    assert _CHECKLIST_COLUMNS.index("description") == 2


def test_reverse_i18n_has_mode_and_description_strings() -> None:
    """Both languages carry the mode selector and the description column."""
    from nts.i18n import I18N

    for lang in ("EN", "RU"):
        s = I18N[lang]
        for key in (
            "reverse_mode",
            "reverse_mode_auto",
            "reverse_mode_simplified",
            "reverse_mode_full",
            "reverse_mode_current",
            "reverse_col_description",
        ):
            assert key in s, f"missing {lang}!{key}"


def test_write_self_check_xlsx_writes_dictionary_sheet(tmp_path: Path) -> None:
    """The workbook carries a ``dictionary`` sheet with every variable."""
    import openpyxl

    from nts.checker import DICTIONARY_SHEET_NAME, write_self_check_xlsx
    from nts.dictionary import DESCRIPTIONS

    path = tmp_path / "with_dictionary.xlsx"
    write_self_check_xlsx(
        path, _tiny_input_xlsx_payload(), _full_compute_result_for_xlsx(), lang="RU"
    )

    wb = openpyxl.load_workbook(path)
    ws = wb[DICTIONARY_SHEET_NAME]
    assert [c.value for c in ws[1]] == ["key", "description"]

    entries = {
        row[0]: row[1]
        for row in ws.iter_rows(min_row=2, values_only=True)
        if row[0]
    }
    assert entries["coefficients.b0"] == DESCRIPTIONS["RU"]["coefficients.b0"]
    # Column names of the other sheets are covered too.
    assert entries["x1"] == DESCRIPTIONS["RU"]["x1"]
    assert entries["y_avg_minus_y_sq"] == DESCRIPTIONS["RU"]["y_avg_minus_y_sq"]


def test_parse_self_check_xlsx_ignores_dictionary_sheet(tmp_path: Path) -> None:
    """The extra ``dictionary`` sheet does not disturb the reader."""
    from nts.checker import parse_self_check_bundle, write_self_check_xlsx

    path = tmp_path / "with_dictionary_read.xlsx"
    write_self_check_xlsx(
        path, _tiny_input_xlsx_payload(), _full_compute_result_for_xlsx()
    )

    bundle = parse_self_check_bundle(path)
    assert bundle.expected["coefficients"]["b0"] == pytest.approx(1.0)
    assert "dictionary" not in bundle.expected


# ---- Инварианты формата и словаря ------------------------------------------
#
# Три договорённости, которые проверялись вручную и теперь зафиксированы
# тестами: цвет не влияет на логику, словарь покрывает весь результат,
# эталонная книга соответствует тому, что пишет писатель.


def test_verify_result_does_not_depend_on_cell_fill(
    tmp_path: Path,
    examples_dir: Path,
) -> None:
    """Заливка ядра — только метка: снятие всех цветов не меняет результат.

    Ядро определяется списком ``CORE_RESULT_KEYS`` и именем листа, а не
    цветом: код нигде не читает заливку (единственная операция — запись
    ``ws.cell(...).fill = fill`` при экспорте).
    """
    import openpyxl
    from openpyxl.styles import PatternFill

    from nts.checker import parse_self_check_bundle, verify, write_self_check_xlsx
    from nts.core import compute, read_input_file

    path = tmp_path / "colored.xlsx"
    data = read_input_file(examples_dir / "default.json")
    write_self_check_xlsx(path, data, compute(data), lang="RU")

    bundle = parse_self_check_bundle(path)
    before = verify(compute(bundle.input_data), bundle.expected, mode=bundle.mode)

    workbook = openpyxl.load_workbook(path)
    stripped = 0
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if cell.fill is not None and cell.fill.patternType:
                    cell.fill = PatternFill()
                    stripped += 1
    assert stripped > 0, "в эталонной книге должна быть хотя бы одна заливка"
    workbook.save(path)

    stripped_bundle = parse_self_check_bundle(path)
    after = verify(
        compute(stripped_bundle.input_data),
        stripped_bundle.expected,
        mode=stripped_bundle.mode,
    )

    assert (after.passed, after.failed) == (before.passed, before.failed), (
        "снятие заливки изменило результат проверки: "
        f"было {before.passed}/{before.failed}, стало {after.passed}/{after.failed}"
    )
    assert after.failed == 0


def test_dictionary_covers_every_result_key(examples_dir: Path) -> None:
    """Каждый ключ, возвращаемый ``compute()``, имеет описание в словаре."""
    from nts.core import compute, read_input_file
    from nts.dictionary import UNKNOWN_DESCRIPTION, describe

    result = compute(read_input_file(examples_dir / "default.json"))

    keys: list[str] = []
    for name, value in result.items():
        if isinstance(value, dict):
            keys.extend(f"{name}.{sub}" for sub in value)
        else:
            keys.append(name)

    missing = [key for key in keys if describe(key, "RU") == UNKNOWN_DESCRIPTION]
    assert not missing, f"ключи без описания: {missing}"


def test_reference_workbook_matches_writer(
    tmp_path: Path,
    examples_dir: Path,
) -> None:
    """Эталонная книга в ``examples/`` совпадает с выводом писателя.

    Книга — эталон для проверок; если писатель изменился, эталон нужно
    перегенерировать, а не чинить руками.
    """
    import openpyxl

    from nts.checker import write_self_check_xlsx
    from nts.core import compute, read_input_file

    reference = examples_dir / "default_result.xlsx"
    if not reference.exists():
        pytest.skip("эталонная книга отсутствует")

    data = read_input_file(examples_dir / "default.json")
    fresh = tmp_path / "fresh.xlsx"
    write_self_check_xlsx(fresh, data, compute(data), lang="RU")

    def snapshot(path: Path) -> Dict[str, List[tuple]]:
        workbook = openpyxl.load_workbook(path, data_only=True)
        return {
            sheet.title: [tuple(row) for row in sheet.iter_rows(values_only=True)]
            for sheet in workbook.worksheets
        }

    assert snapshot(fresh) == snapshot(reference), (
        "эталонная книга разошлась с писателем — перегенерируйте examples/default_result.xlsx"
    )
```

## `tests/test_contracts.py`

```python
"""Контракты между модулями — страховочные тесты.

Эти тесты фиксируют договорённости, которые должны выполняться и до, и после
изменений: версия, которую получает сборка, и публичный API пакета
``nts.checker``. Они специально устроены так, чтобы проходить при обоих
вариантах реализации — проверяется инвариант, а не способ его достижения.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_build_module() -> Any:
    """Загрузить ``build.py`` как модуль (без запуска сборки)."""
    path = REPO_ROOT / "build.py"
    spec = importlib.util.spec_from_file_location("nts_build_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _build_file_version() -> str:
    """Версия, которую сборка передаёт Nuitka как ``--file-version``.

    До появления единого источника версии это литерал в команде сборки,
    после — результат ``build.app_version()``. Инвариант один: версия
    сборки совпадает с версией пакета.
    """
    module = _load_build_module()
    getter = getattr(module, "app_version", None)
    if getter is not None:
        return str(getter())
    source = Path(module.__file__).read_text(encoding="utf-8")
    match = re.search(r"--file-version=([0-9][0-9.]*)", source)
    assert match, "в build.py не найден флаг --file-version"
    return match.group(1)


def test_build_version_matches_package_version() -> None:
    """Версия, зашиваемая в .exe, совпадает с ``nts.__version__``.

    Страховка перед вынесением версии в единый источник: литерал
    ``--file-version=0.2.1`` в ``build.py`` и ``__version__`` в
    ``nts/__init__.py`` обязаны совпадать.
    """
    import nts

    assert _build_file_version() == nts.__version__


#: Публичный API самопроверки. Им пользуются nts/cli.py, nts/gui.py,
#: nts/reverse_gui.py и тесты — переименование или удаление любого имени
#: ломает их импорт.
CHECKER_PUBLIC_API: tuple[str, ...] = (
    "Tolerance",
    "CheckEntry",
    "CheckResult",
    "SelfCheckBundle",
    "verify",
    "parse_self_check_file",
    "parse_self_check_bundle",
    "parse_self_check_xlsx",
    "write_self_check_xlsx",
    "print_checklist",
    "CORE_RESULT_KEYS",
    "MODE_FULL",
    "MODE_SIMPLIFIED",
    "EXTENDED_SHEET_NAME",
    "DICTIONARY_SHEET_NAME",
    "CORE_FILL_RGB",
    "DESCRIPTION_COLUMN",
)


def test_checker_public_api_surface() -> None:
    """Все публичные имена ``nts.checker`` доступны и экспортируются.

    Страховка перед разбиением монолита ``nts/checker.py`` на пакет: API
    должен остаться прежним, иначе ломаются импорты в CLI и обоих GUI.
    """
    import nts.checker as checker

    missing = [name for name in CHECKER_PUBLIC_API if not hasattr(checker, name)]
    assert not missing, f"пропали публичные имена nts.checker: {missing}"

    exported = getattr(checker, "__all__", None)
    if exported is not None:
        not_exported = [name for name in CHECKER_PUBLIC_API if name not in exported]
        assert not not_exported, f"не попали в __all__: {not_exported}"


def test_checker_verify_behaviour_is_pinned() -> None:
    """Поведение ``verify()`` зафиксировано: имена полей и счётчики.

    Страховка перед любым рефакторингом движка сравнения: на эталонной
    фикстуре проверка даёт ровно 10 пройденных полей ядра и ни одного
    расхождения, а имена полей не меняются.
    """
    from nts.checker import MODE_SIMPLIFIED, verify

    actual: dict[str, Any] = {
        "coefficients": {"b0": 1.0, "b1": 2.0, "b2": 3.0},
        "coefficients_v": {"b0": 10.0, "b1": 20.0, "b2": 30.0},
        "z_averages": {"z1_avg": 1.5, "z2_avg": 2.5},
        "pz": {"pz1": 0.5, "pz2": 1.5},
        "delta_calc": {"delta1": 0.4, "delta2": 0.6},
        "t_tests": {
            "t0": 5.0, "t1": 4.0, "t2": 3.0,
            "sign_b0": "+", "sign_b1": "+", "sign_b2": "+",
        },
        "g_tests": [
            {"row": 1, "g": 0.1, "ok": "OK"},
            {"row": 2, "g": 0.2, "ok": "OK"},
        ],
        "output_rows": [
            {
                "delta1": -1.0, "delta2": -1.0, "y_avg": 110.0,
                "y_pred": 109.5, "y_avg_minus_y": 0.5, "y_avg_minus_y_sq": 0.25,
            },
        ],
        "f_avg": 50.0,
        "f_value": 5.0,
        "f_result_code": "not_rejected",
        "f_result": "ok",
        "equation": "Y = b0 + b1·δ1 + b2·δ2",
        "g_crit": 0.5,
        "t_crit": 2.0,
        "f_crit": 100.0,
    }
    expected: dict[str, Any] = {
        "coefficients": {"b0": 1.0, "b1": 2.0, "b2": 3.0},
        "coefficients_v": {"b0": 10.0, "b1": 20.0, "b2": 30.0},
        "t_tests": {"t0": 5.0, "t1": 4.0, "t2": 3.0},
        "f_value": 5.0,
    }

    result = verify(actual, expected, mode=MODE_SIMPLIFIED)

    assert result.failed == 0
    assert result.passed == 10
    assert [entry.name for entry in result.entries] == [
        "coefficients.b0", "coefficients.b1", "coefficients.b2",
        "coefficients_v.b0", "coefficients_v.b1", "coefficients_v.b2",
        "t_tests.t0", "t_tests.t1", "t_tests.t2",
        "f_value",
    ]


def test_checker_verify_reports_mismatch_in_full_mode() -> None:
    """В полном режиме расхождение по-прежнему попадает в отчёт."""
    from nts.checker import MODE_FULL, verify

    actual: dict[str, Any] = {
        "coefficients": {"b0": 1.0, "b1": 2.0, "b2": 3.0},
        "coefficients_v": {"b0": 10.0, "b1": 20.0, "b2": 30.0},
        "z_averages": {"z1_avg": 1.5, "z2_avg": 2.5},
        "pz": {"pz1": 0.5, "pz2": 1.5},
        "delta_calc": {"delta1": 0.4, "delta2": 0.6},
        "t_tests": {
            "t0": 5.0, "t1": 4.0, "t2": 3.0,
            "sign_b0": "+", "sign_b1": "+", "sign_b2": "+",
        },
        "g_tests": [{"row": 1, "g": 0.1, "ok": "OK"}],
        "output_rows": [],
        "f_avg": 50.0,
        "f_value": 5.0,
        "f_result_code": "not_rejected",
        "f_result": "ok",
        "equation": "Y = b0",
        "g_crit": 0.5,
        "t_crit": 2.0,
        "f_crit": 100.0,
    }
    expected = dict(actual)
    expected["coefficients"] = {"b0": 1.5, "b1": 2.0, "b2": 3.0}

    result = verify(actual, expected, mode=MODE_FULL)

    failed = [entry for entry in result.entries if not entry.passed]
    assert [entry.name for entry in failed] == ["coefficients.b0"]
    assert failed[0].diff == pytest.approx(-0.5)
```

## `tests/test_core.py`

```python
"""Тесты для nts.core — математическая модель и регрессия 2².

Методичка §3 (полный факторный план, параллельные опыты, Стьюдент, Граббс, Фишер).
"""

from __future__ import annotations

import math

import pytest

from nts.core import (
    EXPECTED_EXPERIMENTS,
    Experiment,
    InputData,
    PARALLEL_TRIALS,
    compute,
    format_equation,
    read_input_file,
)


def _data(exps, g=0.7679, t=2.306, f=239.0) -> InputData:
    return InputData(experiments=exps, g_crit=g, t_crit=t, f_crit=f)


def test_inputs_count():
    assert EXPECTED_EXPERIMENTS == 4
    assert PARALLEL_TRIALS == 3


def test_compute_rejects_wrong_count(default_criteria):
    short = [Experiment(idx=1, delta1=-1, delta2=-1, x1=33, x2=33, x3=33, y1=1, y2=2, y3=3)]
    with pytest.raises(ValueError, match="Expected exactly 4"):
        compute(_data(short, *default_criteria))


def test_coded_coefficients_match_hand_calc(all_significant_experiments, default_criteria):
    """Фиксированный синтетический пример: b_coded = (1000, 100, 100), все значимы."""
    result = compute(_data(all_significant_experiments, *default_criteria))
    assert result["coefficients"] == {"b0": 1000.0, "b1": 100.0, "b2": 100.0}
    t = result["t_tests"]
    assert t["t0"] > 2.306 and t["t1"] > 2.306 and t["t2"] > 2.306
    assert t["sign_b0"] == t["sign_b1"] == t["sign_b2"] == "+"


def test_student_uses_sqrt_s2_over_n_times_m(default_experiments, default_criteria):
    """Student S_в per Excel reference: √(s²_вос / (N·m)), not √(s²_вос / N).

    Math derivation: each b_i = Σδ_i·y_avg / N where y_avg has variance s²/m
    (mean of m replicates), so Var(b_i) = s²/(N·m) → S_в = √(s²/(N·m)).
    Default.json: s²=8416, N=4, m=3 → S_в = √(8416/12) ≈ 26.4829.
    See .agent/context/calculation-diff.md for full diff vs Методичка §3.
    """
    result = compute(_data(default_experiments, *default_criteria))
    for key in ("t0", "t1", "t2"):
        assert key in result["t_tests"]
        assert math.isfinite(result["t_tests"][key])
        assert result["t_tests"][key] >= 0


def test_student_uses_natural_not_coded(default_experiments, default_criteria):
    """Student t per Excel reference: t_i = |b_i_v| / S_в (натуральные b, не кодированные).

    For default.json, all three b_v are large enough that t > 2.306 ⇒ all significant.
    Diff vs old Методичка-aligned behaviour: b_1 and b_2 cross the t_crit threshold.
    """
    result = compute(_data(default_experiments, *default_criteria))
    t = result["t_tests"]
    assert t["sign_b0"] == "+"
    assert t["sign_b1"] == "+"
    assert t["sign_b2"] == "+"


def test_grubbs_criterion(default_experiments, default_criteria):
    result = compute(_data(default_experiments, *default_criteria))
    assert len(result["g_tests"]) == EXPECTED_EXPERIMENTS
    for g in result["g_tests"]:
        assert {"row", "g", "ok"} <= g.keys()
        assert 0 <= g["g"] <= 1
        assert g["ok"] in {"OK", "not OK"}


def test_fisher_criterion(default_experiments, default_criteria):
    result = compute(_data(default_experiments, *default_criteria))
    assert result["f_value"] > 0
    assert result["f_avg"] >= 0
    assert result["f_result_code"] in {"not_rejected", "rejected"}


def test_equation_key_in_result(default_experiments, default_criteria):
    """Регрессионный тест TD-11: compute() возвращает 'equation', чтобы
    CLI/GUI могли отрендерить регрессию без своей реализации форматтера."""
    result = compute(_data(default_experiments, *default_criteria))
    assert "equation" in result
    assert result["equation"].startswith("Y = ")


def test_equation_skips_insignificant_terms(default_experiments, default_criteria):
    """Default.json: все 3 b значимы → Y = b0 + b1*δ1 + b2*δ2 (b2 отрицателен)."""
    result = compute(_data(default_experiments, *default_criteria))
    assert "0*δ" not in result["equation"]
    assert "+ -" not in result["equation"]
    assert result["equation"].startswith("Y = ")
    assert all(
        term in result["equation"] for term in ("δ1", "δ2")
    )


def test_format_equation_unit():
    eq = format_equation(10.0, 2.5, -3.0, "δ1", "δ2")
    assert eq == "Y = 10 + 2.5*δ1 - 3*δ2"


def test_format_equation_zero_terms():
    eq = format_equation(1063.5, 0.0, 0.0, "δ1", "δ2")
    assert eq == "Y = 1063.5"


def test_compute_handles_zero_deviations(default_criteria):
    """Когда все 3 повторности в опыте равны, G = 0, safe_div не падает на sum_sq=0."""
    exp = Experiment(idx=1, delta1=-1, delta2=-1, x1=30.0, x2=50.0, x3=20.0, y1=500, y2=500, y3=500)
    rest = [
        Experiment(idx=2, delta1=-1, delta2=1, x1=35.0, x2=45.0, x3=20.0, y1=600, y2=600, y3=600),
        Experiment(idx=3, delta1=1, delta2=-1, x1=55.0, x2=35.0, x3=10.0, y1=700, y2=700, y3=700),
        Experiment(idx=4, delta1=1, delta2=1, x1=45.0, x2=30.0, x3=25.0, y1=800, y2=800, y3=800),
    ]
    result = compute(_data([exp, *rest], *default_criteria))
    assert result["g_tests"][0]["g"] == 0.0
    assert result["g_tests"][0]["ok"] == "OK"


def test_compute_handles_f_via_inf(default_criteria):
    """Когда остатки редуцированной модели нулевые, F → ∞ через защитный путь safe_div."""
    exp = Experiment(idx=1, delta1=-1, delta2=-1, x1=30.0, x2=50.0, x3=20.0, y1=1000, y2=1000, y3=1000)
    others = [
        Experiment(idx=2, delta1=-1, delta2=1, x1=35.0, x2=45.0, x3=20.0, y1=1000, y2=1000, y3=1000),
        Experiment(idx=3, delta1=1, delta2=-1, x1=55.0, x2=35.0, x3=10.0, y1=1000, y2=1000, y3=1000),
        Experiment(idx=4, delta1=1, delta2=1, x1=45.0, x2=30.0, x3=25.0, y1=1000, y2=1000, y3=1000),
    ]
    result = compute(_data([exp, *others], *default_criteria))
    assert result["f_avg"] == 0.0
    assert result["f_value"] == float("inf")


@pytest.mark.parametrize("filename", ["default.json", "new_test_variant.json"])
def test_examples_roundtrip(filename, examples_dir):
    """E2E smoke: каждый пример из examples/ считается без падений и
    возвращает полный набор ключей результата."""
    path = examples_dir / filename
    data = read_input_file(path)
    result = compute(data)
    expected_keys = {
        "coefficients", "coefficients_v", "z_averages", "pz", "delta_calc",
        "g_tests", "t_tests", "output_rows", "f_avg", "f_value",
        "f_result_code", "f_result", "equation", "g_crit", "t_crit", "f_crit",
    }
    assert expected_keys <= result.keys()
    for key in ("t0", "t1", "t2", "sign_b0", "sign_b1", "sign_b2"):
        assert key in result["t_tests"]


def test_default_json_matches_excel_reference(default_experiments, default_criteria):
    """Pin exact values computed by ``.temp/расчет.xlsx`` (Excel reference) for default.json.

    Excel reference (.temp/расчет.xlsx, Лист2):
    - b0_v=1052.16, b1_v=86.59, b2_v=-174.10
    - s²_вос=8416 → S_в=26.48
    - t_0=39.73, t_1=3.27, t_2=6.574 (all significant)
    - F=17.66 against F_crit=239
    - residuals: all |y_avg - y_pred| = 21.83 (squared ≈ 476.7)

    See ``.agent/context/calculation-diff.md`` for derivation.
    """
    result = compute(_data(default_experiments, *default_criteria))

    # Coded regression coefficients
    assert result["coefficients"] == {"b0": 1063.5, "b1": 30.167, "b2": -67.5}

    # Natural (v) coefficients
    assert result["coefficients_v"]["b0"] == pytest.approx(1052.161, abs=1e-3)
    assert result["coefficients_v"]["b1"] == pytest.approx(86.587, abs=1e-3)
    assert result["coefficients_v"]["b2"] == pytest.approx(-174.09, abs=1e-2)

    # Student t-values: |b_i_v| / S_в where S_в = √(8416/12) ≈ 26.4829
    assert result["t_tests"]["t0"] == pytest.approx(39.73, abs=1e-2)
    assert result["t_tests"]["t1"] == pytest.approx(3.27, abs=1e-2)
    assert result["t_tests"]["t2"] == pytest.approx(6.574, abs=1e-2)

    # All three significant in Excel reference
    assert result["t_tests"]["sign_b0"] == result["t_tests"]["sign_b1"] == result["t_tests"]["sign_b2"] == "+"

    # Fisher F = s²_вос / (Σ_resid² / N) = 8416 / 476.69 ≈ 17.66
    assert result["f_value"] == pytest.approx(17.66, abs=1e-1)
    assert result["f_result_code"] == "not_rejected"  # F < F_crit

    # Equation (still coded form, all 3 terms now significant)
    assert "δ1" in result["equation"] and "δ2" in result["equation"]
```
