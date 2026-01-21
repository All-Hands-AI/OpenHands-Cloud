#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyGithub"]
# ///
"""Update OpenHands chart script."""

import re

from github import Github

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def get_latest_semver_tag(repo_name: str) -> str | None:
    """Fetch the latest semantic version tag (x.y.z) from a GitHub repository."""
    gh = Github()
    repo = gh.get_repo(repo_name)
    tags = repo.get_tags()
    for tag in tags:
        if SEMVER_PATTERN.match(tag.name):
            return tag.name
    return None


def main() -> None:
    latest_tag = get_latest_semver_tag("All-Hands-AI/OpenHands")
    if latest_tag:
        print(f"Latest OpenHands tag: {latest_tag}")
    else:
        print("No semantic version tag found")


if __name__ == "__main__":
    main()
