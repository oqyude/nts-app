"""NTS Calculator build orchestrator.

Builds the NTS GUI app as a single Windows executable using Nuitka + MSVC.

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
    python build.py             # full build (vcvars -> venv -> deps -> tests -> nuitka)
    python build.py --skip-tests    # skip the pytest sanity pass
    python build.py --compiler=clang-cl   # override default MSVC with clang-cl
    python build.py --python C:/.../python.exe   # build with a different Python
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent
VENV_DIR = REPO_ROOT / ".venv-build"
RELEASE_DIR = REPO_ROOT / "release"

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


def nuitka_build(py: Path, msvc_version: str, extra_env: dict[str, str], assume_yes: bool) -> None:
    RELEASE_DIR.mkdir(exist_ok=True)
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
        "--product-name=NTS Calculator",
        "--file-version=0.2.1",
        "--copyright=Built with Nuitka",
        f"--output-dir={RELEASE_DIR}",
        "--output-filename=nts-app.exe",
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
    cmd.append(str(REPO_ROOT / "main.py"))
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

    print(f"[5/5] nuitka onefile (MSVC {args.msvc_version})")
    nuitka_build(py, args.msvc_version, msvc_env, args.assume_yes)

    exe = RELEASE_DIR / "nts-app.exe"
    if exe.exists():
        print(f"[OK] {exe} ({exe.stat().st_size:,} bytes)")
        return 0
    print("[X] nts-app.exe not produced")
    return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
