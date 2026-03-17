from __future__ import annotations

import argparse
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
    y: List[float]

    @property
    def z1(self) -> float:
        return safe_div(self.x1, self.x2, "x1/x2")

    @property
    def z2(self) -> float:
        return safe_div(self.x3, self.x2, "x3/x2")

    @property
    def y_avg(self) -> float:
        return sum(self.y) / 3


def safe_div(numerator: float, denominator: float, label: str) -> float:
    if denominator == 0:
        raise ValueError(f"Division by zero for {label}.")
    return numerator / denominator


def default_input() -> Tuple[List[Experiment], float, float, float]:
    # Default dataset equivalent to the original Excel input sheet.
    experiments = [
        Experiment(
            idx=1,
            delta1=-1,
            delta2=-1,
            x1=43.75,
            x2=43.75,
            x3=12.5,
            y=[1167, 1238, 963],
        ),
        Experiment(
            idx=2,
            delta1=-1,
            delta2=1,
            x1=35,
            x2=35,
            x3=30,
            y=[991, 992, 849],
        ),
        Experiment(
            idx=3,
            delta1=1,
            delta2=-1,
            x1=55,
            x2=34.97,
            x3=10,
            y=[1167, 1116, 1135],
        ),
        Experiment(
            idx=4,
            delta1=1,
            delta2=1,
            x1=45.83,
            x2=25.17,
            x3=25,
            y=[967, 1119, 1058],
        ),
    ]

    g_crit = 0.7679
    t_crit = 2.306
    f_crit = 239
    return experiments, g_crit, t_crit, f_crit


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
                y=[float(item["y1"]), float(item["y2"]), float(item["y3"])],
            )
        )

    g_crit = float(data["g_crit"])
    t_crit = float(data["t_crit"])
    f_crit = float(data["f_crit"])
    return experiments, g_crit, t_crit, f_crit


def compute(experiments: List[Experiment], g_crit: float, t_crit: float, f_crit: float) -> Dict[str, Any]:
    if len(experiments) != 4:
        raise ValueError("Expected exactly 4 experiments (rows 3-6 in 'input').")

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
        deviations = [(y_avg[i] - y) ** 2 for y in exp.y]
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


def print_report(result: Dict[str, Any]) -> None:
    print(result["equation"])
    print("")
    print("t-tests:")
    print(f"  b0: t={result['t_tests']['t0']:.4f} sign={result['t_tests']['sign_b0']}")
    print(f"  b1: t={result['t_tests']['t1']:.4f} sign={result['t_tests']['sign_b1']}")
    print(f"  b2: t={result['t_tests']['t2']:.4f} sign={result['t_tests']['sign_b2']}")
    print("")
    print("G-tests:")
    for row in result["g_tests"]:
        print(f"  row {row['row']}: G={row['g']:.4f} ({row['ok']})")
    print("")
    print("Output:")
    headers = ["y_avg", "delta1", "delta2", "y_pred", "y_avg-y", "(y_avg-y)^2"]
    print("  " + " | ".join(headers))
    for r in result["output_rows"]:
        print(
            "  "
            + " | ".join(
                [
                    f"{r['y_avg']:.6g}",
                    f"{r['delta1']:.6g}",
                    f"{r['delta2']:.6g}",
                    f"{r['y_pred']:.6g}",
                    f"{r['y_avg_minus_y']:.6g}",
                    f"{r['y_avg_minus_y_sq']:.6g}",
                ]
            )
        )
    print("")
    print(f"F_avg={result['f_avg']:.6g}")
    print(f"F_value={result['f_value']:.6g}")
    print(result["f_result"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute results without Excel dependencies.")
    parser.add_argument("--input", dest="input_path", help="Path to JSON input file.")
    parser.add_argument("--json", dest="json_path", help="Write result JSON to this path.")
    args = parser.parse_args()

    if args.input_path:
        path = Path(args.input_path)
        if not path.exists():
            raise FileNotFoundError(f"Input JSON not found: {path}")
        experiments, g_crit, t_crit, f_crit = read_input_json(path)
    else:
        experiments, g_crit, t_crit, f_crit = default_input()
    result = compute(experiments, g_crit, t_crit, f_crit)
    print_report(result)

    if args.json_path:
        json_path = Path(args.json_path)
        json_path.write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
