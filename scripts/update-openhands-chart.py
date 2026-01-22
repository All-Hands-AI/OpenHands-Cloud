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
GITHUB_REPO = "All-Hands-AI/OpenHands-Cloud"


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


def update_values(
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


def get_branch_name(app_version: str) -> str:
    """Generate branch name for the update PR."""
    return f"update-openhands-chart-{app_version}"


def create_branch_and_pr(app_version: str) -> str | None:
    """Create a new branch from main, commit only chart changes, and open a draft PR."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN required to create PR")
        return None

    branch_name = get_branch_name(app_version)

    try:
        # Save current branch to return to later
        current_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        # Stash any uncommitted changes (including chart changes)
        subprocess.run(
            ["git", "stash", "push", "-m", "temp-chart-updates"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )

        # Fetch latest main
        subprocess.run(
            ["git", "fetch", "origin", "main"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )

        # Create new branch from main
        subprocess.run(
            ["git", "checkout", "-b", branch_name, "origin/main"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )

        # Apply stashed changes
        subprocess.run(
            ["git", "stash", "pop"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )

        # Stage only chart changes
        subprocess.run(
            ["git", "add", "charts/openhands/Chart.yaml", "charts/openhands/values.yaml"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )

        # Commit changes
        commit_message = f"Update OpenHands chart to {app_version}"
        subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )

        # Push branch
        subprocess.run(
            ["git", "push", "-u", "origin", branch_name],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )

        # Create draft PR using GitHub API
        gh = Github(auth=Auth.Token(token))
        repo = gh.get_repo(GITHUB_REPO)

        pr = repo.create_pull(
            title=f"Update OpenHands chart to {app_version}",
            body=f"Automated update of OpenHands Helm chart to version {app_version}.",
            head=branch_name,
            base="main",
            draft=True,
        )

        # Return to original branch
        subprocess.run(
            ["git", "checkout", current_branch],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )

        return pr.html_url

    except subprocess.CalledProcessError as e:
        print(f"Git command failed: {e}")
        # Try to return to original branch on error
        try:
            subprocess.run(
                ["git", "checkout", current_branch],
                cwd=REPO_ROOT,
                capture_output=True,
            )
        except Exception:
            pass
        return None
    except Exception as e:
        print(f"Error creating PR: {e}")
        return None


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Update OpenHands chart with latest versions from GitHub."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes.",
    )
    return parser.parse_args()


def main(dry_run: bool = False) -> None:
    if dry_run:
        print("=" * 60)
        print("DRY RUN MODE - No changes will be made")
        print("=" * 60)
        print()

    print("=" * 60)
    print("Fetching latest versions...")
    print("=" * 60)

    latest_tag = get_latest_semver_tag("OpenHands/OpenHands")
    if latest_tag:
        print(f"Latest OpenHands tag: {latest_tag}")
    else:
        print("No semantic version tag found")
        return

    deploy_tag = get_latest_semver_tag("OpenHands/deploy")
    if deploy_tag:
        print(f"Latest deploy tag: {deploy_tag}")
    else:
        print("No deploy semantic version tag found")

    # Fetch deploy config from the latest tagged version
    deploy_config = get_deploy_config("OpenHands/deploy", ref=deploy_tag)
    if deploy_config:
        print(f"Deploy config (from {deploy_tag}):")
        print(f"  OPENHANDS_SHA: {deploy_config.openhands_sha}")
        print(f"  OPENHANDS_RUNTIME_IMAGE_TAG: {deploy_config.openhands_runtime_image_tag}")
        print(f"  RUNTIME_API_SHA: {deploy_config.runtime_api_sha}")
    else:
        print("Could not fetch deploy config")

    runtime_api_version = get_latest_helm_chart_version(
        "all-hands-ai", "helm-charts/runtime-api"
    )
    if runtime_api_version:
        print(f"Latest runtime-api chart version: {runtime_api_version}")
    else:
        print("Could not fetch runtime-api version")

    print()
    print("=" * 60)
    print("Updating Chart.yaml...")
    print("=" * 60)

    update_chart(CHART_PATH, latest_tag, runtime_api_version, dry_run=dry_run)

    if deploy_config:
        print()
        print("=" * 60)
        print("Updating values.yaml...")
        print("=" * 60)

        update_values(
            VALUES_PATH,
            deploy_config.openhands_sha,
            deploy_config.runtime_api_sha,
            deploy_config.openhands_runtime_image_tag,
            dry_run=dry_run,
        )

    # Handle PR creation
    branch_name = get_branch_name(latest_tag)
    print()
    print("=" * 60)
    print("Pull Request...")
    print("=" * 60)

    if dry_run:
        print(f"Would create draft PR with branch: {branch_name}")
    else:
        print(f"Creating draft PR with branch: {branch_name}")
        pr_url = create_branch_and_pr(latest_tag)
        if pr_url:
            print(f"Draft PR created: {pr_url}")
        else:
            print("Failed to create PR")


if __name__ == "__main__":
    args = parse_args()
    main(dry_run=args.dry_run)
