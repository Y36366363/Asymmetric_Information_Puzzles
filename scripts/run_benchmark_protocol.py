#!/usr/bin/env python3
"""Export the preregistered benchmark grid and optional offline pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aip.benchmark import default_protocol, run_repeated_guess_who_pilot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--pilot-repeats", type=int, default=4)
    parser.add_argument("--pilot-seeds-per-repeat", type=int, default=8)
    args = parser.parse_args()
    payload: dict[str, object] = {"protocol": default_protocol(args.model).as_dict()}
    if args.pilot:
        payload["offlinePilot"] = run_repeated_guess_who_pilot(
            repeats=args.pilot_repeats,
            seeds_per_repeat=args.pilot_seeds_per_repeat,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
