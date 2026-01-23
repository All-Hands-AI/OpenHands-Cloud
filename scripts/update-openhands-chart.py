#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyGithub", "ruamel.yaml", "requests"]
# ///
"""Update OpenHands chart script."""

import argparse
import base64
import io
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import requests
from github import Auth, Github
from ruamel.yaml import YAML

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
SHORT_SHA_LENGTH = 7
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
CHART_PATH = REPO_ROOT / "charts" / "openhands" / "Chart.yaml"
VALUES_PATH = REPO_ROOT / "charts" / "openhands" / "values.yaml"
RUNTIME_API_CHART_PATH = REPO_ROOT / "charts" / "runtime-api" / "Chart.yaml"
RUNTIME_API_VALUES_PATH = REPO_ROOT / "charts" / "runtime-api" / "values.yaml"
OPENHANDS_REPO_PATH = REPO_ROOT.parent / "OpenHands"


def get_short_sha(sha: str) -> str:
    """Return the first 7 characters of a SHA hash."""
    return sha[:SHORT_SHA_LENGTH]


def format_sha_tag(sha: str) -> str:
    """Format a SHA hash into a sha-SHORT_SHA tag format."""
    return f"sha-{get_short_sha(sha)}"


@dataclass
class DeployConfig:
    """Configuration values from the deploy workflow."""

    openhands_sha: str
    openhands_runtime_image_tag: str
    runtime_api_sha: str


def get_latest_semver_tag(repo_name: str) -> str | None:
    """Fetch the latest semantic version tag (x.y.z) from a GitHub repository."""
    token = os.environ.get("GITHUB_TOKEN")
    gh = Github(auth=Auth.Token(token)) if token else Github()
    try:
        repo = gh.get_repo(repo_name)
        tags = repo.get_tags()
        for tag in tags:
            if SEMVER_PATTERN.match(tag.name):
                return tag.name
    except Exception as e:
        print(f"Error fetching tags from {repo_name}: {e}")
    return None


def get_semver_tag_containing_commit(repo_path: Path, commit_sha: str) -> str | None:
    """Get the latest semantic version tag containing a specific commit from a local git repo.

    This function:
    1. Runs git pull to fetch the latest updates
    2. Runs git tag --contains <commit_sha> to get all tags containing the commit
    3. Filters for semantic version tags and returns the latest one
    """
    if not repo_path.exists():
        print(f"Repository not found at {repo_path}")
        return None

    try:
        # Pull latest updates
        subprocess.run(
            ["git", "pull"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Get tags containing the commit
        result = subprocess.run(
            ["git", "tag", "--contains", commit_sha],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
        )

        tags = result.stdout.strip().split("\n")
        # Filter for semantic version tags
        semver_tags = [t for t in tags if t and SEMVER_PATTERN.match(t)]

        if semver_tags:
            # Sort by version number (descending) and return the latest
            semver_tags.sort(key=lambda v: list(map(int, v.split("."))), reverse=True)
            return semver_tags[0]

        return None
    except subprocess.CalledProcessError as e:
        print(f"Git command failed: {e}")
        return None
    except Exception as e:
        print(f"Error getting tags containing commit: {e}")
        return None


def get_deploy_config(repo_name: str, ref: str | None = None) -> DeployConfig | None:
    """Fetch deployment config values from deploy.yaml workflow."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN required to access deploy workflow")
        return None

    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://api.github.com/repos/{repo_name}/contents/.github/workflows/deploy.yaml"
    if ref:
        url += f"?ref={ref}"

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        content = base64.b64decode(response.json()["content"]).decode("utf-8")
        yaml = YAML()
        workflow = yaml.load(io.StringIO(content))

        env = workflow.get("env", {})
        return DeployConfig(
            openhands_sha=env.get("OPENHANDS_SHA", ""),
            openhands_runtime_image_tag=env.get("OPENHANDS_RUNTIME_IMAGE_TAG", ""),
            runtime_api_sha=env.get("RUNTIME_API_SHA", ""),
        )
    except Exception as e:
        print(f"Error fetching deploy config: {e}")
        return None


def bump_patch_version(version: str) -> str:
    """Bump the patch version of a semantic version string."""
    major, minor, patch = version.split(".")
    return f"{major}.{minor}.{int(patch) + 1}"


def update_openhands_chart(
    chart_path: Path,
    new_app_version: str,
    new_runtime_api_version: str | None,
    dry_run: bool = False,
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

    if not dry_run:
        yaml.dump(chart_data, chart_path)


def update_openhands_values(
    values_path: Path,
    openhands_sha: str,
    runtime_api_sha: str,
    runtime_image_tag: str,
    dry_run: bool = False,
) -> None:
    """Update image tags in values.yaml."""
    content = values_path.read_text()

    # Update enterprise-server image tag
    enterprise_new_tag = format_sha_tag(openhands_sha)

    enterprise_pattern = r"(image:\s*\n\s*repository:\s*ghcr\.io/openhands/enterprise-server\s*\n\s*tag:\s*)(\S+)"
    enterprise_match = re.search(enterprise_pattern, content)

    if enterprise_match:
        old_tag = enterprise_match.group(2)
        if old_tag == enterprise_new_tag:
            print(f"enterprise-server image tag unchanged: {old_tag} (already latest)")
        else:
            content = re.sub(enterprise_pattern, rf"\g<1>{enterprise_new_tag}", content)
            print(f"Updated enterprise-server image tag: {old_tag} -> {enterprise_new_tag}")
    else:
        print("Could not find enterprise-server image tag in values.yaml")

    # Update runtime-api image tag
    runtime_api_new_tag = format_sha_tag(runtime_api_sha)

    runtime_api_pattern = r"(runtime-api:\s*\n(?:.*\n)*?\s*image:\s*\n\s*tag:\s*)(\S+)"
    runtime_api_match = re.search(runtime_api_pattern, content)

    if runtime_api_match:
        old_tag = runtime_api_match.group(2)
        if old_tag == runtime_api_new_tag:
            print(f"runtime-api image tag unchanged: {old_tag} (already latest)")
        else:
            content = re.sub(runtime_api_pattern, rf"\g<1>{runtime_api_new_tag}", content)
            print(f"Updated runtime-api image tag: {old_tag} -> {runtime_api_new_tag}")
    else:
        print("Could not find runtime-api image tag in values.yaml")

    # Update runtime image tag (under runtime.image.tag)
    runtime_pattern = r"(runtime:\s*\n\s*image:\s*\n\s*repository:\s*ghcr\.io/openhands/runtime\s*\n\s*tag:\s*)(\S+)"
    runtime_match = re.search(runtime_pattern, content)

    if runtime_match:
        old_tag = runtime_match.group(2)
        if old_tag == runtime_image_tag:
            print(f"runtime image tag unchanged: {old_tag} (already latest)")
        else:
            content = re.sub(runtime_pattern, rf"\g<1>{runtime_image_tag}", content)
            print(f"Updated runtime image tag: {old_tag} -> {runtime_image_tag}")
    else:
        print("Could not find runtime image tag in values.yaml")

    # Update warmRuntimes image (contains full image path with tag)
    warm_runtime_pattern = r'(image:\s*"ghcr\.io/openhands/runtime:)([^"]+)"'
    warm_runtime_match = re.search(warm_runtime_pattern, content)

    if warm_runtime_match:
        old_tag = warm_runtime_match.group(2)
        if old_tag == runtime_image_tag:
            print(f"warmRuntimes image tag unchanged: {old_tag} (already latest)")
        else:
            content = re.sub(warm_runtime_pattern, rf'\g<1>{runtime_image_tag}"', content)
            print(f"Updated warmRuntimes image tag: {old_tag} -> {runtime_image_tag}")
    else:
        print("Could not find warmRuntimes image tag in values.yaml")

    if not dry_run:
        values_path.write_text(content)


def update_runtime_api_chart(
    chart_path: Path,
    dry_run: bool = False,
) -> str:
    """Bump the patch version of the runtime-api chart and return the new version."""
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    chart_data = yaml.load(chart_path)

    old_version = chart_data.get("version")
    new_version = bump_patch_version(old_version)
    chart_data["version"] = new_version
    print(f"Updated runtime-api chart version: {old_version} -> {new_version}")

    if not dry_run:
        yaml.dump(chart_data, chart_path)

    return new_version


def update_runtime_api_values(
    values_path: Path,
    runtime_image_tag: str,
    dry_run: bool = False,
) -> None:
    """Update warmRuntimes default config image in runtime-api values.yaml."""
    content = values_path.read_text()

    # Update warmRuntimes image (contains full image path with tag)
    warm_runtime_pattern = r'(image:\s*"ghcr\.io/openhands/runtime:)([^"]+)"'
    warm_runtime_match = re.search(warm_runtime_pattern, content)

    if warm_runtime_match:
        old_tag = warm_runtime_match.group(2)
        if old_tag == runtime_image_tag:
            print(f"runtime-api warmRuntimes image tag unchanged: {old_tag} (already latest)")
        else:
            content = re.sub(warm_runtime_pattern, rf'\g<1>{runtime_image_tag}"', content)
            print(f"Updated runtime-api warmRuntimes image tag: {old_tag} -> {runtime_image_tag}")
    else:
        print("Could not find warmRuntimes image tag in runtime-api values.yaml")

    if not dry_run:
        values_path.write_text(content)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Update OpenHands and runtime-api charts based on a SaaS deploy."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes.",
    )
    parser.add_argument(
        "--deploy-tag",
        type=str,
        default=None,
        help="A tag of deploy repo to use instead of fetching the latest semantic version.",
    )
    return parser.parse_args()


def main(dry_run: bool = False, deploy_tag: str | None = None) -> None:
    if dry_run:
        print("=" * 60)
        print("DRY RUN MODE - No changes will be made")
        print("=" * 60)
        print()

    print("=" * 60)
    print("Fetching latest versions...")
    print("=" * 60)

    if deploy_tag:
        print(f"Using specified deploy tag: {deploy_tag}")
    else:
        deploy_tag = get_latest_semver_tag("OpenHands/deploy")
        if deploy_tag:
            print(f"Latest deploy tag: {deploy_tag}")
        else:
            print("No deploy semantic version tag found")
            return

    # Fetch deploy config from the tagged version
    deploy_config = get_deploy_config("OpenHands/deploy", ref=deploy_tag)
    if not deploy_config:
        print("Could not fetch deploy config")
        return

    print(f"Deploy config (from {deploy_tag}):")
    print(f"  OPENHANDS_SHA: {deploy_config.openhands_sha}")
    print(f"  OPENHANDS_RUNTIME_IMAGE_TAG: {deploy_config.openhands_runtime_image_tag}")
    print(f"  RUNTIME_API_SHA: {deploy_config.runtime_api_sha}")

    # Get the semver tag containing the OPENHANDS_SHA from local OpenHands repo
    openhands_version = get_semver_tag_containing_commit(
        OPENHANDS_REPO_PATH, deploy_config.openhands_sha
    )
    if openhands_version:
        print(f"OpenHands version (tag containing {deploy_config.openhands_sha[:7]}): {openhands_version}")
    else:
        print(f"No semantic version tag found containing commit {deploy_config.openhands_sha[:7]}")
        return

    # Update runtime-api chart first to get the new version
    print()
    print("=" * 60)
    print("Updating runtime-api chart...")
    print("=" * 60)

    print("Updating runtime-api Chart.yaml...")
    runtime_api_version = update_runtime_api_chart(RUNTIME_API_CHART_PATH, dry_run=dry_run)

    print()
    print("Updating runtime-api values.yaml...")
    update_runtime_api_values(
        RUNTIME_API_VALUES_PATH,
        deploy_config.openhands_runtime_image_tag,
        dry_run=dry_run,
    )

    # Update openhands chart using the bumped runtime-api version
    print()
    print("=" * 60)
    print("Updating openhands chart...")
    print("=" * 60)

    print("Updating openhands Chart.yaml...")
    update_openhands_chart(CHART_PATH, openhands_version, runtime_api_version, dry_run=dry_run)

    print()
    print("Updating openhands values.yaml...")
    update_openhands_values(
        VALUES_PATH,
        deploy_config.openhands_sha,
        deploy_config.runtime_api_sha,
        deploy_config.openhands_runtime_image_tag,
        dry_run=dry_run,
    )


if __name__ == "__main__":
    args = parse_args()
    main(dry_run=args.dry_run, deploy_tag=args.deploy_tag)
