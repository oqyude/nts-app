"""Общие фикстуры для тестов NTS."""

from pathlib import Path

import pytest

from nts.core import Experiment


@pytest.fixture
def examples_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture
def default_experiments() -> list[Experiment]:
    return [
        Experiment(idx=1, delta1=-1, delta2=-1, x1=43.75, x2=43.75, x3=12.5,
                   y1=1167, y2=1238, y3=963),
        Experiment(idx=2, delta1=-1, delta2=1, x1=35.0, x2=35.0, x3=30.0,
                   y1=991, y2=992, y3=849),
        Experiment(idx=3, delta1=1, delta2=-1, x1=55.0, x2=34.97, x3=10.0,
                   y1=1167, y2=1116, y3=1135),
        Experiment(idx=4, delta1=1, delta2=1, x1=45.83, x2=25.17, x3=25.0,
                   y1=967, y2=1119, y3=1058),
    ]


@pytest.fixture
def default_criteria() -> tuple[float, float, float]:
    return 0.7679, 2.306, 239.0


@pytest.fixture
def all_significant_experiments() -> list[Experiment]:
    """Синтетический пример, где все три коэффициента значимы.

    y_avg = [900, 900, 900, 1300] даёт b_coded = (1000, 100, 100) ровно.
    Небольшой шум ±1 добавляет вариабельность для Стьюдента (s²_вос > 0).
    """
    return [
        Experiment(idx=1, delta1=-1, delta2=-1, x1=30.0, x2=50.0, x3=20.0,
                   y1=899, y2=901, y3=900),
        Experiment(idx=2, delta1=-1, delta2=1, x1=35.0, x2=45.0, x3=20.0,
                   y1=901, y2=900, y3=899),
        Experiment(idx=3, delta1=1, delta2=-1, x1=55.0, x2=35.0, x3=10.0,
                   y1=900, y2=901, y3=899),
        Experiment(idx=4, delta1=1, delta2=1, x1=45.0, x2=30.0, x3=25.0,
                   y1=1301, y2=1299, y3=1300),
    ]
