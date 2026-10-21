"""Human-readable descriptions of the calculator's variables.

The machine keys (``coefficients_v.b1``, ``t_tests.t0``, ...) are stable API
surface — they must not change. This module is the companion dictionary that
says what each key *means*, for two audiences:

  * the Excel self-check workbook — an extra ``description`` column next to
    ``key`` / ``value``;
  * the GUIs — the reverse checklist shows what a field actually is instead of
    a bare key.

EN is the base table; RU is a full translation (the wording follows
Методичка.docx §3 and the Excel reference ``.temp/расчет.xlsx``).

Lookup rules
------------
``describe()`` takes a plain key: a result key (``"coefficients.b0"``), a
column name (``"x1"``, ``"y_avg"``) or a criteria name (``"g_crit"``).
``describe_entry()`` takes a *checklist entry name* — the composite names the
verifier emits (``"g_tests[row=1].g"``, ``"output_rows[-1.0, -1.0].y_avg"``)
— and resolves the variable part of it.
"""
from __future__ import annotations

from .i18n import DEFAULT_LANGUAGE, normalize_lang

#: Descriptions of every result key, per language.
DESCRIPTIONS_EN: dict[str, str] = {
    # -- result scalars ----------------------------------------------------
    "equation": "Regression equation Y = b0 + b1·δ1 + b2·δ2",
    "f_avg": "Mean squared residual sum (F_avg)",
    "f_value": "Fisher criterion value",
    "f_result_code": "Fisher criterion result code",
    "f_result": "Fisher criterion verdict (model adequacy)",
    "g_crit": "Grubbs criterion critical value",
    "t_crit": "Student t criterion critical value",
    "f_crit": "Fisher criterion critical value",
    # -- regression coefficients -------------------------------------------
    "coefficients.b0": "Regression intercept (coded coefficients)",
    "coefficients.b1": "Coefficient of δ1 (coded)",
    "coefficients.b2": "Coefficient of δ2 (coded)",
    "coefficients_v.b0": "Regression intercept in natural units (v)",
    "coefficients_v.b1": "Coefficient of δ1 in natural units (v)",
    "coefficients_v.b2": "Coefficient of δ2 in natural units (v)",
    # -- plan in ratios ----------------------------------------------------
    "z_averages.z1_avg": "Mean of z1 = x1/x2 across the experiments",
    "z_averages.z2_avg": "Mean of z2 = x3/x2 across the experiments",
    "pz.pz1": "Reduced range of z1 (z̄1 − min z1)",
    "pz.pz2": "Reduced range of z2 (max z2 − z̄2)",
    "delta_calc.delta1": "Re-derived coded factor δ1",
    "delta_calc.delta2": "Re-derived coded factor δ2",
    # -- Student t ---------------------------------------------------------
    "t_tests.t0": "Student t criterion for b0",
    "t_tests.t1": "Student t criterion for b1",
    "t_tests.t2": "Student t criterion for b2",
    "t_tests.sign_b0": "Sign of b0",
    "t_tests.sign_b1": "Sign of b1",
    "t_tests.sign_b2": "Sign of b2",
    # -- input columns -----------------------------------------------------
    "idx": "Experiment number",
    "delta1": "Coded factor δ1",
    "delta2": "Coded factor δ2",
    "x1": "First component share, %",
    "x2": "Second component share, %",
    "x3": "Third component share, %",
    "y1": "Response, parallel trial 1",
    "y2": "Response, parallel trial 2",
    "y3": "Response, parallel trial 3",
    # -- G-test rows -------------------------------------------------------
    "g_tests": "Grubbs criterion per experiment (row, G, ok)",
    "output_rows": "Per-experiment regression output (delta1, delta2, y_avg, y_pred, ...)",
    "row": "Experiment number",
    "G": "Grubbs criterion value",
    "g": "Grubbs criterion value",
    "ok": "No gross error detected",
    # -- output rows -------------------------------------------------------
    "y_avg": "Mean response of the experiment",
    "y_pred": "Regression prediction for the experiment",
    "y_avg_minus_y": "Mean response minus prediction",
    "y_avg_minus_y_sq": "Squared deviation (contribution to F_avg)",
}

DESCRIPTIONS_RU: dict[str, str] = {
    # -- result scalars ----------------------------------------------------
    "equation": "Уравнение регрессии Y = b0 + b1·δ1 + b2·δ2",
    "f_avg": "Средняя сумма квадратов отклонений (F_ср)",
    "f_value": "Значение критерия Фишера",
    "f_result_code": "Код результата критерия Фишера",
    "f_result": "Вывод по критерию Фишера (адекватность модели)",
    "g_crit": "Критическое значение критерия Граббса",
    "t_crit": "Критическое значение t-критерия Стьюдента",
    "f_crit": "Критическое значение критерия Фишера",
    # -- regression coefficients -------------------------------------------
    "coefficients.b0": "Свободный член регрессии (кодированные коэффициенты)",
    "coefficients.b1": "Коэффициент при δ1 (кодированный)",
    "coefficients.b2": "Коэффициент при δ2 (кодированный)",
    "coefficients_v.b0": "Свободный член регрессии в натуральных единицах (в)",
    "coefficients_v.b1": "Коэффициент при δ1 в натуральных единицах (в)",
    "coefficients_v.b2": "Коэффициент при δ2 в натуральных единицах (в)",
    # -- plan in ratios ----------------------------------------------------
    "z_averages.z1_avg": "Среднее значение z1 = x1/x2 по опытам",
    "z_averages.z2_avg": "Среднее значение z2 = x3/x2 по опытам",
    "pz.pz1": "Приведённый размах z1 (z̄1 − min z1)",
    "pz.pz2": "Приведённый размах z2 (max z2 − z̄2)",
    "delta_calc.delta1": "Пересчитанный кодированный фактор δ1",
    "delta_calc.delta2": "Пересчитанный кодированный фактор δ2",
    # -- Student t ---------------------------------------------------------
    "t_tests.t0": "t-критерий Стьюдента для b0",
    "t_tests.t1": "t-критерий Стьюдента для b1",
    "t_tests.t2": "t-критерий Стьюдента для b2",
    "t_tests.sign_b0": "Знак коэффициента b0",
    "t_tests.sign_b1": "Знак коэффициента b1",
    "t_tests.sign_b2": "Знак коэффициента b2",
    # -- input columns -----------------------------------------------------
    "idx": "Номер опыта",
    "delta1": "Кодированный фактор δ1",
    "delta2": "Кодированный фактор δ2",
    "x1": "Доля первого компонента, %",
    "x2": "Доля второго компонента, %",
    "x3": "Доля третьего компонента, %",
    "y1": "Отклик, параллельный опыт 1",
    "y2": "Отклик, параллельный опыт 2",
    "y3": "Отклик, параллельный опыт 3",
    # -- G-test rows -------------------------------------------------------
    "g_tests": "Критерий Граббса по опытам (row, G, ok)",
    "output_rows": "Поопытный результат регрессии (delta1, delta2, y_avg, y_pred, ...)",
    "row": "Номер опыта",
    "G": "Значение критерия Граббса",
    "g": "Значение критерия Граббса",
    "ok": "Грубная ошибка не обнаружена",
    # -- output rows -------------------------------------------------------
    "y_avg": "Средний отклик опыта",
    "y_pred": "Предсказанное значение регрессии",
    "y_avg_minus_y": "Отклонение среднего отклика от предсказанного",
    "y_avg_minus_y_sq": "Квадрат отклонения (вклад в F_ср)",
}

#: Description tables per language code.
DESCRIPTIONS: dict[str, dict[str, str]] = {
    "EN": DESCRIPTIONS_EN,
    "RU": DESCRIPTIONS_RU,
}

#: Fallback used when a key has no description in the requested language.
UNKNOWN_DESCRIPTION = "—"


def describe(key: str, lang: str = DEFAULT_LANGUAGE) -> str:
    """Return the human-readable description of ``key``.

    Returns :data:`UNKNOWN_DESCRIPTION` when the key is not in the dictionary
    (an unknown key must not break a report).
    """
    table = DESCRIPTIONS.get(normalize_lang(lang), DESCRIPTIONS_EN)
    return table.get(key, UNKNOWN_DESCRIPTION)


def describe_entry(name: str, lang: str = DEFAULT_LANGUAGE) -> str:
    """Return the description of a checklist entry name.

    The verifier emits composite names for list fields — ``g_tests[row=1].g``,
    ``output_rows[-1.0, -1.0].y_avg``. Only the variable part carries meaning,
    so the container prefix is stripped before the lookup:

    * ``"coefficients.b0"``              → description of ``coefficients.b0``
    * ``"g_tests[row=1].g"``             → description of ``g``
    * ``"output_rows[-1.0, -1.0].y_avg"``→ description of ``y_avg``
    """
    key = name
    if "]" in key:
        key = key.split("]", 1)[1].lstrip(".")
    return describe(key, lang)
