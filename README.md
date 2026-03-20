# NTS Excel Calculator

This project reproduces the Excel calculations in pure Python, without any Excel dependency.

## Setup

For JSON input only, no third-party dependencies are required.

For Excel import (.xlsx/.xlsm):

```bash
python -m pip install openpyxl
```

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

## Excel Input Format

The workbook should contain:

- Sheet `experiments` (or the first sheet) with a header row and columns:
  `idx`, `delta1`, `delta2`, `x1`, `x2`, `x3`, `y1`, `y2`, `y3`
- Sheet `criteria` (or `crit`) with a header row:
  `g_crit`, `t_crit`, `f_crit` and values on the next row

If the criteria sheet is missing, the loader also looks for key/value pairs in the
first two columns of the `experiments` sheet using labels `g_crit`, `t_crit`, `f_crit`.

See the sample file: `sample_input.xlsx`.

## Build .exe (Nuitka)

Build on Windows 10 x64 for best compatibility. The build is architecture-specific.

```bash
build.ps1
```

```bat
build.bat
```

The executable will be in `release/nts-app.exe`.

Note: If the target machine is missing VC++ runtime, Windows may ask to install it.
