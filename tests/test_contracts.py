"""Контракты между модулями — страховочные тесты.

Эти тесты фиксируют договорённости, которые должны выполняться и до, и после
изменений: версия, которую получает сборка, и публичный API пакета
``nts.checker``. Они специально устроены так, чтобы проходить при обоих
вариантах реализации — проверяется инвариант, а не способ его достижения.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_build_module() -> Any:
    """Загрузить ``build.py`` как модуль (без запуска сборки)."""
    path = REPO_ROOT / "build.py"
    spec = importlib.util.spec_from_file_location("nts_build_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _build_file_version() -> str:
    """Версия, которую сборка передаёт Nuitka как ``--file-version``.

    До появления единого источника версии это литерал в команде сборки,
    после — результат ``build.app_version()``. Инвариант один: версия
    сборки совпадает с версией пакета.
    """
    module = _load_build_module()
    getter = getattr(module, "app_version", None)
    if getter is not None:
        return str(getter())
    source = Path(module.__file__).read_text(encoding="utf-8")
    match = re.search(r"--file-version=([0-9][0-9.]*)", source)
    assert match, "в build.py не найден флаг --file-version"
    return match.group(1)


def test_build_version_matches_package_version() -> None:
    """Версия, зашиваемая в .exe, совпадает с ``nts.__version__``.

    Страховка перед вынесением версии в единый источник: литерал
    ``--file-version=0.2.1`` в ``build.py`` и ``__version__`` в
    ``nts/__init__.py`` обязаны совпадать.
    """
    import nts

    assert _build_file_version() == nts.__version__


#: Публичный API самопроверки. Им пользуются nts/cli.py, nts/gui.py,
#: nts/reverse_gui.py и тесты — переименование или удаление любого имени
#: ломает их импорт.
CHECKER_PUBLIC_API: tuple[str, ...] = (
    "Tolerance",
    "CheckEntry",
    "CheckResult",
    "SelfCheckBundle",
    "verify",
    "parse_self_check_file",
    "parse_self_check_bundle",
    "parse_self_check_xlsx",
    "write_self_check_xlsx",
    "print_checklist",
    "CORE_RESULT_KEYS",
    "MODE_FULL",
    "MODE_SIMPLIFIED",
    "EXTENDED_SHEET_NAME",
    "DICTIONARY_SHEET_NAME",
    "CORE_FILL_RGB",
    "DESCRIPTION_COLUMN",
)


def test_checker_public_api_surface() -> None:
    """Все публичные имена ``nts.checker`` доступны и экспортируются.

    Страховка перед разбиением монолита ``nts/checker.py`` на пакет: API
    должен остаться прежним, иначе ломаются импорты в CLI и обоих GUI.
    """
    import nts.checker as checker

    missing = [name for name in CHECKER_PUBLIC_API if not hasattr(checker, name)]
    assert not missing, f"пропали публичные имена nts.checker: {missing}"

    exported = getattr(checker, "__all__", None)
    if exported is not None:
        not_exported = [name for name in CHECKER_PUBLIC_API if name not in exported]
        assert not not_exported, f"не попали в __all__: {not_exported}"


def test_checker_verify_behaviour_is_pinned() -> None:
    """Поведение ``verify()`` зафиксировано: имена полей и счётчики.

    Страховка перед любым рефакторингом движка сравнения: на эталонной
    фикстуре проверка даёт ровно 10 пройденных полей ядра и ни одного
    расхождения, а имена полей не меняются.
    """
    from nts.checker import MODE_SIMPLIFIED, verify

    actual: dict[str, Any] = {
        "coefficients": {"b0": 1.0, "b1": 2.0, "b2": 3.0},
        "coefficients_v": {"b0": 10.0, "b1": 20.0, "b2": 30.0},
        "z_averages": {"z1_avg": 1.5, "z2_avg": 2.5},
        "pz": {"pz1": 0.5, "pz2": 1.5},
        "delta_calc": {"delta1": 0.4, "delta2": 0.6},
        "t_tests": {
            "t0": 5.0, "t1": 4.0, "t2": 3.0,
            "sign_b0": "+", "sign_b1": "+", "sign_b2": "+",
        },
        "g_tests": [
            {"row": 1, "g": 0.1, "ok": "OK"},
            {"row": 2, "g": 0.2, "ok": "OK"},
        ],
        "output_rows": [
            {
                "delta1": -1.0, "delta2": -1.0, "y_avg": 110.0,
                "y_pred": 109.5, "y_avg_minus_y": 0.5, "y_avg_minus_y_sq": 0.25,
            },
        ],
        "f_avg": 50.0,
        "f_value": 5.0,
        "f_result_code": "not_rejected",
        "f_result": "ok",
        "equation": "Y = b0 + b1·δ1 + b2·δ2",
        "g_crit": 0.5,
        "t_crit": 2.0,
        "f_crit": 100.0,
    }
    expected: dict[str, Any] = {
        "coefficients": {"b0": 1.0, "b1": 2.0, "b2": 3.0},
        "coefficients_v": {"b0": 10.0, "b1": 20.0, "b2": 30.0},
        "t_tests": {"t0": 5.0, "t1": 4.0, "t2": 3.0},
        "f_value": 5.0,
    }

    result = verify(actual, expected, mode=MODE_SIMPLIFIED)

    assert result.failed == 0
    assert result.passed == 10
    assert [entry.name for entry in result.entries] == [
        "coefficients.b0", "coefficients.b1", "coefficients.b2",
        "coefficients_v.b0", "coefficients_v.b1", "coefficients_v.b2",
        "t_tests.t0", "t_tests.t1", "t_tests.t2",
        "f_value",
    ]


def test_checker_verify_reports_mismatch_in_full_mode() -> None:
    """В полном режиме расхождение по-прежнему попадает в отчёт."""
    from nts.checker import MODE_FULL, verify

    actual: dict[str, Any] = {
        "coefficients": {"b0": 1.0, "b1": 2.0, "b2": 3.0},
        "coefficients_v": {"b0": 10.0, "b1": 20.0, "b2": 30.0},
        "z_averages": {"z1_avg": 1.5, "z2_avg": 2.5},
        "pz": {"pz1": 0.5, "pz2": 1.5},
        "delta_calc": {"delta1": 0.4, "delta2": 0.6},
        "t_tests": {
            "t0": 5.0, "t1": 4.0, "t2": 3.0,
            "sign_b0": "+", "sign_b1": "+", "sign_b2": "+",
        },
        "g_tests": [{"row": 1, "g": 0.1, "ok": "OK"}],
        "output_rows": [],
        "f_avg": 50.0,
        "f_value": 5.0,
        "f_result_code": "not_rejected",
        "f_result": "ok",
        "equation": "Y = b0",
        "g_crit": 0.5,
        "t_crit": 2.0,
        "f_crit": 100.0,
    }
    expected = dict(actual)
    expected["coefficients"] = {"b0": 1.5, "b1": 2.0, "b2": 3.0}

    result = verify(actual, expected, mode=MODE_FULL)

    failed = [entry for entry in result.entries if not entry.passed]
    assert [entry.name for entry in failed] == ["coefficients.b0"]
    assert failed[0].diff == pytest.approx(-0.5)
