"""프로젝트 디렉토리 구조 초기화 스크립트.

새로운 모듈 디렉토리(emulation, realworld, quic)를 생성합니다.

사용법:
    python scripts/init_project_structure.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger(__name__)


def init_directories() -> None:
    """프로젝트에 필요한 디렉토리 구조를 생성한다."""
    directories = [
        "emulation",
        "realworld",
        "quic",
    ]
    
    for dirname in directories:
        dirpath = REPO_ROOT / dirname
        dirpath.mkdir(parents=True, exist_ok=True)
        
        # __init__.py 생성
        init_file = dirpath / "__init__.py"
        if not init_file.exists():
            init_file.write_text(f'"""{ dirname} module."""\n', encoding="utf-8")
        
        logger.info("Created: %s", dirpath)
    
    logger.info("프로젝트 구조 초기화 완료")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    init_directories()


if __name__ == "__main__":
    main()
