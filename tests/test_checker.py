"""Tests for nts.checker.verify() — DISCRETE + NUMERIC + LIST-SORT paths.

Todo 1 (DISCRETE):
  - t_tests.sign_b0 / sign_b1 / sign_b2
  - f_result_code
  - g_tests[i].ok (per-row, position-based)
  - equation
  - f_result

Todo 2 (NUMERIC per-category tolerance):
  - coefficients / coefficients_v / z_averages / pz / delta_calc → coeff_abs
  - t_tests.t0 / t1 / t2 → t_abs
  - g_tests[i].g per-row → coeff_abs (added in todo 3 alongside sort)
  - f_value → f_abs (todo 3, with NaN/inf policy)

Todo 3 (f_value inf/NaN + list-row sort + empty/extra-key policy):
  - f_value: NaN never matches (even NaN==NaN); inf==inf same-sign passes;
    inf vs finite fails with diff=inf.
  - g_tests: row-set validation + sort by ``row`` key (stable) before
    per-row comparison of g and ok.
  - output_rows: row-set validation on ``(delta1, delta2)`` tuple + sort
    by that tuple before per-row comparison of all 6 numeric fields.
  - Empty ``expected`` → ``ValueError("expected must not be empty")``.
  - Extra keys in ``expected`` → silently ignored.

Todo 4 (parse_self_check_file — JSON file loader with bad-schema detection):
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
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

from nts.checker import CheckEntry, CheckResult, Tolerance, print_checklist, verify


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
    f_result_code: str = "not_rejected",
    equation: str = "Y = b0 + b1·δ1 + b2·δ2",
    f_result: str = "F < F_cr → уравнение адекватно",
    g_tests: list[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Build a full ComputeResult-shaped dict with NUMERIC + DISCRETE fields.

    All values are arbitrary distinct constants — NO ``g_crit``/``t_crit``/
    ``f_crit`` literals (per ``.agent/rules/project-rules.md:30``).
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
        "f_result_code": f_result_code,
        "equation": equation,
        "f_result": f_result,
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

    Todo 3 adds 4 per-row ``g_tests.g`` numeric entries (one per row) on top
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


# ---- NUMERIC per-category tolerance (Todo 2) -------------------------------


def test_verify_numeric_tolerance_pass() -> None:
    """NUMERIC delta within coeff_abs (1e-4 ≤ 1e-3) → all NUMERIC entries pass.

    Todo 3 adds 4 per-row ``g_tests.g`` numeric entries; 19 numeric total
    (12 coefficient-like under ``coeff_abs`` + 3 ``t_tests`` under ``t_abs``
    + 4 ``g_tests.g`` per-row under ``coeff_abs``). Discrete entries remain 10.
    Grand total = 29 entries.
    """
    actual = _numeric_compute_result()
    expected = _numeric_compute_result()

    result: CheckResult = verify(actual, expected)

    assert isinstance(result, CheckResult)
    assert result.failed == 0
    assert result.passed == 29
    assert len(result.entries) == 29

    numeric_entries = [e for e in result.entries if e.diff is not None]
    assert len(numeric_entries) == 19
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


# ---- Todo 3: f_value inf/NaN -----------------------------------------------


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


# ---- Todo 3: g_tests sort-by-row + row-set validation ---------------------


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


# ---- Todo 3: output_rows sort by (delta1, delta2) tuple + delta-set check --


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


# ---- Todo 3: empty-expected guard + extra-key ignored ----------------------


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


# ---- Todo 4: parse_self_check_file — JSON loader + bad-schema detection ----


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


# ---- Todo 5: print_checklist() Unicode/ASCII rendering ---------------------


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


# ---- Todo 6: i18n self-check keys present in EN + RU ------------------------

# Names of the 5 self-check i18n keys added by Todo 6 (EN_BASE + RU_OVERRIDES).
SELF_CHECK_KEYS: tuple[str, ...] = (
    "self_check_title",
    "summary_passed",
    "summary_failed",
    "diff_label",
    "missing_label",
)


def test_i18n_self_check_keys_present_en() -> None:
    """All 5 self-check keys present in ``I18N["EN"]`` with non-empty values.

    Todo 6 adds 5 keys to ``EN_BASE`` in ``nts/i18n.py``. Each must be present
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
    # that Todo 5 reuses as ✓/✗ glyphs; if either drifts, Todo 5's assumption
    # breaks BEFORE Todo 5 lands).
    en = I18N["EN"]
    assert en["status_ok"] == "OK"
    assert en["status_bad"] == "not OK"


# ---- Todo 7: CLI integration (--self-check flag) ---------------------------


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

    RED on pre-Todo-7 ``cli.py``: the help message only documents ``--input``
    and ``--json``. GREEN once Todo 7 adds the ``--self-check`` argument.
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
        f"stdout drifted from pre-Todo-7 baseline; "
        f"diff={proc.stdout!r} vs {expected!r}"
    )


def test_cli_self_check_missing_expected_exits_2(
    tmp_path: Path,
    examples_dir: Path,
) -> None:
    """``--self-check`` on a payload without ``expected`` exits with status 2.

    Mirrors the S7 scenario from ``.omo/plans/self-check.md``: a self-check
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


# ---- Todo 8: end-to-end CLI subprocess integration (--self-check happy/mismatch) -


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