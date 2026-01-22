#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyGithub", "ruamel.yaml", "requests"]
# ///
"""Update OpenHands chart script."""

import base64
import io
import os
import re
from dataclasses import dataclass
from pathlib import Path

import requests
from github import Auth, Github
from ruamel.yaml import YAML

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
SCRIPT_DIR = Path(__file__).parent
CHART_PATH = SCRIPT_DIR.parent / "charts" / "openhands" / "Chart.yaml"
VALUES_PATH = SCRIPT_DIR.parent / "charts" / "openhands" / "values.yaml"


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


def update_values(
    values_path: Path, openhands_sha: str, runtime_api_sha: str
) -> None:
    """Update image tags in values.yaml."""
    content = values_path.read_text()

    # Update enterprise-server image tag
    enterprise_short_sha = openhands_sha[:7]
    enterprise_new_tag = f"sha-{enterprise_short_sha}"

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
    runtime_short_sha = runtime_api_sha[:7]
    runtime_new_tag = f"sha-{runtime_short_sha}"

    runtime_pattern = r"(runtime-api:\s*\n(?:.*\n)*?\s*image:\s*\n\s*tag:\s*)(\S+)"
    runtime_match = re.search(runtime_pattern, content)

    if runtime_match:
        old_tag = runtime_match.group(2)
        if old_tag == runtime_new_tag:
            print(f"runtime-api image tag unchanged: {old_tag} (already latest)")
        else:
            content = re.sub(runtime_pattern, rf"\g<1>{runtime_new_tag}", content)
            print(f"Updated runtime-api image tag: {old_tag} -> {runtime_new_tag}")
    else:
        print("Could not find runtime-api image tag in values.yaml")

    values_path.write_text(content)


def main() -> None:
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

    update_chart(CHART_PATH, latest_tag, runtime_api_version)

    if deploy_config:
        update_values(
            VALUES_PATH, deploy_config.openhands_sha, deploy_config.runtime_api_sha
        )


if __name__ == "__main__":
    main()
