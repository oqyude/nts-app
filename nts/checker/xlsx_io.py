"""Чтение и запись эталонной книги самопроверки (Excel).

Листы: ``input`` (опыты), ``criteria`` (критерии), ``result`` (ядро,
вертикально ``key``/``value``/``description``), ``extended`` (остальные ключи,
опциональный), ``grubbs``, ``output_rows`` и ``dictionary``.

Цвет в формате — только метка: ядро определяется списком
:data:`nts.checker.model.CORE_RESULT_KEYS` и именем листа, заливка нигде не
читается.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from ..core import ComputeResult, InputData, _parse_input_data
from ..dictionary import DESCRIPTIONS, describe
from ..i18n import (
    DEFAULT_LANGUAGE,
    canonical_check_value,
    localize_check_value,
    normalize_lang,
)
from .model import (
    CORE_FILL_RGB,
    CORE_RESULT_KEYS,
    DESCRIPTION_COLUMN,
    DICTIONARY_SHEET_NAME,
    EXTENDED_SHEET_NAME,
    MODE_FULL,
    MODE_SIMPLIFIED,
    SelfCheckBundle,
)


# ---- self-check xlsx loader + writer ------------------------------


_REQUIRED_SELF_CHECK_SHEETS: tuple[str, ...] = ("input", "criteria", "result")


def _require_openpyxl() -> Any:
    """Import openpyxl or raise a clear :class:`RuntimeError`."""
    try:
        import openpyxl  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "openpyxl is required for Excel self-check files. "
            "Install it with: python -m pip install openpyxl"
        ) from exc
    return openpyxl


def _read_xlsx_sheet_rows(wb: Any, name: str) -> List[List[Any]]:
    """Read ``wb[name]`` as a list of cell-value rows. Raises if sheet is missing."""
    if name not in wb.sheetnames:
        raise ValueError(
            f"self-check workbook missing required sheet {name!r}; "
            f"found sheets: {wb.sheetnames}"
        )
    ws = wb[name]
    return [list(row) for row in ws.iter_rows(values_only=True)]


def _parse_xlsx_sheet_to_dict(rows: List[List[Any]]) -> List[Dict[str, Any]]:
    """Treat first row as header and remaining non-blank rows as records."""
    if not rows:
        return []
    header = [str(c).strip() if c is not None else "" for c in rows[0]]
    out: List[Dict[str, Any]] = []
    for raw in rows[1:]:
        if all(c is None or str(c).strip() == "" for c in raw):
            continue
        record: Dict[str, Any] = {}
        for i, key in enumerate(header):
            if not key:
                continue
            record[key] = raw[i] if i < len(raw) else None
        out.append(record)
    return out


def _read_xlsx_criteria(wb: Any) -> Dict[str, float]:
    """Read the ``criteria`` sheet.

    Accepts both layouts produced by :func:`nts.core._read_criteria_from_sheet`:
    a header row of ``g_crit,t_crit,f_crit`` followed by one value row, **or**
    bare key/value pairs (e.g. ``A1='g_crit', B1=0.7679``). The first matching
    layout wins.
    """
    rows = _read_xlsx_sheet_rows(wb, "criteria")
    if not rows:
        raise ValueError("self-check workbook 'criteria' sheet is empty")

    header = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
    if "g_crit" in header and "t_crit" in header and "f_crit" in header:
        if len(rows) < 2:
            raise ValueError(
                "self-check workbook 'criteria' sheet has header but no value row"
            )
        value_row = rows[1]
        return {
            "g_crit": float(value_row[header.index("g_crit")]),
            "t_crit": float(value_row[header.index("t_crit")]),
            "f_crit": float(value_row[header.index("f_crit")]),
        }

    crit: Dict[str, float] = {}
    for raw in rows:
        if not raw or raw[0] is None:
            continue
        key = str(raw[0]).strip().lower()
        if key in {"g_crit", "t_crit", "f_crit"} and len(raw) > 1 and raw[1] is not None:
            crit[key] = float(raw[1])
    if set(crit.keys()) != {"g_crit", "t_crit", "f_crit"}:
        missing = {"g_crit", "t_crit", "f_crit"} - set(crit.keys())
        raise ValueError(
            f"self-check workbook 'criteria' sheet missing keys: {sorted(missing)}"
        )
    return crit


def _parse_xlsx_result_sheet(rows: List[List[Any]]) -> Dict[str, Any]:
    """Rebuild a ``ComputeResult``-shaped ``dict`` from a vertical ``(key,value)`` sheet.

    Top-level scalars are stored as dotted-path keys (``equation``, ``f_value``,
    ``coefficients.b0``, ``t_tests.sign_b0``, ...). Returns the in-progress dict;
    the caller is responsible for attaching ``g_tests`` and ``output_rows``.
    """
    if len(rows) < 2:
        raise ValueError("self-check workbook 'result' sheet is empty")
    header = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
    if "key" not in header or "value" not in header:
        raise ValueError(
            "self-check workbook 'result' sheet must have a header row 'key, value'"
        )
    key_idx = header.index("key")
    val_idx = header.index("value")

    result: Dict[str, Any] = {}
    for raw in rows[1:]:
        if all(c is None or str(c).strip() == "" for c in raw):
            continue
        key = raw[key_idx]
        value = raw[val_idx] if val_idx < len(raw) else None
        if key is None or str(key).strip() == "":
            continue
        path = str(key).strip()
        _set_dotted(result, path, value)
    return result


def _set_dotted(target: Dict[str, Any], path: str, value: Any) -> None:
    """Insert ``value`` at ``target[parts[0]][parts[1]]...`` for a dotted key.

    For top-level scalars (``equation``, ``f_value``, ...) the value lands at
    ``target[path]``. Numeric cells are coerced to ``float``; the criterion
    keys (``g_crit``, ``t_crit``, ``f_crit``) and the discrete string fields
    (``equation``, ``f_result_code``, ``f_result``, ``t_tests.sign_*``) keep
    their native type. Booleans (rare) are kept as-is. A localized ``f_result``
    verdict is mapped back to its canonical English form.
    """
    parts = path.split(".")
    value = _coerce_scalar(value)
    if path == "f_result":
        value = canonical_check_value(path, value)
    if len(parts) == 1:
        target[parts[0]] = value
        return
    group = parts[0]
    sub_key = parts[1]
    if group not in target or not isinstance(target.get(group), dict):
        target[group] = {}
    target[group][sub_key] = value


def _coerce_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return None
        try:
            return float(text)
        except ValueError:
            return text
    return value


def parse_self_check_xlsx(path: Path) -> tuple[InputData, ComputeResult]:
    """Load a self-check workbook. Returns ``(input_data, expected_result)``.

    Required sheets (in any order, but the first three are mandatory):

    * ``input``       — header ``idx, delta1, delta2, x1, x2, x3, y1, y2, y3``
                        and 4 data rows (consumed by
                        :func:`nts.core._parse_input_data`).
    * ``criteria``    — either ``g_crit,t_crit,f_crit`` header + 1 value row,
                        or bare key/value pairs ``A=g_crit,B=0.7679``, ...
    * ``result``      — vertical ``(key, value)`` table with the **core** keys;
                        dotted paths such as ``coefficients.b0`` rebuild the
                        nested :class:`ComputeResult`.
    * ``extended``    — optional vertical ``(key, value)`` table with the
                        non-core result keys. Its presence declares full
                        coverage (strict mode); without it the workbook is a
                        complete check on its own (simplified mode).
    * ``grubbs``      — header ``row,G,ok`` + 4 rows. Optional but expected;
                        an empty sheet is treated as missing.
    * ``output_rows`` — header
                        ``delta1,delta2,y_avg,y_pred,y_avg_minus_y,y_avg_minus_y_sq``
                        + 4 rows. Optional; an empty sheet is treated as missing.

    Raises ``ValueError`` when a required sheet is absent or malformed.
    Raises ``FileNotFoundError`` when ``path`` does not exist.
    """
    bundle = load_xlsx_bundle(path)
    return bundle.input_data, cast(ComputeResult, bundle.expected)


def _merge_expected(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    """Merge ``extra`` into ``base``, merging nested groups key-by-key.

    A dotted key such as ``t_tests.sign_b0`` lands in a nested group; a plain
    ``dict.update`` would drop the sibling keys of that group (``t_tests.t0``),
    so groups are merged instead of replaced.
    """
    for key, value in extra.items():
        current = base.get(key)
        if isinstance(value, dict) and isinstance(current, dict):
            base[key] = {**current, **value}
        else:
            base[key] = value
    return base


def load_xlsx_bundle(path: Path) -> SelfCheckBundle:
    """Parse a self-check workbook into a :class:`SelfCheckBundle`."""
    openpyxl = _require_openpyxl()
    wb = openpyxl.load_workbook(str(path), data_only=True)

    for sheet_name in _REQUIRED_SELF_CHECK_SHEETS:
        if sheet_name not in wb.sheetnames:
            raise ValueError(
                f"self-check workbook missing required sheet {sheet_name!r}; "
                f"found sheets: {wb.sheetnames}"
            )

    input_records = _parse_xlsx_sheet_to_dict(_read_xlsx_sheet_rows(wb, "input"))
    if not input_records:
        raise ValueError("self-check workbook 'input' sheet has no data rows")

    crit = _read_xlsx_criteria(wb)

    input_dict: Dict[str, Any] = {
        "experiments": input_records,
        "g_crit": crit["g_crit"],
        "t_crit": crit["t_crit"],
        "f_crit": crit["f_crit"],
    }
    input_data = _parse_input_data(input_dict)

    result_rows = _read_xlsx_sheet_rows(wb, "result")
    expected: Dict[str, Any] = _parse_xlsx_result_sheet(result_rows)

    has_extended = EXTENDED_SHEET_NAME in wb.sheetnames
    if has_extended:
        extended_rows = _read_xlsx_sheet_rows(wb, EXTENDED_SHEET_NAME)
        _merge_expected(expected, _parse_xlsx_result_sheet(extended_rows))

    if "grubbs" in wb.sheetnames:
        grubbs_records = _parse_xlsx_sheet_to_dict(_read_xlsx_sheet_rows(wb, "grubbs"))
        if grubbs_records:
            expected["g_tests"] = [
                {
                    "row": int(float(rec["row"])),
                    "g": float(rec["G"]),
                    "ok": canonical_check_value("g_tests.row.ok", str(rec["ok"])),
                }
                for rec in grubbs_records
                if rec.get("row") is not None
            ]

    if "output_rows" in wb.sheetnames:
        out_records = _parse_xlsx_sheet_to_dict(_read_xlsx_sheet_rows(wb, "output_rows"))
        if out_records:
            expected["output_rows"] = [
                {
                    "delta1": float(rec["delta1"]),
                    "delta2": float(rec["delta2"]),
                    "y_avg": float(rec["y_avg"]),
                    "y_pred": float(rec["y_pred"]),
                    "y_avg_minus_y": float(rec["y_avg_minus_y"]),
                    "y_avg_minus_y_sq": float(rec["y_avg_minus_y_sq"]),
                }
                for rec in out_records
            ]

    return SelfCheckBundle(
        input_data=input_data,
        expected=expected,
        mode=MODE_FULL if has_extended else MODE_SIMPLIFIED,
    )


def _core_fill() -> Any:
    """Yellow fill marking a core cell (matches the reference workbook)."""
    from openpyxl.styles import PatternFill

    return PatternFill(
        fill_type="solid",
        start_color=CORE_FILL_RGB,
        end_color=CORE_FILL_RGB,
    )


def write_self_check_xlsx(
    path: Path,
    input_data: InputData,
    result: ComputeResult,
    *,
    lang: str = DEFAULT_LANGUAGE,
    localize_values: bool = False,
) -> Path:
    """Write a self-check workbook in the same layout :func:`parse_self_check_xlsx` reads.

    Schema matches what the regular GUI's "Export to Excel" button emits
    (:meth:`nts.gui.App._export_xlsx`), so a file round-tripped through either
    tool is interchangeable. Returns the same ``path`` for chaining.

    The ``result`` sheet carries the **core** keys only (see
    :data:`CORE_RESULT_KEYS`), marked with a yellow fill; every other result
    key goes to the optional ``extended`` sheet. Dropping the ``extended``
    sheet therefore leaves a complete — if narrower — check behind.

    Both key/value sheets carry a third ``description`` column with the human
    meaning of the variable (see :mod:`nts.dictionary`), written in ``lang``.
    The ``dictionary`` sheet lists every variable of the workbook — result
    keys and the column names of the other sheets — with its description.
    Human-facing discrete values (the Fisher verdict and the Grubbs status)
    are written in ``lang`` when ``localize_values`` is true; the reader maps
    them back to the canonical English form, so a Russian report stays
    interchangeable with an English one. The default (``False``) keeps the
    canonical values, which is what a reference workbook needs.
    """
    openpyxl = _require_openpyxl()
    wb = openpyxl.Workbook()
    ws_input = wb.active
    ws_input.title = "input"
    ws_input.append(["idx", "delta1", "delta2", "x1", "x2", "x3", "y1", "y2", "y3"])
    for exp in input_data.experiments:
        ws_input.append([
            exp.idx, exp.delta1, exp.delta2,
            exp.x1, exp.x2, exp.x3,
            exp.y1, exp.y2, exp.y3,
        ])

    ws_crit = wb.create_sheet("criteria")
    ws_crit.append(["g_crit", "t_crit", "f_crit"])
    ws_crit.append([input_data.g_crit, input_data.t_crit, input_data.f_crit])

    header = ["key", "value", DESCRIPTION_COLUMN]
    ws_res = wb.create_sheet("result")
    ws_res.append(header)
    ws_ext = wb.create_sheet(EXTENDED_SHEET_NAME)
    ws_ext.append(header)
    coeffs = result["coefficients"]
    coeffs_v = result["coefficients_v"]
    z_avg = result["z_averages"]
    pz = result["pz"]
    delta = result["delta_calc"]
    t_tests = result["t_tests"]

    rows: List[tuple[str, Any]] = []

    def _kv(prefix: str, mapping: Dict[str, Any]) -> None:
        for k, v in mapping.items():
            rows.append((f"{prefix}.{k}" if prefix else k, v))

    rows.append(("equation", result["equation"]))
    rows.append(("f_avg", result["f_avg"]))
    rows.append(("f_value", result["f_value"]))
    rows.append(("f_result_code", result["f_result_code"]))
    rows.append(("f_result", result["f_result"]))
    rows.append(("g_crit", result["g_crit"]))
    rows.append(("t_crit", result["t_crit"]))
    rows.append(("f_crit", result["f_crit"]))
    _kv("coefficients", coeffs)
    _kv("coefficients_v", coeffs_v)
    _kv("z_averages", z_avg)
    _kv("pz", pz)
    _kv("delta_calc", delta)
    rows.append(("t_tests.t0", t_tests["t0"]))
    rows.append(("t_tests.t1", t_tests["t1"]))
    rows.append(("t_tests.t2", t_tests["t2"]))
    rows.append(("t_tests.sign_b0", t_tests["sign_b0"]))
    rows.append(("t_tests.sign_b1", t_tests["sign_b1"]))
    rows.append(("t_tests.sign_b2", t_tests["sign_b2"]))

    fill = _core_fill()
    for key, value in rows:
        is_core = key in CORE_RESULT_KEYS
        ws = ws_res if is_core else ws_ext
        displayed = (
            localize_check_value(key, value, lang)
            if localize_values and key == "f_result"
            else value
        )
        ws.append([key, displayed, describe(key, lang)])
        if is_core:
            ws.cell(row=ws.max_row, column=2).fill = fill

    ws_g = wb.create_sheet("grubbs")
    ws_g.append(["row", "G", "ok"])
    for g in result["g_tests"]:
        status = (
            localize_check_value("g_tests.row.ok", g["ok"], lang)
            if localize_values
            else g["ok"]
        )
        ws_g.append([g["row"], g["g"], status])

    ws_o = wb.create_sheet("output_rows")
    ws_o.append([
        "delta1", "delta2", "y_avg",
        "y_pred", "y_avg_minus_y", "y_avg_minus_y_sq",
    ])
    for r in result["output_rows"]:
        ws_o.append([
            r["delta1"], r["delta2"], r["y_avg"],
            r["y_pred"], r["y_avg_minus_y"], r["y_avg_minus_y_sq"],
        ])

    ws_dict = wb.create_sheet(DICTIONARY_SHEET_NAME)
    ws_dict.append(["key", DESCRIPTION_COLUMN])
    table = DESCRIPTIONS.get(normalize_lang(lang), DESCRIPTIONS["EN"])
    for name, description in table.items():
        ws_dict.append([name, description])

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(path))
    return Path(path)


