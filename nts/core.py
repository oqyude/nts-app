from __future__ import annotations

import json
import math
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

try:
    import openpyxl
except Exception:
    openpyxl = None


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


def _to_float(value: object, label: str) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        raw = value.strip().replace(",", ".")
        if raw == "":
            raise ValueError(f"Empty value for {label}.")
        return float(raw)
    raise ValueError(f"Invalid value for {label}: {value!r}")


def _round3(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.000"), rounding=ROUND_HALF_UP))


# Ожидаемые столбцы таблицы экспериментов.
EXPECTED_COLUMNS = ["idx", "delta1", "delta2", "x1", "x2", "x3", "y1", "y2", "y3"]

# Допустимые имена колонок (Excel) с небольшими вариациями.
_HEADER_ALIASES = {
    "idx": ["idx", "no", "n", "num", "number"],
    "delta1": ["delta1", "d1", "delta-1", "delta_1", "delta 1"],
    "delta2": ["delta2", "d2", "delta-2", "delta_2", "delta 2"],
    "x1": ["x1"],
    "x2": ["x2"],
    "x3": ["x3"],
    "y1": ["y1"],
    "y2": ["y2"],
    "y3": ["y3"],
}

# Допустимые имена для критериев.
_CRIT_ALIASES = {
    "g_crit": ["g_crit", "gcrit", "g-crit", "g crit"],
    "t_crit": ["t_crit", "tcrit", "t-crit", "t crit"],
    "f_crit": ["f_crit", "fcrit", "f-crit", "f crit"],
}


def _normalize_header(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    return text.replace(" ", "").replace("_", "").replace("-", "")


_HEADER_MAP = {
    _normalize_header(alias): key
    for key, aliases in _HEADER_ALIASES.items()
    for alias in aliases
}

_CRIT_MAP = {
    _normalize_header(alias): key
    for key, aliases in _CRIT_ALIASES.items()
    for alias in aliases
}


# Разбор входных данных (общий формат, одинаковый для JSON и Excel).
def _parse_input_data(data: Dict[str, Any]) -> Tuple[List[Experiment], float, float, float]:
    if "experiments" not in data:
        raise ValueError("Input must include 'experiments'.")
    experiments: List[Experiment] = []
    for idx, item in enumerate(data["experiments"]):
        if "y" in item:
            raise ValueError("Use y1, y2, y3 instead of 'y' in experiments.")
        experiments.append(
            Experiment(
                idx=int(_to_float(item["idx"], f"experiments[{idx}].idx")),
                delta1=_to_float(item["delta1"], f"experiments[{idx}].delta1"),
                delta2=_to_float(item["delta2"], f"experiments[{idx}].delta2"),
                x1=_to_float(item["x1"], f"experiments[{idx}].x1"),
                x2=_to_float(item["x2"], f"experiments[{idx}].x2"),
                x3=_to_float(item["x3"], f"experiments[{idx}].x3"),
                y1=_to_float(item["y1"], f"experiments[{idx}].y1"),
                y2=_to_float(item["y2"], f"experiments[{idx}].y2"),
                y3=_to_float(item["y3"], f"experiments[{idx}].y3"),
            )
        )

    g_crit = _to_float(data["g_crit"], "g_crit")
    t_crit = _to_float(data["t_crit"], "t_crit")
    f_crit = _to_float(data["f_crit"], "f_crit")
    return experiments, g_crit, t_crit, f_crit


# Чтение JSON-файла с входными данными.
def read_input_json(path: Path) -> Tuple[List[Experiment], float, float, float]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return _parse_input_data(data)


# Итератор по строкам Excel без зависимостей от структуры листа.
def _iter_rows(ws: "openpyxl.worksheet.worksheet.Worksheet") -> Iterable[List[object]]:  # type: ignore[name-defined]
    for row in ws.iter_rows(values_only=True):
        yield list(row)


# Чтение листа с экспериментами: первая строка — заголовки.
def _read_experiments_sheet(ws: "openpyxl.worksheet.worksheet.Worksheet") -> List[Dict[str, object]]:  # type: ignore[name-defined]
    rows = list(_iter_rows(ws))
    if not rows:
        raise ValueError("Excel sheet is empty.")

    header_row = rows[0]
    column_map: Dict[int, str] = {}
    for idx, cell in enumerate(header_row):
        key = _HEADER_MAP.get(_normalize_header(cell))
        if key:
            column_map[idx] = key

    missing = [key for key in EXPECTED_COLUMNS if key not in column_map.values()]
    if missing:
        missing_str = ", ".join(missing)
        raise ValueError(f"Excel header missing columns: {missing_str}.")

    experiments: List[Dict[str, object]] = []
    for row in rows[1:]:
        if all(cell is None or str(cell).strip() == "" for cell in row):
            continue
        item: Dict[str, object] = {}
        for col_idx, key in column_map.items():
            item[key] = row[col_idx] if col_idx < len(row) else None
        experiments.append(item)
    return experiments


# Чтение критериев (G/T/F) из отдельного листа или из пары "ключ-значение".
def _read_criteria_from_sheet(
    ws: "openpyxl.worksheet.worksheet.Worksheet",
) -> Dict[str, object]:  # type: ignore[name-defined]
    rows = list(_iter_rows(ws))
    if not rows:
        return {}

    header = rows[0]
    header_map: Dict[int, str] = {}
    for idx, cell in enumerate(header):
        key = _CRIT_MAP.get(_normalize_header(cell))
        if key:
            header_map[idx] = key

    if header_map and len(rows) > 1:
        data_row = rows[1]
        data: Dict[str, object] = {}
        for col_idx, key in header_map.items():
            if col_idx < len(data_row):
                data[key] = data_row[col_idx]
        if set(data.keys()) == set(_CRIT_ALIASES.keys()):
            return data

    data: Dict[str, object] = {}
    for row in rows:
        if not row:
            continue
        key = _CRIT_MAP.get(_normalize_header(row[0]))
        if key and len(row) > 1:
            data[key] = row[1]
    return data


# Чтение Excel-файла и приведение к общему формату входных данных.
def read_input_xlsx(path: Path) -> Tuple[List[Experiment], float, float, float]:
    if openpyxl is None:
        raise RuntimeError("openpyxl is required for Excel import. Install it with: python -m pip install openpyxl")

    wb = openpyxl.load_workbook(path, data_only=True)
    exp_ws = wb["experiments"] if "experiments" in wb.sheetnames else wb.active
    experiments = _read_experiments_sheet(exp_ws)

    crit_ws = None
    if "criteria" in wb.sheetnames:
        crit_ws = wb["criteria"]
    elif "crit" in wb.sheetnames:
        crit_ws = wb["crit"]

    crit_data = _read_criteria_from_sheet(crit_ws) if crit_ws is not None else {}
    if not crit_data:
        crit_data = _read_criteria_from_sheet(exp_ws)

    missing = [key for key in _CRIT_ALIASES.keys() if key not in crit_data]
    if missing:
        missing_str = ", ".join(missing)
        raise ValueError(f"Excel input missing criteria: {missing_str}.")

    data: Dict[str, Any] = {
        "experiments": experiments,
        "g_crit": crit_data["g_crit"],
        "t_crit": crit_data["t_crit"],
        "f_crit": crit_data["f_crit"],
    }
    return _parse_input_data(data)


# Унифицированный вход: JSON или Excel.
def read_input_file(path: Path) -> Tuple[List[Experiment], float, float, float]:
    ext = path.suffix.lower()
    if ext == ".json":
        return read_input_json(path)
    if ext in {".xlsx", ".xlsm"}:
        return read_input_xlsx(path)
    raise ValueError(f"Unsupported input format: {path.suffix}")


# Основной расчет: формулы и критерии по исходным данным.
def compute(experiments: List[Experiment], g_crit: float, t_crit: float, f_crit: float) -> Dict[str, Any]:
    if len(experiments) != 4:
        raise ValueError("Expected exactly 4 experiments.")

    # Нормированные факторы и средние отклики.
    z1 = [e.z1 for e in experiments]
    z2 = [e.z2 for e in experiments]
    y_avg = [e.y_avg for e in experiments]

    # Коэффициенты в кодированных переменных (δ1, δ2).
    b0_coded = sum(y_avg) / 4
    b1_coded = (-y_avg[0] - y_avg[1] + y_avg[2] + y_avg[3]) / 4
    b2_coded = (-y_avg[0] + y_avg[1] - y_avg[2] + y_avg[3]) / 4

    # Средние и масштабы для перехода в "натуральные" коэффициенты.
    z1_avg = sum(z1) / 4
    z2_avg = sum(z2) / 4
    pz1 = z1_avg - min(z1)
    pz2 = max(z2) - z2_avg

    # Оценка дельт на основе нормированных факторов.
    delta1_calc = safe_div(z1[0] - z1_avg, pz1, "delta1_calc")
    delta2_calc = safe_div(z2[0] - z2_avg, pz2, "delta2_calc")

    # Критерий Граббса: проверка выбросов по повторностям.
    squares: List[float] = []
    g_tests: List[Dict[str, Any]] = []
    for i, exp in enumerate(experiments):
        deviations = [(y_avg[i] - y) ** 2 for y in exp.y_values]
        sum_sq = sum(deviations)
        g_val = safe_div(max(deviations), sum_sq, "G") if sum_sq != 0 else 0.0
        g_ok = "OK" if g_val < g_crit else "not OK"
        g_tests.append({"row": exp.idx, "g": g_val, "ok": g_ok})
        squares.extend(deviations)

    # Оценка дисперсий для t-критерия.
    s2_vos = sum(squares) / 8
    s_v = math.sqrt(s2_vos / 12)

    # Коэффициенты в "натуральных" переменных (v) и их t-статистики.
    b0_natural = (b0_coded - b1_coded * z1_avg / pz1 - b2_coded * z2_avg / pz2)
    b1_natural = b1_coded / pz1
    b2_natural = b2_coded / pz2

    t0 = abs(b0_natural) / s_v
    t1 = abs(b1_natural) / s_v
    t2 = abs(b2_natural) / s_v

    sign_b0 = "+" if t0 > t_crit else " -"
    sign_b1 = "+" if t1 > t_crit else " -"
    sign_b2 = "+" if t2 > t_crit else " -"

    # Формирование предсказаний с учетом значимых коэффициентов.
    output_rows: List[Dict[str, float]] = []
    for exp, y in zip(experiments, y_avg):
        y_pred = 0.0
        if sign_b0 == "+":
            y_pred += b0_coded
        if sign_b1 == "+":
            y_pred += b1_coded * exp.delta1
        if sign_b2 == "+":
            y_pred += b2_coded * exp.delta2
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

    # Критерий Фишера.
    f_avg = sum(r["y_avg_minus_y_sq"] for r in output_rows) / 4
    f_value = safe_div(s2_vos, f_avg, "F") if f_avg != 0 else float("inf")
    f_result_code = "not_rejected" if f_value < f_crit else "rejected"
    f_result = "Hypothesis not rejected" if f_result_code == "not_rejected" else "Hypothesis rejected"

    return {
        "coefficients": {"b0": _round3(b0_coded), "b1": _round3(b1_coded), "b2": _round3(b2_coded)},
        "coefficients_v": {"b0": _round3(b0_natural), "b1": _round3(b1_natural), "b2": _round3(b2_natural)},
        "z_averages": {"z1_avg": _round3(z1_avg), "z2_avg": _round3(z2_avg)},
        "pz": {"pz1": _round3(pz1), "pz2": _round3(pz2)},
        "delta_calc": {"delta1": _round3(delta1_calc), "delta2": _round3(delta2_calc)},
        "g_tests": [{"row": g["row"], "g": _round3(g["g"]), "ok": g["ok"]} for g in g_tests],
        "t_tests": {
            "t0": _round3(t0),
            "t1": _round3(t1),
            "t2": _round3(t2),
            "sign_b0": sign_b0,
            "sign_b1": sign_b1,
            "sign_b2": sign_b2,
        },
        "output_rows": output_rows,
        "f_avg": _round3(f_avg),
        "f_value": _round3(f_value),
        "f_result_code": f_result_code,
        "f_result": f_result,
        "g_crit": _round3(g_crit),
        "t_crit": _round3(t_crit),
        "f_crit": _round3(f_crit),
    }
