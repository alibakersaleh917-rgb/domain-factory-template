#!/usr/bin/env python3
"""Validate required environment variables for generation workflows."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable


DEFAULT_REQUIRED = ("OPENROUTER_API_KEY", "GROQ_API_KEY")


def parse_env_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def find_missing(names: Iterable[str]) -> list[str]:
    return [name for name in names if not os.getenv(name)]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check that required environment variables are available.",
    )
    parser.add_argument(
        "--required",
        default=",".join(DEFAULT_REQUIRED),
        help="Comma-separated list of required variable names.",
    )
    parser.add_argument(
        "--soft-fail",
        action="store_true",
        help="Exit with status 0 even when variables are missing.",
    )
    args = parser.parse_args()

    required = parse_env_list(args.required)
    missing = find_missing(required)

    print(f"Required variables: {', '.join(required) if required else '(none)'}")
    if missing:
        print(f"Missing variables: {', '.join(missing)}")
        if args.soft_fail:
            print("soft-fail enabled; continuing.")
            return 0
        return 1

    print("All required variables are set.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
