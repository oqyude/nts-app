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

## Self-check mode

Verify a hand-calculated NTS solution against the canonical Python computation.

The input JSON must contain both the experiment data and the expected output values:

```json
{
  "input": { ...experiments + g_crit/t_crit/f_crit... },
  "expected": { ...a ComputeResult-shaped dict... }
}
```

Run:

```bash
python -m nts.cli --self-check path/to/self_check.json
```

Each computed field is compared with `expected` using per-category tolerances
(1e-3 for coefficients, 1e-2 for t-values, 1e-1 for F-value). The checklist shows
`✓` for matching fields and `✗` for mismatches, plus the actual difference.
Exit code: `0` when all match, `1` when any field mismatches, `2` when the input
file is missing or malformed.

Capture the `expected` block from a real run — `--json` writes the computed
result on its own, so the self-check file is assembled from two pieces:

```bash
# 1) посчитать эталон (обычный режим отчёта + JSON результата)
python -m nts.cli --input your_input.json --json result.json

# 2) собрать self-check-файл: {"input": <вход>, "expected": <результат>}
python -c "import json; json.dump({'input': json.load(open('your_input.json')), 'expected': json.load(open('result.json'))}, open('self_check.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)"

# 3) проверить
python -m nts.cli --self-check self_check.json
```

The `--json` file alone is **not** a self-check file: `--self-check` expects
the two blocks (`input` and `expected`) at the top level. See
`examples/default_with_expected.json` for a working demo.

### Workbook layout (`.xlsx`)

A self-check workbook is made of these sheets:

| Sheet | Required | Contents |
|---|---|---|
| `input` | yes | experiments table: `idx, delta1, delta2, x1, x2, x3, y1, y2, y3` |
| `criteria` | yes | `g_crit, t_crit, f_crit` |
| `result` | yes | **core** result keys, vertical `(key, value, description)`, yellow-marked |
| `extended` | no | the remaining result keys, same three columns |
| `grubbs` | no | one row per G-test (`row, G, ok`) |
| `output_rows` | no | one row per `(delta1, delta2)` experiment |
| `dictionary` | no | every variable of the workbook with its description |

The **core** set is the yellow-marked set of `examples/default_result.xlsx`:
`f_value`, `coefficients.b0..b2`, `coefficients_v.b0..b2` and `t_tests.t0..t2` —
the regression coefficients and the Student t-values.

The `extended` sheet is **optional** and decides the verification mode:

- **without** it — *simplified mode*: only the core fields are compared and
  reported (`examples/default_result_core.xlsx`, 10 checks);
- **with** it — *extended mode*: the workbook declares full coverage, so every
  field the verifier knows about must be present and must match (54 checks).

Both modes exit `0` when everything checked matches. The writer
(`nts.checker.write_self_check_xlsx`, also used by the GUI's *Export to
Excel*) emits the core/extended split and marks the core cells yellow.

### Variable descriptions

The machine keys stay stable, but every key has a human meaning. The
`description` column of the `result` / `extended` sheets carries it
(RU by default, EN on request: `write_self_check_xlsx(..., lang="EN")`), and
the reverse GUI shows it in a *Description* column next to the field name.

The dictionary itself lives in `nts/dictionary.py` — one table per language,
covering the result keys, the input columns and the G-test / output-row
columns. The workbook also carries a `dictionary` sheet listing all of them.

### Reverse GUI (self-check)

`python main_reverse.py` (or the *Reverse* variant) opens the self-check GUI.
It verifies in the **simplified** mode by default and switches to the
**extended** mode automatically when the loaded workbook carries an `extended`
sheet. The *Mode* selector overrides this: *Auto (by file)*, *Simplified
(main fields)*, *Extended (all fields)*. The current mode is shown next to the
summary line.

JSON payloads always carry a complete `expected` block, so they are verified
in the extended mode.

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

Two variants are supported:

| Variant | Entry point | Output |
|---|---|---|
| `app` (default) | `main.py` | `release/nts-app.exe` |
| `reverse` | `main_reverse.py` | `release/nts-app-reverse.exe` |

The `reverse` variant is the self-check GUI: load a self-check JSON (with both
`input` and `expected` blocks) and get a colour-coded ✓/✗ checklist of every
field produced by `compute()`.

```bash
build.ps1                     # full build, nts-app.exe
build.ps1 -Variant reverse    # full build, nts-app-reverse.exe
build.bat /VARIANT reverse    # cmd equivalent
```

The executable will be in `release/nts-app.exe` (or `nts-app-reverse.exe`).

Note: If the target machine is missing VC++ runtime, Windows may ask to install it.
