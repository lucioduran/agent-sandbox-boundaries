# Security

This project depends on Wasmtime's WebAssembly isolation and WASI capability
model. It is not a VM, container, OS syscall filter or security certification.
Read docs/design.md and the README limitations before use.

Report security issues through GitHub private vulnerability reporting if
available. Otherwise open an issue requesting a private contact without exploit
payloads or sensitive data. Do not publish credentials or real host file contents.

Tests use only bounded synthetic fixtures. No independent security audit or
escape-proof guarantee is claimed. Review Wasmtime advisories when upgrading
or deploying the runtime. Total process-memory caps remain unsupported.
