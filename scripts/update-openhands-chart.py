#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyGithub", "ruamel.yaml"]
# ///
"""Update OpenHands chart script."""

import re
from pathlib import Path

from github import Github
from ruamel.yaml import YAML

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


def bump_patch_version(version: str) -> str:
    """Bump the patch version of a semantic version string."""
    major, minor, patch = version.split(".")
    return f"{major}.{minor}.{int(patch) + 1}"


def update_chart(chart_path: Path, new_app_version: str) -> None:
    """Update appVersion and bump patch version in Chart.yaml while preserving formatting."""
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    chart_data = yaml.load(chart_path)

    old_app_version = chart_data.get("appVersion")
    chart_data["appVersion"] = new_app_version
    print(f"Updated appVersion: {old_app_version} -> {new_app_version}")

    old_version = chart_data.get("version")
    new_version = bump_patch_version(old_version)
    chart_data["version"] = new_version
    print(f"Updated version: {old_version} -> {new_version}")

    yaml.dump(chart_data, chart_path)


def main() -> None:
    latest_tag = get_latest_semver_tag("OpenHands/OpenHands")
    if latest_tag:
        print(f"Latest OpenHands tag: {latest_tag}")
        update_chart(CHART_PATH, latest_tag)
    else:
        print("No semantic version tag found")


if __name__ == "__main__":
    main()
