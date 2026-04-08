#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyGithub"]
# ///
"""CLI to create a GitHub app for OpenHands Enterprise (OHE)."""

import argparse

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Create Github App for OpenHands Enterprise (OHE)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes.",
    )
    parser.add_argument(
        "--app-name",
        default="openhands",
        help="Name of the GitHub App to create (default: openhands).",
    )
    return parser.parse_args()


def main(dry_run: bool = False) -> None:
    print('Hello World')

if __name__ == "__main__":
    args = parse_args()
    main(dry_run=args.dry_run)
