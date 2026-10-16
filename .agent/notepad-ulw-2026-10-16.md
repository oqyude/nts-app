# Ultrawork Notepad — NTS Self-Check Version

Started: 2026-10-16T...Z
Session: 38dd3237-c3d7-4ade-adc7-d81bc68ec967
Goal: добавить self-check / verification mode в NTS Calculator, который
принимает на вход И входные данные, И ожидаемые результаты, и выводит
чек-лист ✓/✗ совпадений. Долгоживущая ветка → отдельный репозиторий.

## Stop condition (binding)
Я останавливаюсь ровно когда:
- `nts/checker.py` создан и покрыт тестами (RED→GREEN зафиксирован)
- `python -m nts.cli --check path.json` работает и печатает чек-лист
- Все 3+ сценария из раздела "Scenarios" дают PASS с двумя evidence
  (test output + real CLI stdout)
- Изменения закоммичены в feature-ветку, main не тронут

## Plan (после explore)
- C1 `nts/checker.py` — `verify(actual, expected, tolerance) -> CheckResult` + `print_checklist()`
- C2 `nts/cli.py` + `nts/i18n.py` — `--self-check` flag + 5 новых i18n ключей
- C3 `examples/default_with_expected.json` + README секция
- Core `nts/core.py:compute()` НЕ трогаем
- Per-category tolerance: 1e-3/1e-2/1e-1 (mirrors `tests/test_core.py:181-194`)
- Unicode ✓/✗ by default (reuses existing `status_ok`/`status_bad` i18n)
- Exit 0=pass / 1=fail / 2=bad input

## Scenarios (the contract)
1. Happy: `python -m nts.cli --self-check examples/default_with_expected.json` → all ✓, exit 0
2. Tolerance boundary: 0.001 deviation → ✓
3. Mismatch: 1.0 deviation → ✗ with diff
4. `f_value=inf` handling: both inf → ✓
5. Row-mismatch in `g_tests` (different `Experiment.idx` order) → still ✓ if data matches
6. Regression: `python -m nts.cli --input examples/default.json` без `--self-check` работает как раньше, exit 0
7. Bad schema: missing `expected` block → exit 2, понятное сообщение

## Now
- Plan полностью написан и reviewed (оба ревьюера approved / non-blocking fix applied)
- Жду решения пользователя: запускать ли worker-сессию или подождать
- Branch `feat/self-check` готова

## Todo
- [x] Создать ветку feat/self-check от main
- [x] Загрузить /ulw-plan
- [x] Plan agent interview → draft brief
- [x] User approval ("ok")
- [x] Записать plan в .omo/plans/self-check.md
- [x] Metis gap analysis (67 issues, critical ones incorporated)
- [x] Dual high-accuracy review (Momus APPROVED, Oracle CHANGES_REQUESTED → fix applied → ready)
- [ ] Worker session executes plan (ждём "go" от пользователя)
- [ ] Verify all 7 scenarios + 4 F-tasks
- [ ] Commit per task (10 implementation commits)

## Review verdict
- **Momus r2**: APPROVED. "Plan is executable, references are valid, blocker properly fixed."
- **Oracle r2**: CHANGES_REQUESTED → 1 minor (TL;DR line 14 inconsistent with lines 42/137/144). **Fix applied**: line 14 now says "`g_tests` matched by its `row` key, and `output_rows` matched by `(delta1, delta2)` tuple" — matches the detailed work. Oracle's note "non-blocking, optional polish" → resolved.
- **Final SHA-256**: `3957f72e59b27136dd0c18e6d7e365e362c8bd5065d06ffae847a358662ec8d5` (post line-14 fix)

## Findings

### Codebase (from project-state.md + handoff)
- nts/core.py:compute() — единственный источник истины. Ключи result:
  b0/b1/b2, t_tests{b0,b1,b2}, F, F_crit, G[], equation. 424 LOC.
- examples/default.json: Y=1063.5, t0=23.185, F=1.416 — можно
  использовать как regression test expected values.
- main branch HEAD: 315a926 (REPORT), parent a666cb5 (gitignore),
  2889d91 (MetaAgent finalization).
- Active branch: feat/self-check (off main).
- examples/ имеет default.json, new_test_variant.json, sample_input.xlsx.
- tests/: conftest.py + test_core.py (8982 bytes).

### Project rules (project-rules.md)
- Math выравнивать по `.temp/расчет.xlsx` (не Методичке).
- t-test на натуральных (v) коэффициентах: `t_i = |b_i_v| / S_в`.
- S_в = √(s²_вос / (N·m)).
- Code style: type hints, snake_case, 4-space, PEP 8, Python 3.14.
- Запрещено: type suppression, hard-coding constants in tests,
  CI/CD, удаление examples/ или .temp/.

### BOUNDARIES (MetaAgent v3)
- "Менять CI/CD — запрещено" (пользователь явно сказал: CI/CD не нужно).
- "Создавать production-код — в фазе EXECUTION, по задачам из manifest.json".
  → нужен новый манифест для self-check работ.
- "Делать коммиты — по завершении задачи, перед созданием request".
- "Обязательно создавать request в .agent/requests/active/" после задачи.

## Learnings
- Per ULTRAWORK: test-first (RED→GREEN), затем SURFACE (real CLI).
- Per ulw-plan: я — Prometheus, не имплементирую. Только план в .omo/.
  Исполнение — отдельный worker через $start-work (или когда user скажет "go").
- Default compat: гибрид (core nts.compute() не трогаем; новые
  обёртки в nts/checker.py + новый --check флаг).
