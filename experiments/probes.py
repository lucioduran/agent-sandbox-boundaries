from dataclasses import dataclass

import wasmtime

from sandbox_boundaries import Policy


@dataclass(frozen=True)
class Probe:
    name: str
    boundary: str
    wat: str
    policy: Policy
    status: str
    value: int | None
    stress: bool = False

    def binary(self) -> bytes:
        return bytes(wasmtime.wat2wasm(self.wat))


def wasi(body: str, imports: str, data: str = "") -> str:
    return f"""(module {imports} (memory (export "memory") 1) {data}
    (func (export "run") (result i32) {body}))"""


def path_open(path: str, create: bool = False) -> str:
    encoded = path.encode()
    escaped = "".join(f"\\{byte:02x}" for byte in encoded)
    return wasi(
        f"i32.const 3 i32.const 0 i32.const 256 i32.const {len(encoded)} "
        f"i32.const {int(create)} i64.const 66 i64.const 0 i32.const 0 i32.const 128 call $open",
        '(import "wasi_snapshot_preview1" "path_open" (func $open '
        "(param i32 i32 i32 i32 i32 i64 i64 i32 i32) (result i32)))",
        f'(data (i32.const 256) "{escaped}")',
    )


def probes(canary_path: str) -> list[Probe]:
    default = Policy()
    loop = '(module (func (export "run") (result i32) (loop $l br $l) i32.const 0))'
    cases = [
        Probe(
            "answer",
            "control",
            '(module (func (export "run") (result i32) i32.const 42))',
            default,
            "ok",
            42,
        ),
        Probe(
            "fresh_global",
            "ephemerality",
            '(module (global $g (mut i32) (i32.const 0)) (func (export "run") (result i32) global.get $g i32.const 1 i32.add global.set $g global.get $g))',
            default,
            "ok",
            1,
        ),
        Probe(
            "linear_growth",
            "memory",
            '(module (memory 1) (func (export "run") (result i32) i32.const 1 memory.grow))',
            Policy(memory_bytes=65536),
            "ok",
            -1,
        ),
        Probe(
            "initial_memory",
            "memory",
            '(module (memory 2) (func (export "run") (result i32) i32.const 0))',
            Policy(memory_bytes=65536),
            "rejected",
            None,
        ),
        Probe(
            "table_growth",
            "memory",
            '(module (table 1 funcref) (func (export "run") (result i32) ref.null func i32.const 1 table.grow))',
            Policy(table_elements=1),
            "ok",
            -1,
        ),
        Probe(
            "out_of_bounds",
            "memory",
            '(module (memory 1) (func (export "run") (result i32) i32.const 65536 i32.load))',
            default,
            "trap",
            None,
        ),
        Probe("relative_traversal", "filesystem", path_open("../canary.txt"), default, "ok", 8),
        Probe("absolute_canary", "filesystem", path_open(canary_path), default, "ok", 8),
        Probe("create_file", "disk", path_open("created.txt", True), default, "ok", 8),
        Probe(
            "no_preopen",
            "filesystem",
            wasi(
                "i32.const 3 i32.const 0 call $f",
                '(import "wasi_snapshot_preview1" "fd_prestat_get" (func $f (param i32 i32) (result i32)))',
            ),
            default,
            "ok",
            8,
        ),
        Probe(
            "no_environment",
            "environment",
            wasi(
                "i32.const 0 i32.const 4 call $f drop i32.const 0 i32.load",
                '(import "wasi_snapshot_preview1" "environ_sizes_get" (func $f (param i32 i32) (result i32)))',
            ),
            default,
            "ok",
            0,
        ),
        Probe(
            "no_arguments",
            "environment",
            wasi(
                "i32.const 0 i32.const 4 call $f drop i32.const 0 i32.load",
                '(import "wasi_snapshot_preview1" "args_sizes_get" (func $f (param i32 i32) (result i32)))',
            ),
            default,
            "ok",
            0,
        ),
        Probe(
            "socket_send",
            "network",
            wasi(
                "i32.const 3 i32.const 0 i32.const 0 i32.const 0 i32.const 64 call $f",
                '(import "wasi_snapshot_preview1" "sock_send" (func $f (param i32 i32 i32 i32 i32) (result i32)))',
            ),
            default,
            "ok",
            8,
        ),
        Probe(
            "socket_creation",
            "network",
            '(module (import "wasi_snapshot_preview1" "sock_open" (func)) (func (export "run") (result i32) i32.const 0))',
            default,
            "rejected",
            None,
        ),
        Probe(
            "native_import",
            "imports",
            '(module (import "env" "system" (func)) (func (export "run") (result i32) i32.const 0))',
            default,
            "rejected",
            None,
        ),
        Probe("fuel_loop", "CPU", loop, Policy(fuel=10000), "fuel_limit", None, True),
        Probe(
            "cpu_loop",
            "CPU",
            loop,
            Policy(fuel=10**12, cpu_seconds=1, wall_seconds=5),
            "cpu_limit",
            None,
            True,
        ),
        Probe(
            "start_loop",
            "CPU",
            '(module (func $s (loop $l br $l)) (start $s) (func (export "run") (result i32) i32.const 0))',
            Policy(fuel=10000),
            "fuel_limit",
            None,
            True,
        ),
        Probe(
            "blocking_poll",
            "wall time",
            wasi(
                "i32.const 8 i32.const 0 i32.store8 i32.const 16 i32.const 1 i32.store i32.const 24 i64.const 2000000000 i64.store i32.const 0 i32.const 64 i32.const 1 i32.const 128 call $f",
                '(import "wasi_snapshot_preview1" "poll_oneoff" (func $f (param i32 i32 i32 i32) (result i32)))',
            ),
            Policy(wall_seconds=0.5),
            "wall_limit",
            None,
            True,
        ),
    ]
    return cases
