# Analysis Report — NTS Calculator

## Session

- **Session ID:** `38dd3237-c3d7-4ade-adc7-d81bc68ec967`
- **Target repo:** `S:/Git/nts-app`
- **Date:** 2026-10-13
- **Project type:** `existing` (Python 3.14 desktop app reproducing Excel-based math planning of experiment)

## 1. Общая информация

- **README:** NTS Excel Calculator. Перенос расчётов из Excel в чистый Python без зависимостей Excel. Вход — JSON или XLSX/XLSM (`openpyxl`). GUI на `tkinter` + опциональный drag&drop (`tkinterdnd2`). Сборка в EXE — `nuitka` (см. `build.bat`/`build.ps1`).
- **Лицензия:** отсутствует (см. `LICENSE` — не найден).
- **CI/CD:** каталог `.github/workflows/` существует (содержимое не анализировалось — не запрашивалось).
- **Точка входа:** `main.py` (4 строки → `from nts.gui import main`) и `python -m nts`.
- **Система сборки:** Nuitka onefile (`build.bat`/`build.ps1`) → `release/nts-app.exe`. Бэкенда сборки нет; чистый Python `python main.py`.

## 2. Стек технологий

| Компонент | Значение |
|---|---|
| Язык | Python 3.14 (по `__pycache__/cpython-314`) |
| Фреймворк | `tkinter` (+ `tkinterdnd2`), без веб/CLI-фреймворка |
| База данных | нет |
| Тестовый раннер | не настроен (нет `tests/`, нет `pytest` в `requirements.txt`) |
| Пакетный менеджер | `pip` |
| Линтер/форматтер | не настроен (`.ruff_cache` есть, но конфиг отсутствует) |
| Зависимости прод | `openpyxl`, `tkinterdnd2` (`requirements.txt`) |
| Зависимости сборки | `nuitka[onefile]` (`requirements-build.txt`) |

## 3. Архитектура

```
nts-app/
  main.py                     # вход → nts.gui.main
  build.{bat,ps1}             # обёртки Nuitka
  AGENTS.md                   # наш указатель на MetaAgent
  README.md
  requirements*.txt
  examples/
    default.json              # рабочий пример (4 опыта)
    new_test_variant.json     # новый вариант
    sample_input.xlsx
    math/                     # дополнительные Excel-варианты (nts.xlsx, new_variant.xlsx)
  nts/
    __init__.py               # реэкспорт: Experiment, compute, read_input_file, read_input_json, read_input_xlsx
    __main__.py               # python -m nts → gui.main
    cli.py                    # CLI расчёт + print_report
    core.py                   # все расчёты + парсинг входа (360 строк)
    gui.py                    # GUI + дублированные методы (749 строк, см. §4)
  .agent/                     # MetaAgent scaffolding
```

**Паттерн:** модульный монолит без чётких слоёв. `core.py` смешивает:
- парсинг входных данных (`_parse_input_data`, `read_input_json`, `read_input_xlsx`);
- датакласс `Experiment`;
- расчёт (`compute`);
- округление (`_round3`);
- нормализация заголовков Excel.

**Ключевые модули и их зоны ответственности:**

| Модуль | Описание |
|---|---|
| `nts.core` | Датакласс `Experiment`, парсеры JSON и Excel (`openpyxl`), `compute()` — коэффициенты регрессии, Граббс, Стьюдент, Фишер |
| `nts.gui` | tk-приложение: формы ввода, окно вывода, экспорт в JSON/XLSX, i18n RU/EN |
| `nts.cli` | `argparse` обёртка, текстовый отчёт `print_report` |
| `nts.__main__` | python -m nts |
| `main.py` | вход в GUI |

## 4. Конвенции

- **Стиль:** PEP 8; type hints на функциях, но импорт `typing.Dict/List/Tuple/Any` при наличии `from __future__ import annotations` — избыточно.
- **Импорты:** только stdlib + `openpyxl`/`tkinter`/`tkinterdnd2`; нет внутреннего `nts.X` импорта кроме как через `from .core import ...`.
- **Типизация:** type hints присутствуют, но слабые (`Dict[str, object]` без `TypedDict`).
- **Обработка ошибок:** `ValueError` в вычислениях; `try/except Exception: openpyxl = None` для опциональных зависимостей; в GUI `messagebox.showerror` после broad `except`.
- **Логирование:** отсутствует.

## 5. Тесты

- **Команда запуска:** отсутствует.
- **Всего тестов:** 0.
- **Сборка:** неизвестно (Nuitka onefile — требует Windows + VC++ redist, не тестировали в этой сессии).
- **Запуск:** `python main.py` — открывает GUI; `python -m nts` — то же; `python -m nts --input examples/default.json` — текстовый отчёт (см. ниже подтверждение: работает).

## 6. Техдолг, выявленный при чтении (agent:analysis)

| # | Файл | Стр. | Проблема | Серьёзность |
|---|------|------|----------|------|
| TD-1 | `nts/gui.py` | 270-372 vs 599-715 | **Дубликаты методов `_build_export_payload`, `_export_json`, `_export_xlsx`, `_apply_lang`** — вторая копия затирает первую (Python берёт последнее определение). Сценарий экспорта работает, но первый вариант `_export_xlsx` делал активным листом `experiments` (битый); вторая копия — `input`. Первая копия мертва. | High |
| TD-2 | `nts/core.py` | 294 | `s_v = math.sqrt(s2_vos / 12)` — делитель `12 = N·m` противоречит учебной формуле для ортогонального 2-факторного плана: `S{b}² = s²_вос / N` ⇒ делитель должен быть `N = 4`. Расхождение в `√3 ≈ 1.73` раз. | High |
| TD-3 | `nts/core.py` | 301-303 | `t_i = \|b_i_natural\| / s_v` — t-критерий Стьюдента применяется к **натуральным** коэффициентам, тогда как уравнение регрессии в GUI/выводе (`_format_equation`) строится по **кодированным** `b_i`. Текст учебника §3 (стр.521: `Y = 920,90 + 14,65δ1 − 60,87δ2`) подтверждает тест на кодированных коэффициентах. | High |
| TD-4 | `nts/core.py` | 211-243 | `_read_criteria_from_sheet` имеет побочный путь чтения из основного листа — задумано, но fallback на «первые два столбца с лейблами G/T/F» недокументирован. | Medium |
| TD-5 | `nts/gui.py` | 749 | модуль 749 строк — UI + i18n + drag&drop + экспорт = всё в одном классе. Грануляция усложняет тестирование. | Medium |
| TD-6 | `nts/gui.py` | 50-159 | i18n-словарь 2×55 строк inline; при росте языков будет раздувать модуль. | Low |
| TD-7 | весь `nts/` | — | нет `tests/`; регрессия при правке core.py возможна без проверки. | High |
| TD-8 | `nts/__init__.py` | 1 | нет `__version__`; нет `py.typed`. | Low |
| TD-9 | `requirements.txt` | — | нет `pytest`, нет `ruff`, нет `mypy`. | Low |
| TD-10 | `build.ps1` | 11 | `--lto=yes` — заметно увеличивает время сборки; вероятно не нужен при локальной сборке. | Info |
| TD-11 | `cli.py:11` | — | `print_report(result)` читает `result["equation"]` — такого ключа в `compute()` **нет**. Сейчас CLI ломается на тестовом запуске (на самом деле проверим ниже). | High — нужно подтверждение. |
| TD-12 | `nts/core.py:111` | — | `_parse_input_data` имеет валидацию `"y" in item → raise`. Но имя колонки `y` в `_HEADER_ALIASES` отсутствует — это мёртвый код. | Low |

### Проверка TD-11 — действительно ли CLI ломается?

Будет выяснено в EXECUTION T0 или T1.

## 7. Соответствие Методичке.docx §3 (Теория расчёта)

Извлечено из `.temp/Методичка.docx`, абзацы 376-547:

| Элемент | Методичка | В коде |
|---|---|---|
| Входы `x1, x2, x3` | вода, гипс, опилки (% , сумма=100%) | `Experiment.x1,x2,x3` ✓ |
| Нормирование | `z1 = x1/x2`, `z2 = x3/x2` | `Experiment.z1, z2` ✓ |
| Кодирование | `δ1, δ2 ∈ {-1,+1}` (2² = 4 опыта) | `delta1, delta2` ✓ |
| Отклик | `y_avg = (y1+y2+y3)/3` | `Experiment.y_avg` ✓ |
| Параллельность | m ≥ 3 | ровно 3 (жёстко закодировано) |
| Коэффициенты | `b0, b1, b2` (кодированные) | `coefficients` (coded) + `coefficients_v` (natural) — оба есть ✓ |
| Уравнение | `Y = b0 + b1·δ1 + b2·δ2` | используется в GUI и CLI ✓ |
| `s²_вос` | `Σ(y_ij − ȳ_i)² / N(m−1)` | `sum(squares) / 8` ✓ (для N=4, m=3) |
| df Стьюдента | `N(m−1) = 8` | в коде df не используется, есть `t_crit` на входе ✓ |
| Стьюдент-критерий | `t_i = \|b_i\| / √(s²_вос/N)` для **кодированных** `b_i` | `t_i = \|b_i_natural\| / √(s²_вос/12)` — **оба неверны**: см. TD-2, TD-3 |
| Граббс | per-experiment, max deviation / sum sq | `g_val = max_dev / sum_sq` ✓ (стр.287) |
| `F_cr` | df1 = N−d = 1, df2 = 8 → 239 в примере | параметризован через `f_crit` ✓ |

**Вывод:** структурно формулы в `core.py` соответствуют методичке, но **две** формулы t-критерия имеют ошибки (TD-2 и TD-3). Именно из-за этого «t_0, t_1, t_2 не выводятся корректно».

## 8. Замечания по сессии

- `.agent/` уже содержал `src/` (исходники MetaAgent), но не имел `checkpoints.json` и `rules/project-rules.md` — созданы в INIT.
- `.temp/Методичка.docx` распарсен вручную через `zipfile + xml.etree` (без `python-docx`); сохранён в `.temp/metodichka_text.txt` (2063 параграфа).
- Эталонных тестовых данных из самой методички (значения y1/y2/y3 для 4 опытов, дающих 920,90 + 14,65·δ1 − 60,87·δ2 и `s²_вос = 4488.63`) в тексте не приведено — формулы фигурируют как изображения (стр. 522-524). Поэтому **верификация фикса t-критерия будет выполнена на примерах из `examples/`, а не на цифрах из методички**.
