"""Private worker protocol. Only the trusted parent invokes this file."""

from __future__ import annotations

import base64
import json
import resource
import sys
from typing import Any


def execute(request: dict[str, Any]) -> dict[str, Any]:
    policy = request["policy"]
    resource.setrlimit(resource.RLIMIT_CPU, (policy["cpu_seconds"], policy["cpu_seconds"]))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    import wasmtime as wt

    config = wt.Config()
    config.consume_fuel = True
    config.parallel_compilation = False
    config.memory_init_cow = False
    config.max_wasm_stack = 262_144
    config.wasm_threads = False
    config.wasm_gc = False
    config.wasm_function_references = False
    config.wasm_simd = False
    config.wasm_relaxed_simd = False
    config.wasm_memory64 = False
    config.wasm_multi_memory = False
    config.wasm_component_model = False
    config.wasm_stack_switching = False
    config.wasm_exceptions = False
    config.wasm_tail_call = False
    config.wasm_custom_page_sizes = False
    config.wasm_wide_arithmetic = False
    engine = wt.Engine(config)
    store = wt.Store(engine)
    store.set_limits(
        memory_size=policy["memory_bytes"],
        table_elements=policy["table_elements"],
        instances=1,
        tables=1,
        memories=1,
    )
    store.set_fuel(policy["fuel"])
    store.set_wasi(wt.WasiConfig())
    linker = wt.Linker(engine)
    linker.define_wasi()
    try:
        module = wt.Module(engine, base64.b64decode(request["module"], validate=True))
        for item in module.imports:
            if item.module != "wasi_snapshot_preview1" or not isinstance(item.type, wt.FuncType):
                return {"status": "rejected", "value": None, "detail": "unsupported import"}
        exports = {item.name: item.type for item in module.exports}
        name = "run" if "run" in exports else "_start"
        entry_type = exports.get(name)
        expected = [wt.ValType.i32()] if name == "run" else []
        if (
            not isinstance(entry_type, wt.FuncType)
            or list(entry_type.params)
            or list(entry_type.results) != expected
        ):
            return {"status": "rejected", "value": None, "detail": "invalid entrypoint signature"}
        instance = linker.instantiate(store, module)
        entry = instance.exports(store)[name]
        assert isinstance(entry, wt.Func)
        value = entry(store)
        return {"status": "ok", "value": value, "detail": "completed"}
    except wt.ExitTrap as exc:
        return {"status": "exit", "value": exc.code, "detail": "WASI proc_exit"}
    except wt.Trap as exc:
        status = "fuel_limit" if exc.trap_code == wt.TrapCode.OUT_OF_FUEL else "trap"
        return {"status": status, "value": None, "detail": str(exc)[:512]}
    except wt.WasmtimeError as exc:
        return {"status": "rejected", "value": None, "detail": str(exc)[:512]}


def main() -> None:
    try:
        request = json.loads(sys.stdin.buffer.read(1_500_000))
        result = execute(request)
    except Exception as exc:
        result = {"status": "worker_error", "value": None, "detail": type(exc).__name__}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
