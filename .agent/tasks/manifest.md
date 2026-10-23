# Task Manifest

**Session:** `38dd3237-c3d7-4ade-adc7-d81bc68ec967` (цикл 2026-10-23, аудит техдолга)
**Goal:** снять выявленный техдолг репозитория `nts-app`: дрейф между документацией и кодом, дубли и мусор, монолиты, хрупкие решения, пробелы в тестах.
**Date:** 2026-10-23

> Предыдущий цикл (T0–T6) закрыт и архивирован: `.agent/archive/tasks/T0..T6.json`, `.agent/archive/index.json`.
> Machine-readable манифест прошлого цикла — `.agent/tasks/manifest.json` (не изменялся: правила сессии ограничивают правку `.agent/` тремя файлами).

---

## Task Overview

| ID | Title | Type | Depends On | Status |
|---|---|---|---|---|
| T7 | Описательные заголовки вместо ссылок на план (Todo N) | дрейф | — | pending |
| T8 | README: рабочий рецепт self-check-файла вместо `--json` | дрейф | — | pending |
| T9 | Отслеживать baseline-отчёт тестов (исключение в `.gitignore`) | мусор | — | pending |
| T10 | Инварианты: цвет / словарь / эталон (3 теста) | хрупкость | — | pending |
| T11 | Удалить байт-дубликат `examples/fail_intentional_mismatch.xlsx` | мусор | T10 | pending |
| T12 | Единый источник версии (`nts.__version__` ↔ Nuitka `--file-version`) | хрупкость | — | pending |
| T13 | Разбить `nts/checker.py` (1322 LOC) на пакет `nts/checker/` | реструктуризация | — | pending |
| T14 | Покрытие `nts/gui.py` тестами (сейчас 0) | хрупкость | — | pending |
| T15 | Покрытие `build.py` тестами (сейчас 0) | хрупкость | — | pending |
| T16 | Раскладка `examples/` по `inputs/ expected/ qa/` (2 коммита) | реструктуризация | — | pending |
| T17 | Обновить правила проекта (локализация, `Any`, версия Python) | дрейф | — | pending |
| T18 | Формулировка про CI/CD в `session-summary.md` | дрейф | — | pending |
| T19 | `pyproject.toml` + пины зависимостей | хрупкость | — | pending |
| T20 | Судьба вендоренного `.agent/src/` (35 файлов / 3390 LOC) | реструктуризация | — | pending |
| T21 | `docs/` и `tools/` в корне репозитория | реструктуризация | T15 | pending |
| T22 | Вернуть эталон `.temp/расчет.xlsx` под контроль версий | хрупкость | — | pending |
| T23 | Теги `v0.0.x` ↔ версия 0.2.1; мёртвый release-воркфлоу | дрейф | — | pending |
| T24 | Сводный отчёт по аудиту техдолга (архив документа) | мусор | — | pending |

**Total tasks:** 18 (T7–T24)

---

## Task Details

### T7: Описательные заголовки вместо ссылок на план (Todo N)

**Type:** дрейф
**Description:** 35 мест в `nts/checker.py` и `tests/test_checker.py` ссылаются на «Todo N» и на `.omo/plans/self-check.md` — план лежит в `.omo/`, который в `.gitignore:36`, то есть на свежем клоне ссылки в биты. Заменить на описательные заголовки по смыслу («DISCRETE comparison helpers», «JSON loader», «xlsx loader/writer», «checklist rendering»).

**Files:**
- `nts/checker.py:3,290,359,390,400,506,607,812,883,1270`
- `tests/test_checker.py:1225`

**Depends on:** —
**Acceptance Criteria:**
- [ ] В коде нет ни одного упоминания `Todo N` и `.omo/plans/self-check.md`
- [ ] Комментарии описывают назначение блока, а не номер пункта плана
- [ ] Поведение не меняется: `python -m pytest -q` — зелено

**Context:** план-комментарии — прямое следствие того, что `.omo/` вне git; при следующем рефакторинге они же и уводят в сторону.

---

### T8: README: рабочий рецепт self-check-файла вместо `--json`

**Type:** дрейф
**Description:** `README.md:81-85` обещает «Capture the `expected` block … `--json expected.json`», но `--json` пишет сырой `ComputeResult` (`nts/cli.py:106`), а `--self-check` требует верхнего уровня `{"input", "expected"}` (`nts/checker.py:843,845`) → файл из инструкции отвергается с exit 2. Описать реальный вывод `--json` и дать рабочий рецепт сборки self-check-файла.

**Files:**
- `README.md:81-85`

**Depends on:** —
**Acceptance Criteria:**
- [ ] Инструкция не предлагает шаг, который приводит к exit 2
- [ ] Приведён рабочий пример файла `{"input", "expected"}`
- [ ] Формат файлов и поведение CLI не меняются

**Context:** демо `examples/default_with_expected.json` имеет обёртку, но рецепта её получения в README нет.

---

### T9: Отслеживать baseline-отчёт тестов

**Type:** мусор
**Description:** `.agent/context/baseline-test-report.log` упомянут в `project-state.md` и `handoff-summary.md`, но не отслеживается: `*.log` в `.gitignore:6`. Добавить исключение и закоммитить отчёт.

**Files:**
- `.gitignore:6`
- `.agent/context/baseline-test-report.log`

**Depends on:** —
**Acceptance Criteria:**
- [ ] Ссылка из документации ведёт в существующий файл у нового клона
- [ ] Исключение точечное (не отключает игнорирование логов вообще)

**Context:** отчёт — единственный артефакт, на который ссылаются «гейты верификации» в метаданных.

---

### T10: Инварианты: цвет / словарь / эталон

**Type:** хрупкость
**Description:** три инварианта проверены вручную, но не зафиксированы тестами: (1) цвет заливки не влияет на результат проверки; (2) словарь покрывает каждый ключ, возвращаемый `compute()`; (3) эталонная книга в `examples/` соответствует выводу `write_self_check_xlsx`.

**Files:**
- `tests/test_checker.py`

**Depends on:** —
**Acceptance Criteria:**
- [ ] Три теста проходят на текущем коде
- [ ] Тесты падают, если инвариант нарушить (проверено локальным изменением)

**Context:** заливка — единственный «цвет» в формате книги; логика его не читает (`nts/checker.py:1241` — единственная запись, чтений нет).

---

### T11: Удалить байт-дубликат `examples/fail_intentional_mismatch.xlsx`

**Type:** мусор
**Description:** `examples/fail_intentional_mismatch.xlsx` побайтово идентичен `examples/default.xlsx` (md5 `52df10db6877a6a44bfecd1d0d07c2fd`); ни один код/тест/док на него не ссылается. Смысл «намеренного расхождения» несёт JSON-вариант.

**Files:**
- `examples/fail_intentional_mismatch.xlsx` (удаление)

**Depends on:** T10
**Acceptance Criteria:**
- [ ] Дубликат удалён, `examples/default.xlsx` остался
- [ ] Тесты зелёные, ссылок на удалённый файл не осталось

**Context:** правило MetaAgent «удалять файлы — только сообщив пользователю»; удаление именно дубликата, проверенного побайтово, отдельным коммитом.

---

### T12: Единый источник версии

**Type:** хрупкость
**Description:** версия продублирована: `nts/__init__.py:14` (`__version__ = "0.2.1"`) и `build.py:158` (`--file-version=0.2.1`). Сделать `build.py` читать версию из пакета.

**Files:**
- `build.py:158`
- `nts/__init__.py:14`

**Depends on:** —
**Acceptance Criteria:**
- [ ] Тест «версия Nuitka == `nts.__version__`» проходит до и после правки
- [ ] Литерал версии остаётся в одном месте
- [ ] Поведение сборки не меняется (тот же `--file-version`)

**Context:** публичное поведение CLI и формат файлов не затрагиваются.

---

### T13: Разбить `nts/checker.py` на пакет `nts/checker/`

**Type:** реструктуризация
**Description:** `nts/checker.py` — 1322 LOC с четырьмя ответственностями: движок сравнения (172-810), JSON IO (812-881), xlsx IO (883-1268), отчёт (1270-1322). Разложить по модулям `model.py` / `compare.py` / `loader.py` / `xlsx_io.py` / `report.py`, сохранив публичный API `nts.checker` (датаклассы, `verify`, парсеры, писатель, `print_checklist`, константы режимов).

**Files:**
- `nts/checker.py` → `nts/checker/{__init__,model,compare,loader,xlsx_io,report}.py`
- `tests/test_checker.py` (страховка)

**Depends on:** —
**Acceptance Criteria:**
- [ ] `from nts.checker import ...` работает для всех текущих импортов (`nts/cli.py:84`, `nts/gui.py:12`, `nts/reverse_gui.py:26`, `tests/test_checker.py`)
- [ ] Публичный API не изменился (тест-страховка на список экспортов)
- [ ] Поведение `verify` не изменилось (тест-страховка на эталонной фикстуре)
- [ ] Ни один модуль пакета не превышает ~700 LOC

**Context:** приватные имена уже намекают на деление (`_check_*` / `_compare_*` / `_read_xlsx_*` / `_parse_xlsx_*`).

---

### T14: Покрытие `nts/gui.py` тестами

**Type:** хрупкость
**Description:** `nts/gui.py` — 551 LOC и **0 ссылок в тестах**. Покрыть чистые части: `_place_value` (рендер значения с описанием), `_derive_font`, выгрузка XLSX с подменённым диалогом.

**Files:**
- `tests/test_gui.py` (новый)

**Depends on:** —
**Acceptance Criteria:**
- [ ] Тесты не требуют интерактивного дисплея (headless или без окна)
- [ ] Покрыты: текст описания под значением, формат выгрузки, экспорт в книгу
- [ ] Поведение GUI не меняется

**Context:** `python main.py` — единственный ручной «гейт» из `.agent/rules/project-rules.md`.

---

### T15: Покрытие `build.py` тестами

**Type:** хрупкость
**Description:** `build.py` — 258 LOC, 0 тестов. Покрыть чистые части: `find_vcvars64`, `find_cl`, `venv_python`, разбор аргументов `main()`, `_patched_require`-совместимую логику `nts/gui.py:26-72`.

**Files:**
- `tests/test_build.py` (новый)

**Depends on:** —
**Acceptance Criteria:**
- [ ] Тесты не запускают Nuitka и не создают `.venv-build`
- [ ] Проверены: выбор vcvars64, поиск `cl.exe`, разбор `--variant/--skip-tests/--assume-yes/--python`
- [ ] Поведение сборки не меняется

**Context:** патч `tkinterdnd2` под Nuitka onefile (`nts/gui.py:26-72`) не покрыт ничем и ломается молча.

---

### T16: Раскладка `examples/` по `inputs/ expected/ qa/`

**Type:** реструктуризация
**Description:** 19 файлов вперемешку; 11 из них никем не упомянуты, все `*_result.xlsx` — выводы приложения, а не входы. Разложить по `inputs/`, `expected/`, `qa/`, `math/` с README в каждой папке. **Два коммита:** сначала правка всех ссылок, потом перенос.

**Files:**
- `examples/**`
- `README.md`, `tests/**`, `nts/**` (ссылки)

**Depends on:** —
**Acceptance Criteria:**
- [ ] Ни одна ссылка не бита (тесты зелёные, README обновлён)
- [ ] Входы, эталоны и QA-кейсы разделены явно

**Context:** правило проекта запрещает удалять `examples/` — перенос допустим, удаление содержимого нет.

---

### T17: Обновить правила проекта

**Type:** дрейф
**Description:** `.agent/rules/project-rules.md` устарел: локализация вынесена в `nts/dictionary.py` (правило говорит про `i18n/`), запрет `from typing import Any when knowable` не учитывает `Dict[str, Any]` в `nts/checker.py`, версия Python 3.14 не объявлена в коде.

**Files:**
- `.agent/rules/project-rules.md`

**Depends on:** —
**Acceptance Criteria:**
- [ ] Правила соответствуют текущему коду
- [ ] Формат правил не меняется

**Context:** правила читаются перед каждой фазой MetaAgent — расхождение сбивает с толку следующего агента.

---

### T18: Формулировка про CI/CD в `session-summary.md`

**Type:** дрейф
**Description:** три документа утверждают «CI/CD не настроен», хотя `.github/workflows/` содержит два workflow. Часть правок (project-state, handoff) входит в метасостояние этого цикла; `session-summary.md` — отдельная задача (файл под `.agent/` вне разрешённого списка текущей сессии).

**Files:**
- `.agent/session-summary.md:74`

**Depends on:** —
**Acceptance Criteria:**
- [ ] Формулировка соответствует фактическому состоянию

**Context:** правка CI запрещена правилами проекта; меняется только текст.

---

### T19: `pyproject.toml` + пины зависимостей

**Type:** хрупкость
**Description:** версия Python и зависимости нигде не объявлены; `requirements.txt` без пинов, `requirements-build.txt` дублирует два других файла.

**Files:**
- `pyproject.toml` (новый), `requirements*.txt`

**Depends on:** —
**Acceptance Criteria:**
- [ ] `requires-python` и зависимости объявлены в одном месте
- [ ] Сборка Nuitka продолжает использовать `requirements-build.txt`
- [ ] Формат конфигурации согласован с владельцем

**Context:** требует отдельного согласования: это новая конфигурация проекта.

---

### T20: Судьба вендоренного `.agent/src/`

**Type:** реструктуризация
**Description:** 35 файлов / 3390 LOC чужого фреймворка MetaAgent внутри продуктового репозитория; `AGENTS.md` ссылается 16 раз.

**Files:**
- `.agent/src/**`, `AGENTS.md`

**Depends on:** —
**Acceptance Criteria:**
- [ ] Решение владельца зафиксировано (оставить / вынести / submodule)
- [ ] Установщик (`install.sh` / `install.ps1`) продолжает работать

**Context:** правка 16 ссылок в `AGENTS.md` — отдельная задача; без решения владельца не начинать.

---

### T21: `docs/` и `tools/` в корне репозитория

**Type:** реструктуризация
**Description:** `LISTING.md` (1250 строк, дамп исходников) и `REPORT.md` (разовый отчёт) лежат в корне; `build.py` + `build.ps1` + `build.bat` — тоже в корне.

**Files:**
- `LISTING.md`, `REPORT.md`, `build.py`, `build.ps1`, `build.bat`, `docs/`, `tools/`

**Depends on:** T15
**Acceptance Criteria:**
- [ ] `build.py` после переноса находит `examples/` и считает `REPO_ROOT` правильно
- [ ] `build.ps1` / `build.bat` по-прежнему находят `build.py`
- [ ] Ссылка на `LISTING.md` в документах обновлена

**Context:** ⚠ `build.py:163` включает `examples=` в Nuitka, а `REPO_ROOT` (:40) — от своего расположения: перенос ломает сборку, делать только после T15 и со смоуком.

---

### T22: Вернуть эталон `.temp/расчет.xlsx` под контроль версий

**Type:** хрупкость
**Description:** правило проекта требует, чтобы имена переменных и формулы совпадали с `.temp/расчет.xlsx`, но `.temp/` в `.gitignore:33` — на свежем клоне источника истины нет. `examples/math/*.xlsx` — другие книги (md5 `d9662bb8…` против `26a13199…`).

**Files:**
- `docs/reference/` (новый), `.agent/rules/project-rules.md`

**Depends on:** —
**Acceptance Criteria:**
- [ ] Эталон доступен в клоне и явно помечен как «правится сознательно»
- [ ] Правило проекта ссылается на него
- [ ] Содержимое проверено на персональные данные

**Context:** до вендоринга файл нужно открыть целиком — я смотрел только формулы.

---

### T23: Теги `v0.0.x` ↔ версия 0.2.1; мёртвый release-воркфлоу

**Type:** дрейф
**Description:** теги `v0.0.1…v0.0.5` (последний = `previous`) не отражают релиз 0.2.1; `.github/workflows/release.yml:11` ждёт `refs/tags/…`, а `build-windows.yml:5` триггерится только на `push: master` → release-draft не запустится никогда.

**Files:**
- `.git/*` (теги), `.github/workflows/release.yml`

**Depends on:** —
**Acceptance Criteria:**
- [ ] Решение владельца: теги и/или триггер воркфлоу

**Context:** правка CI/CD запрещена правилами проекта — только фиксация.

---

### T24: Сводный отчёт по аудиту техдолга (архив документа)

**Type:** мусор
**Description:** итоговый отчёт аудита (структура, модульность, дрейф, хрупкость, тесты, мусор, план) лежит во временном каталоге вне репозитория. Решение: сохранить в репозитории как исторический документ (например `.agent/context/techdebt-audit-2026-10-23.md`) или оставить вне.

**Files:**
- `.agent/context/techdebt-audit-2026-10-23.md`

**Depends on:** —
**Acceptance Criteria:**
- [ ] Решение владельца зафиксировано

**Context:** отчёт нужен следующему агенту как обоснование текущих задач T7–T23.
