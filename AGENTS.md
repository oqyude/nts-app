# MetaAgent

Этот проект использует [MetaAgent](.agent/src/GUIDE.md) v3.0.0 —
набор инструкций для AI-агента.

## Контекст MetaAgent

| Ресурс | Путь |
|--------|------|
| Главная инструкция | `.agent/src/GUIDE.md` |
| Протоколы фаз | `.agent/src/PROTOCOLS/` |
| Команды (on-demand) | `.agent/src/COMMANDS/` |
| Шаблоны артефактов | `.agent/src/TEMPLATES/` |
| Границы (что разрешено/запрещено) | `.agent/src/BOUNDARIES.md` |
| Правила проекта | `.agent/rules/project-rules.md` |
| Пример работы | `.agent/src/WORKFLOW.md` |
| История версий | `.agent/src/CHANGELOG.md` |
| Версия | `.agent/src/VERSION` |

## Состояние сессии (если инициализировано)

| Артефакт | Путь |
|----------|------|
| Чекпоинты сессии | `.agent/checkpoints.json` |
| Слепок проекта | `.agent/context/project-state.md` |
| Анализ репозитория | `.agent/context/analysis-report.md` |
| Дорожная карта | `.agent/roadmap/sources.md` |
| Манифест задач | `.agent/tasks/manifest.json` |
| Сводка для следующего агента | `.agent/handoff-summary.md` |
| Сводка сессии | `.agent/session-summary.md` |
| Реестр результатов (pending) | `.agent/requests/active/` |
| Реестр результатов (archive) | `.agent/requests/archive/` |
| ADR | `.agent/decisions/` |

## Для агента

Жизненный цикл MetaAgent v3.0:

```
INIT → ANALYSE → ROADMAP → [DESIGN] → DECOMPOSITION → EXECUTION → METASTATE → HANDOFF
```

1. **Прочитай** `.agent/src/GUIDE.md` — пойми цикл и доступные команды.
2. **Прочитай** `.agent/src/BOUNDARIES.md` — соблюдай границы.
3. **Прочитай** `.agent/rules/project-rules.md` — выполни правила пользователя.
4. **Проверь** `.agent/checkpoints.json` — если существует, используй как состояние сессии.
5. **Проверь** `.agent/context/project-state.md` — получи актуальную картину.
6. **Проверь** `.agent/tasks/manifest.json` — если существует, выполняй задачи по порядку.
7. **Проверь** `.agent/requests/active/` — если есть незакрытые request-ы, начни с METASTATE.
8. Если `.agent/` не инициализирован или устарел — запусти `install.sh --update` (Unix) или `install.ps1 -Update` (Windows).

## Команды

В любой момент пользователь может вызвать:

- `/adr` — записать архитектурное решение (см. `.agent/src/COMMANDS/adr.md`)
- `/red-team` — попытаться сломать дизайн (см. `.agent/src/COMMANDS/red-team.md`)
- `/risk-register` — зафиксировать допущения (см. `.agent/src/COMMANDS/risk-register.md`)
- `/alt-arch` — описать альтернативу (см. `.agent/src/COMMANDS/alt-arch.md`)
- `/invariant-tests` — тесты-инварианты для ADR (см. `.agent/src/COMMANDS/invariant-tests.md`)

Команды выполняются **только по явной просьбе**. Не вызываются автоматически.
