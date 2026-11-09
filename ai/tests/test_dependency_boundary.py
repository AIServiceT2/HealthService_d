"""rep_engine은 numpy, pydantic, pyyaml(+표준 라이브러리)만 import한다."""

import ast
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "rep_engine"
ALLOWED_THIRD_PARTY = {"numpy", "pydantic", "yaml"}
FORBIDDEN = {"mediapipe", "cv2"}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_engine_imports_only_allowed_modules() -> None:
    files = list(ENGINE.rglob("*.py"))
    assert files
    for f in files:
        for name in _imports(f):
            assert name not in FORBIDDEN, f"{f}: {name}"
            ok = (
                name == "rep_engine"
                or name in sys.stdlib_module_names
                or name in ALLOWED_THIRD_PARTY
            )
            assert ok, f"{f}: 허용되지 않은 import {name}"
