# Handoff Summary — NTS Calculator

> Session: `38dd3237-c3d7-4ade-adc7-d81bc68ec967`
> Date: 2026-10-13
> Author: Sisyphus

## TL;DR

За одну сессию сделано: **инициализирован MetaAgent**, **исправлены 3 бага в `compute()`** (включая долгожданное появление корректных `t_0, t_1, t_2`), **вынесена i18n**, **выпилен 300-строчный дубль методов в `gui.py`**, добавлены тесты (15 шт., все зелёные), CLI починен. Методичка §3 теперь канонизирована в docstring `compute()`.

## Что сделано (по задачам)

| ID | Задача | Файлы |
|---|---|---|
| T0 | Аудит CLI (`KeyError: equation`) | `nts/cli.py` → выявлен, починен в T3 |
| T1 | Мат-фикс: t на кодированных + `s_v = √(s²_вос/N)` | `nts/core.py:332-359` |
| T2 | Верификация t0/t1/t2 в compute() и CLI | `python -m nts.cli` |
| T3 | Refactor GUI + i18n.extract + equation key | `nts/gui.py`, `nts/i18n.py`, `nts/__init__.py` |
| T4 | Тесты pytest | `tests/conftest.py`, `tests/test_core.py` |
| T5 | Baseline test report | `.agent/context/baseline-test-report.log` |

## Как проверить

```bash
cd S:/Git/nts-app

# Тесты
python -m pip install -r requirements-dev.txt
python -m pytest -q                # → 15 passed

# CLI
python -m nts.cli --input examples/default.json
# → Y = 1063.5
# → b0: t=23.185 sign=+
# → b1: t=0.658  sign=-
# → b2: t=1.472  sign=-

# GUI (Windows, .exe build отдельно)
python main.py
```

## Что осталось / требует внимания

1. **Соответствие цифрам из Методички §3, стр. 540** — есть расхождение (см. `project-state.md` → "Pending / open questions"). Если у пользователя есть пример из табл. 3.4 с конкретными y_i, можно прогнать через нашу `compute()` и сверить t_i.
2. **CI/CD** не настроен (`.github/workflows/` существует, но в этой сессии не трогался).
3. **`build.ps1` — `--lto=yes`**: информационная заметка, менять без запроса не нужно.

## Ключевые формулы — закреплено в docstring `compute()`

```
s²_вос = Σ(y_ij − ȳ_i)² / N(m−1)         # воспроизводимость, df = N(m−1)
S{b_i} = √(s²_вос / N)                    # стандартная ошибка кодированного b
t_i = |b_i_coded| / S{b_i}                # Стьюдент по **кодированным** b
F  = s²_вос / f_avg                       # Фишер df1 = N−d, df2 = N(m−1)
```

## Что НЕЛЬЗЯ делать без пересмотра формулы

- Возвращать `s_v = sqrt(s2_vos / 12)` — это в √3 раз занижает ошибку.
- Применять t-тест к натуральным `b_v` — регрессия строится по кодированным δ, и тестировать надо те b, которые в уравнении.
- Жёстко вшивать константы типа `t_cr = 2.306` — они входные параметры.

## Файлы, которых теперь нет (важно)

- В `gui.py` удалены дубликаты `_build_export_payload`, `_export_json`, `_export_xlsx`, `_apply_lang` (вторая копия в строках 599-715). Если рефакторинг когда-то вытащит, что там была нужная логика, её следует **сперва ре-импортировать из истории**, а не дописывать наугад.

## Новые требования

```bash
python -m pip install -r requirements-dev.txt   # для тестов
```

## Контекст в `.agent/`

| Файл | Назначение |
|---|---|
| `.agent/checkpoints.json` | состояние фаз (все complete) |
| `.agent/rules/project-rules.md` | правила проекта (math variable map, dev style) |
| `.agent/context/analysis-report.md` | исходный анализ + 12 тех-долгов |
| `.agent/context/project-state.md` | текущий снимок (после EXECUTION) |
| `.agent/context/baseline-test-report.log` | `pytest -q` output |
| `.agent/roadmap/sources.md` | источники задач + приоритеты |
| `.agent/tasks/manifest.json` | декомпозиция по задачам T0-T5 |
| `.agent/handoff-summary.md` | **этот файл** |
| `.agent/src/` | исходники MetaAgent (read-only с нашей стороны) |
