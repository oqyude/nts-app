from __future__ import annotations

import json
import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Dict, List, Tuple, TypedDict

try:
    import openpyxl
    from openpyxl.worksheet.worksheet import Worksheet
except Exception:
    openpyxl = None
    Worksheet = None  # type: ignore[assignment,misc]


# Размерность плана (Методичка §3): 2² дизайн, m=3 параллельных опыта.
EXPECTED_EXPERIMENTS: int = 4
PARALLEL_TRIALS: int = 3
DELTA1_SIGNATURE: Tuple[int, ...] = (-1, -1, 1, 1)
DELTA2_SIGNATURE: Tuple[int, ...] = (-1, 1, -1, 1)


class GTest(TypedDict):
    row: int
    g: float
    ok: str


class TTests(TypedDict):
    t0: float
    t1: float
    t2: float
    sign_b0: str
    sign_b1: str
    sign_b2: str


class CoeffsDict(TypedDict):
    b0: float
    b1: float
    b2: float


class ScalarsDict(TypedDict):
    z1_avg: float
    z2_avg: float


class PairsDict(TypedDict):
    pz1: float
    pz2: float


class DeltaCalcDict(TypedDict):
    delta1: float
    delta2: float


class OutputRow(TypedDict):
    y_avg: float
    delta1: float
    delta2: float
    y_pred: float
    y_avg_minus_y: float
    y_avg_minus_y_sq: float


class ComputeResult(TypedDict, total=False):
    """Контракт результата ``compute()``. Методичка §3."""
    coefficients: CoeffsDict
    coefficients_v: CoeffsDict
    z_averages: ScalarsDict
    pz: PairsDict
    delta_calc: DeltaCalcDict
    g_tests: List[GTest]
    t_tests: TTests
    output_rows: List[OutputRow]
    f_avg: float
    f_value: float
    f_result_code: str
    f_result: str
    equation: str
    g_crit: float
    t_crit: float
    f_crit: float


@dataclass(frozen=True)
class InputData:
    """Входные данные, единый формат (JSON и Excel)."""
    experiments: List["Experiment"]
    g_crit: float
    t_crit: float
    f_crit: float


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
        return sum(self.y_values) / PARALLEL_TRIALS


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
    if not math.isfinite(value):
        return value
    return float(Decimal(str(value)).quantize(Decimal("0.000"), rounding=ROUND_HALF_UP))


def fmt3(value: float) -> str:
    """Format a float to 3 decimal places, trim trailing zeros."""
    return f"{value:.3f}".rstrip("0").rstrip(".")


def format_equation(b0: float, b1: float, b2: float, delta1_sym: str, delta2_sym: str) -> str:
    """Format ``Y = b0 + b1·δ1 + b2·δ2`` from **coded** coefficients (Методичка §3, ф-ла 3.3).

    Pass ``0.0`` for any coefficient whose t-test failed (it will be omitted from the
    string instead of rendering as ``+ 0*δ``).
    """
    parts: List[str] = [f"Y = {fmt3(b0)}"]
    for value, name in ((b1, delta1_sym), (b2, delta2_sym)):
        if value == 0:
            continue
        sign = "+" if value >= 0 else "-"
        parts.append(f"{sign} {fmt3(abs(value))}*{name}")
    return " ".join(parts)


# Ожидаемые столбцы таблицы экспериментов.
EXPECTED_COLUMNS: List[str] = ["idx", "delta1", "delta2", "x1", "x2", "x3", "y1", "y2", "y3"]

# Допустимые имена колонок (Excel) с небольшими вариациями.
_HEADER_ALIASES: Dict[str, List[str]] = {
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
_CRIT_ALIASES: Dict[str, List[str]] = {
    "g_crit": ["g_crit", "gcrit", "g-crit", "g crit"],
    "t_crit": ["t_crit", "tcrit", "t-crit", "t crit"],
    "f_crit": ["f_crit", "fcrit", "f-crit", "f crit"],
}


def _normalize_header(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    return text.replace(" ", "").replace("_", "").replace("-", "")


_HEADER_MAP: Dict[str, str] = {
    _normalize_header(alias): key
    for key, aliases in _HEADER_ALIASES.items()
    for alias in aliases
}

_CRIT_MAP: Dict[str, str] = {
    _normalize_header(alias): key
    for key, aliases in _CRIT_ALIASES.items()
    for alias in aliases
}


def _parse_input_data(data: Dict[str, Any]) -> InputData:
    """Parse already-validated dict (от JSON или Excel) в InputData."""
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
    return InputData(
        experiments=experiments,
        g_crit=_to_float(data["g_crit"], "g_crit"),
        t_crit=_to_float(data["t_crit"], "t_crit"),
        f_crit=_to_float(data["f_crit"], "f_crit"),
    )


def read_input_json(path: Path) -> InputData:
    data = json.loads(path.read_text(encoding="utf-8"))
    return _parse_input_data(data)


def _iter_rows(ws: Worksheet) -> List[List[Any]]:
    return [list(row) for row in ws.iter_rows(values_only=True)]


def _read_experiments_sheet(ws: Worksheet) -> List[Dict[str, Any]]:
    rows = _iter_rows(ws)
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
        raise ValueError(f"Excel header missing columns: {', '.join(missing)}.")

    experiments: List[Dict[str, Any]] = []
    for row in rows[1:]:
        if all(cell is None or str(cell).strip() == "" for cell in row):
            continue
        item: Dict[str, Any] = {
            key: row[col_idx] if col_idx < len(row) else None
            for col_idx, key in column_map.items()
        }
        experiments.append(item)
    return experiments


def _read_criteria_from_sheet(ws: Worksheet) -> Dict[str, Any]:
    rows = _iter_rows(ws)
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
        data: Dict[str, Any] = {
            key: data_row[col_idx]
            for col_idx, key in header_map.items()
            if col_idx < len(data_row)
        }
        if set(data.keys()) == set(_CRIT_ALIASES.keys()):
            return data

    data: Dict[str, Any] = {}
    for row in rows:
        if not row:
            continue
        key = _CRIT_MAP.get(_normalize_header(row[0]))
        if key and len(row) > 1:
            data[key] = row[1]
    return data


def read_input_xlsx(path: Path) -> InputData:
    if openpyxl is None or Worksheet is None:
        raise RuntimeError(
            "openpyxl is required for Excel import. Install it with: python -m pip install openpyxl"
        )

    wb = openpyxl.load_workbook(path, data_only=True)
    exp_ws = wb["experiments"] if "experiments" in wb.sheetnames else wb.active
    experiments = _read_experiments_sheet(exp_ws)

    crit_ws: Worksheet | None = None
    if "criteria" in wb.sheetnames:
        crit_ws = wb["criteria"]
    elif "crit" in wb.sheetnames:
        crit_ws = wb["crit"]

    crit_data = _read_criteria_from_sheet(crit_ws) if crit_ws is not None else {}
    if not crit_data:
        crit_data = _read_criteria_from_sheet(exp_ws)

    missing = [key for key in _CRIT_ALIASES if key not in crit_data]
    if missing:
        raise ValueError(f"Excel input missing criteria: {', '.join(missing)}.")

    return _parse_input_data({
        "experiments": experiments,
        "g_crit": crit_data["g_crit"],
        "t_crit": crit_data["t_crit"],
        "f_crit": crit_data["f_crit"],
    })


def read_input_file(path: Path) -> InputData:
    ext = path.suffix.lower()
    if ext == ".json":
        return read_input_json(path)
    if ext in {".xlsx", ".xlsm"}:
        return read_input_xlsx(path)
    raise ValueError(f"Unsupported input format: {path.suffix}")


def _coded_coefficients(y_avg: List[float]) -> Tuple[float, float, float]:
    """b0, b1, b2 в кодированных переменных (δ1, δ2) для ортогонального 2² плана."""
    n = len(y_avg)
    b0 = sum(y_avg) / n
    b1 = sum(s * y for s, y in zip(DELTA1_SIGNATURE, y_avg)) / n
    b2 = sum(s * y for s, y in zip(DELTA2_SIGNATURE, y_avg)) / n
    return b0, b1, b2


def _scaling_factors(z1: List[float], z2: List[float], n: int) -> Tuple[float, float, float, float, float, float]:
    z1_avg = sum(z1) / n
    z2_avg = sum(z2) / n
    return z1_avg, z2_avg, z1_avg - min(z1), max(z2) - z2_avg, z1[0] - z1_avg, z2[0] - z2_avg


def _natural_coefficients(
    b_coded: Tuple[float, float, float],
    z1_avg: float,
    z2_avg: float,
    pz1: float,
    pz2: float,
) -> Tuple[float, float, float]:
    b0, b1, b2 = b_coded
    return (
        b0 - b1 * z1_avg / pz1 - b2 * z2_avg / pz2,
        b1 / pz1,
        b2 / pz2,
    )


def _grubbs_block(experiments: List[Experiment], y_avg: List[float], g_crit: float) -> Tuple[List[GTest], List[float]]:
    """Returns (g_tests, all squared deviations)."""
    g_tests: List[GTest] = []
    squares: List[float] = []
    for i, exp in enumerate(experiments):
        deviations = [(y_avg[i] - y) ** 2 for y in exp.y_values]
        sum_sq = sum(deviations)
        g_val = safe_div(max(deviations), sum_sq, "G") if sum_sq != 0 else 0.0
        g_tests.append(GTest(row=exp.idx, g=g_val, ok="OK" if g_val < g_crit else "not OK"))
        squares.extend(deviations)
    return g_tests, squares


def _student_block(b_natural: Tuple[float, float, float], s_v: float) -> Tuple[float, float, float]:
    """Student t по **натуральным** (v) коэффициентам. При s_v = 0 ненулевые b → inf.

    Базируется на эталоне Excel (.temp/расчет.xlsx), не на Методичке §3.
    См. .agent/context/calculation-diff.md.
    """
    b0, b1, b2 = b_natural
    if s_v > 0:
        return abs(b0) / s_v, abs(b1) / s_v, abs(b2) / s_v
    return (
        float("inf") if b0 else 0.0,
        float("inf") if b1 else 0.0,
        float("inf") if b2 else 0.0,
    )


def _significance_marks(t_values: Tuple[float, float, float], t_crit: float) -> Tuple[str, str, str]:
    return tuple("+" if t > t_crit else "-" for t in t_values)


def _output_rows(experiments: List[Experiment], y_avg: List[float], b_coded: Tuple[float, float, float], signs: Tuple[str, str, str]) -> List[OutputRow]:
    rows: List[OutputRow] = []
    for exp, y in zip(experiments, y_avg):
        y_pred = 0.0
        if signs[0] == "+":
            y_pred += b_coded[0]
        if signs[1] == "+":
            y_pred += b_coded[1] * exp.delta1
        if signs[2] == "+":
            y_pred += b_coded[2] * exp.delta2
        y_res = y - y_pred
        rows.append(OutputRow(
            y_avg=y,
            delta1=exp.delta1,
            delta2=exp.delta2,
            y_pred=y_pred,
            y_avg_minus_y=y_res,
            y_avg_minus_y_sq=y_res ** 2,
        ))
    return rows


def _fisher_block(s2_vos: float, output_rows: List[OutputRow], n: int, f_crit: float) -> Tuple[float, float, str, str]:
    f_avg = sum(r["y_avg_minus_y_sq"] for r in output_rows) / n
    f_value = safe_div(s2_vos, f_avg, "F") if f_avg != 0 else float("inf")
    code = "not_rejected" if f_value < f_crit else "rejected"
    text = "Hypothesis not rejected" if code == "not_rejected" else "Hypothesis rejected"
    return f_avg, f_value, code, text


def compute(input_data: InputData) -> ComputeResult:
    """Full factorial 2² analysis with parallel trials.

    Variable map (per Excel reference ``.temp/расчет.xlsx``; differs from
    Методичка.docx §3 — see ``.agent/context/calculation-diff.md``):

    ============= ==============================================================
    Symbol         Meaning
    ============= ==============================================================
    ``x1,x2,x3``   component shares (% water, binder, filler), ``Σ = 100%``
    ``z1 = x1/x2`` water/binder ratio
    ``z2 = x3/x2`` filler/binder ratio
    ``δ1, δ2``     coded factors ∈ {-1, +1}  (``Experiment.delta1/delta2``)
    ``y1,y2,y3``   three parallel trials; ``y_avg = (y1+y2+y3)/3``
    ``N = 4``      plan points (2² design); ``m = 3`` parallel trials
    ``s²_вос``     ``Σ(y_ij − ȳ_i)² / N(m−1)``, df = 8
    ``S_в``        ``√(s²_вос / (N·m))`` — divisor uses N·m (Excel convention)
    ``t_i``        ``|b_i_v| / S_в`` — Student on NATURAL (v) coeffs
    ``G``          Grubbs per experiment; ``G < G_cr`` ⇒ однородность
    ``F``          ``s²_вос / (Σ_resid² / N)`` — adequacy check, inverted
                   ratio, no df adjustment (per Excel reference)
    ============= ==============================================================
    """
    experiments = input_data.experiments
    if len(experiments) != EXPECTED_EXPERIMENTS:
        raise ValueError(
            f"Expected exactly {EXPECTED_EXPERIMENTS} experiments, got {len(experiments)}."
        )
    n = EXPECTED_EXPERIMENTS
    g_crit, t_crit, f_crit = input_data.g_crit, input_data.t_crit, input_data.f_crit

    z1 = [e.z1 for e in experiments]
    z2 = [e.z2 for e in experiments]
    y_avg = [e.y_avg for e in experiments]

    b_coded = _coded_coefficients(y_avg)
    z1_avg, z2_avg, pz1, pz2, dz1, dz2 = _scaling_factors(z1, z2, n)
    b_natural = _natural_coefficients(b_coded, z1_avg, z2_avg, pz1, pz2)

    g_tests, squares = _grubbs_block(experiments, y_avg, g_crit)
    s2_vos = sum(squares) / (n * (PARALLEL_TRIALS - 1))
    s_v = math.sqrt(s2_vos / (n * PARALLEL_TRIALS)) if s2_vos > 0 else 0.0

    t_values = _student_block(b_natural, s_v)
    signs = _significance_marks(t_values, t_crit)

    out_rows = _output_rows(experiments, y_avg, b_coded, signs)
    f_avg, f_value, f_code, f_text = _fisher_block(s2_vos, out_rows, n, f_crit)

    equation = format_equation(
        b_coded[0] if signs[0] == "+" else 0.0,
        b_coded[1] if signs[1] == "+" else 0.0,
        b_coded[2] if signs[2] == "+" else 0.0,
        "δ1", "δ2",
    )

    return ComputeResult(
        coefficients=CoeffsDict(b0=_round3(b_coded[0]), b1=_round3(b_coded[1]), b2=_round3(b_coded[2])),
        coefficients_v=CoeffsDict(b0=_round3(b_natural[0]), b1=_round3(b_natural[1]), b2=_round3(b_natural[2])),
        z_averages=ScalarsDict(z1_avg=_round3(z1_avg), z2_avg=_round3(z2_avg)),
        pz=PairsDict(pz1=_round3(pz1), pz2=_round3(pz2)),
        delta_calc=DeltaCalcDict(
            delta1=_round3(safe_div(dz1, pz1, "delta1_calc")),
            delta2=_round3(safe_div(dz2, pz2, "delta2_calc")),
        ),
        g_tests=[GTest(row=g["row"], g=_round3(g["g"]), ok=g["ok"]) for g in g_tests],
        t_tests=TTests(
            t0=_round3(t_values[0]),
            t1=_round3(t_values[1]),
            t2=_round3(t_values[2]),
            sign_b0=signs[0],
            sign_b1=signs[1],
            sign_b2=signs[2],
        ),
        output_rows=out_rows,
        f_avg=_round3(f_avg),
        f_value=_round3(f_value),
        f_result_code=f_code,
        f_result=f_text,
        equation=equation,
        g_crit=_round3(g_crit),
        t_crit=_round3(t_crit),
        f_crit=_round3(f_crit),
    )
