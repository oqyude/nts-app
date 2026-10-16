# Отчёт: `previous` → `dev`

Сравнение веток репозитория `nts-app`. Точка расхождения — сам `previous`
(тег `v0.0.5`, SHA `7cd016b`); merge-base с `dev` совпадает с `previous`,
поэтому всё, что перечислено ниже, — это целиком новые изменения в `dev`.

| | |
|---|---|
| `previous` | `7cd016b` (tag `v0.0.5`, "workflow changes") |
| `dev` | `146ba1a` ("Align math with .temp/расчет.xlsx; bundle full tkdnd/ tree; show t_0/t_1/t_2") |
| Диапазон | `previous..dev` — **3 коммита вперёд, 0 откатов** |
| Статистика | **58 файлов, +5486 / −610 строк** |

---

## 1. Коммиты (от старого к новому)

| SHA | Сообщение |
|---|---|
| `2889d91` | Finalize MetaAgent session (T0-T5): math fixes, GUI refactor, tests, handoff |
| `a666cb5` | .gitignore update |
| `146ba1a` | Align math with .temp/расчет.xlsx; bundle full tkdnd/ tree; show t_0/t_1/t_2 |

---

## 2. Математика: `nts/core.py`, `nts/cli.py`, `nts/gui.py`, `nts/i18n.py`

### Шаг 1 — `2889d91` (Методичка §3, "первая правка")

- t-тест по **кодированным** `b_i`, формула дисперсии `S{b} = √(s²_вос / N)`.
- `compute()` теперь возвращает ключ `equation` — собранное уравнение регрессии.
- Введён `InputData` (dataclass), типизированный контракт `ComputeResult` (TypedDict),
  сигнатуры плана `DELTA1/DELTA2`, `EXPECTED_EXPERIMENTS=4`, `PARALLEL_TRIALS=3`.

### Шаг 2 — `146ba1a` (откат к Excel-референсу, по явной просьбе)

- `S_в = √(s²_вос / (N·m))` — добавили `m=3` (параллельные опыты).
- t-тест теперь по **натуральным** `b_i_v`, а не по кодированным.
- F-тест: `F = s²_вос / (Σ_resid² / N)`.
- Подписи строк: `t_0/t_1/t_2` вместо `b0/b1/b2` (стиль Методички в `nts/i18n.py`).
  Форма самих значений в CLI/GUI не поменялась.

> **Результат на `examples/default.json`:**
> - после `2889d91`: `Y=1063.5, t_0=23.185(+), t_1=0.658(−), t_2=1.472(−), F=1.416`
> - после `146ba1a`: `t_0=39.73, t_1=3.27, t_2=6.574, F=17.655` — все три `b` проходят `t_crit`.

Полный side-by-side Методичка vs Excel и рецепт отката — в
`.agent/context/calculation-diff.md`.

---

## 3. GUI-рефакторинг

| Файл | Изменение |
|---|---|
| `nts/gui.py` | **−614 / +...** строк: вырезана i18n-логика, методы используют единый источник |
| `nts/i18n.py` | **новый**, 123 строки — все словари переводов вынесены сюда |

Поведение не сломано: `python main.py` поднимает GUI без traceback (smoke-тест TD-8).

---

## 4. Сборка: `build.py`, `build.bat`, `build.ps1`

- **`build.py` — новый, 227 строк.** Бандлит всё дерево `tkinterdnd2/tkdnd/`
  (раньше тащился только `win-x64-tcl9 .dll`), плюс форсит `force-include` всех
  shared libs (`.dll/.so/.dylib`), которые плагин Nuitka пропускает.
  Чинит тихий краш на старте при Tcl 9 (Python 3.13+).
- `build.bat`, `build.ps1` — подровнены под `build.py`.
- `requirements-build.txt`, `requirements-dev.txt` — добавлены зависимости.

---

## 5. Тесты (новые)

- `tests/conftest.py` — 50 строк, фикстуры.
- `tests/test_core.py` — **16 pytest-кейсов, все зелёные**, в т.ч. pinning-тест
  на точные Excel-значения для `default.json` (`b_v`, `S_в`, `t_i`, `F`).

---

## 6. Версия и CLI

- `nts/__init__.py`: `__version__ = 0.2.0`.
- `nts/cli.py`: читает ключ `equation` из `compute()` — больше нет `KeyError`
  на `examples/default.json`.

---

## 7. MetaAgent-инфраструктура (полностью новая)

Онбординг MetaAgent v3.0.0 как системы ведения проекта.

- **Корень:** `AGENTS.md`.
- **Документы:** `.agent/src/GUIDE.md`, `VERSION`, `CHANGELOG.md`,
  `WORKFLOW.md`, `BOUNDARIES.md`.
- **Протоколы фаз:** `PROTOCOLS/00_INIT.md … 07_HANDOFF.md`.
- **Команды:** `COMMANDS/adr.md`, `red-team.md`, `risk-register.md`,
  `alt-arch.md`, `invariant-tests.md`.
- **Шаблоны:** `TEMPLATES/` + `TEMPLATES/schemas/` (JSON-схемы).
- **Установщики:** `install.sh`, `install.ps1` (`--update` / `-Update`).
- **Артефакты сессии:** `tasks/manifest.json` (T0–T5 = `completed`),
  `context/project-state.md`, `context/analysis-report.md`,
  `context/calculation-diff.md` (новый, 209 строк — side-by-side Методичка vs Excel),
  `checkpoints.json`, `handoff-summary.md`, `session-summary.md`,
  `rules/project-rules.md`, `roadmap/sources.md`.

---

## 8. Прочее

- `.gitignore` — исключён `.temp/` (там лежит `расчет.xlsx`).
- Удаленных файлов нет — все правки это добавления и модификации.

---

## TL;DR

`dev` поверх `previous` (v0.0.5) — это:

1. **Пересбор ядра** (`core.py` +440/−... строк, типизированный контракт `ComputeResult`).
2. **Вынос i18n** из GUI в отдельный модуль.
3. **Тесты:** 16 pytest-кейсов, все зелёные.
4. **Новый Python-билд-скрипт** под Nuitka/Tcl 9 (фикс тихого краша на старте).
5. **MetaAgent v3.0.0** как система ведения проекта (протоколы, шаблоны, ADR-команды).

Математика в финале (`146ba1a`) сознательно приведена к **Excel-референсу** и
отличается от Методички §3 — откат документирован в
`.agent/context/calculation-diff.md`.

---

## 9. Reverse-вариант: `nts-app-reverse.exe`

После `b4299b1` добавлена вторая сборка — **reverse (self-check) GUI**.
Назначение: загрузить self-check JSON (`{ "input": …, "expected": … }`) и
получить цветной чек-лист ✓/✗ по всем полям `ComputeResult`, который
строит `nts.checker.verify`.

**Изменения (5 файлов, +413/−5 строк):**

| Файл | Что |
|---|---|
| `nts/reverse_gui.py` (новый) | `ReverseApp` на базе `TkinterDnD` — без ввода экспериментов руками; только Browse/Reload/Clear/Run/Export + Treeview с тегами `passed`/`failed` (зелёный/красный) + экспорт отчёта в txt. |
| `main_reverse.py` (новый) | Entry-point `from nts.reverse_gui import main`. |
| `nts/i18n.py` | +20 ключей на двух языках (`reverse_title_main`, `reverse_col_*`, `reverse_summary_*`, и т.д.). |
| `build.py` | Словарь `VARIANTS` + флаг `--variant {app, reverse}`; `nuitka_build` параметризован по `entry`/`output`/`product_name`. |
| `build.ps1` / `build.bat` | Пробрасывают `-Variant` / `/VARIANT` в `build.py`. |

**Сборка:**

```bash
build.ps1 -Variant reverse        # → release/nts-app-reverse.exe
build.bat /VARIANT reverse        # cmd-эквивалент
python build.py --variant reverse # прямой Python
```

**Отличия GUI от основного `nts-app`:**

- нет ручного ввода 4 опытов × 9 полей — источник данных только файл;
- результат рендерится **сразу** после загрузки как табличный чек-лист
  (Field / Actual / Expected / Diff / Note), цветные ✓/✗;
- кнопки: `Load self-check JSON`, `Reload`, `Clear`, `Run check`, `Export report`;
- заголовок окна: `NTS Reverse (self-check)` (RU: `НТС Реверс (самопроверка)`).

Поведенческий smoke-test на `examples/default_with_expected.json` (54 чек-а,
все passed) пройден: Tk-окно поднимается, Treeview заполняется, summary
обновляется, переключение языка переводит headings и summary без потери
данных строк. Тесты pytest (47) — зелёные.
