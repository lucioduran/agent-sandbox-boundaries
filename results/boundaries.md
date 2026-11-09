# Observed boundary matrix

Measured source commit: `f062d252d69213c591c06e57417b4c7937bd8ae7`.

One local invocation per case. See boundaries.json for exact policies and environment.

| Probe | Boundary | Status | Value | Elapsed seconds | Expected outcome |
| --- | --- | --- | ---: | ---: | --- |
| answer | control | ok | 42 | 0.0910 | pass |
| fresh_global | ephemerality | ok | 1 | 0.0931 | pass |
| linear_growth | memory | ok | -1 | 0.0941 | pass |
| initial_memory | memory | rejected | None | 0.0928 | pass |
| table_growth | memory | ok | -1 | 0.0943 | pass |
| out_of_bounds | memory | trap | None | 0.0955 | pass |
| relative_traversal | filesystem | ok | 8 | 0.1000 | pass |
| absolute_canary | filesystem | ok | 8 | 0.0994 | pass |
| create_file | disk | ok | 8 | 0.1030 | pass |
| no_preopen | filesystem | ok | 8 | 0.1066 | pass |
| no_environment | environment | ok | 0 | 0.0971 | pass |
| no_arguments | environment | ok | 0 | 0.0970 | pass |
| socket_send | network | ok | 8 | 0.0940 | pass |
| socket_creation | network | rejected | None | 0.0926 | pass |
| native_import | imports | rejected | None | 0.0989 | pass |
| fuel_loop | CPU | fuel_limit | None | 0.0965 | pass |
| cpu_loop | CPU | cpu_limit | None | 1.0117 | pass |
| start_loop | CPU | fuel_limit | None | 0.0993 | pass |
| blocking_poll | wall time | wall_limit | None | 0.5046 | pass |

Unsupported positive disk, allowed network and total process-memory profiles were rejected.
Synthetic canary integrity and absence of new files in its directory were checked.
Guest memory limits do not cap worker RSS. No packet capture or security audit was performed.
