#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyGithub"]
# ///
"""Update OpenHands chart script."""

import re
from pathlib import Path

from github import Github

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
SCRIPT_DIR = Path(__file__).parent
CHART_PATH = SCRIPT_DIR.parent / "charts" / "openhands" / "Chart.yaml"


def get_latest_semver_tag(repo_name: str) -> str | None:
    """Fetch the latest semantic version tag (x.y.z) from a GitHub repository."""
    gh = Github()
    repo = gh.get_repo(repo_name)
    tags = repo.get_tags()
    for tag in tags:
        if SEMVER_PATTERN.match(tag.name):
            return tag.name
    return None


def update_chart_app_version(chart_path: Path, new_version: str) -> None:
    """Update the appVersion in Chart.yaml without reformatting."""
    content = chart_path.read_text()

    # Extract old version for logging
    match = re.search(r"^appVersion:\s*(.+)$", content, re.MULTILINE)
    old_version = match.group(1).strip() if match else None

    # Replace appVersion line in-place
    new_content = re.sub(
        r"^appVersion:\s*.+$",
        f"appVersion: {new_version}",
        content,
        count=1,
        flags=re.MULTILINE,
    )

    chart_path.write_text(new_content)
    print(f"Updated appVersion: {old_version} -> {new_version}")


def main() -> None:
    latest_tag = get_latest_semver_tag("OpenHands/OpenHands")
    if latest_tag:
        print(f"Latest OpenHands tag: {latest_tag}")
        update_chart_app_version(CHART_PATH, latest_tag)
    else:
        print("No semantic version tag found")


if __name__ == "__main__":
    main()
