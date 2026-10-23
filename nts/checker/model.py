"""Модель самопроверки: константы формата и типы результатов.

Константы описывают формат эталонной книги (ядро / расширенное / словарь) и
режимы проверки; датаклассы — результат сравнения, который возвращает
:func:`nts.checker.compare.verify`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..core import ComputeResult, InputData


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


