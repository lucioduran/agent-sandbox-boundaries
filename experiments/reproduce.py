"""Run this bounded matrix under the shared benchmark lock."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from experiments.probes import probes
from sandbox_boundaries import Policy, run

ROOT = Path(__file__).resolve().parents[1]


def command(*args: str) -> str:
    return subprocess.check_output(args, text=True, cwd=ROOT).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("results/boundaries.json"))
    args = parser.parse_args()
    rows = []
    with tempfile.TemporaryDirectory(prefix="boundary-canary-") as directory:
        canary = Path(directory) / "canary.txt"
        canary.write_text("synthetic canary, no real secrets\n")
        before = hashlib.sha256(canary.read_bytes()).hexdigest()
        for probe in probes(str(canary)):
            result = run(probe.binary(), probe.policy)
            passed = (result.status, result.value) == (probe.status, probe.value)
            rows.append(
                {
                    "name": probe.name,
                    "boundary": probe.boundary,
                    "expected_status": probe.status,
                    "expected_value": probe.value,
                    "passed": passed,
                    "result": asdict(result),
                }
            )
            print(f"{probe.name}: {result.status}, value={result.value}, pass={passed}", flush=True)
        canary_intact = hashlib.sha256(canary.read_bytes()).hexdigest() == before
        no_created_files = list(Path(directory).iterdir()) == [canary]
    unsupported = []
    for settings in ({"disk_bytes": 1}, {"network": "allow"}, {"process_memory_bytes": 2**30}):
        try:
            Policy(**settings)
        except ValueError as exc:
            unsupported.append({"settings": settings, "rejected": True, "reason": str(exc)})
        else:
            unsupported.append({"settings": settings, "rejected": False})
    sources = {}
    for folder in ("sandbox_boundaries", "experiments", "tests", "fixtures"):
        for path in sorted((ROOT / folder).glob("*")):
            if path.is_file():
                sources[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    hardware = {"logical_cpus": os.cpu_count(), "architecture": platform.machine()}
    if platform.system() == "Darwin":
        hardware["cpu"] = command("sysctl", "-n", "machdep.cpu.brand_string")
        hardware["memory_bytes"] = int(command("sysctl", "-n", "hw.memsize"))
        hardware["os_version"] = command("sw_vers", "-productVersion")
        hardware["os_build"] = command("sw_vers", "-buildVersion")
    passed = all(row["passed"] for row in rows) and canary_intact and no_created_files
    passed = passed and all(row["rejected"] for row in unsupported)
    report = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "source_commit": command("git", "rev-parse", "HEAD"),
        "source_tree_clean": not bool(command("git", "status", "--porcelain")),
        "source_sha256": sources,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "hardware": hardware,
        "wasmtime": importlib.metadata.version("wasmtime"),
        "thread_limit": 1,
        "api_cost_usd": 0,
        "repetitions": 1,
        "passed": passed,
        "canary_intact": canary_intact,
        "no_created_files_in_canary_directory": no_created_files,
        "unsupported_profiles": unsupported,
        "cases": rows,
        "limitations": [
            "Synthetic regression evidence, not a security audit or escape-proof claim.",
            "Memory budget covers guest linear memory, not total worker RSS or compiler allocation.",
            "No packet capture: network evidence is capability rejection, not host firewall validation.",
            "CPU signal attribution cannot distinguish an external SIGKILL.",
            "Single local run; elapsed timings are observations, not performance estimates.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
