from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

MAX_MODULE_BYTES = 1_048_576


@dataclass(frozen=True)
class Policy:
    fuel: int = 1_000_000
    cpu_seconds: int = 2
    wall_seconds: float = 5.0
    memory_bytes: int = 1_048_576
    table_elements: int = 1024
    disk_bytes: int = 0
    network: str = "deny"
    process_memory_bytes: int | None = None

    def __post_init__(self) -> None:
        for name, minimum, maximum in (
            ("fuel", 1, 10**12),
            ("cpu_seconds", 1, 30),
            ("memory_bytes", 65_536, 67_108_864),
            ("table_elements", 0, 65_536),
        ):
            value = getattr(self, name)
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")
        if (
            type(self.wall_seconds) not in (int, float)
            or not math.isfinite(self.wall_seconds)
            or not 0.01 <= self.wall_seconds <= 60
        ):
            raise ValueError("wall_seconds must be finite and in [0.01, 60]")
        if type(self.disk_bytes) is not int or self.disk_bytes != 0:
            raise ValueError("only zero guest disk bytes are supported")
        if self.network != "deny":
            raise ValueError("only denied guest network access is supported")
        if self.process_memory_bytes is not None:
            raise ValueError("total process-memory enforcement is unavailable")


@dataclass(frozen=True)
class Result:
    status: str
    value: int | None
    detail: str
    elapsed_seconds: float
    module_sha256: str
    policy: dict[str, Any]


def run(module: bytes, policy: Policy | None = None) -> Result:
    """Run bounded binary Wasm in a fresh worker; never execute native modules."""
    policy = Policy() if policy is None else policy
    if not isinstance(policy, Policy):
        raise TypeError("policy must be a Policy")
    policy.__post_init__()
    if sys.platform not in ("darwin", "linux"):
        raise RuntimeError("only macOS and Linux resource enforcement is supported")
    if not isinstance(module, bytes):
        raise TypeError("module must be bytes")
    if not 8 <= len(module) <= MAX_MODULE_BYTES or module[:8] != b"\0asm\x01\0\0\0":
        raise ValueError("expected binary core Wasm, at most 1 MiB")
    digest = hashlib.sha256(module).hexdigest()
    request = json.dumps(
        {"module": base64.b64encode(module).decode("ascii"), "policy": asdict(policy)}
    ).encode()
    started = time.monotonic()
    worker = Path(__file__).with_name("_worker.py").resolve()
    with tempfile.TemporaryDirectory(prefix="wasm-boundary-") as scratch:
        with subprocess.Popen(
            [sys.executable, "-I", "-B", str(worker)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=scratch,
            env={"OMP_NUM_THREADS": "1", "RAYON_NUM_THREADS": "1"},
            close_fds=True,
            start_new_session=True,
        ) as process:
            try:
                remaining = max(0.001, policy.wall_seconds - (time.monotonic() - started))
                output, _ = process.communicate(request, timeout=remaining)
            except subprocess.TimeoutExpired:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
                status, value, detail = "wall_limit", None, "worker deadline exceeded"
            except BaseException:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
                raise
            else:
                if process.returncode in (-signal.SIGKILL, -signal.SIGXCPU):
                    status, value, detail = (
                        "cpu_limit",
                        None,
                        "worker killed by signal consistent with CPU cap; external kill is indistinguishable",
                    )
                elif process.returncode:
                    status, value, detail = "worker_error", None, "worker failed without a report"
                else:
                    try:
                        report = json.loads(output)
                        status, value, detail = report["status"], report["value"], report["detail"]
                    except (ValueError, KeyError, TypeError):
                        status, value, detail = "worker_error", None, "invalid worker report"
    return Result(status, value, detail, time.monotonic() - started, digest, asdict(policy))
