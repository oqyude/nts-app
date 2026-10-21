# Roadmap Sources — NTS Calculator

## User Requests

| # | Запрос | Источник | Приоритет | Статус |
|---|--------|----------|-----------|--------|
| UR-1 | Initialize MetaAgent | user:direct (session 2026-10-13) | P0 | ✅ done (T0) |
| UR-2 | Rewrite current architecture (tech debt) | user:direct | P0 | ✅ done (T3) |
| UR-3 | Map all variables from `Методичка.docx` §3 into code | user:direct | P0 | ✅ done (T1–T2) |
| UR-4 | Fix missing/wrong `t_0, t_1, t_2` in output | user:direct | P0 | ✅ done (T1–T2) |
| UR-5 | Verify CLI works (`python -m nts.cli --input ...`) | agent:analysis (TD-11) | P1 | ✅ done (T3) |
| UR-6 | Self-check mode: input + expected → checklist | user:direct (2026-10-16) | P0 | ✅ done (план `.omo/plans/self-check.md`) |
| UR-7 | Вынести не-жёлтые ключи в отдельный лист `extended`, сделать его optional; упрощённый режим без него | user:direct (2026-10-21) | P0 | ✅ done (T6) |
| UR-8 | По умолчанию упрощённый режим в reverse-GUI; при наличии `extended` — автоматически расширенный | user:direct (2026-10-21) | P0 | ✅ done (T6) |
| UR-9 | Человекочитаемый словарь переменных: колонка описания в Excel + вывод описаний в GUI | user:direct (2026-10-21) | P0 | ✅ done (T6) |

## FUTURE/

*(not present in repo)*

## ADR-Derived

*(no `decisions/index.json` — решения фиксируются в `.agent/context/project-state.md`)*

## Agent-Identified Improvements

| ID | Наблюдение | Задача | Статус |
|----|------------|--------|--------|
| TD-1 | GUI дублировал `_build_export_payload`, `_export_json`, `_export_xlsx`, `_apply_lang` | T3 | ✅ |
| TD-2 | `s_v = sqrt(s2_vos / 12)` — делитель Excel-референса | T1 | ✅ (откат 2026-10-13 на `√(s²/(N·m))`) |
| TD-3 | t-тест по натуральным `b_v` (Excel-референс) | T1 | ✅ (откат 2026-10-13) |
| TD-5 | `gui.py` смешивал UI/i18n/DnD/export | T3 | ✅ |
| TD-6 | i18n не выделен | T3 | ✅ |
| TD-7 | Тестов не было | T4 | ✅ (79 тестов) |
| TD-8 | Нет `__version__`, `py.typed` | T3 | ✅ |
| TD-9 | Нет dev-зависимостей | T3 | ✅ |
| TD-11 | CLI: `KeyError('equation')` | T3 | ✅ |
| TD-12 | `_export_xlsx` выпал из класса `App` — кнопка экспорта падала | T6 | ✅ |
| TD-13 | CLI падал на консоли cp1252 (`δ`, `✓`) | T6 | ✅ |
| TD-14 | Упрощённый режим тащил опциональные поля (G-тесты, поопытный вывод) | T6 | ✅ |
| TD-15 | Проверка не читает цвета — ядро определяется ключами и именем листа | T6 | ✅ (проверено экспериментом) |

## Consolidated Priority Queue

Активных задач нет — цикл T0–T6 закрыт и архивирован (`.agent/archive/`).

Кандидаты на следующий цикл (по возрастанию приоритета):

1. **JSON-режим самопроверки → упрощённый по умолчанию** (сейчас расширенный; правка в `parse_self_check_bundle`).
2. **CLI-чек-лист с описаниями** — `print_checklist(..., lang=DEFAULT_LANGUAGE)` уже поддержан, не задействован.
3. **CI/CD** — пользователь явно не просил, не трогать без запроса.
4. **`build.ps1 --lto=yes`** — только по отдельному запросу.

## Archive

- `.agent/archive/tasks/T0..T6.json` — полные описания задач.
- `.agent/archive/index.json` — индекс архива.
- `.agent/requests/archive/req-self-check-core-extended.json` — одобренный request.
