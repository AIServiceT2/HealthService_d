from pathlib import Path
from typing import Any

import pytest
import yaml

from rep_engine.config import (
    DEFAULT_CATALOG_DIR,
    list_catalog_versions,
    load_catalog,
    parse_catalog,
)
from rep_engine.errors import CatalogNotFoundError, ConfigError

VERSION = "cat_2026-11-01"


def _raw() -> dict[str, Any]:
    with (DEFAULT_CATALOG_DIR / f"{VERSION}.yaml").open(encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f)
    return data


def test_default_catalog_loads() -> None:
    cat = load_catalog(VERSION)
    assert cat.version == VERSION
    assert cat.base.squat.depth_accept_angle == 100
    assert VERSION in list_catalog_versions()


def test_model_override_applies_only_to_that_family() -> None:
    cat = load_catalog(VERSION)
    assert cat.for_model("movenet").features.min_visibility == 0.3
    assert cat.for_model("mediapipe").features.min_visibility == 0.5
    assert cat.for_model("unknown_family") is cat.base


def test_missing_catalog_and_bad_version() -> None:
    with pytest.raises(CatalogNotFoundError):
        load_catalog("cat_1999-01-01")
    with pytest.raises(CatalogNotFoundError):
        load_catalog("../etc/passwd")


def test_weights_must_sum_to_one() -> None:
    d = _raw()
    d["confidence"]["weights"]["vis"] = 0.5
    with pytest.raises(ConfigError, match="합이 1"):
        parse_catalog(d)


def test_missing_field_fails() -> None:
    d = _raw()
    del d["squat"]["stand_angle"]
    with pytest.raises(ConfigError):
        parse_catalog(d)


@pytest.mark.parametrize(
    "points",
    [
        [[0.0, 0.0], [0.5, 0.5], [0.4, 0.6], [1.0, 1.0]],  # raw 순서 틀림
        [[0.0, 0.0], [0.5, 0.7], [1.0, 0.6]],  # 보정값 감소
        [[0.1, 0.0], [1.0, 1.0]],  # 0 없음
        [[0.0, 0.0], [1.0, 1.5]],  # 범위 밖
    ],
)
def test_calibration_validation(points: list[list[float]]) -> None:
    d = _raw()
    d["confidence"]["calibration"] = points
    with pytest.raises(ConfigError):
        parse_catalog(d)


def test_squat_angle_order_validation() -> None:
    d = _raw()
    d["squat"]["attempt_angle"] = 90
    with pytest.raises(ConfigError):
        parse_catalog(d)
    d = _raw()
    d["squat"]["min_rep_ms"] = 200
    with pytest.raises(ConfigError):
        parse_catalog(d)


def test_bad_override_rejected() -> None:
    d = _raw()
    d["model_overrides"] = {"movenet": {"features": {"min_visibility": 3}}}
    with pytest.raises(ConfigError):
        parse_catalog(d)
    d["model_overrides"] = {"movenet": {"nope": 1}}
    with pytest.raises(ConfigError):
        parse_catalog(d)
    d["model_overrides"] = ["x"]
    with pytest.raises(ConfigError):
        parse_catalog(d)


def test_non_mapping_and_version_mismatch(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        parse_catalog([])  # type: ignore[arg-type]
    d = _raw()
    (tmp_path / "cat_other.yaml").write_text(yaml.safe_dump(d), encoding="utf-8")
    with pytest.raises(ConfigError, match="다름"):
        load_catalog("cat_other", tmp_path)
