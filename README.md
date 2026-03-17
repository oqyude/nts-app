# NTS Excel Calculator

This project reproduces the Excel calculations in pure Python, without any Excel dependency.

## Setup

No third-party dependencies are required for normal run.

Optional for drag & drop:

```bash
python -m pip install tkinterdnd2
```

## Run

```bash
python main.py
```

You can also run as a module:

```bash
python -m nts
```

## JSON Input Format

```json
{
  "experiments": [
    {
      "idx": 1,
      "delta1": -1,
      "delta2": -1,
      "x1": 43.75,
      "x2": 43.75,
      "x3": 12.5,
      "y1": 1167,
      "y2": 1238,
      "y3": 963
    }
  ],
  "g_crit": 0.7679,
  "t_crit": 2.306,
  "f_crit": 239
}
```

## Build .exe (Nuitka)

Build on Windows 10 x64 for best compatibility. The build is architecture-specific.

```bash
build.ps1
```

```bat
build.bat
```

The executable will be in `release/nts-app.exe`.

### Optional size reduction (UPX)

If you have UPX installed, you can set `NTS_USE_UPX=1` to compress the exe. This can reduce size but may trigger antivirus false positives on some systems.

```bash
set NTS_USE_UPX=1
build.bat
```

```powershell
$env:NTS_USE_UPX = "1"
./build.ps1
```
