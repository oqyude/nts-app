# Project State (Snapshot)

> Updated 2026-10-21 (session `38dd3237-c3d7-4ade-adc7-d81bc68ec967`, цикл T0–T6). METASTATE + HANDOFF закрыты.

## Type & status

- **Project type:** existing (Python 3.14 desktop math-planning app, Tkinter + openpyxl)
- **Goal (текущий цикл):** самопроверка (self-check) с разделением «ядро / расширенное», опциональным листом `extended` и человекочитаемым словарём переменных.
- **Phase:** все фазы MetaAgent завершены (INIT → HANDOFF), задачи T0–T6 архивированы.

## Architecture (актуальная)

```
nts/
  __init__.py     # exports + __version__ = 0.2.0
  __main__.py     # python -m nts → gui
  cli.py          # argparse: --input / --self-check / --json; UTF-8 stdout, ~110 LOC
  core.py         # dataclass + parsing + compute() + format_equation(), 424 LOC
  checker.py      # самопроверка: verify(), парсер/писатель xlsx, print_checklist(), ~1000 LOC
  dictionary.py   # описания переменных RU/EN + describe()/describe_entry(), 45 записей
  gui.py          # основной Tk-клиент, DnD, экспорт, ~590 LOC
  reverse_gui.py  # GUI самопроверки (чек-лист), режимы проверки, ~380 LOC
  i18n.py         # RU/EN словарь UI + normalize_lang(), ~190 LOC
tests/
  conftest.py     # фикстуры
  test_core.py    # 16 тестов: регрессия, t-тест, Граббс, Фишер, границы
  test_checker.py # 63 теста: DISCRETE/NUMERIC, режимы, xlsx, словарь, GUI-режимы
examples/         # входы + эталонная книга (core/extended/dictionary)
```

LOC-дельта за цикл самопроверки: `checker.py` +636, `dictionary.py` новый (206), `reverse_gui.py` +117, `gui.py` +147/−70 (дубль писателя удалён), `cli.py` +26, `i18n.py` +28.

## Формат книги самопроверки (T6)

| Лист | Обязателен | Содержимое |
|---|---|---|
| `input` | да | `idx, delta1, delta2, x1, x2, x3, y1, y2, y3` + 4 строки |
| `criteria` | да | `g_crit, t_crit, f_crit` |
| `result` | да | **ядро**: 10 ключей, вертикально `(key, value, description)`, жёлтая заливка |
| `extended` | нет | остальные 16 ключей, те же три колонки |
| `dictionary` | нет | весь словарь переменных (45 записей) |
| `grubbs` | нет | по строке на G-тест (`row, G, ok`) |
| `output_rows` | нет | по строке на `(delta1, delta2)` |

- **Ядро** = `CORE_RESULT_KEYS`: `f_value`, `coefficients.b0..b2`, `coefficients_v.b0..b2`, `t_tests.t0..t2` — ровно жёлтые ячейки эталонной книги.
- Цвет **не участвует в логике**: ядро определяется списком ключей и именем листа; заливка снимается без последствий (проверено: 54/54 при нуле заливок).
- Читатель терпит и 2-колоночный (legacy), и 3-колоночный формат; лишние листы игнорируются.

## Режимы проверки

| Режим | Когда | Что проверяется |
|---|---|---|
| `MODE_FULL` | JSON-полayload; книга с листом `extended` | все известные поля (54) — отсутствующее = провал |
| `MODE_SIMPLIFIED` | книга без `extended` | только ядро (10 полей); G-тесты и поопытный вывод пропускаются |

- `verify(actual, expected, mode=...)`; режим бандла выводится из файла (`SelfCheckBundle.mode`).
- Reverse GUI: по умолчанию упрощённый, лист `extended` переключает в расширенный автоматически; селектор «Режим» (Авто / Упрощённый / Расширенный) перекрывает.

## Словарь переменных (T6)

`nts/dictionary.py`: RU + EN описания каждой переменной (45 записей) — ключи результата, колонки `input`/`criteria`/`grubbs`/`output_rows`, контейнеры `g_tests`/`output_rows`.
Показывается в трёх местах: колонка `description` в Excel, лист `dictionary`, колонка «Описание» в чек-листе reverse-GUI, приглушённая подпись под значением в панели результата основного GUI.

## Математическая модель (Методичка §3 / `.temp/расчет.xlsx`) — без изменений

| Переменная | Смысл | Статус |
|---|---|---|
| `x1, x2, x3` | доли компонентов, % | ok |
| `z1 = x1/x2`, `z2 = x3/x2` | нормированные отношения | ok |
| `δ1, δ2 ∈ {-1, +1}` | кодированные факторы | ok |
| `y1, y2, y3` → `y_avg` | 3 параллельных опыта | ok |
| `b0, b1, b2` | кодированные коэффициенты | ok |
| `b0_v, b1_v, b2_v` | натуральные (в) | ok (t-тест по ним) |
| `s²_вос = Σ/(N(m−1))` | воспроизводимость, df=8 | ok |
| `S{b_i} = √(s²_вос/(N·m))` | ошибка коэффициента | ok (Excel-референс) |
| `t_i = \|b_i_v\| / S{b_i}` | Стьюдент по натуральным `b_v` | ok |
| `F = s²_вос / f_avg` | Фишер df1=1, df2=8 | ok |
| `G` | Граббс поопытно | ok |

Расхождение Excel ↔ Методичка остаётся в одной формуле `S_b`: Excel `√(s²/(N·m))`, Методичка `√(s²/N)`. Выбран Excel-референс (`.agent/context/calculation-diff.md`).

## Исправленные дефекты

| ID | Sev | Фикс |
|---|---|---|
| TD-1 | High | удалены дубли методов в gui.py |
| TD-5 | Med | gui.py LOC уменьшен; i18n вынесен |
| TD-6 | Low | `nts/i18n.py` |
| TD-7 | High | `tests/test_core.py` + `tests/test_checker.py` (79 тестов) |
| TD-8 | Low | `__version__ = "0.2.0"` |
| TD-9 | Low | `requirements-dev.txt` |
| TD-11 | High | `compute()` возвращает `equation`; CLI читает его |
| TD-12 | High | **экспорт XLSX в GUI был сломан**: `_export_xlsx` выпал из класса `App` (незакоммиченные правки прошлой сессии) → `AttributeError`. Метод возвращён в класс, экспорт делегирует `nts.checker.write_self_check_xlsx` (−70 строк дубля) |
| TD-13 | High | **CLI падал с `UnicodeEncodeError` на консоли cp1252** (`δ`, `✓`) — stdout/stderr переводятся в UTF-8 (`_force_utf8_output`) |
| TD-14 | Med | `verify()` в упрощённом режиме больше не требует опциональных полей (G-тесты, поопытный вывод пропускаются) |

## Верификация (2026-10-21)

| Проверка | Результат |
|---|---|
| `python -m pytest -q` | exit 0, **79 passed** (`.agent/context/baseline-test-report.log`) |
| `python -m nts.cli --input examples/default_result.xlsx --self-check` | 54 passed, exit 0 (полный режим) |
| `python -m nts.cli --input examples/default_result_core.xlsx --self-check` | 10 passed, exit 0 (упрощённый режим) |
| `python -m nts.cli --input examples/default_with_expected.json --self-check` | 54 passed, exit 0 |
| `python -m nts.cli --input examples/default.json` | байт-в-байт как baseline (тест `test_cli_default_input_path_byte_identical`) |
| GUI: панель результата (RU/EN) | описания под каждым значением, смоук-прогон |
| GUI: кнопка «Export XLSX» | файл на 7 листов → самопроверка 54/54 |
| reverse GUI (смоук) | 10 строк / 54 строки / принудит. 10; описания RU/EN; селектор режима |
| Книга без единой заливки | 54 passed — цвет не влияет на логику |

## Открытые вопросы

1. **JSON-режим** оставлен расширенным (`expected` — полный payload). Если нужен упрощённый по умолчанию — правится в `parse_self_check_bundle`.
2. **CLI-чек-лист** печатает «голые» ключи; описания только в GUI и Excel. Добавление — параметр `lang` у `print_checklist` (уже есть).
3. **`build.ps1` — `--lto=yes`** удлиняет сборку; не менялось (вне scope).
4. **CI/CD** не настроен (вне scope, пользователь его не просил).
5. **`.metaagent-director/`** — служебный артефакт оркестратора, не коммитится.
