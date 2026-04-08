#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyGithub"]
# ///
"""CLI to create a GitHub app for OpenHands Enterprise (OHE)."""

import argparse
from typing import Any, Protocol


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
        default="openhands",
        help="Name of the GitHub App to create (default: openhands).",
    )
    parser.add_argument(
        "--base-domain",
        required=True,
        help="Base domain for the GitHub App (e.g., mycompany.com).",
    )
    return parser.parse_args()


def build_app_manifest(app_name: str, base_domain: str) -> dict[str, Any]:
    """Build the GitHub App manifest configuration."""
    return {
        "name": app_name,
        "url": f"https://{base_domain}",
        "callback_urls": [f"https://{base_domain}/github/callback"],
        "public": False,
        "default_permissions": {
            "contents": "read",
            "metadata": "read",
        },
    }


def create_github_app(
    app_name: str,
    base_domain: str,
    github_client: GithubClient,
) -> dict:
    """Create a GitHub App using the provided client."""
    manifest = build_app_manifest(app_name, base_domain)
    return github_client.create_app_from_manifest(manifest)


def main(
    app_name: str,
    base_domain: str,
    dry_run: bool = False,
    github_client: GithubClient | None = None,
) -> None:
    """Main entry point for creating a GitHub App."""
    if dry_run:
        print(f"Would create GitHub App '{app_name}' for domain '{base_domain}'")
        return

    if github_client is None:
        raise ValueError("github_client is required when not in dry-run mode")

    result = create_github_app(app_name, base_domain, github_client)
    print(f"Created GitHub App '{result['name']}' at {result['html_url']}")


if __name__ == "__main__":
    args = parse_args()
    main(
        app_name=args.app_name,
        base_domain=args.base_domain,
        dry_run=args.dry_run,
    )
