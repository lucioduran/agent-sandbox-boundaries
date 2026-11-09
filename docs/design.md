# Boundary contract

The trust boundary is WebAssembly validation, Wasmtime execution and the WASI
capability table. A subprocess supplies lifecycle and CPU accounting only. It is
not the security sandbox. The trusted computing base includes Python, Wasmtime,
the OS, the installed package and the caller. Runtime vulnerabilities remain possible.

Each invocation creates one process, engine, store and instance, with a fresh
empty working directory that is removed after exit. The parent supplies binary
Wasm bytes over a pipe. No native artifacts are deserialized. The worker has an
empty inherited environment except explicit thread-count controls. Python runs
in isolated mode without site/user path injection. WASI has no inherited argv,
environment, stdin, stdout, stderr, preopened directories or sockets. No mounts,
network probes against real destinations, shell, native plugins or custom host
callbacks are exposed. Only WASI Preview 1 function imports are linked.

The supported profile is deliberately narrow:

| Resource | Enforcement | Scope |
| --- | --- | --- |
| CPU | POSIX RLIMIT_CPU hard and soft limit, plus Wasmtime fuel | Worker CPU seconds including compilation; fuel covers guest instructions |
| Memory | Store limiter, one memory, bounded table and Wasm stack | Guest linear memory, not Python/JIT RSS |
| Wall time | Parent deadline, process-group SIGKILL and reap | Worker lifetime including compilation; scheduling/cleanup can add latency |
| Disk | No directory or writable file capabilities; RLIMIT_FSIZE zero | Zero guest persistent disk bytes, no positive quota support |
| Network | No socket capabilities or socket-creation imports | Deny all guest egress, no allowlists |
| Input | Binary format only, maximum 1 MiB | Caller file is read once with a size bound |

Nonzero disk budgets, allowed network access and total process-memory caps are
unsupported and rejected before execution. Unsupported operating systems also
fail closed. Native programs and WASI Preview 2 components are unsupported.
An export named `run` must take no arguments and return i32, or `_start` must
take no arguments and return nothing. A Wasm start section is also budgeted.
Guest stdout/stderr are discarded by the default WASI configuration. Only the
integer return value and bounded runtime status leave the worker.

The parent does not accept policy from the guest. Validation rejects booleans,
nonfinite numbers, unknown fields, out-of-range values and unsupported settings.
A clean process and store per call prevent instance reuse. The package does not
provide a multi-tenant service or protect a compromised runtime using OS network
or filesystem namespaces. It does not claim a host-wide denial-of-service bound:
compiler/JIT/Python allocations are outside the guest memory limit. The input
cap and disabled proposals reduce scope but do not prove a compiler-memory bound.
Deployments requiring a total RSS bound must use a separately verified VM or
container mechanism; this runner rejects that requested profile.

Wasmtime parallel compilation and Wasm threads are disabled. GC, memory64,
multi-memory, stack switching, components, SIMD and additional advanced proposals
are disabled to keep the execution contract small. The table and stack are
separately bounded, not counted as linear memory.

References: [Wasmtime security model](https://docs.wasmtime.dev/security.html),
[Python API](https://bytecodealliance.github.io/wasmtime-py/), and
[Python resource limits](https://docs.python.org/3/library/resource.html).
Review upstream advisories before exposing any runtime to hostile inputs.
