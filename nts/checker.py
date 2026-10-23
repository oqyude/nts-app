"""Self-check verification for ``ComputeResult`` payloads.

DISCRETE: signs, f_result_code, equation, f_result, ``g_tests[i].ok``.
NUMERIC: per-category tolerance for coefficient-like fields
(``coeff_abs``) and t-tests values (``t_abs``).
f_value policy: ``f_value`` inf/NaN handling, list-row sort-by-(key) with set validation,
empty-expected guard, and missing/extra-key policy.

DISCRETE comparison contract:
  * exact ``==`` on string-valued fields (signs, codes, equation, f_result);
  * per-row comparison of ``g_tests[i].ok`` after row-set validation and
    stable sort by ``row`` key (``GTest`` HAS a ``row`` field per
    ``nts/core.py:25-28``);
  * one ``None`` ⇒ ``"missing in expected"|"missing in actual"`` entry;
    ``None,None`` ⇒ no entry.

NUMERIC comparison contract:
  * ``math.isclose(actual, expected, abs_tol=t.coeff_abs)`` for
    ``coefficients`` / ``coefficients_v`` / ``z_averages`` / ``pz`` /
    ``delta_calc`` fields, per-row ``g_tests.g``, and per-row
    ``output_rows.<field>``;
  * ``math.isclose(actual, expected, abs_tol=t.t_abs)`` for ``t_tests`` values;
  * ``f_value`` uses ``tolerance.f_abs`` with explicit ``NaN``/``inf`` policy
    (NaN never matches; matched infinities pass; ``inf`` vs finite fails).
  * entries with diff > tolerance get ``passed=False, diff=actual-expected``;
  * entries are skipped when both sides are missing the field; entries with
    one side missing get ``passed=False, diff=None``.

List-row sort contract:
  * ``g_tests`` — key = ``row`` (``int`` from ``GTest``);
  * ``output_rows`` — key = ``(delta1, delta2)`` tuple (OutputRow has NO
    ``row`` key per ``nts/core.py:61-67``; uniqueness follows
    ``DELTA1/2_SIGNATURE`` per ``nts/core.py:21-22``);
  * set mismatch ⇒ single explicit fail entry before any per-row compare.

Policy contract:
  * empty ``expected`` ⇒ ``ValueError("expected must not be empty")``;
  * unknown keys in ``expected`` are silently ignored (not compared).

Core vs extended:
  * a workbook keeps the **core** result keys on the ``result`` sheet and every
    other result key on the optional ``extended`` sheet;
  * the core set is the yellow-marked cell set of the reference workbook — the
    regression coefficients (coded and natural) plus the Student t-values, i.e.
    the numbers that answer "is the model right?";
  * a workbook **without** an ``extended`` sheet is a complete, runnable check:
    the simplified mode compares only the fields the reference file provides.

Public API:
  * :class:`Tolerance` — category-specific numeric tolerances (defaults).
  * :class:`CheckEntry` — single field comparison result.
  * :class:`CheckResult` — aggregate with ``.passed`` / ``.failed`` / ``.entries``.
  * :class:`SelfCheckBundle` — parsed file plus the verification mode it implies.
  * :func:`verify` — entry point.
  * :func:`parse_self_check_bundle` — load a self-check file into a
    :class:`SelfCheckBundle` (mode resolved from the file).
  * :func:`parse_self_check_file` — load a self-check file into a typed
    ``(InputData, ComputeResult)`` pair, with explicit ``ValueError`` on
    bad schema (missing ``input`` / ``expected`` key or empty payload).
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, cast

from nts.core import ComputeResult, InputData, _parse_input_data

from .dictionary import DESCRIPTIONS, UNKNOWN_DESCRIPTION, describe, describe_entry
from .i18n import DEFAULT_LANGUAGE, normalize_lang

# ---- Verification modes ------------------------------------------------------

#: Every field the verifier knows about must be present in the reference and
#: must match (JSON payloads, workbooks with an ``extended`` sheet).
MODE_FULL = "full"

#: Only the core keys (:data:`CORE_RESULT_KEYS`) are compared; the optional
#: fields (extended keys, G-tests, per-row output) are skipped.
MODE_SIMPLIFIED = "simplified"

#: Name of the optional sheet holding the non-core result keys.
EXTENDED_SHEET_NAME = "extended"

#: ARGB fill used to mark core cells (matches the reference workbook).
CORE_FILL_RGB = "FFFFFF00"

#: Header of the description column added next to ``key`` / ``value``.
DESCRIPTION_COLUMN = "description"

#: Name of the sheet carrying the full variable dictionary.
DICTIONARY_SHEET_NAME = "dictionary"

# ---- Core vs extended result keys --------------------------------------------
#
# The ``result`` sheet of a self-check workbook holds the *core* keys only.
# Everything else goes to the optional ``extended`` sheet, so a reference file
# without that sheet still verifies the model end-to-end (simplified mode).
#
# The core set mirrors the yellow-marked cells of the reference workbook:
# the regression coefficients (coded and natural) and the Student t-values.

CORE_RESULT_KEYS: tuple[str, ...] = (
    "f_value",
    "coefficients.b0",
    "coefficients.b1",
    "coefficients.b2",
    "coefficients_v.b0",
    "coefficients_v.b1",
    "coefficients_v.b2",
    "t_tests.t0",
    "t_tests.t1",
    "t_tests.t2",
)


@dataclass(frozen=True)
class SelfCheckBundle:
    """A parsed self-check file together with the mode it implies.

    ``mode`` is :data:`MODE_FULL` when the reference file declares full
    coverage — a JSON payload, or a workbook carrying an ``extended`` sheet —
    and :data:`MODE_SIMPLIFIED` for a workbook without that sheet, where only
    the core keys are compared.
    """

    input_data: InputData
    expected: Dict[str, Any]
    mode: str


@dataclass(frozen=True)
class Tolerance:
    """Per-category numeric tolerances. Defaults follow Excel reference precision."""

    coeff_abs: float = 1e-3  # b0, b1, b2 (and their variance counterparts)
    t_abs: float = 1e-2  # Student t-values
    f_abs: float = 1e-1  # Fisher F-value


@dataclass(frozen=True)
class CheckEntry:
    """Outcome of comparing one field between actual and expected."""

    name: str
    passed: bool
    actual: Any
    expected: Any
    diff: Optional[float]
    message: str


@dataclass(frozen=True)
class CheckResult:
    """Aggregate verification report."""

    passed: int
    failed: int
    entries: List[CheckEntry] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.passed + self.failed != len(self.entries):
            raise ValueError(
                f"CheckResult invariant violated: passed({self.passed}) "
                f"+ failed({self.failed}) != len(entries)({len(self.entries)})"
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
    * :data:`MODE_SIMPLIFIED` — only the core keys (:data:`CORE_RESULT_KEYS`)
      are compared. The optional fields (extended keys, G-tests, per-row
      output) are skipped, so a reference file without them still verifies the
      model.

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
        return _load_xlsx_bundle(path)
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
    their native type. Booleans (rare) are kept as-is.
    """
    parts = path.split(".")
    if len(parts) == 1:
        target[parts[0]] = _coerce_scalar(value)
        return
    group = parts[0]
    sub_key = parts[1]
    if group not in target or not isinstance(target.get(group), dict):
        target[group] = {}
    target[group][sub_key] = _coerce_scalar(value)


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
    bundle = _load_xlsx_bundle(path)
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


def _load_xlsx_bundle(path: Path) -> SelfCheckBundle:
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
        expected["g_tests"] = [
            {"row": int(float(rec["row"])), "g": float(rec["G"]), "ok": str(rec["ok"])}
            for rec in grubbs_records
            if rec.get("row") is not None
        ]

    if "output_rows" in wb.sheetnames:
        out_records = _parse_xlsx_sheet_to_dict(_read_xlsx_sheet_rows(wb, "output_rows"))
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
        ws.append([key, value, describe(key, lang)])
        if is_core:
            ws.cell(row=ws.max_row, column=2).fill = fill

    ws_g = wb.create_sheet("grubbs")
    ws_g.append(["row", "G", "ok"])
    for g in result["g_tests"]:
        ws_g.append([g["row"], g["g"], g["ok"]])

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


# ---- print_checklist() Unicode/ASCII output ------------------------


def print_checklist(
    result: CheckResult,
    *,
    ascii: bool = False,
    file: Optional[Any] = None,
    lang: Optional[str] = None,
) -> None:
    """Render a :class:`CheckResult` as a human-readable checklist.

    Format per entry::

        <icon> <name>: actual=... expected=... (diff: <diff>)
            <message-if-any>

    With ``lang`` set, the human description of the variable is appended to
    the name (``coefficients.b0 — Regression intercept (coded coefficients)``),
    so a reader does not have to know the key.

    Title is the hardcoded English ``"Self-check"`` for now (todo 6 wires i18n).
    Summary line at end: ``"<passed> passed, <failed> failed"``.

    Parameters:
        result: Aggregate verification report from :func:`verify`.
        ascii: When ``True`` use ``[OK]``/``[FAIL]`` instead of the Unicode
            glyphs ``✓``/``✗``. Useful for terminals/codepages that can't
            render the glyphs.
        file: Writable text stream (defaults to ``sys.stdout``). Caller is
            responsible for encoding.
        lang: Language code for the variable descriptions (see
            :mod:`nts.dictionary`). ``None`` keeps the bare key names.
    """
    if file is None:
        file = sys.stdout
    pass_icon = "[OK]" if ascii else "✓"
    fail_icon = "[FAIL]" if ascii else "✗"
    file.write("Self-check\n")
    for entry in result.entries:
        icon = pass_icon if entry.passed else fail_icon
        diff_str = "n/a" if entry.diff is None else f"{entry.diff:.6g}"
        label = entry.name
        if lang is not None:
            description = describe_entry(entry.name, lang)
            if description and description != UNKNOWN_DESCRIPTION:
                label = f"{entry.name} — {description}"
        file.write(
            f"  {icon} {label}: actual={entry.actual!r} "
            f"expected={entry.expected!r} (diff: {diff_str})\n"
        )
        if entry.message:
            file.write(f"      {entry.message}\n")
    file.write(f"\n{result.passed} passed, {result.failed} failed\n")