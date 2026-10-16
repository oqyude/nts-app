# NTS Self-Check — Полный листинг программы

**Назначение.** Листинг всего Python-кода, который исполняется при запуске режима
`python -m nts.cli --self-check FILE`. Используется для академической работы
«nts-app-reverse» (индивидуальный разбор исходных текстов).

**Состав дистрибутива self-check.**

| Файл | LOC | Назначение | Статус |
|------|----:|------------|--------|
| `nts/checker.py` | 745 | Верификация `ComputeResult` против эталона | новый |
| `nts/cli.py` | 92 | CLI-обёртка с режимом `--self-check` | изменён |
| `nts/i18n.py` | 133 | EN/RU словарь UI (5 новых ключей) | изменён |
| `examples/default_with_expected.json` | 149 | Демо-фикстура «input + expected» | новый |

**Неизменённые зависимости** (для полноты self-check используют, но сами не
модифицировались):

- `nts/core.py` — содержит `compute()`, `_parse_input_data()`, `ComputeResult`,
  `InputData`. Используется через `from nts.core import ...`.
- `tests/test_checker.py` — pytest-покрытие (1137 LOC).

**Запуск.**

```bash
# обычный режим (без изменений)
PYTHONIOENCODING=utf-8 python -m nts.cli --input examples/default.json

# режим самопроверки
PYTHONIOENCODING=utf-8 python -m nts.cli --self-check examples/default_with_expected.json
```

**Кодировка.** Все запуски требуют `PYTHONIOENCODING=utf-8` (Windows-консоль
по умолчанию CP1252, не печатает `δ`).

---

## Файл 1. `nts/checker.py`

```python
"""Self-check verification for ``ComputeResult`` payloads.

Todo 1 (DISCRETE): signs, f_result_code, equation, f_result, ``g_tests[i].ok``.
Todo 2 (NUMERIC): per-category tolerance for coefficient-like fields
(``coeff_abs``) and t-tests values (``t_abs``).
Todo 3: ``f_value`` inf/NaN policy, list-row sort-by-(key) with set validation,
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

Public API:
  * :class:`Tolerance` — category-specific numeric tolerances (defaults).
  * :class:`CheckEntry` — single field comparison result.
  * :class:`CheckResult` — aggregate with ``.passed`` / ``.failed`` / ``.entries``.
  * :func:`verify` — entry point.
  * :func:`parse_self_check_file` — load a self-check JSON file into a typed
    ``(InputData, ComputeResult)`` pair, with explicit ``ValueError`` on
    bad schema (missing ``input`` / ``expected`` key or empty payload).
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, List, Optional, cast

from nts.core import ComputeResult, InputData, _parse_input_data


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


# ---- NUMERIC comparison helpers (Todo 2) -----------------------------------


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
    """Emit ``CheckEntry`` rows for every NUMERIC field handled in Todo 2."""
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


# ---- f_value NaN/inf policy (Todo 3) ---------------------------------------


def _check_f_value(
    actual: Any,
    expected: Any,
    abs_tol: float,
) -> Optional[CheckEntry]:
    """Compare ``f_value`` with explicit NaN/``inf`` policy.

    Rules (per ``self-check.md`` Todo 3):
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


# ---- g_tests row-set validation + sort-by-row (Todo 3) ---------------------


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


# ---- output_rows delta-tuple sort (Todo 3) ---------------------------------


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


def verify(
    actual: dict[str, Any],
    expected: dict[str, Any],
    *,
    tolerance: Optional[Tolerance] = None,
) -> CheckResult:
    """Verify a ``ComputeResult`` payload against an expected reference.

    Compares DISCRETE top-level fields (signs, codes, equation, f_result),
    NUMERIC coefficient-like groups (``coeff_abs``), ``t_tests`` values
    (``t_abs``), the Fisher ``f_value`` (``f_abs``, with NaN/inf policy),
    ``g_tests`` row-set with sort-by-row plus per-row ``g``/``ok`` compare,
    and ``output_rows`` row-set with sort-by-(delta1, delta2) plus per-row
    numeric compare.

    Raises ``ValueError("expected must not be empty")`` when ``expected`` is an
    empty mapping. Unknown keys inside ``expected`` are silently ignored.
    """
    if not expected:
        raise ValueError("expected must not be empty")
    if tolerance is None:
        tolerance = Tolerance()
    entries = _compare_discrete(actual, expected)
    entries.extend(_compare_numeric(actual, expected, tolerance))
    entries.extend(_compare_f_value(actual, expected, tolerance))
    entries.extend(_compare_g_tests(actual, expected, tolerance))
    entries.extend(_compare_output_rows(actual, expected, tolerance))
    return _summarize(entries)


# ---- Todo 4: self-check JSON file loader -----------------------------------


def parse_self_check_file(path: Path) -> tuple[InputData, ComputeResult]:
    """Load a self-check JSON file. Returns ``(input_data, expected_result)``.

    Schema (top-level object, both keys required):

    ::

        {
          "input":    { ...InputData-shaped JSON... },
          "expected": { ...ComputeResult-shaped JSON... }
        }

    The ``input`` block is parsed via :func:`nts.core._parse_input_data` (same
    semantics as :func:`nts.core.read_input_json`); the ``expected`` block is
    kept as a raw ``dict`` cast to :class:`nts.core.ComputeResult` — its
    runtime fields are arbitrary and only consumed by :func:`verify`.

    Raises ``ValueError`` when the top-level payload is not a JSON object, is
    empty, or is missing either the ``input`` or ``expected`` key. Underlying
    ``_parse_input_data`` errors propagate unchanged.
    """
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
    return input_data, expected


# ---- Todo 5: print_checklist() Unicode/ASCII output ------------------------


def print_checklist(
    result: CheckResult,
    *,
    ascii: bool = False,
    file: Optional[Any] = None,
) -> None:
    """Render a :class:`CheckResult` as a human-readable checklist.

    Format per entry::

        <icon> <name>: actual=... expected=... (diff: <diff>)
            <message-if-any>

    Title is the hardcoded English ``"Self-check"`` for now (todo 6 wires i18n).
    Summary line at end: ``"<passed> passed, <failed> failed"``.

    Parameters:
        result: Aggregate verification report from :func:`verify`.
        ascii: When ``True`` use ``[OK]``/``[FAIL]`` instead of the Unicode
            glyphs ``✓``/``✗``. Useful for terminals/codepages that can't
            render the glyphs.
        file: Writable text stream (defaults to ``sys.stdout``). Caller is
            responsible for encoding.
    """
    if file is None:
        file = sys.stdout
    pass_icon = "[OK]" if ascii else "✓"
    fail_icon = "[FAIL]" if ascii else "✗"
    file.write("Self-check\n")
    for entry in result.entries:
        icon = pass_icon if entry.passed else fail_icon
        diff_str = "n/a" if entry.diff is None else f"{entry.diff:.6g}"
        file.write(
            f"  {icon} {entry.name}: actual={entry.actual!r} "
            f"expected={entry.expected!r} (diff: {diff_str})\n"
        )
        if entry.message:
            file.write(f"      {entry.message}\n")
    file.write(f"\n{result.passed} passed, {result.failed} failed\n")
```

---

## Файл 2. `nts/cli.py`

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import ComputeResult, InputData, compute, read_input_file


def print_report(result: ComputeResult) -> None:
    t = result["t_tests"]
    print(result["equation"])
    print("")
    print("t-tests:")
    for label, key, sign_key in (("t_0", "t0", "sign_b0"), ("t_1", "t1", "sign_b1"), ("t_2", "t2", "sign_b2")):
        print(f"  {label}: t={t[key]:.4f} sign={t[sign_key]}")
    print("")
    print("G-tests:")
    for row in result["g_tests"]:
        print(f"  row {row['row']}: G={row['g']:.4f} ({row['ok']})")
    print("")
    print("Output:")
    headers = ("y_avg", "delta1", "delta2", "y_pred", "y_avg-y", "(y_avg-y)^2")
    print("  " + " | ".join(headers))
    for r in result["output_rows"]:
        cells = (
            f"{r['y_avg']:.6g}", f"{r['delta1']:.6g}", f"{r['delta2']:.6g}",
            f"{r['y_pred']:.6g}", f"{r['y_avg_minus_y']:.6g}", f"{r['y_avg_minus_y_sq']:.6g}",
        )
        print("  " + " | ".join(cells))
    print("")
    print(f"F_avg={result['f_avg']:.6g}")
    print(f"F_value={result['f_value']:.6g}")
    print(result["f_result"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute results without Excel dependencies.")
    parser.add_argument(
        "path",
        nargs="?",
        help="Input file path (positional alternative to --input).",
    )
    parser.add_argument(
        "--input",
        dest="input_path",
        default=None,
        help="Path to JSON or XLSX input file (or self-check file when --self-check).",
    )
    parser.add_argument(
        "--self-check",
        dest="self_check",
        action="store_true",
        help="Run self-check mode: input JSON must be {\"input\": {...}, \"expected\": {...}}.",
    )
    parser.add_argument("--json", dest="json_path", help="Write result JSON to this path.")
    args = parser.parse_args()

    input_path_str = args.input_path or args.path
    if input_path_str is None:
        parser.error("the following arguments are required: --input or a positional path")
    args.input_path = input_path_str

    if args.self_check:
        from .checker import parse_self_check_file, print_checklist, verify
        try:
            input_data, expected = parse_self_check_file(Path(args.input_path))
        except (ValueError, FileNotFoundError) as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(2)
        actual = compute(input_data)
        result = verify(actual, expected)
        print_checklist(result)
        sys.exit(0 if result.failed == 0 else 1)
        return

    path = Path(args.input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    data: InputData = read_input_file(path)
    result = compute(data)
    print_report(result)

    if args.json_path:
        json_path = Path(args.json_path)
        json_path.write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
```

---

## Файл 3. `nts/i18n.py`

Изменены только словари `EN_BASE` (добавлены 5 ключей) и `RU_OVERRIDES` (добавлены
5 ключей). Все остальные строки файла без изменений.

### `EN_BASE` — финальная версия

```python
EN_BASE: Dict[str, Any] = {
    "title_main": "NTS Calculator",
    "title_output": "Output",
    "input_file": "Input file:",
    "browse": "Browse",
    "clear": "Clear",
    "calculate": "Calculate",
    "g_crit": "G_crit",
    "t_crit": "t_crit",
    "f_crit": "F_crit",
    "f_avg": "F_avg",
    "f_value": "F_value",
    "dnd_hint": "(Install tkinterdnd2 for drag & drop)",
    "load_error": "Load error",
    "calc_error": "Calculation error",
    "drop_file": "Please drop a .json or .xlsx file.",
    "empty_value": "Empty value in row {row}, {key}.",
    "crit_required": "G_crit, t_crit and F_crit must be filled.",
    "t_0": "t_0",
    "t_1": "t_1",
    "t_2": "t_2",
    "b0v": "b0 (v)",
    "b1v": "b1 (v)",
    "b2v": "b2 (v)",
    "lang": "Lang:",
    "result_not_rejected": "Hypothesis not rejected",
    "result_rejected": "Hypothesis rejected",
    "export_json": "Export JSON",
    "export_xlsx": "Export XLSX",
    "export_done": "Saved successfully.",
    "export_error": "Export error",
    "export_title": "Export",
    "delta1_sym": "δ1",
    "delta2_sym": "δ2",
    "grubbs_title": "Grubbs criterion",
    "grubbs_row": "Experiment {row}: G={g} {cmp} G_crit={gcrit} ({status})",
    "fisher_title": "Fisher criterion",
    "fisher_cmp": "F={f} {cmp} F_crit={fcrit}",
    "cmp_le": "<=",
    "cmp_gt": ">",
    "status_ok": "OK",
    "status_bad": "not OK",
    "self_check_title": "Self-check",                  # NEW
    "summary_passed": "{passed} passed",               # NEW
    "summary_failed": "{failed} failed",               # NEW
    "diff_label": "diff",                              # NEW
    "missing_label": "missing",                        # NEW
}
```

### `RU_OVERRIDES` — финальная версия

```python
RU_OVERRIDES: Dict[str, Any] = {
    "title_main": "Калькулятор НТС",
    "title_output": "Результат",
    "input_file": "Файл ввода:",
    "browse": "Обзор",
    "clear": "Очистить",
    "calculate": "Расчет",
    "g_crit": "G_крит",
    "t_crit": "t_крит",
    "f_crit": "F_крит",
    "f_avg": "F_ср",
    "f_value": "F_знач",
    "dnd_hint": "(Установите tkinterdnd2 для drag & drop)",
    "load_error": "Ошибка загрузки",
    "calc_error": "Ошибка расчета",
    "drop_file": "Перетащите файл .json или .xlsx.",
    "empty_value": "Пустое значение в строке {row}, {key}.",
    "crit_required": "Заполните G_крит, t_крит и F_крит.",
    "b0v": "b0 (в)",
    "b1v": "b1 (в)",
    "b2v": "b2 (в)",
    "lang": "Язык:",
    "result_not_rejected": "Гипотеза не отвергается",
    "result_rejected": "Гипотеза отвергается",
    "export_json": "Экспорт JSON",
    "export_xlsx": "Экспорт XLSX",
    "export_done": "Файл сохранен.",
    "export_error": "Ошибка экспорта",
    "export_title": "Экспорт",
    "grubbs_title": "Критерий Граббса",
    "grubbs_row": "Опыт {row}: G={g} {cmp} G_крит={gcrit} ({status})",
    "fisher_title": "Критерий Фишера",
    "fisher_cmp": "F={f} {cmp} F_крит={fcrit}",
    "status_bad": "не OK",
    "self_check_title": "Самопроверка",                  # NEW
    "summary_passed": "{passed} пройдено",               # NEW
    "summary_failed": "{failed} провалено",              # NEW
    "diff_label": "расхождение",                        # NEW
    "missing_label": "отсутствует",                     # NEW
}
```

### Сборка словарей (не изменилась)

```python
EN_HEADERS: Dict[str, str] = {
    "no": "No",
    "delta1": "δ1",
    "delta2": "δ2",
    "x1": "x1", "x2": "x2", "x3": "x3",
    "y1": "y1", "y2": "y2", "y3": "y3",
}

RU_HEADERS_OVERRIDES: Dict[str, str] = {
    "no": "№",
}


def _build(base, overrides, base_headers, header_overrides):
    out = {**base, **overrides}
    out["headers"] = {**base_headers, **header_overrides}
    return out


TRANSLATIONS: Dict[str, Dict[str, Any]] = {
    "EN": _build(EN_BASE, {}, EN_HEADERS, {}),
    "RU": _build(EN_BASE, RU_OVERRIDES, EN_HEADERS, RU_HEADERS_OVERRIDES),
}

I18N = TRANSLATIONS


def normalize_lang(lang: str) -> str:
    """Return a language code that exists in TRANSLATIONS (defaults to DEFAULT_LANGUAGE)."""
    return lang if lang in TRANSLATIONS else DEFAULT_LANGUAGE
```

---

## Файл 4. `examples/default_with_expected.json`

```json
{
  "input": {
    "experiments": [
      {
        "idx": 1,
        "delta1": -1,
        "delta2": -1,
        "x1": 43.75,
        "x2": 43.75,
        "x3": 12.5,
        "y1": 1167,
        "y2": 1238,
        "y3": 963
      },
      {
        "idx": 2,
        "delta1": -1,
        "delta2": 1,
        "x1": 35,
        "x2": 35,
        "x3": 30,
        "y1": 991,
        "y2": 992,
        "y3": 849
      },
      {
        "idx": 3,
        "delta1": 1,
        "delta2": -1,
        "x1": 55,
        "x2": 34.97,
        "x3": 10,
        "y1": 1167,
        "y2": 1116,
        "y3": 1135
      },
      {
        "idx": 4,
        "delta1": 1,
        "delta2": 1,
        "x1": 45.83,
        "x2": 25.17,
        "x3": 25,
        "y1": 967,
        "y2": 1119,
        "y3": 1058
      }
    ],
    "g_crit": 0.7679,
    "t_crit": 2.306,
    "f_crit": 239
  },
  "expected": {
    "coefficients": {
      "b0": 1063.5,
      "b1": 30.167,
      "b2": -67.5
    },
    "coefficients_v": {
      "b0": 1052.161,
      "b1": 86.587,
      "b2": -174.09
    },
    "z_averages": {
      "z1_avg": 1.348,
      "z2_avg": 0.606
    },
    "pz": {
      "pz1": 0.348,
      "pz2": 0.388
    },
    "delta_calc": {
      "delta1": -1.0,
      "delta2": -0.825
    },
    "g_tests": [
      { "row": 1, "g": 0.625, "ok": "OK" },
      { "row": 2, "g": 0.667, "ok": "OK" },
      { "row": 3, "g": 0.576, "ok": "OK" },
      { "row": 4, "g": 0.561, "ok": "OK" }
    ],
    "t_tests": {
      "t0": 39.73,
      "t1": 3.27,
      "t2": 6.574,
      "sign_b0": "+",
      "sign_b1": "+",
      "sign_b2": "+"
    },
    "output_rows": [
      {
        "y_avg": 1122.6666666666667,
        "delta1": -1.0,
        "delta2": -1.0,
        "y_pred": 1100.8333333333335,
        "y_avg_minus_y": 21.833333333333258,
        "y_avg_minus_y_sq": 476.69444444444116
      },
      {
        "y_avg": 944.0,
        "delta1": -1.0,
        "delta2": 1.0,
        "y_pred": 965.8333333333335,
        "y_avg_minus_y": -21.833333333333485,
        "y_avg_minus_y_sq": 476.69444444445105
      },
      {
        "y_avg": 1139.3333333333333,
        "delta1": 1.0,
        "delta2": -1.0,
        "y_pred": 1161.1666666666665,
        "y_avg_minus_y": -21.833333333333258,
        "y_avg_minus_y_sq": 476.69444444444116
      },
      {
        "y_avg": 1048.0,
        "delta1": 1.0,
        "delta2": 1.0,
        "y_pred": 1026.1666666666665,
        "y_avg_minus_y": 21.833333333333485,
        "y_avg_minus_y_sq": 476.69444444445105
      }
    ],
    "f_avg": 476.694,
    "f_value": 17.655,
    "f_result_code": "not_rejected",
    "f_result": "Hypothesis not rejected",
    "equation": "Y = 1063.5 + 30.167*δ1 - 67.5*δ2",
    "g_crit": 0.768,
    "t_crit": 2.306,
    "f_crit": 239.0
  }
}
```

---

## Контракт входа/выхода

### Вход: схема self-check JSON

```json
{
  "input":    { "experiments": [...], "g_crit": <float>, "t_crit": <float>, "f_crit": <float> },
  "expected": { /* ComputeResult-shaped dict, см. выше */ }
}
```

### Выход: чек-лист на stdout

```
Self-check
  ✓ <field>: actual=<val> expected=<val> (diff: <число|n/a>)
      <сообщение-при-ошибке>
  ✗ <field>: actual=<val> expected=<val> (diff: <число>)
      numeric mismatch: |<a> - <b>| = <Δ> > abs_tol=<tol>

<N> passed, <M> failed
```

Иконки `✓` `✗` (Unicode) или `[OK]` `[FAIL]` (ASCII, флаг `--ascii`).

### Коды возврата CLI

| Код | Когда |
|----:|-------|
| 0   | все поля прошли проверку (`result.failed == 0`) |
| 1   | хотя бы одно поле не совпало |
| 2   | файл не найден / пустой / не объект / нет `input` или `expected` ключа |

### Допуски

| Категория | `Tolerance.abs_tol` |
|-----------|---------------------|
| коэффициенты, z-средние, pz, δ, per-row g, per-row output_rows | `1e-3` |
| t-значения (`t0`, `t1`, `t2`) | `1e-2` |
| Fisher F-значение | `1e-1` |

---

## Точка входа (полная цепочка вызовов)

```
python -m nts.cli
  └─ nts.cli.main()                              nts/cli.py:38
       ├─ argparse (positional path, --input, --self-check, --json)
       ├─ if self_check:
       │     ├─ nts.checker.parse_self_check_file(path)
       │     │     ├─ json.load(path) → dict
       │     │     └─ nts.core._parse_input_data(data["input"])  → InputData
       │     ├─ nts.core.compute(input_data)   → ComputeResult
       │     ├─ nts.checker.verify(actual, expected)  → CheckResult
       │     │     ├─ _compare_discrete
       │     │     ├─ _compare_numeric    (coeff_abs + t_abs)
       │     │     ├─ _compare_f_value   (NaN/inf policy, f_abs)
       │     │     ├─ _compare_g_tests   (set compare → sort-by-row → per-row)
       │     │     └─ _compare_output_rows (set compare → sort-by-Δ → per-row)
       │     ├─ nts.checker.print_checklist(result)
       │     └─ sys.exit(0|1|2)
       └─ else (default mode, unchanged):
             ├─ nts.core.read_input_file(path) → InputData
             ├─ nts.core.compute(data)          → ComputeResult
             ├─ print_report(result)
             └─ (optional) write --json output
```

---

## Метрика

| Метрика | Значение |
|---------|----------|
| Новый Python LOC (без тестов) | 745 + 92 + 10 = 847 |
| Изменённый Python LOC (дифф i18n) | +10 в EN, +5 в RU |
| Новых JSON LOC | 149 |
| Файлов изменено | 5 (+ checker, test_checker, default_with_expected, cli, i18n, README) |
| Тестов добавлено | 31 (всего 47, +31 от baseline 16) |
| Manual scenarios | 7/7 PASS |
| Final F1-F4 verdict | 4/4 APPROVED |
