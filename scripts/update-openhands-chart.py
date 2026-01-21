#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyGithub", "ruamel.yaml", "requests"]
# ///
"""Update OpenHands chart script."""

import os
import re
from pathlib import Path

import requests
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


def get_latest_helm_chart_version(org: str, package: str) -> str | None:
    """Fetch the latest version of a helm chart from GitHub Container Registry."""
    # Get anonymous token for ghcr.io
    token_url = f"https://ghcr.io/token?scope=repository:{org}/{package}:pull"
    token_response = requests.get(token_url)
    token_response.raise_for_status()
    token = token_response.json().get("token")

    # List tags from the registry
    headers = {"Authorization": f"Bearer {token}"}
    tags_url = f"https://ghcr.io/v2/{org}/{package}/tags/list"
    response = requests.get(tags_url, headers=headers)
    response.raise_for_status()

    tags = response.json().get("tags", [])
    # Sort tags to get the latest semver
    semver_tags = [t for t in tags if SEMVER_PATTERN.match(t)]
    if semver_tags:
        semver_tags.sort(key=lambda v: list(map(int, v.split("."))), reverse=True)
        return semver_tags[0]
    return None


def bump_patch_version(version: str) -> str:
    """Bump the patch version of a semantic version string."""
    major, minor, patch = version.split(".")
    return f"{major}.{minor}.{int(patch) + 1}"


def update_chart(
    chart_path: Path, new_app_version: str, new_runtime_api_version: str | None
) -> None:
    """Update appVersion, bump patch version, and update runtime-api dependency."""
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

    if new_runtime_api_version:
        for dep in chart_data.get("dependencies", []):
            if dep.get("name") == "runtime-api":
                old_runtime_version = dep.get("version")
                if old_runtime_version == new_runtime_api_version:
                    print(
                        f"runtime-api version unchanged: {old_runtime_version} (already latest)"
                    )
                else:
                    dep["version"] = new_runtime_api_version
                    print(
                        f"Updated runtime-api version: {old_runtime_version} -> {new_runtime_api_version}"
                    )
                break

    yaml.dump(chart_data, chart_path)


def main() -> None:
    latest_tag = get_latest_semver_tag("OpenHands/OpenHands")
    if latest_tag:
        print(f"Latest OpenHands tag: {latest_tag}")
    else:
        print("No semantic version tag found")
        return

    runtime_api_version = get_latest_helm_chart_version(
        "all-hands-ai", "helm-charts/runtime-api"
    )
    if runtime_api_version:
        print(f"Latest runtime-api chart version: {runtime_api_version}")
    else:
        print("Could not fetch runtime-api version")

    update_chart(CHART_PATH, latest_tag, runtime_api_version)


if __name__ == "__main__":
    main()
