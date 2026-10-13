# Roadmap Sources — NTS Calculator

## User Requests

| # | Запрос | Источник | Приоритет |
|---|--------|----------|-----------|
| UR-1 | Initialize MetaAgent | user:direct (this session) | **P0** (already in progress) |
| UR-2 | Rewrite current architecture (tech debt) | user:direct | **P0** |
| UR-3 | Map all variables from `Методичка.docx` §3 into code; refactor to remove confusion | user:direct | **P0** |
| UR-4 | Fix missing/wrong `t_0, t_1, t_2` in output | user:direct | **P0** |
| UR-5 | Verify CLI works (`python -m nts.cli --input ...`) — currently KeyError on `equation` | agent:analysis (TD-11) | P1 |

## FUTURE/

*(not present in repo)*

## ADR-Derived

*(no `decisions/index.json` yet — to be created in this session)*

## Agent-Identified Improvements

| ID | Наблюдение | Задача-кандидат |
|----|------------|---------------|
| TD-1 | GUI duplicates `_build_export_payload`, `_export_json`, `_export_xlsx`, `_apply_lang` | T3 — refactor gui |
| TD-2 | `s_v = sqrt(s2_vos / 12)` — wrong divisor (should be `N=4`) | T1 — math fix |
| TD-3 | `t_i = \|b_natural\| / s_v` — t-test on natural coefs; textbook says coded | T1 — math fix |
| TD-5 | `gui.py` 749 lines, mixes UI/i18n/DnD/export | T3 — refactor |
| TD-7 | No tests | T4 — add `tests/` |
| TD-8 | No `__version__`, no `py.typed` | T3 |
| TD-9 | No dev deps (`pytest`, `ruff`) in requirements | T3 |

## Consolidated Priority Queue

1. **T1** Fix math model (`t_0..t_2` on coded coefs, `s_v = √(s²_вос/N)`) — UR-2/3/4
2. **T2** Verify `t_0..t_2` present and corrected via `examples/default.json` & `new_test_variant.json` — UR-4
3. **T3** Refactor `gui.py` (remove duplicates, split i18n), wire equation formatter into shared util, fix CLI — UR-2 + TD-1/TD-5/TD-11
4. **T4** Add `tests/` for `core.compute` regression, t-tests, Grubbs, Fisher — TD-7
5. **T5** Baseline test report, METASTATE update — bookkeeping

## Archive

*(none — first roadmap cycle for this project)*
