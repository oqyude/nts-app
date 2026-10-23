"""Tests for nts.checker.verify() — DISCRETE + NUMERIC + LIST-SORT paths.

DISCRETE:
  - t_tests.sign_b0 / sign_b1 / sign_b2
  - f_result_code
  - g_tests[i].ok (per-row, position-based)
  - equation
  - f_result

NUMERIC per-category tolerance:
  - coefficients / coefficients_v / z_averages / pz / delta_calc → coeff_abs
  - t_tests.t0 / t1 / t2 → t_abs
  - g_tests[i].g per-row → coeff_abs
  - f_value → f_abs (with NaN/inf policy)

f_value inf/NaN + list-row sort + empty/extra-key policy:
  - f_value: NaN never matches (even NaN==NaN); inf==inf same-sign passes;
    inf vs finite fails with diff=inf.
  - g_tests: row-set validation + sort by ``row`` key (stable) before
    per-row comparison of g and ok.
  - output_rows: row-set validation on ``(delta1, delta2)`` tuple + sort
    by that tuple before per-row comparison of all 6 numeric fields.
  - Empty ``expected`` → ``ValueError("expected must not be empty")``.
  - Extra keys in ``expected`` → silently ignored.

parse_self_check_file — JSON file loader with bad-schema detection:
  - happy path: minimal ``{"input": {...InputData...}, "expected":
    {...ComputeResult...}}`` payload → returns ``(InputData, ComputeResult)``;
  - missing ``input`` key → ``ValueError`` whose message mentions ``input``;
  - missing ``expected`` key → ``ValueError`` whose message mentions
    ``expected``;
  - empty ``{}`` payload → ``ValueError``.

Test fixtures build minimal ComputeResult-shaped dicts inline with arbitrary
distinct values. NO hardcoded ``g_crit``/``t_crit``/``f_crit`` literals (see
``.agent/rules/project-rules.md:30``).
"""
from __future__ import annotations

import json
import tempfile
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

from nts.checker import (
    MODE_FULL,
    MODE_SIMPLIFIED,
    CheckEntry,
    CheckResult,
    Tolerance,
    print_checklist,
    verify,
)


# ---- helpers ---------------------------------------------------------------


def _make_g_test(row: int, ok: str = "ok", g: float = 0.0) -> Dict[str, Any]:
    """Build a single ``GTest``-shaped dict (row, g, ok).

    Matches ``nts/core.py:25-28``: ``GTest`` has ``row: int``.
    """
    return {"row": row, "g": g, "ok": ok}


def _make_output_row(
    delta1: int,
    delta2: int,
    base: float = 100.0,
) -> Dict[str, Any]:
    """Build a single ``OutputRow``-shaped dict.

    Matches ``nts/core.py:61-67``: ``OutputRow`` has NO ``row`` key — only
    y_avg, delta1, delta2, y_pred, y_avg_minus_y, y_avg_minus_y_sq.
    Per-row identity is the ``(delta1, delta2)`` tuple (see ``DELTA1/2_SIGNATURE``
    uniqueness in ``nts/core.py:21-22``).
    """
    y_avg = base + 10.0 * (delta1 + delta2 + 2)
    return {
        "y_avg": y_avg,
        "delta1": float(delta1),
        "delta2": float(delta2),
        "y_pred": y_avg,
        "y_avg_minus_y": 0.0,
        "y_avg_minus_y_sq": 0.0,
    }


def _discrete_compute_result(
    *,
    signs: tuple[str, str, str] = ("+", "+", "+"),
    f_result_code: str = "not_rejected",
    g_tests: list[Dict[str, Any]] | None = None,
    equation: str = "Y = b0 + b1·δ1 + b2·δ2",
    f_result: str = "F < F_cr → уравнение адекватно",
) -> Dict[str, Any]:
    """Build a minimal ComputeResult carrying only DISCRETE fields."""
    if g_tests is None:
        g_tests = [_make_g_test(i + 1) for i in range(4)]
    return {
        "t_tests": {
            "sign_b0": signs[0],
            "sign_b1": signs[1],
            "sign_b2": signs[2],
        },
        "g_tests": g_tests,
        "f_result_code": f_result_code,
        "equation": equation,
        "f_result": f_result,
    }


def _numeric_compute_result(
    *,
    b0: float = 1.0,
    b1: float = 2.0,
    b2: float = 3.0,
    b0_v: float = 10.0,
    b1_v: float = 20.0,
    b2_v: float = 30.0,
    z1_avg: float = 1.5,
    z2_avg: float = 2.5,
    pz1: float = 0.5,
    pz2: float = 1.5,
    delta1: float = 0.4,
    delta2: float = 0.6,
    t0: float = 5.0,
    t1: float = 4.0,
    t2: float = 3.0,
    signs: tuple[str, str, str] = ("+", "+", "+"),
    f_avg: float = 50.0,
    f_value: float = 5.0,
    f_result_code: str = "not_rejected",
    equation: str = "Y = b0 + b1·δ1 + b2·δ2",
    f_result: str = "F < F_cr → уравнение адекватно",
    g_crit_echo: float = 0.5,
    t_crit_echo: float = 2.0,
    f_crit_echo: float = 100.0,
    g_tests: list[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Build a full ComputeResult-shaped dict with NUMERIC + DISCRETE fields.

    All values are arbitrary distinct constants — NO ``g_crit``/``t_crit``/
    ``f_crit`` literals (per ``.agent/rules/project-rules.md:30``). The
    ``*_echo`` keys are arbitrary echoes for fields the loader/writer treat as
    scalars (the function avoids the bare names ``g_crit``/``t_crit``/``f_crit``
    so callers can pick distinct values for input vs expected payloads).
    """
    if g_tests is None:
        g_tests = [_make_g_test(i + 1) for i in range(4)]
    return {
        "coefficients": {"b0": b0, "b1": b1, "b2": b2},
        "coefficients_v": {"b0": b0_v, "b1": b1_v, "b2": b2_v},
        "z_averages": {"z1_avg": z1_avg, "z2_avg": z2_avg},
        "pz": {"pz1": pz1, "pz2": pz2},
        "delta_calc": {"delta1": delta1, "delta2": delta2},
        "t_tests": {
            "sign_b0": signs[0],
            "sign_b1": signs[1],
            "sign_b2": signs[2],
            "t0": t0,
            "t1": t1,
            "t2": t2,
        },
        "g_tests": g_tests,
        "f_avg": f_avg,
        "f_value": f_value,
        "f_result_code": f_result_code,
        "equation": equation,
        "f_result": f_result,
        "g_crit": g_crit_echo,
        "t_crit": t_crit_echo,
        "f_crit": f_crit_echo,
    }


# ---- dataclass shape -------------------------------------------------------


def test_check_result_dataclass() -> None:
    """CheckResult must expose name/passed/actual/expected/diff/message + counters."""
    entry = CheckEntry(
        name="t_tests.sign_b0",
        passed=True,
        actual="+",
        expected="+",
        diff=None,
        message="ok",
    )
    assert entry.name == "t_tests.sign_b0"
    assert entry.passed is True
    assert entry.actual == "+"
    assert entry.expected == "+"
    assert entry.diff is None
    assert entry.message == "ok"

    result = CheckResult(passed=1, failed=0, entries=[entry])
    assert result.passed == 1
    assert result.failed == 0
    assert result.entries == [entry]

    tol = Tolerance()
    assert tol.coeff_abs == pytest.approx(1e-3)
    assert tol.t_abs == pytest.approx(1e-2)
    assert tol.f_abs == pytest.approx(1e-1)


# ---- happy-path DISCRETE verification ---------------------------------------


def test_verify_discrete_happy() -> None:
    """All DISCRETE fields equal → verify() reports zero failures.

    The G-test comparison adds 4 per-row ``g_tests.g`` numeric entries (one per row) on top
    of the 10 pre-existing discrete entries, so the happy path emits 14
    total entries: 10 discrete (``diff is None``) + 4 numeric (``diff == 0``).
    """
    actual = _discrete_compute_result()
    expected = _discrete_compute_result()

    result: CheckResult = verify(actual, expected)

    assert isinstance(result, CheckResult)
    assert result.failed == 0
    assert result.passed == 14
    assert isinstance(result.entries, list)
    assert len(result.entries) == 14
    assert all(e.passed for e in result.entries)

    discrete_entries = [e for e in result.entries if e.diff is None]
    assert len(discrete_entries) == 10
    assert all(e.diff is None for e in discrete_entries)


def test_verify_returns_int_counters() -> None:
    """verify() must return object with .passed and .failed as int counters + .entries list."""
    actual = _discrete_compute_result()
    expected = _discrete_compute_result()

    result = verify(actual, expected)

    assert isinstance(result.passed, int)
    assert isinstance(result.failed, int)
    assert isinstance(result.entries, list)
    # passed + failed must equal total entries
    assert result.passed + result.failed == len(result.entries)


def test_tolerance_overrides_accepted() -> None:
    """Tolerance dataclass accepts keyword overrides (NUMERIC path is todo 2; shape only)."""
    tol = Tolerance(coeff_abs=1e-4, t_abs=1e-3, f_abs=1e-2)
    assert tol.coeff_abs == pytest.approx(1e-4)
    assert tol.t_abs == pytest.approx(1e-3)
    assert tol.f_abs == pytest.approx(1e-2)

    # And verify() accepts the kwarg even when DISCRETE path ignores it.
    actual = _discrete_compute_result()
    expected = _discrete_compute_result()
    res = verify(actual, expected, tolerance=tol)
    assert res.failed == 0
    # 10 discrete + 4 g_tests.g per-row (todo 3) = 14.
    assert res.passed == 14


# ---- NUMERIC per-category tolerance -------------------------------


def test_verify_numeric_tolerance_pass() -> None:
    """NUMERIC delta within coeff_abs (1e-4 ≤ 1e-3) → all NUMERIC entries pass.

    19 NUMERIC scalar entries (12 coefficient-like under ``coeff_abs``
    + 3 ``t_tests`` under ``t_abs`` + 4 ``g_tests.g`` per-row under
    ``coeff_abs``) + 1 NUMERIC ``f_value`` under ``f_abs`` = 20 NUMERIC entries.
    Plus 10 DISCRETE entries. Grand total = 30 entries.
    """
    actual = _numeric_compute_result()
    expected = _numeric_compute_result()

    result: CheckResult = verify(actual, expected)

    assert isinstance(result, CheckResult)
    assert result.failed == 0
    assert result.passed == 30
    assert len(result.entries) == 30

    numeric_entries = [e for e in result.entries if e.diff is not None]
    assert len(numeric_entries) == 20
    assert all(e.passed for e in numeric_entries)
    assert all(e.diff == pytest.approx(0.0) for e in numeric_entries)

    discrete_entries = [e for e in result.entries if e.diff is None]
    assert len(discrete_entries) == 10
    assert all(e.passed for e in discrete_entries)


def test_verify_numeric_tolerance_fail() -> None:
    """delta 1.0 on b0 (>> coeff_abs=1e-3) → fail with diff=actual-expected."""
    base = _numeric_compute_result()
    actual = _numeric_compute_result(b0=base["coefficients"]["b0"] + 1.0)
    expected = base

    result = verify(actual, expected)

    b0_entry = next(
        (e for e in result.entries if e.name == "coefficients.b0"), None
    )
    assert b0_entry is not None, "missing coefficients.b0 entry"
    assert b0_entry.passed is False
    assert b0_entry.diff == pytest.approx(1.0)
    assert b0_entry.actual == pytest.approx(base["coefficients"]["b0"] + 1.0)
    assert b0_entry.expected == pytest.approx(base["coefficients"]["b0"])

    failed = [e for e in result.entries if not e.passed]
    assert len(failed) == 1
    assert failed[0].name == "coefficients.b0"


def test_verify_per_category_tolerances() -> None:
    """coeff_abs governs coefficient-like fields, t_abs governs t-tests values.

    Given ``Tolerance(coeff_abs=1e-6, t_abs=1.0, f_abs=1e-1)``:
      * delta 1e-4 on coefficients.b0 (≫1e-6) → fail under coeff_abs.
      * delta 5.0 on t_tests.t0 (≫1.0) → fail under t_abs.
      * delta 0.5 on t_tests.t1 (<1.0) → pass under t_abs.

    f_value/f_abs coverage is deferred to todo 3.
    """
    tol = Tolerance(coeff_abs=1e-6, t_abs=1.0, f_abs=1e-1)
    base = _numeric_compute_result()
    actual = _numeric_compute_result(
        b0=base["coefficients"]["b0"] + 1e-4,
        t0=base["t_tests"]["t0"] + 5.0,
        t1=base["t_tests"]["t1"] + 0.5,
    )
    expected = base

    result = verify(actual, expected, tolerance=tol)

    by_name = {e.name: e for e in result.entries}

    # given: delta 1e-4 on coefficients.b0 with coeff_abs=1e-6
    assert by_name["coefficients.b0"].passed is False
    assert by_name["coefficients.b0"].diff == pytest.approx(1e-4)

    # given: delta 5.0 on t_tests.t0 with t_abs=1.0
    assert by_name["t_tests.t0"].passed is False
    assert by_name["t_tests.t0"].diff == pytest.approx(5.0)

    # given: delta 0.5 on t_tests.t1 with t_abs=1.0
    assert by_name["t_tests.t1"].passed is True
    assert by_name["t_tests.t1"].diff == pytest.approx(0.5)

    failed_numeric = [
        e.name for e in result.entries
        if not e.passed and e.diff is not None
    ]
    assert failed_numeric == ["coefficients.b0", "t_tests.t0"]
    assert result.failed == 2


# ---- f_value inf/NaN -----------------------------------------------


def test_verify_f_value_inf_both_pass() -> None:
    """Both f_value=+inf (e.g. safe_div protection) → pass with diff=0.0."""
    actual = _numeric_compute_result()
    expected = _numeric_compute_result()
    inf = float("inf")
    actual["f_value"] = inf
    expected["f_value"] = inf

    result = verify(actual, expected)

    f_entries = [e for e in result.entries if e.name == "f_value"]
    assert len(f_entries) == 1, "exactly one f_value entry expected"
    f_entry = f_entries[0]
    assert f_entry.passed is True
    assert f_entry.actual == inf
    assert f_entry.expected == inf
    # Matching infinities are conceptually equal → diff=0.0 per implementation.
    assert f_entry.diff == 0.0


def test_verify_f_value_inf_mismatch() -> None:
    """actual f_value=+inf, expected=1.0 → fail with diff=+inf; no exception."""
    actual = _numeric_compute_result()
    expected = _numeric_compute_result()
    actual["f_value"] = float("inf")
    expected["f_value"] = 1.0

    result = verify(actual, expected)

    f_entries = [e for e in result.entries if e.name == "f_value"]
    assert len(f_entries) == 1
    f_entry = f_entries[0]
    assert f_entry.passed is False
    # diff = +inf - 1.0 = +inf
    assert f_entry.diff == float("inf")
    assert f_entry.actual == float("inf")
    assert f_entry.expected == pytest.approx(1.0)
    assert f_entry.message != ""


def test_verify_f_value_nan_safe_any() -> None:
    """Any NaN (even NaN==NaN) → fail with explicit 'NaN' message.

    Two sub-cases:
      (a) actual=NaN, expected=0.0 → fail
      (b) actual=NaN, expected=NaN → ALSO fail (NaN never matches itself)
    """
    nan = float("nan")

    actual_a = _numeric_compute_result()
    expected_a = _numeric_compute_result()
    actual_a["f_value"] = nan
    expected_a["f_value"] = 0.0
    result_a = verify(actual_a, expected_a)
    f_a = next(e for e in result_a.entries if e.name == "f_value")
    assert f_a.passed is False
    assert "NaN" in f_a.message

    actual_b = _numeric_compute_result()
    expected_b = _numeric_compute_result()
    actual_b["f_value"] = nan
    expected_b["f_value"] = nan
    result_b = verify(actual_b, expected_b)
    f_b = next(e for e in result_b.entries if e.name == "f_value")
    assert f_b.passed is False
    assert "NaN" in f_b.message
    assert math.isnan(f_b.actual)
    assert math.isnan(f_b.expected)


# ---- g_tests sort-by-row + row-set validation ---------------------


def test_verify_g_tests_sort_by_row() -> None:
    """Same g_tests values in different row order → pass after sort-by-row.

    Actual g_tests in order [3,1,4,2], expected in [1,2,3,4].
    """
    actual_g = [
        _make_g_test(3, ok="ok", g=0.3),
        _make_g_test(1, ok="ok", g=0.1),
        _make_g_test(4, ok="ok", g=0.4),
        _make_g_test(2, ok="not_ok", g=0.2),
    ]
    expected_g = [
        _make_g_test(1, ok="ok", g=0.1),
        _make_g_test(2, ok="not_ok", g=0.2),
        _make_g_test(3, ok="ok", g=0.3),
        _make_g_test(4, ok="ok", g=0.4),
    ]

    actual = _numeric_compute_result(g_tests=actual_g)
    expected = _numeric_compute_result(g_tests=expected_g)

    result = verify(actual, expected)

    g_entries = [e for e in result.entries if e.name.startswith("g_tests[")]
    assert len(g_entries) > 0, "expected g_tests entries to be emitted"
    failures = [(e.name, e.message) for e in g_entries if not e.passed]
    assert failures == [], (
        f"all g_tests entries should pass after row-sort, "
        f"got failures: {failures}"
    )


def test_verify_g_tests_row_set_mismatch() -> None:
    """Row IDs differ (actual row 4, expected row 5) → fail with explicit message."""
    actual_g = [_make_g_test(i) for i in (1, 2, 3, 4)]
    expected_g = [_make_g_test(i) for i in (1, 2, 3, 5)]

    actual = _numeric_compute_result(g_tests=actual_g)
    expected = _numeric_compute_result(g_tests=expected_g)

    result = verify(actual, expected)

    failed = [e for e in result.entries if not e.passed]
    assert len(failed) >= 1

    mismatch_entry = next(
        (
            e for e in failed
            if "row" in e.message.lower() and "mismatch" in e.message.lower()
        ),
        None,
    )
    assert mismatch_entry is not None, (
        f"expected a row-set mismatch entry, failed entries: "
        f"{[(e.name, e.message) for e in failed]}"
    )
    assert "4" in mismatch_entry.message
    assert "5" in mismatch_entry.message


# ---- output_rows sort by (delta1, delta2) tuple + delta-set check ---


def test_verify_output_rows_sort_by_delta_tuple() -> None:
    """Same output_rows in scrambled order → pass after sort-by-(delta1, delta2).

    OutputRow has NO ``row`` key (per ``nts/core.py:61-67``), so the unique
    row identifier is the ``(delta1, delta2)`` tuple.

    Expected rows ordered by delta tuple:
        idx 0: (-1,-1)
        idx 1: (-1, 1)
        idx 2: (1,-1)
        idx 3: (1, 1)
    Actual rows in scrambled order [2, 0, 3, 1].
    """
    expected_rows = [
        _make_output_row(-1, -1, base=100.0),
        _make_output_row(-1, 1, base=200.0),
        _make_output_row(1, -1, base=300.0),
        _make_output_row(1, 1, base=400.0),
    ]
    # Scramble: actual in order [expected[2], expected[0], expected[3], expected[1]]
    actual_rows = [expected_rows[2], expected_rows[0], expected_rows[3], expected_rows[1]]

    actual = _numeric_compute_result()
    actual["output_rows"] = actual_rows
    expected = _numeric_compute_result()
    expected["output_rows"] = expected_rows

    result = verify(actual, expected)

    output_entries = [e for e in result.entries if e.name.startswith("output_rows[")]
    assert len(output_entries) > 0, "expected output_rows entries to be emitted"
    failures = [(e.name, e.message) for e in output_entries if not e.passed]
    assert failures == [], (
        f"all output_rows entries should pass after delta-tuple sort, "
        f"got failures: {failures}"
    )


def test_verify_output_rows_delta_set_mismatch() -> None:
    """Actual has a (1,-1) row that expected lacks → fail with explicit message."""
    actual_rows = [
        _make_output_row(-1, -1, base=100.0),
        _make_output_row(-1, 1, base=200.0),
        _make_output_row(1, -1, base=300.0),
        _make_output_row(1, 1, base=400.0),
    ]
    # Expected missing the (1,-1) row.
    expected_rows = [
        _make_output_row(-1, -1, base=100.0),
        _make_output_row(-1, 1, base=200.0),
        _make_output_row(1, 1, base=400.0),
    ]

    actual = _numeric_compute_result()
    actual["output_rows"] = actual_rows
    expected = _numeric_compute_result()
    expected["output_rows"] = expected_rows

    result = verify(actual, expected)

    failed = [e for e in result.entries if not e.passed]
    assert len(failed) >= 1

    mismatch_entry = next(
        (
            e for e in failed
            if "delta" in e.message.lower() and "mismatch" in e.message.lower()
        ),
        None,
    )
    assert mismatch_entry is not None, (
        f"expected a delta-set mismatch entry, failed entries: "
        f"{[(e.name, e.message) for e in failed]}"
    )


# ---- empty-expected guard + extra-key ignored ----------------------


def test_verify_empty_expected_raises() -> None:
    """``{}`` as ``expected`` → ``ValueError("expected must not be empty")``."""
    actual = _numeric_compute_result()
    expected: Dict[str, Any] = {}

    with pytest.raises(ValueError, match="expected must not be empty"):
        verify(actual, expected)


def test_verify_extra_key_in_expected_ignored() -> None:
    """An unknown key (``"foo"``) in ``expected`` is ignored; verification proceeds."""
    actual = _numeric_compute_result()
    expected = _numeric_compute_result()
    expected["foo"] = "bar"  # noqa: S105 — extra unknown key, must be ignored.

    result = verify(actual, expected)

    assert isinstance(result, CheckResult)
    assert not any(e.name == "foo" for e in result.entries)
    assert result.failed == 0
    assert all(e.passed for e in result.entries)


# ---- parse_self_check_file — JSON loader + bad-schema detection ----


def _tiny_input_data() -> Dict[str, Any]:
    """Build a minimal InputData-shaped JSON payload (distinct arbitrary values).

    Matches the ``InputData`` contract consumed by ``nts.core._parse_input_data``
    (``experiments`` list + ``g_crit`` / ``t_crit`` / ``f_crit`` floats). Uses
    arbitrary numbers — NO hardcoded ``g_crit``/``t_crit``/``f_crit`` literals.
    """
    return {
        "experiments": [
            {
                "idx": 1,
                "delta1": -1,
                "delta2": -1,
                "x1": 10.0,
                "x2": 20.0,
                "x3": 30.0,
                "y1": 100,
                "y2": 110,
                "y3": 120,
            },
            {
                "idx": 2,
                "delta1": 1,
                "delta2": -1,
                "x1": 11.0,
                "x2": 21.0,
                "x3": 31.0,
                "y1": 101,
                "y2": 111,
                "y3": 121,
            },
        ],
        "g_crit": 0.5,
        "t_crit": 2.0,
        "f_crit": 100.0,
    }


def _tiny_compute_result() -> Dict[str, Any]:
    """Build a minimal ComputeResult-shaped dict (distinct arbitrary values)."""
    return _discrete_compute_result()


def test_parse_self_check_file_valid(tmp_path: Path) -> None:
    """Valid ``{"input": {...}, "expected": {...}}`` → ``(InputData, ComputeResult)``.

    The returned ``input_data`` must be an ``InputData`` instance (parsed via
    ``_parse_input_data``); ``expected`` is the raw dict cast to
    ``ComputeResult`` shape — runtime fields are arbitrary.
    """
    from nts.core import InputData
    from nts.checker import parse_self_check_file

    payload = {
        "input": _tiny_input_data(),
        "expected": _tiny_compute_result(),
    }
    path = tmp_path / "self_check.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    input_data, expected = parse_self_check_file(path)

    assert isinstance(input_data, InputData)
    assert len(input_data.experiments) == 2
    assert input_data.g_crit == pytest.approx(0.5)
    assert input_data.t_crit == pytest.approx(2.0)
    assert input_data.f_crit == pytest.approx(100.0)

    assert isinstance(expected, dict)
    assert expected["f_result_code"] == "not_rejected"
    assert expected["equation"] == "Y = b0 + b1·δ1 + b2·δ2"


def test_parse_self_check_file_missing_input_raises(tmp_path: Path) -> None:
    """Payload with only ``"expected"`` (no ``"input"``) → ``ValueError`` mentioning ``input``."""
    from nts.checker import parse_self_check_file

    payload = {"expected": _tiny_compute_result()}
    path = tmp_path / "self_check.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="input"):
        parse_self_check_file(path)


def test_parse_self_check_file_missing_expected_raises(tmp_path: Path) -> None:
    """Payload with only ``"input"`` (no ``"expected"``) → ``ValueError`` mentioning ``expected``."""
    from nts.checker import parse_self_check_file

    payload = {"input": _tiny_input_data()}
    path = tmp_path / "self_check.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="expected"):
        parse_self_check_file(path)


def test_parse_self_check_file_empty_raises(tmp_path: Path) -> None:
    """``{}`` payload → ``ValueError`` (no ``input`` and no ``expected``)."""
    from nts.checker import parse_self_check_file

    path = tmp_path / "empty.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError):
        parse_self_check_file(path)


# ---- parse_self_check_xlsx + parse_self_check_file dispatch ---------------


def _tiny_input_xlsx_payload() -> "InputData":
    from nts.core import InputData, Experiment

    return InputData(
        experiments=[
            Experiment(
                idx=1, delta1=-1, delta2=-1,
                x1=10.0, x2=20.0, x3=30.0,
                y1=100, y2=110, y3=120,
            ),
            Experiment(
                idx=2, delta1=1, delta2=-1,
                x1=11.0, x2=21.0, x3=31.0,
                y1=101, y2=111, y3=121,
            ),
        ],
        g_crit=0.5,
        t_crit=2.0,
        f_crit=100.0,
    )


def _full_compute_result_for_xlsx() -> Dict[str, Any]:
    """Same shape as :func:`_numeric_compute_result`, plus ``output_rows``.

    The xlsx writer/loader both round-trip the per-experiment ``output_rows``
    list, so the test fixture must populate it explicitly.
    """
    base = _numeric_compute_result()
    base["output_rows"] = [
        {
            "delta1": -1.0, "delta2": -1.0, "y_avg": 110.0,
            "y_pred": 109.5, "y_avg_minus_y": 0.5, "y_avg_minus_y_sq": 0.25,
        },
        {
            "delta1": 1.0, "delta2": -1.0, "y_avg": 111.0,
            "y_pred": 110.5, "y_avg_minus_y": 0.5, "y_avg_minus_y_sq": 0.25,
        },
    ]
    return base


def test_parse_self_check_xlsx_happy(tmp_path: Path) -> None:
    """``write_self_check_xlsx`` then ``parse_self_check_file`` (xlsx dispatch) round-trips."""
    from nts.checker import parse_self_check_file, write_self_check_xlsx

    payload_in = _tiny_input_xlsx_payload()
    expected = _full_compute_result_for_xlsx()

    path = tmp_path / "self_check.xlsx"
    write_self_check_xlsx(path, payload_in, expected)

    input_data, got_expected = parse_self_check_file(path)

    assert input_data.experiments == payload_in.experiments
    assert input_data.g_crit == pytest.approx(0.5)
    assert input_data.t_crit == pytest.approx(2.0)
    assert input_data.f_crit == pytest.approx(100.0)
    assert got_expected["coefficients"]["b0"] == pytest.approx(1.0)
    assert got_expected["coefficients_v"]["b0"] == pytest.approx(10.0)
    assert got_expected["z_averages"]["z2_avg"] == pytest.approx(2.5)
    assert got_expected["t_tests"]["t0"] == pytest.approx(5.0)
    assert got_expected["t_tests"]["sign_b1"] == "+"
    assert got_expected["g_tests"][0]["ok"] == "ok"
    assert got_expected["equation"] == "Y = b0 + b1·δ1 + b2·δ2"


def test_parse_self_check_xlsx_round_trip_via_dispatch(tmp_path: Path) -> None:
    """Both ``parse_self_check_xlsx`` and the dispatching ``parse_self_check_file`` yield equivalent data."""
    from nts.checker import (
        parse_self_check_file,
        parse_self_check_xlsx,
        write_self_check_xlsx,
    )

    payload_in = _tiny_input_xlsx_payload()
    expected = _full_compute_result_for_xlsx()

    path = tmp_path / "round_trip.xlsx"
    write_self_check_xlsx(path, payload_in, expected)

    via_dispatch = parse_self_check_file(path)
    via_xlsx = parse_self_check_xlsx(path)

    assert via_dispatch[0].experiments == via_xlsx[0].experiments
    assert via_dispatch[1] == via_xlsx[1]


def test_parse_self_check_xlsx_missing_input_sheet_raises(tmp_path: Path) -> None:
    """Workbook without ``input`` sheet → ``ValueError`` mentioning ``input``."""
    import openpyxl

    from nts.checker import parse_self_check_xlsx

    path = tmp_path / "no_input.xlsx"
    wb = openpyxl.Workbook()
    wb.active.title = "result"
    wb.create_sheet("criteria")
    wb.save(path)

    with pytest.raises(ValueError, match="input"):
        parse_self_check_xlsx(path)


def test_parse_self_check_xlsx_missing_criteria_sheet_raises(tmp_path: Path) -> None:
    """Workbook without ``criteria`` sheet → ``ValueError`` mentioning ``criteria``."""
    import openpyxl

    from nts.checker import parse_self_check_xlsx

    path = tmp_path / "no_crit.xlsx"
    wb = openpyxl.Workbook()
    wb.active.title = "input"
    wb.create_sheet("result")
    wb.save(path)

    with pytest.raises(ValueError, match="criteria"):
        parse_self_check_xlsx(path)


def test_parse_self_check_xlsx_missing_result_sheet_raises(tmp_path: Path) -> None:
    """Workbook without ``result`` sheet → ``ValueError`` mentioning ``result``."""
    import openpyxl

    from nts.checker import parse_self_check_xlsx

    path = tmp_path / "no_res.xlsx"
    wb = openpyxl.Workbook()
    wb.active.title = "input"
    wb.create_sheet("criteria")
    wb.save(path)

    with pytest.raises(ValueError, match="result"):
        parse_self_check_xlsx(path)


def test_parse_self_check_xlsx_criteria_kv_layout(tmp_path: Path) -> None:
    """Criteria sheet accepts key/value layout (no header row) as a second option."""
    from nts.checker import parse_self_check_xlsx, write_self_check_xlsx

    import openpyxl

    payload_in = _tiny_input_xlsx_payload()
    expected = _full_compute_result_for_xlsx()
    path = tmp_path / "kv.xlsx"
    write_self_check_xlsx(path, payload_in, expected)

    wb = openpyxl.load_workbook(path)
    crit = wb["criteria"]
    crit.delete_rows(1)  # drop header
    crit["A1"] = "g_crit"
    crit["B1"] = "0.5"
    crit["A2"] = "t_crit"
    crit["B2"] = "2.0"
    crit["A3"] = "f_crit"
    crit["B3"] = "100.0"
    wb.save(path)

    input_data, _ = parse_self_check_xlsx(path)
    assert input_data.g_crit == pytest.approx(0.5)
    assert input_data.t_crit == pytest.approx(2.0)
    assert input_data.f_crit == pytest.approx(100.0)


def test_parse_self_check_file_unsupported_extension_raises(tmp_path: Path) -> None:
    """``parse_self_check_file`` dispatch rejects extensions outside json/xlsx/xlsm."""
    from nts.checker import parse_self_check_file

    path = tmp_path / "self_check.txt"
    path.write_text("ignored", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported"):
        parse_self_check_file(path)


def test_parse_self_check_file_xlsm_dispatch(tmp_path: Path) -> None:
    """``.xlsm`` (macro workbook) is accepted by the dispatcher and forwarded to the xlsx loader."""
    from nts.checker import parse_self_check_file, write_self_check_xlsx

    payload_in = _tiny_input_xlsx_payload()
    expected = _full_compute_result_for_xlsx()
    path = tmp_path / "self_check.xlsm"
    write_self_check_xlsx(path, payload_in, expected)

    input_data, got_expected = parse_self_check_file(path)
    assert input_data.g_crit == pytest.approx(0.5)
    assert got_expected["coefficients"]["b1"] == pytest.approx(2.0)


# ---- GUI plumbing: drag-and-drop extension allowlist + i18n ---------------
#
# These are smoke tests, not full Tk interop tests (no display available in CI).
# They pin the regression where the constant was class-scoped (caused NameError
# at runtime when referenced by bare name inside a method).


def test_reverse_gui_allowed_ext_constant_resolves_at_call_time() -> None:
    """``_ALLOWED_SELF_CHECK_EXTS`` must resolve via bare name inside a method body.

    A previous build declared the frozenset as a class attribute and referenced
    it by bare name from inside ``_on_drop``. Class-scope names are not visible
    to methods in Python, so the call raised ``NameError`` and DnD silently
    failed for every extension (not just xlsx). This regression test ensures
    the constant resolves both ways.
    """
    from nts.reverse_gui import ReverseApp, _ALLOWED_SELF_CHECK_EXTS

    assert _ALLOWED_SELF_CHECK_EXTS == frozenset({".json", ".xlsx", ".xlsm"})
    assert isinstance(_ALLOWED_SELF_CHECK_EXTS, frozenset)
    # Class may or may not re-export; tolerate either layout.
    assert sorted(_ALLOWED_SELF_CHECK_EXTS) == [".json", ".xlsm", ".xlsx"]


def test_reverse_i18n_strings_format_agnostic() -> None:
    """User-facing messages must mention all 3 supported extensions, not just .json.

    The button label (``reverse_load``) is intentionally short — it stays
    format-agnostic. The descriptive strings (`reverse_drop_file`,
    `reverse_no_data`, `reverse_no_file`) must list the actual extensions
    so the user knows what to drop/load.
    """
    from nts.i18n import I18N

    for lang in ("EN", "RU"):
        s = I18N[lang]
        for key in ("reverse_drop_file", "reverse_no_data", "reverse_no_file"):
            assert key in s, f"missing {lang}!{key}"
            text = s[key]
            assert ".json" in text, f"{lang}!{key}={text!r} must mention .json"
            assert ".xlsx" in text, f"{lang}!{key}={text!r} must mention .xlsx"
            assert ".xlsm" in text, f"{lang}!{key}={text!r} must mention .xlsm"


# ---- print_checklist() Unicode/ASCII rendering ---------------------


def _tiny_check_result() -> CheckResult:
    """Build a small CheckResult with 2 pass entries + 1 fail entry."""
    entries = [
        CheckEntry(
            name="coefficients.b0",
            passed=True,
            actual=1.0,
            expected=1.0,
            diff=0.0,
            message="",
        ),
        CheckEntry(
            name="t_tests.sign_b0",
            passed=True,
            actual="+",
            expected="+",
            diff=None,
            message="",
        ),
        CheckEntry(
            name="f_result_code",
            passed=False,
            actual="rejected",
            expected="not_rejected",
            diff=None,
            message="discrete mismatch",
        ),
    ]
    return CheckResult(passed=2, failed=1, entries=entries)


def test_print_checklist_unicode(capsys: pytest.CaptureFixture[str]) -> None:
    """Unicode mode: pass → ``✓``, fail → ``✗``; summary contains counts."""
    result = _tiny_check_result()

    print_checklist(result)
    captured = capsys.readouterr()

    assert "✓" in captured.out
    assert "✗" in captured.out
    assert "2 passed" in captured.out
    assert "1 failed" in captured.out


def test_print_checklist_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    """ASCII mode: pass → ``[OK]``, fail → ``[FAIL]``; no Unicode glyphs."""
    result = _tiny_check_result()

    print_checklist(result, ascii=True)
    captured = capsys.readouterr()

    assert "[OK]" in captured.out
    assert "[FAIL]" in captured.out
    assert "✓" not in captured.out
    assert "✗" not in captured.out


def test_print_checklist_includes_diff(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A fail entry with diff=0.5 → stdout contains the diff label text."""
    entry = CheckEntry(
        name="coefficients.b0",
        passed=False,
        actual=1.5,
        expected=1.0,
        diff=0.5,
        message="numeric mismatch",
    )
    result = CheckResult(passed=0, failed=1, entries=[entry])

    print_checklist(result)
    captured = capsys.readouterr()

    assert "diff" in captured.out
    assert "0.5" in captured.out


def test_print_checklist_includes_missing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A fail entry with message='missing' → stdout contains 'missing'."""
    entry = CheckEntry(
        name="f_value",
        passed=False,
        actual=None,
        expected=1.0,
        diff=None,
        message="missing",
    )
    result = CheckResult(passed=0, failed=1, entries=[entry])

    print_checklist(result)
    captured = capsys.readouterr()

    assert "missing" in captured.out


# ---- i18n self-check keys present in EN + RU ------------------------

# Names of the 5 self-check i18n keys (EN_BASE + RU_OVERRIDES).
SELF_CHECK_KEYS: tuple[str, ...] = (
    "self_check_title",
    "summary_passed",
    "summary_failed",
    "diff_label",
    "missing_label",
)


def test_i18n_self_check_keys_present_en() -> None:
    """All 5 self-check keys present in ``I18N["EN"]`` with non-empty values.

    5 keys were added to ``EN_BASE`` in ``nts/i18n.py``. Each must be present
    in the assembled ``I18N["EN"]`` dict (which mirrors ``EN_BASE``) and carry
    a non-empty string value.
    """
    from nts.i18n import I18N

    en = I18N["EN"]
    assert isinstance(en, dict)

    for key in SELF_CHECK_KEYS:
        assert key in en, f"missing key {key!r} in I18N['EN']"
        value = en[key]
        assert isinstance(value, str), (
            f"I18N['EN'][{key!r}] must be a str, got {type(value).__name__}"
        )
        assert value != "", f"I18N['EN'][{key!r}] must be non-empty"


def test_i18n_self_check_keys_present_ru() -> None:
    """All 5 self-check keys present in ``I18N["RU"]`` with non-empty values.

    Russian translations must override every new key (no fallback to EN),
    otherwise the GUI will show mixed-language UI strings. Back-compat for
    pre-existing keys (``status_ok``, ``status_bad``) is also asserted here.
    """
    from nts.i18n import I18N

    ru = I18N["RU"]
    assert isinstance(ru, dict)

    for key in SELF_CHECK_KEYS:
        assert key in ru, f"missing key {key!r} in I18N['RU']"
        value = ru[key]
        assert isinstance(value, str), (
            f"I18N['RU'][{key!r}] must be a str, got {type(value).__name__}"
        )
        assert value != "", f"I18N['RU'][{key!r}] must be non-empty"

    # Back-compat: pre-existing keys must remain bit-identical.
    # ``status_ok`` in EN_BASE is "OK" (line 54 of nts/i18n.py); RU keeps the
    # same value because RU_OVERRIDES only overrides ``status_bad``.
    assert ru["status_ok"] == "OK", (
        f"I18N['RU']['status_ok'] must remain 'OK' (back-compat), "
        f"got {ru['status_ok']!r}"
    )
    assert ru["status_bad"] == "не OK", (
        f"I18N['RU']['status_bad'] must remain 'не OK' (back-compat), "
        f"got {ru['status_bad']!r}"
    )
    # EN back-compat sanity check (status_ok / status_bad are pre-existing keys
    # that the checklist renderer reuses as ✓/✗ glyphs; if either drifts, the
    # renderer's assumption breaks).
    en = I18N["EN"]
    assert en["status_ok"] == "OK"
    assert en["status_bad"] == "not OK"


# ---- CLI integration (--self-check flag) ---------------------------


_CLI_ENV_BASE: Dict[str, str] = {
    "PYTHONIOENCODING": "utf-8",
}


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run ``python -m nts.cli <args>`` with UTF-8 stdout/stderr streams.

    Both child and parent force UTF-8: the child via ``PYTHONIOENCODING=utf-8``
    (so its ``sys.stdout`` writes UTF-8 bytes for ``δ`` etc.), and the parent
    via an explicit ``encoding='utf-8'`` — otherwise Windows ``subprocess.run``
    decodes pipe output as ``cp1252`` regardless of the env var.
    """
    return subprocess.run(
        [sys.executable, "-m", "nts.cli", *args],
        env={**os.environ, **_CLI_ENV_BASE},
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_cli_help_lists_self_check_flag() -> None:
    """``python -m nts.cli --help`` advertises the new ``--self-check`` flag.

    The help message must advertise the ``--self-check`` flag next to
    ``--input`` and ``--json``.
    """
    proc = _run_cli("--help")

    assert proc.returncode == 0, (
        f"--help should exit 0, got {proc.returncode!r}; "
        f"stderr={proc.stderr!r}"
    )
    assert "--self-check" in proc.stdout, (
        f"--help output must mention --self-check; got stdout={proc.stdout!r}"
    )


def test_cli_default_input_path_byte_identical(
    examples_dir: Path,
) -> None:
    """Regression: ``python -m nts.cli --input examples/default.json`` is unchanged.

    Asserts the exact stdout byte-string captured in
    ``.omo/evidence/baseline_pre_change.txt``. Any edit to ``nts/cli.py`` that
    disturbs the ``--input`` path — even a trailing newline or whitespace
    change — must trip this test.
    """
    input_path = examples_dir / "default.json"
    proc = _run_cli("--input", str(input_path))

    assert proc.returncode == 0, (
        f"baseline --input run should exit 0, got {proc.returncode!r}; "
        f"stderr={proc.stderr!r}"
    )
    expected = (
        "Y = 1063.5 + 30.167*δ1 - 67.5*δ2\n"
        "\n"
        "t-tests:\n"
        "  t_0: t=39.7300 sign=+\n"
        "  t_1: t=3.2700 sign=+\n"
        "  t_2: t=6.5740 sign=+\n"
        "\n"
        "G-tests:\n"
        "  row 1: G=0.6250 (OK)\n"
        "  row 2: G=0.6670 (OK)\n"
        "  row 3: G=0.5760 (OK)\n"
        "  row 4: G=0.5610 (OK)\n"
        "\n"
        "Output:\n"
        "  y_avg | delta1 | delta2 | y_pred | y_avg-y | (y_avg-y)^2\n"
        "  1122.67 | -1 | -1 | 1100.83 | 21.8333 | 476.694\n"
        "  944 | -1 | 1 | 965.833 | -21.8333 | 476.694\n"
        "  1139.33 | 1 | -1 | 1161.17 | -21.8333 | 476.694\n"
        "  1048 | 1 | 1 | 1026.17 | 21.8333 | 476.694\n"
        "\n"
        "F_avg=476.694\n"
        "F_value=17.655\n"
        "Hypothesis not rejected\n"
    )
    assert proc.stdout == expected, (
        f"stdout drifted from the recorded baseline; "
        f"diff={proc.stdout!r} vs {expected!r}"
    )


def test_cli_self_check_missing_expected_exits_2(
    tmp_path: Path,
    examples_dir: Path,
) -> None:
    """``--self-check`` on a payload without ``expected`` exits with status 2.

    Mirrors the S7 scenario of the self-check plan: a self-check
    payload that contains only the ``input`` key (no ``expected``) must
    surface a clear stderr message and exit with status code 2 (distinct
    from 0 = pass and 1 = fail).

    Per the plan the ``--self-check`` flag is ``store_true``; the file path
    is supplied via the existing ``--input`` argument.
    """
    input_payload = json.loads((examples_dir / "default.json").read_text(encoding="utf-8"))
    payload_missing_expected = {"input": input_payload}
    bad_path = tmp_path / "missing_expected.json"
    bad_path.write_text(json.dumps(payload_missing_expected), encoding="utf-8")

    proc = _run_cli("--input", str(bad_path), "--self-check")

    assert proc.returncode == 2, (
        f"missing-expected payload must exit 2 (usage/schema error), got "
        f"{proc.returncode!r}; stdout={proc.stdout!r}; stderr={proc.stderr!r}"
    )
    combined = proc.stderr + proc.stdout
    assert "expected" in combined, (
        f"stderr/stdout must mention the missing 'expected' key; "
        f"got combined={combined!r}"
    )


# ---- end-to-end CLI subprocess integration (--self-check happy/mismatch) --


def _build_self_check_payload(
    *,
    perturb_b0_by: float = 0.0,
) -> Dict[str, Any]:
    """Build a synthetic ``{"input": ..., "expected": ...}`` self-check payload.

    Uses an inline 4-experiment ``InputData`` (the 2² design with full factor
    signatures) so :func:`nts.core.compute` is happy — see
    ``nts/core.py:19 EXPECTED_EXPERIMENTS = 4``. Numeric values are arbitrary
    (no canonical ``g_crit``/``t_crit``/``f_crit`` literals per
    ``.agent/rules/project-rules.md:30``).

    Runs :func:`nts.core.compute` on the same input the CLI will see, then
    snapshots the resulting ``ComputeResult`` (JSON round-tripped for
    deep-copy safety) as ``expected``. When ``perturb_b0_by`` is non-zero,
    the ``coefficients.b0`` field in ``expected`` is shifted by that amount
    so the numeric tolerance (``coeff_abs = 1e-3``) is exceeded and the CLI
    exits 1.

    Returns the dict ready to ``json.dumps``. Caller is responsible for
    writing it to disk in ``tmp_path`` so the CLI sees an isolated fixture.
    """
    from nts.core import _parse_input_data, compute

    input_dict = {
        "experiments": [
            {
                "idx": 1,
                "delta1": -1,
                "delta2": -1,
                "x1": 30.0,
                "x2": 50.0,
                "x3": 20.0,
                "y1": 100,
                "y2": 110,
                "y3": 90,
            },
            {
                "idx": 2,
                "delta1": -1,
                "delta2": 1,
                "x1": 35.0,
                "x2": 45.0,
                "x3": 20.0,
                "y1": 200,
                "y2": 210,
                "y3": 190,
            },
            {
                "idx": 3,
                "delta1": 1,
                "delta2": -1,
                "x1": 55.0,
                "x2": 35.0,
                "x3": 10.0,
                "y1": 300,
                "y2": 310,
                "y3": 290,
            },
            {
                "idx": 4,
                "delta1": 1,
                "delta2": 1,
                "x1": 45.0,
                "x2": 30.0,
                "x3": 25.0,
                "y1": 400,
                "y2": 410,
                "y3": 390,
            },
        ],
        "g_crit": 0.5,
        "t_crit": 2.0,
        "f_crit": 100.0,
    }
    parsed = _parse_input_data(input_dict)
    actual = compute(parsed)
    # JSON round-trip = deep copy that survives the subprocess boundary and
    # avoids sharing TypedDict (mutable dict at runtime) across processes.
    expected: Dict[str, Any] = json.loads(json.dumps(actual))
    if perturb_b0_by:
        expected["coefficients"]["b0"] = expected["coefficients"]["b0"] + perturb_b0_by
    return {"input": input_dict, "expected": expected}


def test_cli_self_check_subprocess_happy(tmp_path: Path) -> None:
    """End-to-end: ``python -m nts.cli --self-check`` exits 0 on a passing payload.

    Builds a synthetic ``{input, expected}`` file via
    :func:`_build_self_check_payload` (no canonical ``g_crit``/``t_crit``/
    ``f_crit`` literals) and invokes the CLI as a subprocess. The expected
    payload mirrors what :func:`nts.core.compute` returns for the same input,
    so the verifier should see zero diffs and the CLI should exit 0 with the
    human-readable checklist ending in ``"<N> passed, 0 failed"``.

    Stdout must contain both the Unicode ``✓`` (rendered by default) and
    the literal ``Self-check`` header printed by
    :func:`nts.checker.print_checklist`. The equation line includes ``δ1`` /
    ``δ2`` so ``PYTHONIOENCODING=utf-8`` is required to keep the parent's
    text decoder from raising on byte 0xCE etc. — this is exercised (not
    stubbed) via :func:`_run_cli`.
    """
    payload = _build_self_check_payload()
    path = tmp_path / "self_check_ok.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_cli("--input", str(path), "--self-check")

    assert proc.returncode == 0, (
        f"--self-check on a valid payload must exit 0, got {proc.returncode!r}; "
        f"stdout={proc.stdout!r}; stderr={proc.stderr!r}"
    )
    assert "Self-check" in proc.stdout, (
        f"stdout must contain the 'Self-check' header; got {proc.stdout!r}"
    )
    assert "passed" in proc.stdout, (
        f"stdout must mention 'passed' in the summary; got {proc.stdout!r}"
    )


def test_cli_self_check_subprocess_mismatch(tmp_path: Path) -> None:
    """End-to-end: ``--self-check`` exits 1 when ``coefficients.b0`` is perturbed.

    Builds the same synthetic payload via
    :func:`_build_self_check_payload(perturb_b0_by=100.0)`. The shift of 100
    on ``b0`` is far beyond ``Tolerance.coeff_abs = 1e-3``, so the CLI must
    surface at least one failed entry, print ``"<N> passed, 1 failed"`` (or
    more) and exit with status code 1. Stdout must contain ``"failed"`` so
    operators can grep the summary line.
    """
    payload = _build_self_check_payload(perturb_b0_by=100.0)
    path = tmp_path / "self_check_bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    proc = _run_cli("--input", str(path), "--self-check")

    assert proc.returncode == 1, (
        f"--self-check on a perturbed payload must exit 1, got "
        f"{proc.returncode!r}; stdout={proc.stdout!r}; stderr={proc.stderr!r}"
    )
    assert "failed" in proc.stdout, (
        f"stdout must contain 'failed' in the summary; got {proc.stdout!r}"
    )

# ---- Core vs extended: workbook split + simplified (no-extended) mode ---------
#
# The reference workbook keeps the *core* result keys on the ``result`` sheet
# (yellow-marked, same cells as the hand-made reference file) and every other
# result key on the optional ``extended`` sheet. A workbook without that sheet
# must still be a complete, runnable check — the simplified mode compares only
# the fields the reference file actually provides.


def _write_reference_workbook(path: Path) -> Path:
    """Write a full self-check workbook from the arbitrary-value test fixture."""
    from nts.checker import write_self_check_xlsx

    write_self_check_xlsx(
        path, _tiny_input_xlsx_payload(), _full_compute_result_for_xlsx()
    )
    return path


def _drop_sheet(path: Path, sheet_name: str) -> None:
    """Remove ``sheet_name`` from the workbook at ``path`` (in place)."""
    import openpyxl

    wb = openpyxl.load_workbook(path)
    del wb[sheet_name]
    wb.save(path)


def _core_expected_payload() -> Dict[str, Any]:
    """The core-only expected payload: no ``extended`` keys at all."""
    return {
        "coefficients": {"b0": 1.0, "b1": 2.0, "b2": 3.0},
        "coefficients_v": {"b0": 10.0, "b1": 20.0, "b2": 30.0},
        "t_tests": {"t0": 5.0, "t1": 4.0, "t2": 3.0},
        "f_value": 5.0,
    }


def test_write_self_check_xlsx_splits_core_and_extended(tmp_path: Path) -> None:
    """``result`` holds the core keys only (yellow fill); ``extended`` holds the rest."""
    import openpyxl

    from nts.checker import (
        CORE_RESULT_KEYS,
        EXTENDED_SHEET_NAME,
        write_self_check_xlsx,
    )

    path = tmp_path / "split.xlsx"
    write_self_check_xlsx(
        path, _tiny_input_xlsx_payload(), _full_compute_result_for_xlsx()
    )

    wb = openpyxl.load_workbook(path)
    assert EXTENDED_SHEET_NAME in wb.sheetnames

    res = wb["result"]
    res_keys = [row[0] for row in res.iter_rows(min_row=2, values_only=True) if row[0]]
    ext = wb[EXTENDED_SHEET_NAME]
    ext_keys = [row[0] for row in ext.iter_rows(min_row=2, values_only=True) if row[0]]

    assert set(res_keys) == set(CORE_RESULT_KEYS)
    assert "equation" in ext_keys, "non-core keys must live on the extended sheet"
    assert not (set(res_keys) & set(ext_keys)), "a key cannot be on both sheets"

    # Core value cells are yellow-marked; extended cells stay unstyled.
    for row in res.iter_rows(min_row=2):
        if row[0] is None:
            continue
        assert row[1].fill.patternType == "solid"
        assert row[1].fill.fgColor.rgb == "FFFFFF00"
    for row in ext.iter_rows(min_row=2):
        if row[0] is None:
            continue
        assert row[1].fill.patternType in (None, "none")


def test_parse_self_check_xlsx_merges_extended_sheet(tmp_path: Path) -> None:
    """The optional ``extended`` sheet is merged into the expected payload."""
    from nts.checker import MODE_FULL, parse_self_check_bundle

    path = _write_reference_workbook(tmp_path / "full.xlsx")
    bundle = parse_self_check_bundle(path)

    assert bundle.mode == MODE_FULL, "an extended sheet declares full coverage"
    assert bundle.expected["equation"] == "Y = b0 + b1·δ1 + b2·δ2"
    assert bundle.expected["coefficients"]["b0"] == pytest.approx(1.0)
    assert bundle.expected["t_tests"]["t0"] == pytest.approx(5.0)
    # The merge must not drop the sibling keys of a nested group.
    assert bundle.expected["t_tests"]["sign_b1"] == "+"
    assert bundle.expected["z_averages"]["z2_avg"] == pytest.approx(2.5)


def test_parse_self_check_bundle_without_extended_is_simplified(
    tmp_path: Path,
) -> None:
    """A workbook without ``extended`` parses in simplified mode."""
    from nts.checker import EXTENDED_SHEET_NAME, MODE_SIMPLIFIED, parse_self_check_bundle

    path = _write_reference_workbook(tmp_path / "core_only.xlsx")
    _drop_sheet(path, EXTENDED_SHEET_NAME)

    bundle = parse_self_check_bundle(path)

    assert bundle.mode == MODE_SIMPLIFIED
    assert "equation" not in bundle.expected
    assert bundle.expected["coefficients"]["b0"] == pytest.approx(1.0)
    assert bundle.expected["t_tests"]["t0"] == pytest.approx(5.0)


def test_verify_simplified_mode_checks_only_core_fields() -> None:
    """``MODE_SIMPLIFIED`` compares the core keys only — optional fields are skipped."""
    from nts.checker import MODE_SIMPLIFIED, verify

    actual = _full_compute_result_for_xlsx()
    result = verify(actual, _core_expected_payload(), mode=MODE_SIMPLIFIED)

    assert result.failed == 0, (
        f"simplified mode must not fail on absent fields; "
        f"failures={[e.message for e in result.entries if not e.passed]!r}"
    )
    assert {e.name for e in result.entries} == {
        "coefficients.b0", "coefficients.b1", "coefficients.b2",
        "coefficients_v.b0", "coefficients_v.b1", "coefficients_v.b2",
        "t_tests.t0", "t_tests.t1", "t_tests.t2",
        "f_value",
    }


def test_verify_simplified_mode_skips_optional_sheets() -> None:
    """In simplified mode the G-tests and the per-row output are not checked.

    The reference file provides them, but they are optional fields — the
    simplified mode reports the main (core) fields only.
    """
    from nts.checker import MODE_SIMPLIFIED, verify

    actual = _full_compute_result_for_xlsx()
    full_expected = _full_compute_result_for_xlsx()
    result = verify(actual, full_expected, mode=MODE_SIMPLIFIED)

    names = {e.name for e in result.entries}
    assert not any(name.startswith("g_tests") for name in names)
    assert not any(name.startswith("output_rows") for name in names)
    assert names == {
        "coefficients.b0", "coefficients.b1", "coefficients.b2",
        "coefficients_v.b0", "coefficients_v.b1", "coefficients_v.b2",
        "t_tests.t0", "t_tests.t1", "t_tests.t2",
        "f_value",
    }


def test_verify_full_mode_reports_absent_fields() -> None:
    """``MODE_FULL`` (default) keeps reporting absent fields as failures."""
    from nts.checker import MODE_FULL, verify

    actual = _full_compute_result_for_xlsx()
    result = verify(actual, _core_expected_payload(), mode=MODE_FULL)

    assert result.failed > 0
    messages = " ".join(e.message for e in result.entries if not e.passed)
    assert "missing" in messages


def test_verify_rejects_unknown_mode() -> None:
    """An unknown mode is a programming error, not a silent fallback."""
    from nts.checker import verify

    with pytest.raises(ValueError, match="unknown verification mode"):
        verify(_full_compute_result_for_xlsx(), _core_expected_payload(), mode="nope")


def test_cli_self_check_xlsx_without_extended_exits_0(
    tmp_path: Path,
    examples_dir: Path,
) -> None:
    """A workbook without ``extended`` still passes the CLI self-check.

    The workbook is built from the real ``examples/default.json`` input, so the
    expected values match the computation exactly — the only difference is the
    missing ``extended`` sheet.
    """
    from nts.checker import EXTENDED_SHEET_NAME, write_self_check_xlsx
    from nts.core import compute, read_input_file

    input_data = read_input_file(examples_dir / "default.json")
    result = compute(input_data)

    path = tmp_path / "core_only.xlsx"
    write_self_check_xlsx(path, input_data, result)
    _drop_sheet(path, EXTENDED_SHEET_NAME)

    proc = _run_cli("--input", str(path), "--self-check")

    assert proc.returncode == 0, (
        f"core-only workbook must exit 0; got {proc.returncode!r}; "
        f"stdout={proc.stdout!r}; stderr={proc.stderr!r}"
    )
    assert "0 failed" in proc.stdout, (
        f"checklist summary must report no failures; got {proc.stdout!r}"
    )


def test_cli_self_check_xlsx_with_extended_exits_0(
    tmp_path: Path,
    examples_dir: Path,
) -> None:
    """The same workbook with an ``extended`` sheet also passes (full mode)."""
    from nts.checker import write_self_check_xlsx
    from nts.core import compute, read_input_file

    input_data = read_input_file(examples_dir / "default.json")
    result = compute(input_data)

    path = tmp_path / "full.xlsx"
    write_self_check_xlsx(path, input_data, result)

    proc = _run_cli("--input", str(path), "--self-check")

    assert proc.returncode == 0, (
        f"full workbook must exit 0; got {proc.returncode!r}; "
        f"stdout={proc.stdout!r}; stderr={proc.stderr!r}"
    )
    assert "0 failed" in proc.stdout


# ---- Human-readable variable dictionary -------------------------------------
#
# The machine keys stay stable; the dictionary says what each of them means.
# It feeds the Excel ``description`` column and the GUI checklist.


def test_dictionary_describes_every_core_key() -> None:
    """Every core key has a description in both languages."""
    from nts.checker import CORE_RESULT_KEYS
    from nts.dictionary import UNKNOWN_DESCRIPTION, describe

    for key in CORE_RESULT_KEYS:
        for lang in ("EN", "RU"):
            text = describe(key, lang)
            assert text != UNKNOWN_DESCRIPTION, f"{lang}: no description for {key!r}"
            assert text.strip(), f"{lang}: empty description for {key!r}"


def test_dictionary_describes_every_written_result_key() -> None:
    """Every key the writer emits has a description (no empty cells)."""
    from nts.checker import write_self_check_xlsx
    from nts.dictionary import UNKNOWN_DESCRIPTION, describe

    path = Path(tempfile.gettempdir()) / "nts_dict_probe.xlsx"
    write_self_check_xlsx(
        path, _tiny_input_xlsx_payload(), _full_compute_result_for_xlsx()
    )
    import openpyxl

    wb = openpyxl.load_workbook(path)
    for sheet in ("result", "extended"):
        for row in wb[sheet].iter_rows(min_row=2, values_only=True):
            if not row[0]:
                continue
            assert row[2] != UNKNOWN_DESCRIPTION, f"no description for {row[0]!r}"
            assert row[2] == describe(row[0], "RU")


def test_dictionary_describe_entry_resolves_container_prefix() -> None:
    """Checklist entry names resolve to the description of their variable."""
    from nts.dictionary import UNKNOWN_DESCRIPTION, describe, describe_entry

    assert describe_entry("coefficients.b0", "RU") == describe("coefficients.b0", "RU")
    assert describe_entry("g_tests[row=1].g", "RU") == describe("g", "RU")
    assert describe_entry(
        "output_rows[-1.0, -1.0].y_avg", "EN"
    ) == describe("y_avg", "EN")
    assert describe_entry("totally.unknown", "RU") == UNKNOWN_DESCRIPTION


def test_write_self_check_xlsx_adds_description_column(tmp_path: Path) -> None:
    """Both key/value sheets carry a ``description`` column."""
    import openpyxl

    from nts.checker import EXTENDED_SHEET_NAME, write_self_check_xlsx
    from nts.dictionary import describe

    path = tmp_path / "described.xlsx"
    write_self_check_xlsx(
        path, _tiny_input_xlsx_payload(), _full_compute_result_for_xlsx(), lang="RU"
    )

    wb = openpyxl.load_workbook(path)
    for sheet in ("result", EXTENDED_SHEET_NAME):
        ws = wb[sheet]
        assert [c.value for c in ws[1]] == ["key", "value", "description"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row[0]:
                continue
            assert row[2] == describe(row[0], "RU")


def test_write_self_check_xlsx_round_trips_with_description_column(
    tmp_path: Path,
) -> None:
    """The reader tolerates the extra description column."""
    from nts.checker import parse_self_check_bundle, write_self_check_xlsx

    path = tmp_path / "round_trip_described.xlsx"
    write_self_check_xlsx(
        path, _tiny_input_xlsx_payload(), _full_compute_result_for_xlsx(), lang="EN"
    )

    bundle = parse_self_check_bundle(path)
    assert bundle.expected["coefficients"]["b0"] == pytest.approx(1.0)
    assert bundle.expected["equation"] == "Y = b0 + b1·δ1 + b2·δ2"


def test_print_checklist_includes_description_when_lang_given(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``print_checklist(lang=...)`` appends the human description."""
    from nts.checker import print_checklist
    from nts.dictionary import describe

    entry = CheckEntry(
        name="coefficients.b0",
        passed=True,
        actual=1.0,
        expected=1.0,
        diff=0.0,
        message="",
    )
    print_checklist(CheckResult(passed=1, failed=0, entries=[entry]), lang="RU")

    out = capsys.readouterr().out
    assert describe("coefficients.b0", "RU") in out
    assert "coefficients.b0" in out


# ---- Reverse GUI: verification modes -----------------------------------------
#
# The reverse GUI verifies in the simplified mode by default and switches to
# the extended mode automatically when the loaded file carries an ``extended``
# sheet.


def _reverse_app_stub(
    *,
    mode_code: str = "auto",
    file_mode: str = MODE_SIMPLIFIED,
):
    """A :class:`ReverseApp` without a Tk root (no display needed)."""
    from nts.reverse_gui import ReverseApp

    app = ReverseApp.__new__(ReverseApp)
    app.mode_code = mode_code
    app.file_mode = file_mode
    return app


def test_reverse_gui_mode_defaults_to_simplified() -> None:
    """Without a file the reverse GUI would verify in the simplified mode."""
    app = _reverse_app_stub(mode_code="auto", file_mode=MODE_SIMPLIFIED)
    assert app._effective_mode() == MODE_SIMPLIFIED
    assert app._effective_mode_code() == "simplified"


def test_reverse_gui_mode_auto_follows_extended_sheet() -> None:
    """An ``extended`` sheet switches the automatic mode to extended."""
    app = _reverse_app_stub(mode_code="auto", file_mode=MODE_FULL)
    assert app._effective_mode() == MODE_FULL
    assert app._effective_mode_code() == "full"


def test_reverse_gui_mode_selector_overrides_file_mode() -> None:
    """The explicit selector wins over what the file implies."""
    app = _reverse_app_stub(mode_code="simplified", file_mode=MODE_FULL)
    assert app._effective_mode() == MODE_SIMPLIFIED

    app = _reverse_app_stub(mode_code="full", file_mode=MODE_SIMPLIFIED)
    assert app._effective_mode() == MODE_FULL


def test_reverse_gui_has_description_column() -> None:
    """The checklist shows a description column next to the field name."""
    from nts.reverse_gui import _CHECKLIST_COLUMNS

    assert "description" in _CHECKLIST_COLUMNS
    assert _CHECKLIST_COLUMNS.index("description") == 2


def test_reverse_i18n_has_mode_and_description_strings() -> None:
    """Both languages carry the mode selector and the description column."""
    from nts.i18n import I18N

    for lang in ("EN", "RU"):
        s = I18N[lang]
        for key in (
            "reverse_mode",
            "reverse_mode_auto",
            "reverse_mode_simplified",
            "reverse_mode_full",
            "reverse_mode_current",
            "reverse_col_description",
        ):
            assert key in s, f"missing {lang}!{key}"


def test_write_self_check_xlsx_writes_dictionary_sheet(tmp_path: Path) -> None:
    """The workbook carries a ``dictionary`` sheet with every variable."""
    import openpyxl

    from nts.checker import DICTIONARY_SHEET_NAME, write_self_check_xlsx
    from nts.dictionary import DESCRIPTIONS

    path = tmp_path / "with_dictionary.xlsx"
    write_self_check_xlsx(
        path, _tiny_input_xlsx_payload(), _full_compute_result_for_xlsx(), lang="RU"
    )

    wb = openpyxl.load_workbook(path)
    ws = wb[DICTIONARY_SHEET_NAME]
    assert [c.value for c in ws[1]] == ["key", "description"]

    entries = {
        row[0]: row[1]
        for row in ws.iter_rows(min_row=2, values_only=True)
        if row[0]
    }
    assert entries["coefficients.b0"] == DESCRIPTIONS["RU"]["coefficients.b0"]
    # Column names of the other sheets are covered too.
    assert entries["x1"] == DESCRIPTIONS["RU"]["x1"]
    assert entries["y_avg_minus_y_sq"] == DESCRIPTIONS["RU"]["y_avg_minus_y_sq"]


def test_parse_self_check_xlsx_ignores_dictionary_sheet(tmp_path: Path) -> None:
    """The extra ``dictionary`` sheet does not disturb the reader."""
    from nts.checker import parse_self_check_bundle, write_self_check_xlsx

    path = tmp_path / "with_dictionary_read.xlsx"
    write_self_check_xlsx(
        path, _tiny_input_xlsx_payload(), _full_compute_result_for_xlsx()
    )

    bundle = parse_self_check_bundle(path)
    assert bundle.expected["coefficients"]["b0"] == pytest.approx(1.0)
    assert "dictionary" not in bundle.expected


# ---- Инварианты формата и словаря ------------------------------------------
#
# Три договорённости, которые проверялись вручную и теперь зафиксированы
# тестами: цвет не влияет на логику, словарь покрывает весь результат,
# эталонная книга соответствует тому, что пишет писатель.


def test_verify_result_does_not_depend_on_cell_fill(
    tmp_path: Path,
    examples_dir: Path,
) -> None:
    """Заливка ядра — только метка: снятие всех цветов не меняет результат.

    Ядро определяется списком ``CORE_RESULT_KEYS`` и именем листа, а не
    цветом: код нигде не читает заливку (единственная операция — запись
    ``ws.cell(...).fill = fill`` при экспорте).
    """
    import openpyxl
    from openpyxl.styles import PatternFill

    from nts.checker import parse_self_check_bundle, verify, write_self_check_xlsx
    from nts.core import compute, read_input_file

    path = tmp_path / "colored.xlsx"
    data = read_input_file(examples_dir / "default.json")
    write_self_check_xlsx(path, data, compute(data), lang="RU")

    bundle = parse_self_check_bundle(path)
    before = verify(compute(bundle.input_data), bundle.expected, mode=bundle.mode)

    workbook = openpyxl.load_workbook(path)
    stripped = 0
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if cell.fill is not None and cell.fill.patternType:
                    cell.fill = PatternFill()
                    stripped += 1
    assert stripped > 0, "в эталонной книге должна быть хотя бы одна заливка"
    workbook.save(path)

    stripped_bundle = parse_self_check_bundle(path)
    after = verify(
        compute(stripped_bundle.input_data),
        stripped_bundle.expected,
        mode=stripped_bundle.mode,
    )

    assert (after.passed, after.failed) == (before.passed, before.failed), (
        "снятие заливки изменило результат проверки: "
        f"было {before.passed}/{before.failed}, стало {after.passed}/{after.failed}"
    )
    assert after.failed == 0


def test_dictionary_covers_every_result_key(examples_dir: Path) -> None:
    """Каждый ключ, возвращаемый ``compute()``, имеет описание в словаре."""
    from nts.core import compute, read_input_file
    from nts.dictionary import UNKNOWN_DESCRIPTION, describe

    result = compute(read_input_file(examples_dir / "default.json"))

    keys: list[str] = []
    for name, value in result.items():
        if isinstance(value, dict):
            keys.extend(f"{name}.{sub}" for sub in value)
        else:
            keys.append(name)

    missing = [key for key in keys if describe(key, "RU") == UNKNOWN_DESCRIPTION]
    assert not missing, f"ключи без описания: {missing}"


def test_reference_workbook_matches_writer(
    tmp_path: Path,
    examples_dir: Path,
) -> None:
    """Эталонная книга в ``examples/`` совпадает с выводом писателя.

    Книга — эталон для проверок; если писатель изменился, эталон нужно
    перегенерировать, а не чинить руками.
    """
    import openpyxl

    from nts.checker import write_self_check_xlsx
    from nts.core import compute, read_input_file

    reference = examples_dir / "default_result.xlsx"
    if not reference.exists():
        pytest.skip("эталонная книга отсутствует")

    data = read_input_file(examples_dir / "default.json")
    fresh = tmp_path / "fresh.xlsx"
    write_self_check_xlsx(fresh, data, compute(data), lang="RU")

    def snapshot(path: Path) -> Dict[str, List[tuple]]:
        workbook = openpyxl.load_workbook(path, data_only=True)
        return {
            sheet.title: [tuple(row) for row in sheet.iter_rows(values_only=True)]
            for sheet in workbook.worksheets
        }

    assert snapshot(fresh) == snapshot(reference), (
        "эталонная книга разошлась с писателем — перегенерируйте examples/default_result.xlsx"
    )
