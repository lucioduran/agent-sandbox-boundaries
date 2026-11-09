import json
import os
import subprocess
import sys
from dataclasses import replace

import pytest
import wasmtime

from experiments.probes import probes
from sandbox_boundaries import Policy, run
from sandbox_boundaries.__main__ import read_module
from sandbox_boundaries.runner import MAX_MODULE_BYTES


@pytest.fixture
def binary():
    return bytes(wasmtime.wat2wasm('(module (func (export "run") (result i32) i32.const 42))'))


@pytest.mark.parametrize(
    "probe",
    [
        pytest.param(p, marks=pytest.mark.stress if p.stress else (), id=p.name)
        for p in probes("/synthetic-only/canary.txt")
    ],
)
def test_probe(probe):
    result = run(probe.binary(), probe.policy)
    assert (result.status, result.value) == (probe.status, probe.value), result
    assert result.elapsed_seconds < probe.policy.wall_seconds + 2


@pytest.mark.parametrize(
    "settings",
    [
        {"fuel": 0},
        {"fuel": True},
        {"fuel": 10**12 + 1},
        {"cpu_seconds": 0},
        {"cpu_seconds": 1.2},
        {"memory_bytes": 65535},
        {"memory_bytes": 2**30},
        {"table_elements": -1},
        {"wall_seconds": float("nan")},
        {"wall_seconds": float("inf")},
        {"wall_seconds": True},
        {"wall_seconds": 0},
        {"wall_seconds": 61},
        {"disk_bytes": 1},
        {"disk_bytes": False},
        {"network": "allow"},
        {"process_memory_bytes": 2**30},
    ],
)
def test_invalid_policy(settings):
    with pytest.raises(ValueError):
        Policy(**settings)


def test_unknown_policy():
    with pytest.raises(TypeError):
        Policy(extra=1)


@pytest.mark.parametrize(
    "module", [b"", b"(module)", b"\0asm\x02\0\0\0", b"\0asm\x01\0\0\0" + b"x" * MAX_MODULE_BYTES]
)
def test_invalid_input(module):
    with pytest.raises(ValueError):
        run(module)


def test_types(binary):
    with pytest.raises(TypeError):
        run("text")
    for invalid in ({"fuel": 1}, {}, False, 0):
        with pytest.raises(TypeError):
            run(binary, invalid)


def test_unsupported_platform(monkeypatch, binary):
    monkeypatch.setattr(sys, "platform", "win32")
    with pytest.raises(RuntimeError):
        run(binary)


def test_malformed_binary(binary):
    assert run(binary + b"\xff").status == "rejected"


@pytest.mark.parametrize(
    "wat",
    [
        "(module)",
        '(module (func (export "run") (param i32)))',
        '(module (memory (export "run") 1))',
    ],
)
def test_entrypoint_rejected(wat):
    assert run(bytes(wasmtime.wat2wasm(wat))).status == "rejected"


def test_wasi_start_and_exit():
    for code in (0, 7):
        wat = f"""(module (import "wasi_snapshot_preview1" "proc_exit" (func $exit (param i32)))
        (memory (export "memory") 1) (func (export "_start") i32.const {code} call $exit))"""
        result = run(bytes(wasmtime.wat2wasm(wat)))
        assert (result.status, result.value) == ("exit", code)
    assert run(bytes(wasmtime.wat2wasm('(module (func (export "_start")))'))).status == "ok"


def test_fresh_instance_and_synthetic_canary(tmp_path, monkeypatch):
    canary = tmp_path / "canary.txt"
    canary.write_text("synthetic private value")
    monkeypatch.setenv("BOUNDARY_SYNTHETIC_SECRET", "synthetic private value")
    selected = {
        "absolute_canary",
        "relative_traversal",
        "create_file",
        "no_environment",
        "fresh_global",
    }
    for probe in probes(str(canary)):
        if probe.name in selected:
            for _ in range(2):
                result = run(probe.binary(), probe.policy)
                assert (result.status, result.value) == (probe.status, probe.value)
    assert canary.read_text() == "synthetic private value"
    assert list(tmp_path.iterdir()) == [canary]


def test_file_reader(tmp_path, binary):
    path = tmp_path / "input.wasm"
    path.write_bytes(binary)
    assert read_module(path) == binary
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(OSError):
        read_module(link)
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(ValueError):
        read_module(fifo)
    path.write_bytes(b"x" * (MAX_MODULE_BYTES + 10))
    assert len(read_module(path)) == MAX_MODULE_BYTES + 1


def test_cli(tmp_path, binary):
    path = tmp_path / "input.wasm"
    path.write_bytes(binary)
    command = [sys.executable, "-m", "sandbox_boundaries", str(path)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(result.stdout)["value"] == 42
    policy = tmp_path / "policy.json"
    policy.write_text('{"network":"allow"}')
    result = subprocess.run(command + ["--policy", str(policy)], capture_output=True, text=True)
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "configuration_error"
    path.write_bytes(
        bytes(wasmtime.wat2wasm('(module (func (export "run") (result i32) unreachable))'))
    )
    assert subprocess.run(command, capture_output=True).returncode == 1


def test_policy_immutable():
    assert replace(Policy(), fuel=10).fuel == 10


def test_worker_environment_and_cleanup(monkeypatch, binary):
    import sandbox_boundaries.runner as runner

    original = subprocess.Popen
    calls = []

    def observe(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(runner.subprocess, "Popen", observe)
    assert run(binary).status == "ok"
    assert calls[0]["env"] == {"OMP_NUM_THREADS": "1", "RAYON_NUM_THREADS": "1"}
    assert calls[0]["close_fds"] is True
    assert not os.path.exists(calls[0]["cwd"])


def test_interruption_kills_worker(monkeypatch, binary):
    import sandbox_boundaries.runner as runner

    class Interrupted:
        pid = 123456789
        returncode = None
        calls = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def communicate(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise KeyboardInterrupt
            return b"", None

    process = Interrupted()
    killed = []
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: process)
    monkeypatch.setattr(runner.os, "killpg", lambda *a: killed.append(a))
    with pytest.raises(KeyboardInterrupt):
        run(binary)
    assert killed == [(process.pid, runner.signal.SIGKILL)]
    assert process.calls == 2


@pytest.mark.parametrize("returncode,output", [(1, b""), (0, b"not JSON"), (0, b"{}")])
def test_worker_failure_reports(monkeypatch, binary, returncode, output):
    import sandbox_boundaries.runner as runner

    class Failed:
        def __enter__(self):
            self.returncode = returncode
            return self

        def __exit__(self, *args):
            pass

        def communicate(self, *args, **kwargs):
            return output, None

    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: Failed())
    assert run(binary).status == "worker_error"
