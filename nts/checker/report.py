"""Отчёт по результату проверки: текстовый чек-лист."""
from __future__ import annotations

import sys
from typing import Any, Optional

from ..dictionary import UNKNOWN_DESCRIPTION, describe_entry
from ..i18n import I18N, localize_check_value, normalize_lang, translate_message
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
    so a reader does not have to know the key. The same ``lang`` localizes the
    title, the labels, the canonical values (Fisher verdict, G-test status)
    and the technical note of a failed check. Without ``lang`` the output is
    the language-neutral English checklist.

    Summary line at end: ``"<passed> passed, <failed> failed"`` (translated
    when ``lang`` is given).

    Parameters:
        result: Aggregate verification report from :func:`verify`.
        ascii: When ``True`` use ``[OK]``/``[FAIL]`` instead of the Unicode
            glyphs ``✓``/``✗``. Useful for terminals/codepages that can't
            render the glyphs.
        file: Writable text stream (defaults to ``sys.stdout``). Caller is
            responsible for encoding.
        lang: Language code for the variable descriptions and the report
            labels (see :mod:`nts.dictionary` / :mod:`nts.i18n`). ``None``
            keeps the bare key names and the English labels.
    """
    if file is None:
        file = sys.stdout
    table = I18N[normalize_lang(lang)] if lang is not None else I18N["EN"]
    pass_icon = "[OK]" if ascii else "✓"
    fail_icon = "[FAIL]" if ascii else "✗"
    file.write(f"{table['self_check_title']}\n")
    for entry in result.entries:
        icon = pass_icon if entry.passed else fail_icon
        diff_str = (
            table["report_not_applicable"]
            if entry.diff is None
            else f"{entry.diff:.6g}"
        )
        label = entry.name
        actual = entry.actual
        expected = entry.expected
        message = entry.message
        if lang is not None:
            description = describe_entry(entry.name, lang)
            if description and description != UNKNOWN_DESCRIPTION:
                label = f"{entry.name} — {description}"
            actual = localize_check_value(entry.name, actual, lang)
            expected = localize_check_value(entry.name, expected, lang)
            message = translate_message(message, lang)
        file.write(
            f"  {icon} {label}: {table['report_actual']}={actual!r} "
            f"{table['report_expected']}={expected!r} "
            f"({table['report_diff']}: {diff_str})\n"
        )
        if message:
            file.write(f"      {message}\n")
    summary = (
        table["summary_passed"].format(passed=result.passed)
        + ", "
        + table["summary_failed"].format(failed=result.failed)
    )
    file.write(f"\n{summary}\n")
