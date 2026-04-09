#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyGithub", "requests"]
# ///
"""CLI to create a GitHub app for OpenHands Enterprise (OHE)."""

import argparse
import base64
import json
import tempfile
import webbrowser
from typing import Any, Protocol

import requests

DEFAULT_APP_NAME = "openhands"


class GithubClient(Protocol):
    """Protocol for GitHub client to enable dependency injection."""

    def create_app_from_manifest(self, manifest: dict) -> dict:
        """Create a GitHub App from a manifest."""
        ...


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
        default=DEFAULT_APP_NAME,
        help=f"Name of the GitHub App to create (default: {DEFAULT_APP_NAME}).",
    )
    parser.add_argument(
        "--base-domain",
        required=True,
        help="Base domain for the GitHub App (e.g., mycompany.com).",
    )
    return parser.parse_args()


def build_app_manifest(base_domain: str, app_name: str = DEFAULT_APP_NAME) -> dict[str, Any]:
    """Build the GitHub App manifest configuration."""
    return {
        "name": app_name,
        "url": f"https://app.{base_domain}",
        "callback_urls": [f"https://auth.app.{base_domain}/realms/allhands/broker/github/endpoint"],
        "public": False,
        "default_permissions": {
            "actions": "write",
            "contents": "write",
            "emails": "read",
            "issues": "write",
            "metadata": "read",
            "organization_events": "read",
            "pull_requests": "write",
            "statuses": "write",
            "webhooks": "write",
            "workflows": "write",
        },
        "hook_attributes": {
            "url": f"https://app.{base_domain}/integration/github/events",
        },
    }


def generate_manifest_html(base_domain: str, app_name: str = DEFAULT_APP_NAME) -> str:
    """Generate HTML form that POSTs to GitHub to create app from manifest."""
    manifest = build_app_manifest(base_domain, app_name)
    manifest_json = json.dumps(manifest)
    return f"""<!DOCTYPE html>
<html>
<head><title>Creating GitHub App...</title></head>
<body>
<p>Redirecting to GitHub to create your app...</p>
<form id="manifest-form" action="https://github.com/settings/apps/new" method="post">
<input type="hidden" name="manifest" value='{manifest_json}'>
</form>
<script>document.getElementById('manifest-form').submit();</script>
</body>
</html>"""


def open_manifest_in_browser(base_domain: str, app_name: str = DEFAULT_APP_NAME) -> str:
    """Write manifest HTML to temp file and open in browser. Returns file path."""
    html = generate_manifest_html(base_domain, app_name)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
        f.write(html)
        filepath = f.name
    webbrowser.open(f"file://{filepath}")
    return filepath


def exchange_code_for_credentials(code: str) -> dict:
    """Exchange the temporary code for app credentials."""
    response = requests.post(
        f"https://api.github.com/app-manifests/{code}/conversions",
        headers={"Accept": "application/vnd.github+json"},
    )
    response.raise_for_status()
    return response.json()


def create_github_app(
    base_domain: str,
    github_client: GithubClient,
    app_name: str = DEFAULT_APP_NAME,
) -> dict:
    """Create a GitHub App using the provided client."""
    manifest = build_app_manifest(base_domain, app_name)
    return github_client.create_app_from_manifest(manifest)


def main(
    base_domain: str,
    dry_run: bool = False,
    github_client: GithubClient | None = None,
    app_name: str = DEFAULT_APP_NAME,
) -> None:
    """Main entry point for creating a GitHub App."""
    if dry_run:
        print(f"Would create GitHub App '{app_name}' for domain '{base_domain}'")
        return

    # Interactive flow: open browser, prompt for code, exchange for credentials
    print(f"\nOpening browser to create GitHub App '{app_name}'...")
    open_manifest_in_browser(base_domain, app_name)
    print("After completing the flow, GitHub will redirect you to a URL with a 'code' parameter.")

    code = input("\nEnter the code from the URL: ").strip()

    credentials = exchange_code_for_credentials(code)
    print(f"\nGitHub App created successfully!")
    print(f"\nCredentials:")
    for key in ["id", "name", "client_id", "client_secret", "pem", "webhook_secret"]:
        if key in credentials:
            value = credentials[key]
            if key == "pem":
                value = value[:50] + "..." if len(value) > 50 else value
            print(f"  {key}: {value}")


if __name__ == "__main__":
    args = parse_args()
    main(
        base_domain=args.base_domain,
        dry_run=args.dry_run,
        app_name=args.app_name,
    )
