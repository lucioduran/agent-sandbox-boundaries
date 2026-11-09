from __future__ import annotations

import argparse
import json
import os
import stat
from dataclasses import asdict
from pathlib import Path

from .runner import MAX_MODULE_BYTES, Policy, run


def read_module(path: Path) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("module must be a regular file, not a symlink or device")
        return stream.read(MAX_MODULE_BYTES + 1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run capability-free binary Wasm")
    parser.add_argument("module", type=Path)
    parser.add_argument("--policy", type=Path, help="strict JSON policy object")
    args = parser.parse_args()
    try:
        settings = json.loads(args.policy.read_text()) if args.policy else {}
        policy = Policy(**settings)
        result = run(read_module(args.module), policy)
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        print(json.dumps({"status": "configuration_error", "detail": str(exc)}))
        return 2
    print(json.dumps(asdict(result), sort_keys=True))
    return 0 if result.status == "ok" or (result.status == "exit" and result.value == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
