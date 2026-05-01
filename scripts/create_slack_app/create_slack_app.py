#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["requests"]
# ///
"""CLI to create a Slack app for an OpenHands Enterprise (OHE) instance."""

import argparse
import os
from typing import Any

import requests

SLACK_MANIFEST_API = "https://slack.com/api/apps.manifest.create"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a Slack app for an OpenHands Enterprise (OHE) instance."
    )
    parser.add_argument(
        "--base-domain",
        required=True,
        help="Base domain for the OpenHands instance (e.g., mycompany.com). "
        "The app URLs will be constructed as https://app.<base-domain>/slack/...",
    )
    parser.add_argument(
        "--slack-token",
        default=os.environ.get("SLACK_CONFIG_TOKEN"),
        help="Slack app configuration token (xoxe-...). "
        "Falls back to SLACK_CONFIG_TOKEN env var. "
        "Obtain one from https://api.slack.com/apps in the "
        "Your App Configuration Tokens section.",
    )
    parser.add_argument(
        "--app-name",
        default=None,
        help="Display name for the Slack app (default: OpenHands).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without calling the Slack API.",
    )
    return parser.parse_args(argv)


def build_app_manifest(
    base_domain: str,
    app_name: str | None = None,
) -> dict[str, Any]:
    display_name = app_name if app_name is not None else "OpenHands"
    app_base_url = f"https://app.{base_domain}"
    return {
        "display_information": {
            "name": display_name,
        },
        "features": {
            "bot_user": {
                "display_name": display_name,
                "always_online": False,
            },
        },
        "oauth_config": {
            "redirect_urls": [
                f"{app_base_url}/slack/install-callback",
            ],
            "scopes": {
                "bot": [
                    "app_mentions:read",
                    "chat:write",
                    "users:read",
                    "channels:history",
                    "groups:history",
                    "mpim:history",
                    "im:history",
                ],
            },
        },
        "settings": {
            "event_subscriptions": {
                "request_url": f"{app_base_url}/slack/on-event",
                "bot_events": ["app_mention"],
            },
            "interactivity": {
                "is_enabled": True,
                "request_url": f"{app_base_url}/slack/on-form-interaction",
                "message_menu_options_url": f"{app_base_url}/slack/on-options-load",
            },
            "org_deploy_enabled": False,
            "socket_mode_enabled": False,
            "token_rotation_enabled": False,
        },
    }


def create_slack_app(manifest: dict[str, Any], token: str) -> dict:
    response = requests.post(
        SLACK_MANIFEST_API,
        headers={"Authorization": f"Bearer {token}"},
        json={"manifest": manifest},
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        detail = data.get("errors") or data.get("error", "unknown error")
        raise RuntimeError(f"Slack API error: {detail}\nFull response: {data}")
    return data


def main(
    base_domain: str,
    slack_token: str,
    dry_run: bool = False,
    app_name: str | None = None,
) -> None:
    if dry_run:
        print(f"Would create Slack app for domain '{base_domain}'")
        return

    manifest = build_app_manifest(base_domain, app_name)
    result = create_slack_app(manifest, token=slack_token)
    credentials = result.get("credentials", {})

    print(f"Slack Client ID: {credentials.get('client_id')}")
    print(f"Slack Client Secret: {credentials.get('client_secret')}")
    print(f"Slack Signing Secret: {credentials.get('signing_secret')}")


def missing_token_message() -> str:
    return (
        "Error: Slack configuration token required. "
        "Pass --slack-token or set SLACK_CONFIG_TOKEN env var.\n\n"
        "To get a token:\n"
        "  1. Go to https://api.slack.com/apps\n"
        "  2. Click Generate Token in the Your App Configuration Tokens section\n"
        "  3. Use the access token (starts with xoxe.xoxp-)"
    )


if __name__ == "__main__":
    args = parse_args()
    if not args.slack_token:
        raise SystemExit(missing_token_message())
    main(
        base_domain=args.base_domain,
        slack_token=args.slack_token,
        dry_run=args.dry_run,
        app_name=args.app_name,
    )
