#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyGithub", "requests", "fastapi", "uvicorn"]
# ///
"""CLI to create a GitHub app for OpenHands Enterprise (OHE)."""

import argparse
import html
import json
import secrets
import tempfile
import threading
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import requests
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

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


DEFAULT_CALLBACK_PORT = 9876  # Using high port that doesn't require root


def build_app_manifest(
    base_domain: str,
    app_name: str | None = None,
    callback_port: int = DEFAULT_CALLBACK_PORT,
) -> dict[str, Any]:
    """Build the GitHub App manifest configuration."""
    if app_name is None:
        app_name = generate_unique_app_name()
    return {
        "name": app_name,
        "url": f"https://app.{base_domain}",
        "redirect_url": f"http://localhost:{callback_port}/callback",
        "callback_urls": [f"https://auth.app.{base_domain}/realms/allhands/broker/github/endpoint"],
        "public": False,
        "request_oauth_on_install": True,
        "default_permissions": {
            "actions": "write",
            "contents": "write",
            "emails": "read",
            "issues": "write",
            "metadata": "read",
            "organization_events": "read",
            "pull_requests": "write",
            "repository_hooks": "write",
            "statuses": "write",
            "workflows": "write",
        },
        "default_events": [
            "issue_comment",
            "pull_request",
            "pull_request_review_comment",
        ],
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


def open_manifest_in_browser(
    base_domain: str,
    app_name: str | None = None,
    callback_port: int = DEFAULT_CALLBACK_PORT,
) -> str:
    """Write manifest HTML to temp file and open in browser. Returns file path."""
    manifest = build_app_manifest(base_domain, app_name, callback_port=callback_port)
    html = generate_manifest_html(manifest)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
        f.write(html)
        filepath = f.name
    webbrowser.open(f"file://{filepath}")
    return filepath


@dataclass
class CodeHolder:
    """Holds the OAuth code received from GitHub callback."""

    code: str | None = None
    code_received: threading.Event = field(default_factory=threading.Event)


def create_callback_app() -> tuple[FastAPI, CodeHolder]:
    """Create a FastAPI app with a /callback endpoint to capture the OAuth code."""
    app = FastAPI()
    code_holder = CodeHolder()

    @app.get("/callback", response_class=HTMLResponse)
    def callback(code: str | None = None):
        if code is None:
            return HTMLResponse(
                content="<html><body><h1>Error</h1><p>Missing code parameter.</p></body></html>",
                status_code=400,
            )
        code_holder.code = code
        code_holder.code_received.set()
        return HTMLResponse(
            content="""<html>
<head><title>Success</title></head>
<body>
<h1>Success!</h1>
<p>GitHub App code received. You can close this window.</p>
<p>Return to the terminal to continue.</p>
</body>
</html>""",
            status_code=200,
        )

    return app, code_holder


class ServerHandle:
    """Handle for managing a running uvicorn server."""

    def __init__(self, server: uvicorn.Server, thread: threading.Thread):
        self.server = server
        self.thread = thread


def start_callback_server(port: int = 80) -> tuple[ServerHandle, CodeHolder]:
    """Start the callback server in a background thread."""
    app, code_holder = create_callback_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    return ServerHandle(server, thread), code_holder


def stop_callback_server(handle: ServerHandle) -> None:
    """Stop the callback server."""
    handle.server.should_exit = True
    handle.thread.join(timeout=5)


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
    callback_port: int = DEFAULT_CALLBACK_PORT,
) -> None:
    """Main entry point for creating a GitHub App."""
    if app_name is None:
        app_name = generate_unique_app_name()
    if dry_run:
        print(f"Would create GitHub App '{app_name}' for domain '{base_domain}'")
        return

    # Start callback server to capture the code from GitHub redirect
    server_handle, code_holder = start_callback_server(port=callback_port)

    try:
        # Open browser for user to create app (they're already logged into GitHub)
        print(f"\nOpening browser to create GitHub App '{app_name}'...")
        print("Click 'Create GitHub App for <your-username>' to continue.")
        print("Waiting for GitHub callback...\n")
        open_manifest_in_browser(base_domain, app_name, callback_port=callback_port)

        # Wait for the code to be received via callback
        print("Waiting for authorization code...")
        code_holder.code_received.wait(timeout=300)  # 5 minute timeout
        code = code_holder.code

        if code is None:
            print("Error: Timed out waiting for authorization code.")
            return

        print("Authorization code received!")
    finally:
        # Always stop the callback server
        stop_callback_server(server_handle)

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
        "client_id": "GitHub App Client ID",
        "client_secret": "GitHub App Client Secret",
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
