from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass
class Experiment:
    idx: int
    delta1: float
    delta2: float
    x1: float
    x2: float
    x3: float
    y1: float
    y2: float
    y3: float

    @property
    def z1(self) -> float:
        return safe_div(self.x1, self.x2, "x1/x2")

    @property
    def z2(self) -> float:
        return safe_div(self.x3, self.x2, "x3/x2")

    @property
    def y_values(self) -> List[float]:
        return [self.y1, self.y2, self.y3]

    @property
    def y_avg(self) -> float:
        return sum(self.y_values) / 3


def safe_div(numerator: float, denominator: float, label: str) -> float:
    if denominator == 0:
        raise ValueError(f"Division by zero for {label}.")
    return numerator / denominator


def read_input_json(path: Path) -> Tuple[List[Experiment], float, float, float]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "experiments" not in data:
        raise ValueError("JSON must include 'experiments'.")
    experiments: List[Experiment] = []
    for item in data["experiments"]:
        if "y" in item:
            raise ValueError("Use y1, y2, y3 instead of 'y' in experiments.")
        experiments.append(
            Experiment(
                idx=int(item["idx"]),
                delta1=float(item["delta1"]),
                delta2=float(item["delta2"]),
                x1=float(item["x1"]),
                x2=float(item["x2"]),
                x3=float(item["x3"]),
                y1=float(item["y1"]),
                y2=float(item["y2"]),
                y3=float(item["y3"]),
            )
        )

    g_crit = float(data["g_crit"])
    t_crit = float(data["t_crit"])
    f_crit = float(data["f_crit"])
    return experiments, g_crit, t_crit, f_crit


def compute(experiments: List[Experiment], g_crit: float, t_crit: float, f_crit: float) -> Dict[str, Any]:
    if len(experiments) != 4:
        raise ValueError("Expected exactly 4 experiments.")

    z1 = [e.z1 for e in experiments]
    z2 = [e.z2 for e in experiments]
    y_avg = [e.y_avg for e in experiments]

    b0 = sum(y_avg) / 4
    b1 = (-y_avg[0] - y_avg[1] + y_avg[2] + y_avg[3]) / 4
    b2 = (-y_avg[0] + y_avg[1] - y_avg[2] + y_avg[3]) / 4

    z1_avg = sum(z1) / 4
    z2_avg = sum(z2) / 4
    pz1 = z1_avg - min(z1)
    pz2 = max(z2) - z2_avg

    delta1_calc = safe_div(z1[0] - z1_avg, pz1, "delta1_calc")
    delta2_calc = safe_div(z2[0] - z2_avg, pz2, "delta2_calc")

    squares: List[float] = []
    g_tests: List[Dict[str, Any]] = []
    for i, exp in enumerate(experiments):
        deviations = [(y_avg[i] - y) ** 2 for y in exp.y_values]
        sum_sq = sum(deviations)
        g_val = safe_div(max(deviations), sum_sq, "G") if sum_sq != 0 else 0.0
        g_ok = "OK" if g_val < g_crit else "not OK"
        g_tests.append({"row": exp.idx, "g": g_val, "ok": g_ok})
        squares.extend(deviations)

    s2_vos = sum(squares) / 8
    s_v = math.sqrt(s2_vos / 12)

    b0_t = (b0 - b1 * z1_avg / pz1 - b2 * z2_avg / pz2)
    t0 = abs(b0_t) / s_v
    t1 = abs(b1 / pz1) / s_v
    t2 = abs(b2 / pz2) / s_v

    sign_b0 = "+" if t0 > t_crit else " -"
    sign_b1 = "+" if t1 > t_crit else " -"
    sign_b2 = "+" if t2 > t_crit else " -"

    output_rows: List[Dict[str, float]] = []
    for exp, y in zip(experiments, y_avg):
        y_pred = 0.0
        if sign_b0 == "+":
            y_pred += b0
        if sign_b1 == "+":
            y_pred += b1 * exp.delta1
        if sign_b2 == "+":
            y_pred += b2 * exp.delta2
        y_res = y - y_pred
        output_rows.append(
            {
                "y_avg": y,
                "delta1": exp.delta1,
                "delta2": exp.delta2,
                "y_pred": y_pred,
                "y_avg_minus_y": y_res,
                "y_avg_minus_y_sq": y_res ** 2,
            }
        )

    f_avg = sum(r["y_avg_minus_y_sq"] for r in output_rows) / 4
    f_value = safe_div(s2_vos, f_avg, "F") if f_avg != 0 else float("inf")
    f_result = "Hypothesis not rejected" if f_value < f_crit else "Hypothesis rejected"

    def format_term(coeff: float, name: str) -> str:
        sign = "+" if coeff >= 0 else "-"
        return f"{sign}{abs(coeff):.2f}*{name}"

    eq = f"Y={b0:.2f}{format_term(b1, 'delta1')}{format_term(b2, 'delta2')}"

    return {
        "equation": eq,
        "coefficients": {"b0": b0, "b1": b1, "b2": b2},
        "z_averages": {"z1_avg": z1_avg, "z2_avg": z2_avg},
        "pz": {"pz1": pz1, "pz2": pz2},
        "delta_calc": {"delta1": delta1_calc, "delta2": delta2_calc},
        "g_tests": g_tests,
        "t_tests": {
            "t0": t0,
            "t1": t1,
            "t2": t2,
            "sign_b0": sign_b0,
            "sign_b1": sign_b1,
            "sign_b2": sign_b2,
        },
        "output_rows": output_rows,
        "f_avg": f_avg,
        "f_value": f_value,
        "f_result": f_result,
    }
