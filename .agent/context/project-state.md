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
| TD-2 | High | `s_v = √(s2_vos/N)` вместо `/12` |
| TD-3 | High | t-тест по **кодированным** b, не по натуральным |
| TD-5 | Med | gui.py LOC уменьшен с 748 до 449 (i18n вынесен) |
| TD-6 | Low | i18n вынесен в `nts/i18n.py` |
| TD-7 | High | добавлен `tests/test_core.py` (15 тестов, 100% pass) |
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

## Pending / open questions

1. **Методичка §3, стр. 540** утверждает, что для её синтетического примера все 3 b значимы (`b0=920.90, b1=14.65, b2=-60.87; s²_вос=4488.63; t_cr=2.306`). При стандартной формуле `S{b}=√(s²_вос/N)` получается `t1=0.44, t2=1.82` — **не значимы**. Цифры из методички противоречивы. Возможные объяснения:
   - (а) данные примера выдуманы/неточны, формула в учебнике верна → наш фикс корректен;
   - (б) в учебнике подразумевается другой вариант формулы (например, с поправкой на df или с иной нормировкой) → нужен уточнённый источник.
   - **Запрос пользователю:** если есть пример из табл. 3.4 с конкретными y_i, прогнать через `compute()` и сверить t_i.

2. **`build.ps1` — `--lto=yes`** удлиняет сборку; оставлено как было (требует отдельного запроса на изменение).

3. **CI/CD** не настроен (`.github/workflows/` существует, но не анализировался в этой сессии — изменение CI вне scope текущего запроса).
