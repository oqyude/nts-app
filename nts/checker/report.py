"""Отчёт по результату проверки: текстовый чек-лист."""
from __future__ import annotations

import sys
from typing import Any, Optional

from ..dictionary import UNKNOWN_DESCRIPTION, describe_entry
from .model import CheckResult


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