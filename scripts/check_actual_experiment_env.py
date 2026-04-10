from __future__ import annotations

import importlib.util
import json
import platform
import shutil


def main() -> None:
    dependency_status = {
        "platform": platform.platform(),
        "python3": shutil.which("python3") is not None,
        "ffprobe": shutil.which("ffprobe") is not None,
        "mn": shutil.which("mn") is not None,
        "pyav": importlib.util.find_spec("av") is not None,
    }
    dependency_status["ready"] = all(
        dependency_status[name]
        for name in ("python3", "ffprobe", "mn", "pyav")
    )
    print(json.dumps(dependency_status, indent=2))


if __name__ == "__main__":
    main()
