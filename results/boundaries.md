# Observed boundary matrix

Measured source commit: `bdffaf85ff10f9e28682592af0c9d041c04862f7`.

One local invocation per case. See boundaries.json for exact policies and environment.

| Probe | Boundary | Status | Value | Elapsed seconds | Expected outcome |
| --- | --- | --- | ---: | ---: | --- |
| answer | control | ok | 42 | 0.0883 | pass |
| fresh_global | ephemerality | ok | 1 | 0.0887 | pass |
| linear_growth | memory | ok | -1 | 0.0908 | pass |
| initial_memory | memory | rejected | None | 0.0907 | pass |
| table_growth | memory | ok | -1 | 0.0922 | pass |
| out_of_bounds | memory | trap | None | 0.0912 | pass |
| relative_traversal | filesystem | ok | 8 | 0.0927 | pass |
| absolute_canary | filesystem | ok | 8 | 0.0937 | pass |
| create_file | disk | ok | 8 | 0.0925 | pass |
| no_preopen | filesystem | ok | 8 | 0.0899 | pass |
| no_environment | environment | ok | 0 | 0.0981 | pass |
| no_arguments | environment | ok | 0 | 0.0935 | pass |
| socket_send | network | ok | 8 | 0.0907 | pass |
| socket_creation | network | rejected | None | 0.0909 | pass |
| native_import | imports | rejected | None | 0.0910 | pass |
| fuel_loop | CPU | fuel_limit | None | 0.0913 | pass |
| cpu_loop | CPU | cpu_limit | None | 1.0118 | pass |
| start_loop | CPU | fuel_limit | None | 0.0910 | pass |
| blocking_poll | wall time | wall_limit | None | 0.5045 | pass |

Unsupported positive disk, allowed network and total process-memory profiles were rejected.
Synthetic canary integrity and absence of new files in its directory were checked.
Guest memory limits do not cap worker RSS. No packet capture or security audit was performed.
