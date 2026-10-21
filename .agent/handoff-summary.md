# Handoff Summary — NTS Calculator

## Session Summary

**Session:** `38dd3237-c3d7-4ade-adc7-d81bc68ec967`
**Goal:** самопроверка (self-check) с разделением «ядро / расширенное», опциональным листом `extended` и человекочитаемым словарём переменных.
**Completed:** 7 задач (T0–T6), все архивированы
**Pending:** 0
**Approved requests:** `req-self-check-core-extended` → `.agent/requests/archive/`

## Project State

Python 3.14 / Tkinter приложение для расчёта НТС (Методичка §3 + Excel-референс `.temp/расчет.xlsx`).

```
nts/ core.py (вычисления)  checker.py (самопроверка)  dictionary.py (описания переменных)
     gui.py (основной клиент)  reverse_gui.py (чек-лист)  cli.py  i18n.py
tests/ test_core.py (16)  test_checker.py (63) → 79 passed
```

Ключевые решения текущего состояния:

- **Ядро проверки** — 10 ключей (`f_value`, `coefficients.b0..b2`, `coefficients_v.b0..b2`, `t_tests.t0..t2`), они лежат на листе `result` (жёлтая заливка — только метка).
- **`extended`** — опциональный лист с остальными 16 ключами; его наличие переводит проверку в расширенный режим (54 поля), отсутствие — в упрощённый (только 10 основных).
- **Цвет в логике не участвует**: ни одна строка кода не читает заливку; эксперимент «снять все 10 заливок» → 54/54 без изменений.
- **Словарь** (`nts/dictionary.py`, RU/EN, 45 записей) → колонка `description` в Excel, лист `dictionary`, колонка «Описание» в reverse-GUI, приглушённая подпись под значением в основном GUI.

## Что сделано за цикл самопроверки (T6)

| Что | Где |
|---|---|
| Разделение `result`/`extended` + жёлтое ядро | `nts/checker.py` (`CORE_RESULT_KEYS`, `write_self_check_xlsx`) |
| Опциональный `extended` + слияние в expected | `nts/checker.py` (`_load_xlsx_bundle`, `_merge_expected`) |
| Режимы `MODE_SIMPLIFIED` / `MODE_FULL` | `nts/checker.py` (`verify`, `_select_core_expected`) |
| Упрощённый режим + авто-переключение + селектор режима | `nts/reverse_gui.py` |
| Словарь описаний | `nts/dictionary.py` (новый) |
| Описания в панели результата основного GUI | `nts/gui.py` (`_place_value`, `CAPTION_COLOR`) |
| Экспорт XLSX: единый писатель, метод вернулся в класс | `nts/gui.py` → `nts.checker.write_self_check_xlsx` |
| UTF-8 stdout/stderr в CLI | `nts/cli.py` (`_force_utf8_output`) |

## Next Steps

Активных задач нет. Если продолжить — кандидаты из `.agent/roadmap/sources.md`:
1. JSON-режим самопроверки → упрощённый по умолчанию.
2. CLI-чек-лист с описаниями (`print_checklist(lang=...)` уже умеет).
3. CI/CD и `build.ps1 --lto=yes` — только по явному запросу.

## Как проверить

```bash
cd S:/Git/nts-app
python -m pytest -q                                   # → 79 passed

python -m nts.cli --input examples/default_result.xlsx --self-check       # → 54 passed (расширенный)
python -m nts.cli --input examples/default_result_core.xlsx --self-check  # → 10 passed (упрощённый)
python -m nts.cli --input examples/default_with_expected.json --self-check # → 54 passed (JSON)

python main.py            # основной GUI (описания под значениями)
python main_reverse.py    # reverse GUI (режимы + колонка «Описание»)
```

## Key Artifacts

| Файл | Назначение |
|---|---|
| `.agent/context/project-state.md` | актуальный слепок проекта |
| `.agent/tasks/manifest.json` | манифест (все задачи archived) |
| `.agent/archive/tasks/T0..T6.json` | полные описания задач |
| `.agent/archive/index.json` | индекс архива |
| `.agent/requests/archive/req-self-check-core-extended.json` | одобренный request |
| `.agent/roadmap/sources.md` | источники задач и кандидаты следующего цикла |
| `.agent/context/baseline-test-report.log` | `pytest -q` output (79 passed) |
| `.agent/context/calculation-diff.md` | Excel ↔ Методичка §3 расхождения по формулам |
| `examples/default_result.xlsx` | эталонная книга (ядро + extended + dictionary) |
| `examples/default_result_core.xlsx` | тот же эталон без `extended` (упрощённый режим) |

## Что НЕЛЬЗЯ делать без пересмотра формулы

- Возвращать `s_v = sqrt(s2_vos / 12)` — в Excel-референсе `√(s²/(N·m))`.
- Применять t-тест к кодированным `b` — по Excel-референсу t-тест идёт по натуральным `b_v`.
- Хардкодить `t_cr = 2.306` / `F_crit = 239` / `G_crit = 0.7679` — это входные параметры.
- Менять CI/CD — пользователь явно не просил.

## Незакоммиченное

Дерево было грязным до начала сессии (правки прошлых сессий по self-check). Всё это вошло в коммит `dev` вместе с текущей работой. Служебный каталог `.metaagent-director/` (артефакт оркестратора) намеренно не коммитится.
