#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyGithub", "requests"]
# ///
"""CLI to create a GitHub app for OpenHands Enterprise (OHE)."""

import argparse
import html
import json
import secrets
import tempfile
import webbrowser
from pathlib import Path
from typing import Any, Protocol

import requests

SCRIPT_DIR = Path(__file__).parent

APP_NAME_PREFIX = "openhands"


def generate_unique_app_name() -> str:
    """Generate a unique app name with random suffix."""
    return f"{APP_NAME_PREFIX}-{secrets.token_hex(4)}"


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
        default=None,
        help="Name of the GitHub App to create (default: openhands-<random>).",
    )
    parser.add_argument(
        "--base-domain",
        required=True,
        help="Base domain for the GitHub App (e.g., mycompany.com).",
    )
    return parser.parse_args()


def build_app_manifest(base_domain: str, app_name: str | None = None) -> dict[str, Any]:
    """Build the GitHub App manifest configuration."""
    if app_name is None:
        app_name = generate_unique_app_name()
    return {
        "name": app_name,
        "url": f"https://app.{base_domain}",
        "redirect_url": "http://localhost/callback",
        "callback_urls": [f"https://auth.app.{base_domain}/realms/allhands/broker/github/endpoint"],
        "public": False,
        "request_oauth_on_install": True,
        "default_permissions": {
            "actions": "write",
            "contents": "write",
            "emails": "read",
            "issues": "write",
            "metadata": "read",
            "pull_requests": "write",
            "statuses": "write",
            "workflows": "write",
        },
        "hook_attributes": {
            "url": f"https://app.{base_domain}/integration/github/events",
        },
    }


def generate_manifest_html(manifest: dict[str, Any]) -> str:
    """Generate HTML form that POSTs to GitHub to create app from manifest."""
    manifest_json = json.dumps(manifest)
    # HTML-escape the JSON to safely embed in the value attribute
    escaped_json = html.escape(manifest_json)
    return f"""<!DOCTYPE html>
<html>
<head><title>Creating GitHub App...</title></head>
<body>
<p>Redirecting to GitHub to create your app...</p>
<form id="manifest-form" action="https://github.com/settings/apps/new" method="post">
<input type="hidden" name="manifest" value="{escaped_json}">
</form>
<script>document.getElementById('manifest-form').submit();</script>
</body>
</html>"""


def open_manifest_in_browser(base_domain: str, app_name: str | None = None) -> str:
    """Write manifest HTML to temp file and open in browser. Returns file path."""
    manifest = build_app_manifest(base_domain, app_name)
    html = generate_manifest_html(manifest)
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
    app_name: str | None = None,
) -> dict:
    """Create a GitHub App using the provided client."""
    manifest = build_app_manifest(base_domain, app_name)
    return github_client.create_app_from_manifest(manifest)


def main(
    base_domain: str,
    dry_run: bool = False,
    github_client: GithubClient | None = None,
    app_name: str | None = None,
) -> None:
    """Main entry point for creating a GitHub App."""
    if app_name is None:
        app_name = generate_unique_app_name()
    if dry_run:
        print(f"Would create GitHub App '{app_name}' for domain '{base_domain}'")
        return

    # Open browser for user to create app (they're already logged into GitHub)
    print(f"\nOpening browser to create GitHub App '{app_name}'...")
    print("Click 'Create GitHub App for <your-username>' to continue.")
    print("You'll be redirected to a page that shows a 404 error - this is expected.")
    print("Copy the 'code' parameter from the URL.\n")
    open_manifest_in_browser(base_domain, app_name)

    code = input("Enter the code from the redirect URL: ").strip()

    credentials = exchange_code_for_credentials(code)
    print(f"\nGitHub App created successfully!")

    # Save pem to keys/ directory relative to script location
    pem_path = None
    if "pem" in credentials:
        script_dir = Path(__file__).parent
        keys_dir = script_dir / "keys"
        keys_dir.mkdir(exist_ok=True)
        pem_path = keys_dir / f"{app_name}.pem"
        pem_path.write_text(credentials["pem"])

    print(f"\nCredentials:")
    display_names = {
        "id": "GitHub App ID",
        "client_id": "GitHub OAuth Client ID",
        "client_secret": "GitHub OAuth Client Secret",
        "webhook_secret": "GitHub App Webhook Secret",
    }
    for key in ["client_id", "client_secret", "id", "webhook_secret"]:
        if key in credentials:
            display_key = display_names.get(key, key)
            print(f"  {display_key}: {credentials[key]}")
    if pem_path:
        display_path = f"./scripts/create_github_app/keys/{app_name}.pem"
        print(f"  GitHub App Private Key: {display_path}")


if __name__ == "__main__":
    args = parse_args()
    main(
        base_domain=args.base_domain,
        dry_run=args.dry_run,
        app_name=args.app_name,
    )
