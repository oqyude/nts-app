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
    "reverse_load": "Load self-check JSON",
    "reverse_reload": "Reload",
    "reverse_clear": "Clear",
    "reverse_export_report": "Export report",
    "reverse_no_data": "Load a self-check JSON to start.",
    "reverse_drop_file": "Please drop a self-check JSON file (.json).",
    "reverse_col_name": "Field",
    "reverse_col_actual": "Actual",
    "reverse_col_expected": "Expected",
    "reverse_col_diff": "Diff",
    "reverse_col_message": "Note",
    "reverse_summary_all_passed": "All {total} checks passed.",
    "reverse_summary_some_failed": "{passed} passed, {failed} failed of {total}.",
    "reverse_load_error": "Self-check load error",
    "reverse_no_file": "Load a self-check JSON file first.",
    "reverse_export_title": "Export self-check report",
    "reverse_export_done": "Report saved.",
    "reverse_export_error": "Report export error",
    "reverse_run": "Run check",
    "reverse_run_error": "Verification error",
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
    "reverse_load": "Загрузить JSON самопроверки",
    "reverse_reload": "Перечитать",
    "reverse_clear": "Очистить",
    "reverse_export_report": "Экспорт отчёта",
    "reverse_no_data": "Загрузите JSON самопроверки, чтобы начать.",
    "reverse_drop_file": "Перетащите JSON-файл самопроверки (.json).",
    "reverse_col_name": "Поле",
    "reverse_col_actual": "Факт",
    "reverse_col_expected": "Эталон",
    "reverse_col_diff": "Δ",
    "reverse_col_message": "Примечание",
    "reverse_summary_all_passed": "Все {total} проверок пройдены.",
    "reverse_summary_some_failed": "{passed} пройдено, {failed} провалено из {total}.",
    "reverse_load_error": "Ошибка загрузки самопроверки",
    "reverse_no_file": "Сначала загрузите JSON-файл самопроверки.",
    "reverse_export_title": "Экспорт отчёта самопроверки",
    "reverse_export_done": "Отчёт сохранён.",
    "reverse_export_error": "Ошибка экспорта отчёта",
    "reverse_run": "Проверить",
    "reverse_run_error": "Ошибка проверки",
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
