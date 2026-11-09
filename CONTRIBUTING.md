# Contributing

Use English for code, documentation and commit messages. Keep changes focused.
Run the formatting, lint, typing and non-stress tests in README.md. Run stress
cases only within an exclusive benchmark lock with one thread per worker.

Never use real secrets, user files or external attack targets in fixtures.
Capability additions need an explicit threat-model update and denial tests.
Do not describe unmeasured boundaries as verified. Preserve the distinction
between guest linear memory and host RSS. Record exact versions and source
hashes when regenerating evidence.
