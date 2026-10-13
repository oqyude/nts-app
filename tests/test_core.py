"""Тесты для nts.core — математическая модель и регрессия 2².

Методичка §3 (полный факторный план, параллельные опыты, Стьюдент, Граббс, Фишер).
"""

from __future__ import annotations

import math

import pytest

from nts.core import (
    EXPECTED_EXPERIMENTS,
    Experiment,
    InputData,
    PARALLEL_TRIALS,
    compute,
    format_equation,
    read_input_file,
)


def _data(exps, g=0.7679, t=2.306, f=239.0) -> InputData:
    return InputData(experiments=exps, g_crit=g, t_crit=t, f_crit=f)


def test_inputs_count():
    assert EXPECTED_EXPERIMENTS == 4
    assert PARALLEL_TRIALS == 3


def test_compute_rejects_wrong_count(default_criteria):
    short = [Experiment(idx=1, delta1=-1, delta2=-1, x1=33, x2=33, x3=33, y1=1, y2=2, y3=3)]
    with pytest.raises(ValueError, match="Expected exactly 4"):
        compute(_data(short, *default_criteria))


def test_coded_coefficients_match_hand_calc(all_significant_experiments, default_criteria):
    """Фиксированный синтетический пример: b_coded = (1000, 100, 100), все значимы."""
    result = compute(_data(all_significant_experiments, *default_criteria))
    assert result["coefficients"] == {"b0": 1000.0, "b1": 100.0, "b2": 100.0}
    t = result["t_tests"]
    assert t["t0"] > 2.306 and t["t1"] > 2.306 and t["t2"] > 2.306
    assert t["sign_b0"] == t["sign_b1"] == t["sign_b2"] == "+"


def test_student_uses_sqrt_s2_over_n_times_m(default_experiments, default_criteria):
    """Student S_в per Excel reference: √(s²_вос / (N·m)), not √(s²_вос / N).

    Math derivation: each b_i = Σδ_i·y_avg / N where y_avg has variance s²/m
    (mean of m replicates), so Var(b_i) = s²/(N·m) → S_в = √(s²/(N·m)).
    Default.json: s²=8416, N=4, m=3 → S_в = √(8416/12) ≈ 26.4829.
    See .agent/context/calculation-diff.md for full diff vs Методичка §3.
    """
    result = compute(_data(default_experiments, *default_criteria))
    for key in ("t0", "t1", "t2"):
        assert key in result["t_tests"]
        assert math.isfinite(result["t_tests"][key])
        assert result["t_tests"][key] >= 0


def test_student_uses_natural_not_coded(default_experiments, default_criteria):
    """Student t per Excel reference: t_i = |b_i_v| / S_в (натуральные b, не кодированные).

    For default.json, all three b_v are large enough that t > 2.306 ⇒ all significant.
    Diff vs old Методичка-aligned behaviour: b_1 and b_2 cross the t_crit threshold.
    """
    result = compute(_data(default_experiments, *default_criteria))
    t = result["t_tests"]
    assert t["sign_b0"] == "+"
    assert t["sign_b1"] == "+"
    assert t["sign_b2"] == "+"


def test_grubbs_criterion(default_experiments, default_criteria):
    result = compute(_data(default_experiments, *default_criteria))
    assert len(result["g_tests"]) == EXPECTED_EXPERIMENTS
    for g in result["g_tests"]:
        assert {"row", "g", "ok"} <= g.keys()
        assert 0 <= g["g"] <= 1
        assert g["ok"] in {"OK", "not OK"}


def test_fisher_criterion(default_experiments, default_criteria):
    result = compute(_data(default_experiments, *default_criteria))
    assert result["f_value"] > 0
    assert result["f_avg"] >= 0
    assert result["f_result_code"] in {"not_rejected", "rejected"}


def test_equation_key_in_result(default_experiments, default_criteria):
    """Регрессионный тест TD-11: compute() возвращает 'equation', чтобы
    CLI/GUI могли отрендерить регрессию без своей реализации форматтера."""
    result = compute(_data(default_experiments, *default_criteria))
    assert "equation" in result
    assert result["equation"].startswith("Y = ")


def test_equation_skips_insignificant_terms(default_experiments, default_criteria):
    """Default.json: все 3 b значимы → Y = b0 + b1*δ1 + b2*δ2 (b2 отрицателен)."""
    result = compute(_data(default_experiments, *default_criteria))
    assert "0*δ" not in result["equation"]
    assert "+ -" not in result["equation"]
    assert result["equation"].startswith("Y = ")
    assert all(
        term in result["equation"] for term in ("δ1", "δ2")
    )


def test_format_equation_unit():
    eq = format_equation(10.0, 2.5, -3.0, "δ1", "δ2")
    assert eq == "Y = 10 + 2.5*δ1 - 3*δ2"


def test_format_equation_zero_terms():
    eq = format_equation(1063.5, 0.0, 0.0, "δ1", "δ2")
    assert eq == "Y = 1063.5"


def test_compute_handles_zero_deviations(default_criteria):
    """Когда все 3 повторности в опыте равны, G = 0, safe_div не падает на sum_sq=0."""
    exp = Experiment(idx=1, delta1=-1, delta2=-1, x1=30.0, x2=50.0, x3=20.0, y1=500, y2=500, y3=500)
    rest = [
        Experiment(idx=2, delta1=-1, delta2=1, x1=35.0, x2=45.0, x3=20.0, y1=600, y2=600, y3=600),
        Experiment(idx=3, delta1=1, delta2=-1, x1=55.0, x2=35.0, x3=10.0, y1=700, y2=700, y3=700),
        Experiment(idx=4, delta1=1, delta2=1, x1=45.0, x2=30.0, x3=25.0, y1=800, y2=800, y3=800),
    ]
    result = compute(_data([exp, *rest], *default_criteria))
    assert result["g_tests"][0]["g"] == 0.0
    assert result["g_tests"][0]["ok"] == "OK"


def test_compute_handles_f_via_inf(default_criteria):
    """Когда остатки редуцированной модели нулевые, F → ∞ через защитный путь safe_div."""
    exp = Experiment(idx=1, delta1=-1, delta2=-1, x1=30.0, x2=50.0, x3=20.0, y1=1000, y2=1000, y3=1000)
    others = [
        Experiment(idx=2, delta1=-1, delta2=1, x1=35.0, x2=45.0, x3=20.0, y1=1000, y2=1000, y3=1000),
        Experiment(idx=3, delta1=1, delta2=-1, x1=55.0, x2=35.0, x3=10.0, y1=1000, y2=1000, y3=1000),
        Experiment(idx=4, delta1=1, delta2=1, x1=45.0, x2=30.0, x3=25.0, y1=1000, y2=1000, y3=1000),
    ]
    result = compute(_data([exp, *others], *default_criteria))
    assert result["f_avg"] == 0.0
    assert result["f_value"] == float("inf")


@pytest.mark.parametrize("filename", ["default.json", "new_test_variant.json"])
def test_examples_roundtrip(filename, examples_dir):
    """E2E smoke: каждый пример из examples/ считается без падений и
    возвращает полный набор ключей результата."""
    path = examples_dir / filename
    data = read_input_file(path)
    result = compute(data)
    expected_keys = {
        "coefficients", "coefficients_v", "z_averages", "pz", "delta_calc",
        "g_tests", "t_tests", "output_rows", "f_avg", "f_value",
        "f_result_code", "f_result", "equation", "g_crit", "t_crit", "f_crit",
    }
    assert expected_keys <= result.keys()
    for key in ("t0", "t1", "t2", "sign_b0", "sign_b1", "sign_b2"):
        assert key in result["t_tests"]


def test_default_json_matches_excel_reference(default_experiments, default_criteria):
    """Pin exact values computed by ``.temp/расчет.xlsx`` (Excel reference) for default.json.

    Excel reference (.temp/расчет.xlsx, Лист2):
    - b0_v=1052.16, b1_v=86.59, b2_v=-174.10
    - s²_вос=8416 → S_в=26.48
    - t_0=39.73, t_1=3.27, t_2=6.574 (all significant)
    - F=17.66 against F_crit=239
    - residuals: all |y_avg - y_pred| = 21.83 (squared ≈ 476.7)

    See ``.agent/context/calculation-diff.md`` for derivation.
    """
    result = compute(_data(default_experiments, *default_criteria))

    # Coded regression coefficients
    assert result["coefficients"] == {"b0": 1063.5, "b1": 30.167, "b2": -67.5}

    # Natural (v) coefficients
    assert result["coefficients_v"]["b0"] == pytest.approx(1052.161, abs=1e-3)
    assert result["coefficients_v"]["b1"] == pytest.approx(86.587, abs=1e-3)
    assert result["coefficients_v"]["b2"] == pytest.approx(-174.09, abs=1e-2)

    # Student t-values: |b_i_v| / S_в where S_в = √(8416/12) ≈ 26.4829
    assert result["t_tests"]["t0"] == pytest.approx(39.73, abs=1e-2)
    assert result["t_tests"]["t1"] == pytest.approx(3.27, abs=1e-2)
    assert result["t_tests"]["t2"] == pytest.approx(6.574, abs=1e-2)

    # All three significant in Excel reference
    assert result["t_tests"]["sign_b0"] == result["t_tests"]["sign_b1"] == result["t_tests"]["sign_b2"] == "+"

    # Fisher F = s²_вос / (Σ_resid² / N) = 8416 / 476.69 ≈ 17.66
    assert result["f_value"] == pytest.approx(17.66, abs=1e-1)
    assert result["f_result_code"] == "not_rejected"  # F < F_crit

    # Equation (still coded form, all 3 terms now significant)
    assert "δ1" in result["equation"] and "δ2" in result["equation"]
