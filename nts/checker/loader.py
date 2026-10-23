"""Загрузка файлов самопроверки: JSON и Excel.

Формат на входе — либо JSON с блоками ``input``/``expected``, либо книга
Excel (см. :mod:`nts.checker.xlsx_io`). Режим проверки выводится из файла:
книга с листом ``extended`` объявляет полное покрытие, остальные — ядро.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, cast

from ..core import ComputeResult, InputData, _parse_input_data
from .model import MODE_FULL, MODE_SIMPLIFIED, SelfCheckBundle
from .xlsx_io import load_xlsx_bundle


# ---- self-check JSON file loader -----------------------------------


def parse_self_check_bundle(path: Path) -> SelfCheckBundle:
    """Load a self-check file and resolve the verification mode it implies.

    Dispatches on extension:

    * ``.json`` — JSON payload shaped as ``{"input": ..., "expected": ...}``.
      The ``expected`` block is a complete payload, so the mode is
      :data:`MODE_FULL`.
    * ``.xlsx`` / ``.xlsm`` — self-check workbook (see
      :func:`parse_self_check_xlsx` for the layout). The mode is
      :data:`MODE_FULL` when the workbook carries an ``extended`` sheet (full
      coverage declared) and :data:`MODE_SIMPLIFIED` otherwise — a workbook
      without that sheet is a complete check on its own.

    Raises ``ValueError`` for JSON payloads that are not objects, are empty, or
    are missing the ``input`` or ``expected`` key. Raises ``FileNotFoundError``
    when the path does not exist. Underlying ``_parse_input_data`` errors
    propagate unchanged.
    """
    ext = path.suffix.lower()
    if ext == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("self-check file must be a JSON object")
        if not data:
            raise ValueError("self-check file must not be empty")
        if "input" not in data:
            raise ValueError("self-check file is missing 'input' key")
        if "expected" not in data:
            raise ValueError("self-check file is missing 'expected' key")
        input_data = _parse_input_data(data["input"])
        expected = cast(ComputeResult, data["expected"])
        return SelfCheckBundle(
            input_data=input_data,
            expected=cast(Dict[str, Any], expected),
            mode=MODE_FULL,
        )
    if ext in {".xlsx", ".xlsm"}:
        return load_xlsx_bundle(path)
    raise ValueError(
        f"unsupported self-check extension {ext!r} (expected .json, .xlsx or .xlsm)"
    )


def parse_self_check_file(path: Path) -> tuple[InputData, ComputeResult]:
    """Load a self-check file. Returns ``(input_data, expected_result)``.

    Dispatches on extension:

    * ``.json`` — JSON payload shaped as ``{"input": ..., "expected": ...}``.
    * ``.xlsx`` / ``.xlsm`` — self-check workbook (see
      :func:`parse_self_check_xlsx` for the layout).

    Both paths validate the ``input`` block via
    :func:`nts.core._parse_input_data`; the ``expected`` block is kept as a raw
    ``dict`` cast to :class:`nts.core.ComputeResult` (its fields are arbitrary,
    consumed only by :func:`verify`).

    Raises ``ValueError`` for JSON payloads that are not objects, are empty, or
    are missing the ``input`` or ``expected`` key. Raises ``FileNotFoundError``
    when the path does not exist. Underlying ``_parse_input_data`` errors
    propagate unchanged.
    """
    bundle = parse_self_check_bundle(path)
    return bundle.input_data, cast(ComputeResult, bundle.expected)


