# Project Rules — NTS Calculator

Read before every phase. Project-specific rules override protocol defaults.

## Mandatory rules

1. **Math variable names MUST match Excel reference `.temp/расчет.xlsx` (not Методичка §3).**
   - Inputs: `x1, x2, x3` — component shares (% water, binder, filler), `x1 + x2 + x3 = 100%`.
   - Normalized ratios: `z1 = x1 / x2`, `z2 = x3 / x2`.
   - Coded factors: `δ1, δ2 ∈ {-1, +1}` (no δ0 — 2² design, N=4).
   - Responses: `y1, y2, y3` (3 parallel trials per experiment), averaged to `y_avg = ȳ`.
   - Regression equation display: `Y = b0 + b1·δ1 + b2·δ2` (coded form), but `b_i` shown here = the **coded** coefficient.
   - Reproducibility variance: `s²_вос = Σ(y_ij − ȳ_i)² / N(m−1)`, df = `N(m−1) = 8` for N=4, m=3.
   - Standard error of regression coefficient: **`S_в = √(s²_вос / (N·m))`** — divisor uses N·m (Excel convention).
     Mathematical derivation: each `b_i` is an average over N design points, where each y_avg is itself a mean of m replicates; so Var(b_i) = s²/m / N = s² / (N·m).
   - Student criterion on **natural (v) coefficients**: `t_i = |b_i_v| / S_в`. `t_cr = 2.306` is input-driven (default.json), not hard-coded.
   - Fisher criterion (Excel reference): `F = s²_вос / (Σ_resid² / N)`. Compared against input `F_cr = 239`.
   - Grubbs: per-experiment outlier test, df1 = `m−1 = 2`, df2 = `N = 4`.

   > Historical note: prior session fixed math to align with Методичка.docx §3 (`s_v = √(s²/N)`, t on coded b's). User explicitly requested alignment with `.temp/расчет.xlsx` instead — that takes precedence. Full diff in `.agent/context/calculation-diff.md`.

2. **Code must remain import-clean.** Never suppress type errors (`as any`, `@ts-ignore`). For Python: no `from typing import Any` when actual types are knowable; no bare `except:`.

3. **GUI/IO must not duplicate logic.** No two methods doing the same job in the same class.

4. **Internationalization stays in `i18n/` (when split).** No UI strings hardcoded inline.

## Prohibited

- Hard-coding constants (e.g., `t_cr = 2.306`, `g_crit = 0.7679`, `f_crit = 239`) as literals in test fixtures or examples — read from the input file or pass as arguments.
- Adding CI/CD or workflow changes.
- Deleting the `examples/` and `.temp/` directories or their contents.

## Conventions

- Python version: 3.14 (per existing `__pycache__` artifacts).
- Indentation: 4 spaces; PEP 8; type hints everywhere in `core.py`.
- Naming: `snake_case` for functions/variables, `PascalCase` for classes/dataclasses, UPPER_SNAKE for module-level constants.
- Output value rounding: `_round3()` for 3 decimals — same precision as textbook examples.
- Tests: `pytest`, located in `tests/`, file naming `test_*.py`.

## Verification gates

- `python -m pytest -q` returns exit code 0 before any request is filed.
- `python main.py` opens GUI without traceback.
- `python -m nts --help` prints CLI help.
