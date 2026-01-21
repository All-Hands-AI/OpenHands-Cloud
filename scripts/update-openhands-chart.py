#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyGithub"]
# ///
"""Update OpenHands chart script."""

from github import Github


def get_latest_tag(repo_name: str) -> str:
    """Fetch the latest tag from a GitHub repository."""
    gh = Github()
    repo = gh.get_repo(repo_name)
    tags = repo.get_tags()
    latest_tag = tags[0]
    return latest_tag.name


def main() -> None:
    latest_tag = get_latest_tag("All-Hands-AI/OpenHands")
    print(f"Latest OpenHands tag: {latest_tag}")


if __name__ == "__main__":
    main()
