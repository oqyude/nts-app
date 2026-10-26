"""Движок сравнения: фактический результат против эталона.

Сравнение разбито по видам полей:

* DISCRETE — строковые поля (знаки, коды, уравнение, вердикт);
* NUMERIC — коэффициентоподобные группы и t-значения с погрешностями по
  категориям;
* ``f_value`` — отдельная политика NaN/inf;
* списки ``g_tests`` и ``output_rows`` — сверка множества строк и сравнение
  по ключу (соответственно ``row`` и ``(delta1, delta2)``).

Режимы: :data:`MODE_FULL` требует полноты эталона, :data:`MODE_SIMPLIFIED`
сравнивает ядро и, если он есть в эталоне, блок Граббса.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional

from .model import (
    CORE_RESULT_KEYS,
    MODE_FULL,
    MODE_SIMPLIFIED,
    SIMPLIFIED_EXTRA_KEYS,
    CheckEntry,
    CheckResult,
    Tolerance,
)


# ---- DISCRETE comparison helpers -------------------------------------------


def _eq_entry(
    name: str,
    actual: Any,
    expected: Any,
) -> CheckEntry:
    """Compare two scalar values with exact ``==``. Discrete fields only.

    Treats ``None`` on either side as a regular value (used by simple top-level
    discrete comparisons). Use :func:`_check_discrete` when ``(None, None)``
    must be skipped and one-sided ``None`` must be reported as "missing".
    """
    ok = actual == expected
    return CheckEntry(
        name=name,
        passed=bool(ok),
        actual=actual,
        expected=expected,
        diff=None,
        message="" if ok else f"discrete mismatch: {actual!r} != {expected!r}",
    )


def _check_discrete(
    name: str,
    actual: Any,
    expected: Any,
) -> Optional[CheckEntry]:
    """Compare discrete values with explicit handling of missing sides.

    Returns ``None`` when both sides are missing. Returns a failed
    ``CheckEntry`` (with ``diff=None`` and a "missing in expected/actual"
    message) when exactly one side is missing. Otherwise performs exact
    ``==`` comparison.
    """
    if actual is None and expected is None:
        return None
    if actual is None:
        return CheckEntry(
            name=name,
            passed=False,
            actual=actual,
            expected=expected,
            diff=None,
            message=f"missing in actual: actual={actual!r}, expected={expected!r}",
        )
    if expected is None:
        return CheckEntry(
            name=name,
            passed=False,
            actual=actual,
            expected=expected,
            diff=None,
            message=f"missing in expected: actual={actual!r}, expected={expected!r}",
        )
    return _eq_entry(name, actual, expected)


def _compare_discrete(
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> List[CheckEntry]:
    """Emit ``CheckEntry`` rows for top-level DISCRETE fields.

    ``g_tests`` per-row handling lives in :func:`_compare_g_tests` (todo 3).
    """
    entries: List[CheckEntry] = []

    # 1. t-tests signs (sign_b0, sign_b1, sign_b2) — exact string match.
    actual_t = actual.get("t_tests") or {}
    expected_t = expected.get("t_tests") or {}
    for key in ("sign_b0", "sign_b1", "sign_b2"):
        entry = _check_discrete(
            f"t_tests.{key}",
            actual_t.get(key),
            expected_t.get(key),
        )
        if entry is not None:
            entries.append(entry)

    # 2. f_result_code — single discrete string.
    entry = _check_discrete(
        "f_result_code",
        actual.get("f_result_code"),
        expected.get("f_result_code"),
    )
    if entry is not None:
        entries.append(entry)

    # 3. equation — full string (display form may include δ1, δ2).
    entry = _check_discrete(
        "equation",
        actual.get("equation"),
        expected.get("equation"),
    )
    if entry is not None:
        entries.append(entry)

    # 4. f_result — discrete verdict text.
    entry = _check_discrete(
        "f_result",
        actual.get("f_result"),
        expected.get("f_result"),
    )
    if entry is not None:
        entries.append(entry)

    return entries


def _summarize(entries: Iterable[CheckEntry]) -> CheckResult:
    passed = sum(1 for e in entries if e.passed)
    failed = sum(1 for e in entries if not e.passed)
    return CheckResult(passed=passed, failed=failed, entries=list(entries))


# ---- NUMERIC comparison helpers -----------------------------------


# Coefficient-like groups compared against ``tolerance.coeff_abs``.
_NUMERIC_COEFF_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("coefficients", ("b0", "b1", "b2")),
    ("coefficients_v", ("b0", "b1", "b2")),
    ("z_averages", ("z1_avg", "z2_avg")),
    ("pz", ("pz1", "pz2")),
    ("delta_calc", ("delta1", "delta2")),
)

# t-tests values compared against ``tolerance.t_abs`` (``sign_*`` are DISCRETE).
_NUMERIC_T_KEYS: tuple[str, ...] = ("t0", "t1", "t2")


def _check_numeric(
    name: str,
    actual: Any,
    expected: Any,
    abs_tol: float,
) -> Optional[CheckEntry]:
    """Compare two scalars with ``math.isclose``.

    Returns ``None`` when both sides are missing (no entry emitted). Returns a
    failed ``CheckEntry`` with ``diff=None`` when exactly one side is missing.
    Otherwise returns the entry with ``passed = math.isclose(...)`` and
    ``diff = actual - expected``.
    """
    if actual is None and expected is None:
        return None
    if actual is None or expected is None:
        return CheckEntry(
            name=name,
            passed=False,
            actual=actual,
            expected=expected,
            diff=None,
            message=f"missing numeric value: actual={actual!r}, expected={expected!r}",
        )
    ok = math.isclose(actual, expected, abs_tol=abs_tol)
    diff = actual - expected
    if ok:
        return CheckEntry(
            name=name,
            passed=True,
            actual=actual,
            expected=expected,
            diff=diff,
            message="",
        )
    return CheckEntry(
        name=name,
        passed=False,
        actual=actual,
        expected=expected,
        diff=diff,
        message=(
            f"numeric mismatch: |{actual!r} - {expected!r}| = {abs(diff)!r} "
            f"> abs_tol={abs_tol!r}"
        ),
    )


def _compare_numeric(
    actual: dict[str, Any],
    expected: dict[str, Any],
    tolerance: Tolerance,
) -> List[CheckEntry]:
    """Emit ``CheckEntry`` rows for every NUMERIC field of the coefficient-like groups."""
    entries: List[CheckEntry] = []

    for group_name, keys in _NUMERIC_COEFF_GROUPS:
        actual_group = actual.get(group_name) or {}
        expected_group = expected.get(group_name) or {}
        for key in keys:
            entry = _check_numeric(
                f"{group_name}.{key}",
                actual_group.get(key),
                expected_group.get(key),
                tolerance.coeff_abs,
            )
            if entry is not None:
                entries.append(entry)

    actual_t = actual.get("t_tests") or {}
    expected_t = expected.get("t_tests") or {}
    for key in _NUMERIC_T_KEYS:
        entry = _check_numeric(
            f"t_tests.{key}",
            actual_t.get(key),
            expected_t.get(key),
            tolerance.t_abs,
        )
        if entry is not None:
            entries.append(entry)

    return entries


# ---- f_value NaN/inf policy ---------------------------------------


def _check_f_value(
    actual: Any,
    expected: Any,
    abs_tol: float,
) -> Optional[CheckEntry]:
    """Compare ``f_value`` with explicit NaN/``inf`` policy.

    Rules:
      * ``None,None`` → no entry;
      * one side ``None`` → "missing" entry, ``passed=False``, ``diff=None``;
      * either side ``NaN`` → "NaN never matches" entry (NaN never matches
        even against itself);
      * both ``±inf`` of the same sign → pass, ``diff=0.0``;
      * both ``±inf`` of opposite sign → fail;
      * one ``inf`` and the other finite → fail with ``diff=±inf``;
      * both finite → ``math.isclose`` with ``abs_tol``.
    """
    if actual is None and expected is None:
        return None
    if actual is None or expected is None:
        return CheckEntry(
            name="f_value",
            passed=False,
            actual=actual,
            expected=expected,
            diff=None,
            message=f"missing numeric value: actual={actual!r}, expected={expected!r}",
        )

    # NaN never matches — even NaN vs NaN fails.
    if math.isnan(actual) or math.isnan(expected):
        return CheckEntry(
            name="f_value",
            passed=False,
            actual=actual,
            expected=expected,
            diff=None,
            message=f"NaN never matches: actual={actual!r}, expected={expected!r}",
        )

    actual_inf = math.isinf(actual)
    expected_inf = math.isinf(expected)

    if actual_inf and expected_inf:
        same_sign = (actual > 0) == (expected > 0)
        return CheckEntry(
            name="f_value",
            passed=same_sign,
            actual=actual,
            expected=expected,
            diff=0.0 if same_sign else float("inf"),
            message=(
                ""
                if same_sign
                else (
                    f"inf sign mismatch: actual={actual!r} != expected={expected!r}"
                )
            ),
        )

    if actual_inf or expected_inf:
        # ``actual - expected`` here is ±inf (never NaN — the ``both +inf``
        # case was handled above and NaN was rejected earlier).
        diff = actual - expected
        return CheckEntry(
            name="f_value",
            passed=False,
            actual=actual,
            expected=expected,
            diff=diff,
            message=(
                f"inf vs finite mismatch: actual={actual!r} != expected={expected!r}"
            ),
        )

    diff = actual - expected
    ok = math.isclose(actual, expected, abs_tol=abs_tol)
    if ok:
        return CheckEntry(
            name="f_value",
            passed=True,
            actual=actual,
            expected=expected,
            diff=diff,
            message="",
        )
    return CheckEntry(
        name="f_value",
        passed=False,
        actual=actual,
        expected=expected,
        diff=diff,
        message=(
            f"numeric mismatch: |{actual!r} - {expected!r}| = {abs(diff)!r} "
            f"> abs_tol={abs_tol!r}"
        ),
    )


def _compare_f_value(
    actual: dict[str, Any],
    expected: dict[str, Any],
    tolerance: Tolerance,
) -> List[CheckEntry]:
    """Emit a single ``f_value`` entry using the NaN/inf policy."""
    entry = _check_f_value(
        actual.get("f_value"),
        expected.get("f_value"),
        tolerance.f_abs,
    )
    return [entry] if entry is not None else []


# ---- g_tests row-set validation + sort-by-row ---------------------


def _compare_g_tests(
    actual: dict[str, Any],
    expected: dict[str, Any],
    tolerance: Tolerance,
) -> List[CheckEntry]:
    """Compare ``g_tests`` row-sets then per-row ``g`` (numeric) and ``ok``.

    Contract:
      * both sides absent → no entries;
      * exactly one side absent → single "missing" entry;
      * both sides empty → no entries;
      * row-set inequality → single explicit "row set mismatch" entry;
      * row-set equality → sort by ``row`` (stable) then per-row ``g`` and
        ``ok`` comparisons (numeric ``coeff_abs`` for ``g``).
    """
    entries: List[CheckEntry] = []

    actual_raw = actual.get("g_tests")
    expected_raw = expected.get("g_tests")
    actual_present = actual_raw is not None
    expected_present = expected_raw is not None

    if not actual_present and not expected_present:
        return entries
    if not actual_present or not expected_present:
        return [
            CheckEntry(
                name="g_tests",
                passed=False,
                actual=list(actual_raw) if actual_present else None,
                expected=list(expected_raw) if expected_present else None,
                diff=None,
                message=(
                    f"missing g_tests list: actual="
                    f"{'present' if actual_present else 'missing'}, "
                    f"expected={'present' if expected_present else 'missing'}"
                ),
            )
        ]

    actual_list: List[dict[str, Any]] = list(actual_raw)  # type: ignore[arg-type]
    expected_list: List[dict[str, Any]] = list(expected_raw)  # type: ignore[arg-type]

    if not actual_list and not expected_list:
        return entries

    actual_row_ids = [r.get("row") for r in actual_list]
    expected_row_ids = [r.get("row") for r in expected_list]

    if set(actual_row_ids) != set(expected_row_ids):
        actual_set = set(actual_row_ids)
        expected_set = set(expected_row_ids)
        actual_only = sorted(actual_set - expected_set)
        expected_only = sorted(expected_set - actual_set)
        msg_parts = []
        if actual_only:
            msg_parts.append(f"actual-only-rows={actual_only}")
        if expected_only:
            msg_parts.append(f"expected-only-rows={expected_only}")
        return [
            CheckEntry(
                name="g_tests",
                passed=False,
                actual=actual_row_ids,
                expected=expected_row_ids,
                diff=None,
                message=(
                    f"g_tests row set mismatch: actual={sorted(actual_set)} "
                    f"!= expected={sorted(expected_set)}"
                    + (f"; {'; '.join(msg_parts)}" if msg_parts else "")
                ),
            )
        ]

    actual_sorted = sorted(actual_list, key=lambda r: r.get("row"))
    expected_sorted = sorted(expected_list, key=lambda r: r.get("row"))

    for a_row, e_row in zip(actual_sorted, expected_sorted):
        row_id = a_row.get("row")
        g_entry = _check_numeric(
            f"g_tests[row={row_id}].g",
            a_row.get("g"),
            e_row.get("g"),
            tolerance.coeff_abs,
        )
        if g_entry is not None:
            entries.append(g_entry)
        ok_entry = _check_discrete(
            f"g_tests[row={row_id}].ok",
            a_row.get("ok"),
            e_row.get("ok"),
        )
        if ok_entry is not None:
            entries.append(ok_entry)

    return entries


# ---- output_rows delta-tuple sort ---------------------------------


_OUTPUT_ROW_FIELDS: tuple[str, ...] = (
    "y_avg",
    "delta1",
    "delta2",
    "y_pred",
    "y_avg_minus_y",
    "y_avg_minus_y_sq",
)


def _compare_output_rows(
    actual: dict[str, Any],
    expected: dict[str, Any],
    tolerance: Tolerance,
) -> List[CheckEntry]:
    """Compare ``output_rows`` row-sets then per-row fields.

    ``OutputRow`` has NO ``row`` key (``nts/core.py:61-67``), so the unique
    per-row identifier is the ``(delta1, delta2)`` tuple. Uniqueness follows
    ``DELTA1/2_SIGNATURE`` (``nts/core.py:21-22``).

    Same missing/empty/set-mismatch contract as :func:`_compare_g_tests`.
    """
    entries: List[CheckEntry] = []

    actual_raw = actual.get("output_rows")
    expected_raw = expected.get("output_rows")
    actual_present = actual_raw is not None
    expected_present = expected_raw is not None

    if not actual_present and not expected_present:
        return entries
    if not actual_present or not expected_present:
        return [
            CheckEntry(
                name="output_rows",
                passed=False,
                actual=list(actual_raw) if actual_present else None,
                expected=list(expected_raw) if expected_present else None,
                diff=None,
                message=(
                    f"missing output_rows list: actual="
                    f"{'present' if actual_present else 'missing'}, "
                    f"expected={'present' if expected_present else 'missing'}"
                ),
            )
        ]

    actual_list: List[dict[str, Any]] = list(actual_raw)  # type: ignore[arg-type]
    expected_list: List[dict[str, Any]] = list(expected_raw)  # type: ignore[arg-type]

    if not actual_list and not expected_list:
        return entries

    actual_keys = [(r.get("delta1"), r.get("delta2")) for r in actual_list]
    expected_keys = [(r.get("delta1"), r.get("delta2")) for r in expected_list]

    if set(actual_keys) != set(expected_keys):
        actual_set = set(actual_keys)
        expected_set = set(expected_keys)
        return [
            CheckEntry(
                name="output_rows",
                passed=False,
                actual=sorted(actual_set),
                expected=sorted(expected_set),
                diff=None,
                message=(
                    f"output_rows delta set mismatch: "
                    f"actual={sorted(actual_set)} != expected={sorted(expected_set)}"
                ),
            )
        ]

    actual_sorted = sorted(
        actual_list, key=lambda r: (r.get("delta1"), r.get("delta2"))
    )
    expected_sorted = sorted(
        expected_list, key=lambda r: (r.get("delta1"), r.get("delta2"))
    )

    for a_row, e_row in zip(actual_sorted, expected_sorted):
        row_key = (a_row.get("delta1"), a_row.get("delta2"))
        for field_name in _OUTPUT_ROW_FIELDS:
            entry = _check_numeric(
                f"output_rows{list(row_key)!s}.{field_name}",
                a_row.get(field_name),
                e_row.get(field_name),
                tolerance.coeff_abs,
            )
            if entry is not None:
                entries.append(entry)

    return entries


# ---- public entry point ----------------------------------------------------


def _project_actual_to_expected(
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    """Restrict ``actual`` to the fields ``expected`` actually provides.

    Used by the simplified mode: a reference file may legitimately omit
    fields (that is exactly what the optional ``extended`` sheet is for).
    Dropping those fields from the *actual* payload makes the comparison skip
    them instead of reporting them as missing. A field present in ``expected``
    but absent from ``actual`` stays absent on purpose — that is a real
    failure, not a coverage gap.
    """
    projected: dict[str, Any] = {}
    for key, exp_value in expected.items():
        act_value = actual.get(key)
        if isinstance(exp_value, dict):
            if not isinstance(act_value, dict):
                continue
            sub = {k: act_value[k] for k in exp_value if k in act_value}
            if sub:
                projected[key] = sub
            continue
        if isinstance(exp_value, list):
            if act_value is not None:
                projected[key] = act_value
            continue
        if key in actual:
            projected[key] = act_value
    return projected


def _select_core_expected(expected: dict[str, Any]) -> dict[str, Any]:
    """Keep only the core keys of an expected payload.

    :data:`CORE_RESULT_KEYS` are dotted paths (``coefficients.b0``); the
    result is a nested dict shaped like ``expected`` again. Groups keep only
    the core leaves — ``coefficients`` keeps ``b0``/``b1``/``b2`` and nothing
    else.

    :data:`SIMPLIFIED_EXTRA_KEYS` (the Grubbs block) are carried over when the
    reference file provides them: a core-only workbook still ships a
    ``grubbs`` sheet, and the criterion belongs to the core method even though
    it is not one of the yellow-marked scalar cells.
    """
    out: dict[str, Any] = {}
    for path in CORE_RESULT_KEYS:
        parts = path.split(".")
        if len(parts) == 1:
            if path in expected:
                out[path] = expected[path]
            continue
        group_name, leaf = parts[0], parts[1]
        group = expected.get(group_name)
        if not isinstance(group, dict) or leaf not in group:
            continue
        out.setdefault(group_name, {})[leaf] = group[leaf]
    for path in SIMPLIFIED_EXTRA_KEYS:
        if path in expected:
            out[path] = expected[path]
    return out


def verify(
    actual: dict[str, Any],
    expected: dict[str, Any],
    *,
    tolerance: Optional[Tolerance] = None,
    mode: str = MODE_FULL,
) -> CheckResult:
    """Verify a ``ComputeResult`` payload against an expected reference.

    Compares DISCRETE top-level fields (signs, codes, equation, f_result),
    NUMERIC coefficient-like groups (``coeff_abs``), ``t_tests`` values
    (``t_abs``), the Fisher ``f_value`` (``f_abs``, with NaN/inf policy),
    ``g_tests`` row-set with sort-by-row plus per-row ``g``/``ok`` compare,
    and ``output_rows`` row-set with sort-by-(delta1, delta2) plus per-row
    numeric compare.

    ``mode``:

    * :data:`MODE_FULL` (default) — the reference must cover every field the
      comparison knows about; a field missing from ``expected`` is a failure.
    * :data:`MODE_SIMPLIFIED` — the core keys (:data:`CORE_RESULT_KEYS`) are
      compared, plus the Grubbs block (:data:`SIMPLIFIED_EXTRA_KEYS`) when the
      reference provides it. The remaining optional fields (extended keys,
      per-row output) are skipped, so a reference file without them still
      verifies the model.

    Raises ``ValueError("expected must not be empty")`` when ``expected`` is an
    empty mapping. Unknown keys inside ``expected`` are silently ignored.
    """
    if not expected:
        raise ValueError("expected must not be empty")
    if tolerance is None:
        tolerance = Tolerance()
    if mode == MODE_SIMPLIFIED:
        expected = _select_core_expected(expected)
        actual = _project_actual_to_expected(actual, expected)
    elif mode != MODE_FULL:
        raise ValueError(
            f"unknown verification mode {mode!r} "
            f"(expected {MODE_FULL!r} or {MODE_SIMPLIFIED!r})"
        )
    entries = _compare_discrete(actual, expected)
    entries.extend(_compare_numeric(actual, expected, tolerance))
    entries.extend(_compare_f_value(actual, expected, tolerance))
    entries.extend(_compare_g_tests(actual, expected, tolerance))
    entries.extend(_compare_output_rows(actual, expected, tolerance))
    return _summarize(entries)


