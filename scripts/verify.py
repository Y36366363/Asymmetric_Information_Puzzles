#!/usr/bin/env python3
"""Run the complete AIP verification pipeline from a source checkout."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def run(label: str, command: list[str], *, env: dict[str, str] | None = None) -> None:
    print(f"\n== {label} ==", flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and test every AIP runtime")
    parser.add_argument(
        "--node",
        default=os.environ.get("AIP_NODE") or shutil.which("node"),
        help="Node.js executable (or set AIP_NODE)",
    )
    args = parser.parse_args()
    if not args.node:
        parser.error("Node.js was not found; pass --node /path/to/node or set AIP_NODE")

    python_env = os.environ.copy()
    source = str(ROOT / "src")
    python_env["PYTHONPATH"] = os.pathsep.join(
        part for part in (source, python_env.get("PYTHONPATH", "")) if part
    )
    run(
        "Python solver and service tests",
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        env=python_env,
    )
    run("Build deployable worker bundle", [args.node, "web/build.mjs"])
    run("Build zero-backend public lobby", [args.node, "web/build-static.mjs"])
    run(
        "Public browser engine and build tests",
        [
            args.node,
            "--test",
            "web/tests/public-worker.test.mjs",
            "web/tests/static-build.test.mjs",
        ],
    )
    print("\nAIP verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
