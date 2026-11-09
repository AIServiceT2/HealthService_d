from __future__ import annotations

import pytest

from rep_engine.config import Catalog, EngineConfig, load_catalog


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    return load_catalog("cat_2026-11-01")


@pytest.fixture(scope="session")
def cfg(catalog: Catalog) -> EngineConfig:
    return catalog.for_model("mediapipe")
