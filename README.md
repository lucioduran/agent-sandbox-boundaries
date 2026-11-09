# Agent Sandbox Boundaries

[![CI](https://github.com/lucioduran/agent-sandbox-boundaries/actions/workflows/ci.yml/badge.svg)](https://github.com/lucioduran/agent-sandbox-boundaries/actions/workflows/ci.yml)

An ephemeral WebAssembly runner with explicit resource policies and reproducible boundary evidence.

## Problem

An agent executing generated code needs isolation and observable limits. A subprocess timeout alone cannot prevent filesystem access, network egress or memory growth. This project makes the enforcement mechanism and its limits inspectable.

## Scope

Runs binary core WebAssembly through Wasmtime 50.0.1 on macOS and Linux. Each call gets a fresh process, store and empty working directory. WASI Preview 1 receives no inherited environment, arguments, files, directories or sockets. The isolation mechanism is Wasmtime, not the subprocess.

CPU seconds, instruction fuel, guest linear memory, table elements, wall time, zero guest persistent disk and denied guest network access are enforced. Positive disk quotas, network allowlists and total process-memory limits are rejected. No native executables, shell commands, containers, VM service installation or paid APIs are used.

## Quick start

Use Python 3.11.9 on macOS or Linux:

```sh
git clone https://github.com/lucioduran/agent-sandbox-boundaries.git
cd agent-sandbox-boundaries
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -c 'import wasmtime; from pathlib import Path; Path("build").mkdir(exist_ok=True); Path("build/answer.wasm").write_bytes(wasmtime.wat2wasm(Path("fixtures/answer.wat").read_text()))'
sandbox-boundaries build/answer.wasm
```

The JSON report has `status: "ok"` and `value: 42`. WAT conversion is a trusted development step outside the runner. The runner accepts only bounded binary Wasm.

## Usage

```python
from pathlib import Path
from sandbox_boundaries import Policy, run

result = run(Path("build/answer.wasm").read_bytes(), Policy(
    fuel=100_000,
    cpu_seconds=2,
    wall_seconds=5,
    memory_bytes=65_536,
))
print(result.status, result.value)
```

The CLI also accepts `--policy policy.json`. Omitted fields retain defaults; unknown or invalid fields fail closed. `disk_bytes` must be `0`, `network` must be `"deny"`, and `process_memory_bytes` must be `null` or omitted. A requested process-memory cap is an error, not silently ignored.

Export `run: () -> i32` or `_start: () -> ()`. WASI calls generally require an exported memory. WASI stdout and stderr are discarded. Return a bounded integer rather than a log stream. CLI exit codes are 0 for normal completion or WASI exit 0, 1 for guest rejection/trap/limit/nonzero exit, and 2 for configuration or input errors. Status `ok` means execution completed, not that a guest operation succeeded: WASI error 8 means a bad file descriptor.

## Architecture

```text
strict policy + bounded Wasm bytes
             |
parent deadline and fresh worker
             |
POSIX CPU/file limits + single-threaded Wasmtime compiler
             |
fuel + guest memory/table/stack limits
             |
WASI with no file, directory or socket capabilities
             |
bounded JSON result -> reap worker -> remove scratch directory
```

See [the boundary contract](docs/design.md) for enforcement scope, trust assumptions and upstream references. The trusted runtime and host OS are not isolated from each other by this package.

## Reproduction

The local bounded stress matrix must run under the series-wide exclusive lock:

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
python3 /Users/luchoduran/Sites/open-source-projects/.coordination/benchmark_lock.py \
  .venv/bin/python -m experiments.reproduce --output results/boundaries.json
```

That wrapper is supplied by the project-series workspace, outside this independent repository. Other installations must supply an equivalent exclusive benchmark lock and run the module within it. Do not run concurrent stress workloads. No stress benchmark runs in GitHub CI; CI executes the small non-stress regression suite.

The experiment creates its own synthetic canary, attempts relative traversal and absolute access to that canary, and checks it remains unchanged. No real host files, credentials, external servers or attack targets are tested. Each result includes policy, module hash, elapsed wall time and expected outcome. Source hashes and the measured source commit identify the implementation even after documentation or result commits.

## Results

The [raw report](results/boundaries.json) records 19 of 19 expected outcomes and rejection of all three unsupported profiles on an Intel Xeon W-3223 host with 48 GiB RAM, Python 3.11.9 and Wasmtime 50.0.1. Exact OS build, architecture, timestamp and source hashes are included. The [boundary matrix](results/matrix.md) summarizes each observation.

| Boundary | Observed outcome |
| --- | --- |
| CPU | Fuel exhausted; OS CPU cap killed bounded loop |
| Wall time | Blocking WASI poll terminated at the parent deadline |
| Guest memory | Growth returned -1; oversized initial memory rejected; invalid access trapped |
| Disk/filesystem | Traversal, absolute canary access and file creation returned bad descriptor |
| Network | Socket send returned bad descriptor; socket creation import rejected |
| Environment/lifecycle | Empty WASI environment and arguments; fresh instance state |

These are single-run synthetic regression results, not a security certification or a performance benchmark. No independent human security review is claimed.

## Testing

```sh
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest -q -m 'not stress'
python -m build
```

For all tests, including four bounded stress cases, use the same lock:

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
python3 /Users/luchoduran/Sites/open-source-projects/.coordination/benchmark_lock.py \
  .venv/bin/python -m pytest -q
```

The suite includes malformed policy/module inputs, forbidden capabilities, synthetic canaries, fresh state, file-reader symlink/FIFO rejection, CLI outcomes, worker failures and interruption cleanup. CI checks Linux and macOS and smoke-tests an independently installed wheel. Dependencies and action revisions are pinned at their direct dependency boundaries.

## Limitations

- Guest linear memory limits do not cap Python, compiler, JIT or total process RSS. A total process-memory profile fails closed. This host had no running Docker daemon, and no privileged service was installed.
- No OS-level filesystem or network namespace surrounds a compromised Wasmtime runtime. Runtime escapes, side channels and kernel bugs are outside the tested boundary.
- CPU signal attribution cannot distinguish an external SIGKILL from CPU enforcement. Fuel is an instruction budget, not a duration. Cleanup and OS scheduling may add wall latency.
- Disk scope is zero guest persistent writes. Positive quotas, writable scratch mounts and guest output capture are unsupported.
- Network evidence validates unavailable guest capabilities, not a host firewall or packet-level isolation.
- Only one memory and one table are allowed. Windows and WASI Preview 2 components fail closed. Reference types remain enabled because the pinned engine requires them; table growth is bounded. Advanced proposals listed in the design are disabled.
- The caller must bound request concurrency and protect package installation and policy configuration. This is a local runner, not a hosted multi-tenant execution service.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md). Include regression evidence and update the boundary contract for changes to capabilities or limits. Security reporting guidance is in [SECURITY.md](SECURITY.md).

## License

Code, original synthetic fixtures, documentation and results use the [MIT license](LICENSE). Wasmtime and development tools retain their upstream licenses.
