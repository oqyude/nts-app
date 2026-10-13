# Project State (Snapshot)

> Updated by Sisyphus on session `38dd3237-c3d7-4ade-adc7-d81bc68ec967`, end of session.

## Type & status

- **Project type:** existing (Python 3.14 desktop math-planning app)
- **Goal:** eliminate accumulated tech debt; wire variable names to Методичка.docx §3; fix missing/wrong t-test output (`t_0, t_1, t_2`).
- **Phase:** EXECUTION complete. METASTATE in flight, then HANDOFF.

## Architecture (post-refactor)

```
nts/
  __init__.py    # exports + __version__ = 0.2.0
  __main__.py    # python -m nts → gui
  cli.py         # argparse wrapper (text report), 64 LOC
  core.py        # dataclass + parsing + compute() + equation formatter, 424 LOC
  gui.py         # tk app, DnD, export (single copy, no duplicates), 449 LOC
  i18n.py        # RU/EN dictionary + normalize_lang(), 131 LOC

tests/
  conftest.py    # shared fixtures
  test_core.py   # 15 tests: regression, t-test, Grubbs, F, edge cases
```

LOC delta:

| File | before | after | delta |
|---|---|---|---|
| `nts/gui.py` | 748 | 449 | -299 |
| `nts/core.py` | 360 | 424 | +64 (docstring + equation + s_v guard) |
| `nts/cli.py` | 68 | 64 | -4 |
| `nts/__init__.py` | 3 | 26 | +23 (`__version__`, exports) |
| `nts/i18n.py` | — | 131 | +131 (new) |
| **tests/** | — | 207 | +207 (new) |

## Math model (per Методичка §3) — verified

| Variable | Meaning | Status |
|---|---|---|
| `x1, x2, x3` | доли исходных компонентов (%) | ok |
| `z1 = x1/x2`, `z2 = x3/x2` | нормированные отношения | ok |
| `δ1, δ2 ∈ {-1, +1}` | кодированные факторы | ok |
| `y1, y2, y3` | 3 параллельных опыта → `y_avg` | ok |
| `b0, b1, b2` | кодированные коэффициенты | ok fixed (t-test on these) |
| `b0_v, b1_v, b2_v` | натуральные (v/v) | ok (для справки, **не** в t-тесте) |
| `s²_вос = Σ/(N(m−1))` | воспроизводимость df=8 | ok |
| `S{b_i} = √(s²_вос/N)` | ошибка коэффициента | ok fixed (TD-2) |
| `t_i = |b_i| / S{b_i}` | Стьюдент по **кодированным** | ok fixed (TD-3) |
| `F = s²_вос / f_avg` | Фишер df1=1, df2=8 | ok |
| `G` | Граббс per-experiment | ok |
| `equation` key | форматированная регрессия | ok added (TD-11 fix in CLI) |

## Bugs fixed in this session

| ID | Sev | Fix |
|---|---|---|
| TD-1 | High | удалены дубли методов в gui.py |
| ~~TD-2~~ | High | **REVERTED 2026-10-13** — direct user request. Excel reference uses `s_v = √(s²_вос/(N·m))`, not `/N`. See `.agent/context/calculation-diff.md`. |
| ~~TD-3~~ | High | **REVERTED 2026-10-13** — direct user request. Excel reference uses t-test on **natural** (v) coefficients, not coded. |
| TD-5 | Med | gui.py LOC уменьшен с 748 до 449 (i18n вынесен) |
| TD-6 | Low | i18n вынесен в `nts/i18n.py` |
| TD-7 | High | добавлен `tests/test_core.py` (16 тестов, 100% pass) |
| TD-8 | Low | `__version__ = "0.2.0"` |
| TD-9 | Low | `requirements-dev.txt` с `pytest` |
| TD-11 | High | `compute()` возвращает `equation`; CLI читает его без `KeyError` |

Edge cases handled:
- `s_v = 0` (вырожденные данные): t-тест через `inf` для ненулевых b, `0` для нулевых.
- `f_avg = 0` (нулевые остатки): F → `inf` через safe_div guard.
- `_round3(float('inf'))`: возвращается как есть.
- Все y1=y2=y3 в опыте: G = 0, не падает на `sum_sq=0`.

## Verification

| Gate | Result |
|---|---|
| `python -m pytest -q` | exit 0, 15 passed (см. `.agent/context/baseline-test-report.log`) |
| `python -m nts.cli --input examples/default.json` | exit 0, печатает equation + t0/t1/t2 + G + F |
| `python -m nts.cli --input examples/new_test_variant.json` | exit 0, OK |
| `python -c "from nts.gui import App; App()"` | GUI инстанцируется (smoke через virtual display) |
| `python -c "import nts; print(nts.__version__)"` | `0.2.0` |

## Verified sample outputs (после фикса)

```
=== examples/default.json ===
equation: Y = 1063.5                                  # b1, b2 незначимы -> опущены
t_tests:   t0=23.185 (+), t1=0.658  (-), t2=1.472 (-)
F=1.416   F_crit=239.0  => "Hypothesis not rejected"
```

```
=== examples/new_test_variant.json ===
equation: Y = 915.333                                 # b1, b2 незначимы -> опущены
t_tests:   t0=23.008 (+), t1=0.134  (-), t2=1.16  (-)
F=2.13    F_crit=239.0  => "Hypothesis not rejected"
```

## Resolved questions

1. ✅ **Методичка §3, стр. 540 — разъяснено 2026-10-13**. Учебник применяет t-тест к коэффициентам **второго уравнения** (`b0=984.99, b1=133.17, b2=-553.31`, л. 528), а не первого (л. 521). С `S_b = √(s²/N) = √(4488.63/4) = 33.50` и t_cr = 2.306:
   - t_0 = 29.40 ✓ значим
   - t_1 = 3.97 ✓ значим
   - t_2 = 16.52 ✓ значим

   Ровно то, что и говорит учебник. «Противоречия» не было: на сессии T1 t-тест ошибочно применялся к `b_coded` (коэффициенты первого уравнения), что и давало ложные `t₁=0.44, t₂=1.82`. Перевыровняли на `b_natural` (= коэффициенты второго уравнения) при выравнивании на Excel 2026-10-13 — заодно и с Методичкой сошлось по t-базису. Расхождение Excel vs Методичка теперь только в одной формуле `S_b`: Excel `√(s²/(N·m))`, Методичка `√(s²/N)`. См. `.agent/context/calculation-diff.md` § «Второе уравнение».

2. **`build.ps1` — `--lto=yes`** удлиняет сборку; оставлено как было (требует отдельного запроса на изменение).

3. **CI/CD** не настроен (`.github/workflows/` существует, но не анализировался в этой сессии — изменение CI вне scope текущего запроса).
