"""MediaPipe Pose Landmarker 모델(.task)을 models/에 내려받는다.

URL 출처: https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker
(2026-11-09 확인). 이미 있으면 건너뛴다.

    python -m tools.download_models                 # lite, full, heavy 모두
    python -m tools.download_models --models lite
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import ssl
import urllib.request
from pathlib import Path

from tools.common import MODELS_DIR, setup_logging

VARIANTS = ("lite", "full", "heavy")
URL_TEMPLATE = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_{v}/float16/latest/pose_landmarker_{v}.task"
)
TIMEOUT_S = 120


def model_path(variant: str, models_dir: Path = MODELS_DIR) -> Path:
    return models_dir / f"pose_landmarker_{variant}.task"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _ssl_context() -> ssl.SSLContext:
    """인증서 검증을 켠 SSL 컨텍스트. macOS python.org 빌드는 시스템 인증서를 못 찾는 경우가 있어
    certifi(httpx 의존성으로 설치됨)가 있으면 그 인증서 묶음을 쓴다. 검증을 끄지 않는다."""
    try:
        import certifi
    except ImportError:  # pragma: no cover
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def download(variant: str, models_dir: Path = MODELS_DIR, force: bool = False) -> Path:
    """모델 1개를 내려받는다 (임시 파일에 받은 뒤 이름을 바꿔 중간 실패 파일을 남기지 않음)."""
    log = setup_logging()
    dest = model_path(variant, models_dir)
    if dest.is_file() and dest.stat().st_size > 0 and not force:
        log.info("있음, 건너뜀: %s", dest.name)
        return dest
    models_dir.mkdir(parents=True, exist_ok=True)
    url = URL_TEMPLATE.format(v=variant)
    tmp = dest.with_suffix(".part")
    log.info("내려받는 중: %s", url)
    with (
        urllib.request.urlopen(url, timeout=TIMEOUT_S, context=_ssl_context()) as resp,
        tmp.open("wb") as out,
    ):
        shutil.copyfileobj(resp, out)
    tmp.replace(dest)
    log.info("저장: %s (%d bytes, sha256 %s)", dest, dest.stat().st_size, sha256(dest))
    return dest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="MediaPipe Pose Landmarker 모델 내려받기")
    p.add_argument("--models", nargs="+", choices=VARIANTS, default=list(VARIANTS))
    p.add_argument("--dest", type=Path, default=MODELS_DIR, help="저장 폴더 (기본 models/)")
    p.add_argument("--force", action="store_true", help="이미 있어도 다시 받기")
    a = p.parse_args(argv)
    for v in a.models:
        download(v, a.dest, a.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
