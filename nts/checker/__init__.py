"""Самопроверка: сверка расчёта с эталоном.

Пакет разделён по ответственностям:

* :mod:`nts.checker.model` — формат эталона (ядро/расширенное/словарь),
  режимы проверки и типы результата;
* :mod:`nts.checker.compare` — движок сравнения (DISCRETE / NUMERIC /
  ``f_value`` / списки строк);
* :mod:`nts.checker.loader` — загрузка файлов самопроверки (JSON и Excel) и
  выбор режима по содержимому файла;
* :mod:`nts.checker.xlsx_io` — чтение и запись эталонной книги Excel;
* :mod:`nts.checker.report` — текстовый чек-лист по результату.

Публичный API прежний: ``from nts.checker import verify, write_self_check_xlsx``
и так далее работает как раньше.

Сравнение разбито по видам полей:

* DISCRETE — строковые поля (знаки, коды, уравнение, вердикт);
* NUMERIC — коэффициентоподобные группы и t-значения с погрешностями по
  категориям (1e-3 / 1e-2 / 1e-1);
* ``f_value`` — отдельная политика NaN/inf (NaN не совпадает никогда,
  совпадающие бесконечности — да);
* списки ``g_tests`` и ``output_rows`` — сверка множества строк и сравнение
  по ключу (соответственно ``row`` и ``(delta1, delta2)``).

Политика полноты:

* :data:`MODE_FULL` — эталон должен покрывать все известные поля, отсутствие
  поля считается провалом;
* :data:`MODE_SIMPLIFIED` — сравнивается только ядро
  (:data:`CORE_RESULT_KEYS`), опциональные поля пропускаются.

Цвет в формате книги — только метка: ядро определяется
:data:`CORE_RESULT_KEYS` и именем листа, заливка нигде не читается.
"""
from __future__ import annotations

from .compare import verify
from .loader import parse_self_check_bundle, parse_self_check_file
from .model import (
    CORE_FILL_RGB,
    CORE_RESULT_KEYS,
    DESCRIPTION_COLUMN,
    DICTIONARY_SHEET_NAME,
    EXTENDED_SHEET_NAME,
    MODE_FULL,
    MODE_SIMPLIFIED,
    CheckEntry,
    CheckResult,
    SelfCheckBundle,
    Tolerance,
)
from .report import print_checklist
from .xlsx_io import parse_self_check_xlsx, write_self_check_xlsx

__all__ = [
    "CORE_FILL_RGB",
    "CORE_RESULT_KEYS",
    "DESCRIPTION_COLUMN",
    "DICTIONARY_SHEET_NAME",
    "EXTENDED_SHEET_NAME",
    "MODE_FULL",
    "MODE_SIMPLIFIED",
    "CheckEntry",
    "CheckResult",
    "SelfCheckBundle",
    "Tolerance",
    "parse_self_check_bundle",
    "parse_self_check_file",
    "parse_self_check_xlsx",
    "print_checklist",
    "verify",
    "write_self_check_xlsx",
]
