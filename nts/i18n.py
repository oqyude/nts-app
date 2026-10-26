"""UI translations for the NTS calculator.

EN — базовый словарь. RU задаёт отличия от EN. Чтобы добавить язык, добавьте
его в ``TRANSLATIONS`` с переопределением только нужных ключей; остальные
возьмутся из ``EN_BASE``.
"""

from typing import Any, Dict

LANGUAGES: tuple[str, ...] = ("RU", "EN")
DEFAULT_LANGUAGE: str = "RU"


EN_BASE: Dict[str, Any] = {
    "title_main": "NTS Calculator",
    "title_output": "Output",
    "input_file": "Input file:",
    "browse": "Browse",
    "clear": "Clear",
    "calculate": "Calculate",
    "g_crit": "G_crit",
    "t_crit": "t_crit",
    "f_crit": "F_crit",
    "f_avg": "F_avg",
    "f_value": "F_value",
    "dnd_hint": "(Install tkinterdnd2 for drag & drop)",
    "load_error": "Load error",
    "calc_error": "Calculation error",
    "drop_file": "Please drop a .json or .xlsx file.",
    "empty_value": "Empty value in row {row}, {key}.",
    "crit_required": "G_crit, t_crit and F_crit must be filled.",
    "t_0": "t_0",
    "t_1": "t_1",
    "t_2": "t_2",
    "b0v": "b0 (v)",
    "b1v": "b1 (v)",
    "b2v": "b2 (v)",
    "lang": "Lang:",
    "result_not_rejected": "Hypothesis not rejected",
    "result_rejected": "Hypothesis rejected",
    "export_json": "Export JSON",
    "export_xlsx": "Export XLSX",
    "export_done": "Saved successfully.",
    "export_error": "Export error",
    "export_title": "Export",
    "delta1_sym": "δ1",
    "delta2_sym": "δ2",
    "grubbs_title": "Grubbs criterion",
    "grubbs_row": "Experiment {row}: G={g} {cmp} G_crit={gcrit} ({status})",
    "fisher_title": "Fisher criterion",
    "fisher_cmp": "F={f} {cmp} F_crit={fcrit}",
    "cmp_le": "<=",
    "cmp_gt": ">",
    "status_ok": "OK",
    "status_bad": "not OK",
    "self_check_title": "Self-check",
    "summary_passed": "{passed} passed",
    "summary_failed": "{failed} failed",
    "diff_label": "diff",
    "missing_label": "missing",
    "reverse_title_main": "NTS Reverse (self-check)",
    "reverse_load": "Open file",
    "reverse_reload": "Reload",
    "reverse_clear": "Clear",
    "reverse_export_report": "Export report",
    "reverse_no_data": "Load a self-check file (.json, .xlsx, .xlsm) to start.",
    "reverse_drop_file": "Please drop a self-check file (.json, .xlsx, .xlsm).",
    "reverse_col_name": "Field",
    "reverse_col_description": "Description",
    "reverse_col_actual": "Actual",
    "reverse_col_expected": "Expected",
    "reverse_col_diff": "Diff",
    "reverse_col_message": "Note",
    "reverse_summary_all_passed": "All {total} checks passed.",
    "reverse_summary_some_failed": "{passed} passed, {failed} failed of {total}.",
    "reverse_load_error": "Self-check load error",
    "reverse_no_file": "Load a self-check file (.json, .xlsx, .xlsm) first.",
    "reverse_export_title": "Export self-check report",
    "reverse_export_done": "Report saved.",
    "reverse_export_error": "Report export error",
    "reverse_report_source": "source",
    "reverse_run": "Run check",
    "reverse_run_error": "Verification error",
    "reverse_mode": "Mode:",
    "reverse_mode_auto": "Auto (by file)",
    "reverse_mode_simplified": "Simplified (main fields)",
    "reverse_mode_full": "Extended (all fields)",
    "reverse_mode_current": "Mode: {mode}",
    # -- CLI report headings / labels -------------------------------------
    "cli_report_t": "t-tests:",
    "cli_report_g": "G-tests:",
    "cli_report_output": "Output:",
    "cli_report_row": "row {row}: G={g} ({status})",
    "cli_error": "error:",
    # -- checklist text labels --------------------------------------------
    "report_actual": "actual",
    "report_expected": "expected",
    "report_diff": "diff",
    "report_not_applicable": "n/a",
    # -- canonical value translations -------------------------------------
    "code_not_rejected": "not_rejected",
    "code_rejected": "rejected",
    # -- file dialogs / message boxes -------------------------------------
    "filter_input_files": "Input files",
    "filter_self_check_files": "Self-check files",
    "filter_json": "JSON",
    "filter_excel": "Excel",
    "filter_text": "Text",
    "filter_all": "All files",
    "msg_openpyxl_missing": "openpyxl is not installed.",
    "msg_no_input_data": "No input data to export.",
}

EN_HEADERS: Dict[str, str] = {
    "no": "No",
    "delta1": "δ1",
    "delta2": "δ2",
    "x1": "x1", "x2": "x2", "x3": "x3",
    "y1": "y1", "y2": "y2", "y3": "y3",
}

RU_OVERRIDES: Dict[str, Any] = {
    "title_main": "Калькулятор НТС",
    "title_output": "Результат",
    "input_file": "Файл ввода:",
    "browse": "Обзор",
    "clear": "Очистить",
    "calculate": "Расчет",
    "g_crit": "G_крит",
    "t_crit": "t_крит",
    "f_crit": "F_крит",
    "f_avg": "F_ср",
    "f_value": "F_знач",
    "dnd_hint": "(Установите tkinterdnd2 для drag & drop)",
    "load_error": "Ошибка загрузки",
    "calc_error": "Ошибка расчета",
    "drop_file": "Перетащите файл .json или .xlsx.",
    "empty_value": "Пустое значение в строке {row}, {key}.",
    "crit_required": "Заполните G_крит, t_крит и F_крит.",
    "b0v": "b0 (в)",
    "b1v": "b1 (в)",
    "b2v": "b2 (в)",
    "lang": "Язык:",
    "result_not_rejected": "Гипотеза не отвергается",
    "result_rejected": "Гипотеза отвергается",
    "export_json": "Экспорт JSON",
    "export_xlsx": "Экспорт XLSX",
    "export_done": "Файл сохранен.",
    "export_error": "Ошибка экспорта",
    "export_title": "Экспорт",
    "grubbs_title": "Критерий Граббса",
    "grubbs_row": "Опыт {row}: G={g} {cmp} G_крит={gcrit} ({status})",
    "fisher_title": "Критерий Фишера",
    "fisher_cmp": "F={f} {cmp} F_крит={fcrit}",
    "status_bad": "не OK",
    "self_check_title": "Самопроверка",
    "summary_passed": "{passed} пройдено",
    "summary_failed": "{failed} провалено",
    "diff_label": "расхождение",
    "missing_label": "отсутствует",
    "reverse_title_main": "НТС Реверс (самопроверка)",
    "reverse_load": "Открыть файл",
    "reverse_reload": "Перечитать",
    "reverse_clear": "Очистить",
    "reverse_export_report": "Экспорт отчёта",
    "reverse_no_data": "Загрузите файл самопроверки (.json, .xlsx, .xlsm), чтобы начать.",
    "reverse_drop_file": "Перетащите файл самопроверки (.json, .xlsx, .xlsm).",
    "reverse_col_name": "Поле",
    "reverse_col_description": "Описание",
    "reverse_col_actual": "Факт",
    "reverse_col_expected": "Эталон",
    "reverse_col_diff": "Δ",
    "reverse_col_message": "Примечание",
    "reverse_summary_all_passed": "Все {total} проверок пройдены.",
    "reverse_summary_some_failed": "{passed} пройдено, {failed} провалено из {total}.",
    "reverse_load_error": "Ошибка загрузки самопроверки",
    "reverse_no_file": "Сначала загрузите файл самопроверки (.json, .xlsx, .xlsm).",
    "reverse_export_title": "Экспорт отчёта самопроверки",
    "reverse_export_done": "Отчёт сохранён.",
    "reverse_export_error": "Ошибка экспорта отчёта",
    "reverse_report_source": "источник",
    "reverse_run": "Проверить",
    "reverse_run_error": "Ошибка проверки",
    "reverse_mode": "Режим:",
    "reverse_mode_auto": "Авто (по файлу)",
    "reverse_mode_simplified": "Упрощённый (основные поля)",
    "reverse_mode_full": "Расширенный (все поля)",
    "reverse_mode_current": "Режим: {mode}",
    # -- CLI report headings / labels -------------------------------------
    "cli_report_t": "t-критерии:",
    "cli_report_g": "Критерий Граббса:",
    "cli_report_output": "Поопытный вывод:",
    "cli_report_row": "Опыт {row}: G={g} ({status})",
    "cli_error": "ошибка:",
    # -- checklist text labels --------------------------------------------
    "report_actual": "факт",
    "report_expected": "эталон",
    "report_diff": "расхождение",
    "report_not_applicable": "н/д",
    # -- canonical value translations -------------------------------------
    "code_not_rejected": "не отвергается",
    "code_rejected": "отвергается",
    # -- file dialogs / message boxes -------------------------------------
    "filter_input_files": "Файлы ввода",
    "filter_self_check_files": "Файлы самопроверки",
    "filter_json": "JSON",
    "filter_excel": "Excel",
    "filter_text": "Текст",
    "filter_all": "Все файлы",
    "msg_openpyxl_missing": "openpyxl не установлен.",
    "msg_no_input_data": "Нет входных данных для экспорта.",
}

RU_HEADERS_OVERRIDES: Dict[str, str] = {
    "no": "№",
}


def _build(base: Dict[str, Any], overrides: Dict[str, Any], base_headers: Dict[str, str], header_overrides: Dict[str, str]) -> Dict[str, Any]:
    out = {**base, **overrides}
    out["headers"] = {**base_headers, **header_overrides}
    return out


TRANSLATIONS: Dict[str, Dict[str, Any]] = {
    "EN": _build(EN_BASE, {}, EN_HEADERS, {}),
    "RU": _build(EN_BASE, RU_OVERRIDES, EN_HEADERS, RU_HEADERS_OVERRIDES),
}

I18N: Dict[str, Dict[str, Any]] = TRANSLATIONS


def normalize_lang(lang: str) -> str:
    """Return a language code that exists in TRANSLATIONS (defaults to DEFAULT_LANGUAGE)."""
    return lang if lang in TRANSLATIONS else DEFAULT_LANGUAGE


#: Rusification of the technical note prefixes emitted by ``nts.checker.verify``.
#: Keyed by the exact English prefix; the remainder of the message is kept as is.
_RU_MESSAGE_PREFIXES: dict[str, str] = {
    "discrete mismatch: ": "расхождение значений: ",
    "missing in actual: ": "отсутствует в факте: ",
    "missing in expected: ": "отсутствует в эталоне: ",
    "missing numeric value: ": "отсутствует числовое значение: ",
    "numeric mismatch: ": "числовое расхождение: ",
    "NaN never matches: ": "NaN не совпадает никогда: ",
    "inf sign mismatch: ": "несовпадение знака бесконечности: ",
    "inf vs finite mismatch: ": "бесконечность против конечного значения: ",
    "missing g_tests list: ": "отсутствует список g_tests: ",
    "g_tests row set mismatch: ": "несовпадение набора строк g_tests: ",
    "missing output_rows list: ": "отсутствует список output_rows: ",
    "output_rows delta set mismatch: ": "несовпадение набора delta output_rows: ",
}


def _entry_leaf(name: str) -> str:
    """Variable part of a checklist entry name (``g_tests[row=1].ok`` → ``ok``)."""
    if "]" in name:
        return name.split("]", 1)[1].lstrip(".")
    return name.rsplit(".", 1)[-1]


def localize_check_value(name: str, value: Any, lang: str) -> Any:
    """Translate a *canonical* result value for display.

    The data model keeps ``f_result`` (``Hypothesis not rejected``),
    ``f_result_code`` (``not_rejected``) and the G-test status (``OK``) in a
    single canonical form so files and comparisons stay language-neutral. The
    UI must not show those English strings in the Russian locale, so this
    helper maps them at render time.

    Non-string values, unknown keys and unknown strings are returned unchanged.
    """
    if not isinstance(value, str):
        return value
    table = TRANSLATIONS[normalize_lang(lang)]
    leaf = _entry_leaf(name)
    if leaf == "f_result":
        if value == "Hypothesis not rejected":
            return table["result_not_rejected"]
        if value == "Hypothesis rejected":
            return table["result_rejected"]
    elif leaf == "f_result_code":
        if value == "not_rejected":
            return table["code_not_rejected"]
        if value == "rejected":
            return table["code_rejected"]
    elif leaf == "ok":
        if value == "OK":
            return table["status_ok"]
        if value == "not OK":
            return table["status_bad"]
    return value


def translate_message(message: str, lang: str) -> str:
    """Translate the technical note of a failed check for the given language.

    Only the known English prefixes are replaced; the variable tail
    (numbers, repr values) is preserved. Unknown messages pass through.
    """
    if not message or normalize_lang(lang) != "RU":
        return message
    for prefix, translated in _RU_MESSAGE_PREFIXES.items():
        if message.startswith(prefix):
            return translated + message[len(prefix):]
    return message


def canonical_check_value(name: str, value: Any) -> Any:
    """Map a localized display value back to the language-neutral form.

    The inverse of :func:`localize_check_value` for the values the writer may
    localize in an exported workbook. Used by the workbook reader, so a
    Russian report stays interchangeable with an English one.
    """
    if not isinstance(value, str):
        return value
    leaf = _entry_leaf(name)
    if leaf in ("f_result", "f_result_code", "ok"):
        for table in TRANSLATIONS.values():
            if leaf == "f_result":
                if value == table["result_not_rejected"]:
                    return "Hypothesis not rejected"
                if value == table["result_rejected"]:
                    return "Hypothesis rejected"
            elif leaf == "f_result_code":
                if value == table["code_not_rejected"]:
                    return "not_rejected"
                if value == table["code_rejected"]:
                    return "rejected"
            else:
                if value == table["status_bad"]:
                    return "not OK"
                if value == table["status_ok"]:
                    return "OK"
    return value
