#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest", "requests", "playwright", "fastapi", "httpx"]
# ///
"""Unit tests for create_github_app.py."""

import sys
from pathlib import Path

import pytest

# Add the script's directory to sys.path so we can import it directly
sys.path.insert(0, str(Path(__file__).parent))

from create_github_app import (
    build_app_manifest,
    create_github_app,
    main,
    parse_args,
    SCRIPT_DIR,
)


class TestNoChangesOutsideScriptFolder:
    """Tests to verify all file changes are contained within script folder."""

    def test_keys_saved_relative_to_script(self):
        """Test that keys are saved in keys/ subdirectory of script location."""
        import threading
        from unittest.mock import MagicMock, patch

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 123,
            "pem": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
        }
        mock_response.raise_for_status = MagicMock()

        # Mock the callback server
        code_holder = MagicMock()
        code_holder.code = "test-code"
        code_holder.code_received = threading.Event()
        code_holder.code_received.set()
        server_handle = MagicMock()

        keys_dir = SCRIPT_DIR / "keys"
        pem_path = keys_dir / "test-app.pem"
        if pem_path.exists():
            pem_path.unlink()

        try:
            with patch("create_github_app.start_callback_server", return_value=(server_handle, code_holder)):
                with patch("create_github_app.open_manifest_in_browser"):
                    with patch("create_github_app.stop_callback_server"):
                        with patch("create_github_app.requests.post", return_value=mock_response):
                            main(base_domain="example.com", dry_run=False, app_name="test-app")

            # Verify the pem was saved inside script dir/keys/
            assert pem_path.exists()
            assert pem_path.parent.name == "keys"
            assert pem_path.parent.parent == SCRIPT_DIR
        finally:
            if pem_path.exists():
                pem_path.unlink()


class FakeGithubClient:
    """Fake GitHub client for testing without hitting real API."""

    def __init__(self):
        self.created_apps = []

    def create_app_from_manifest(self, manifest: dict) -> dict:
        """Record the app creation request and return fake result."""
        self.created_apps.append(manifest)
        return {
            "id": 12345,
            "name": manifest["name"],
            "html_url": f"https://github.com/apps/{manifest['name']}",
        }


class TestBuildAppManifest:
    """Tests for build_app_manifest function."""

    def test_manifest_contains_app_name_when_provided(self):
        """Test that manifest includes the app name when provided."""
        manifest = build_app_manifest(app_name="my-app", base_domain="example.com")
        assert manifest["name"] == "my-app"

    def test_manifest_app_name_defaults_to_unique_name(self):
        """Test that default app name is unique (has random suffix)."""
        manifest = build_app_manifest(base_domain="example.com")
        assert manifest["name"].startswith("openhands-")
        suffix = manifest["name"].split("-", 1)[1]
        assert len(suffix) == 8
        int(suffix, 16)  # Should be valid hex

    def test_default_app_names_are_different(self):
        """Test that multiple calls generate different default names."""
        manifest1 = build_app_manifest(base_domain="example.com")
        manifest2 = build_app_manifest(base_domain="example.com")
        assert manifest1["name"] != manifest2["name"]

    def test_manifest_url_uses_app_subdomain(self):
        """Test that manifest URL is https://app.BASE_DOMAIN."""
        manifest = build_app_manifest(base_domain="mycompany.com")
        assert manifest["url"] == "https://app.mycompany.com"

    def test_manifest_callback_url_format(self):
        """Test that callback URL is https://auth.app.BASE_DOMAIN/realms/allhands/broker/github/endpoint."""
        manifest = build_app_manifest(base_domain="mycompany.com")
        assert manifest["callback_urls"][0] == "https://auth.app.mycompany.com/realms/allhands/broker/github/endpoint"

    @pytest.mark.parametrize(
        "permission,expected_level",
        [
            ("actions", "write"),
            ("contents", "write"),
            ("emails", "read"),
            ("issues", "write"),
            ("metadata", "read"),
            ("organization_events", "read"),
            ("pull_requests", "write"),
            ("repository_hooks", "write"),
            ("statuses", "write"),
            ("workflows", "write"),
        ],
    )
    def test_manifest_permission(self, permission, expected_level):
        """Test that manifest has correct permission level."""
        manifest = build_app_manifest(base_domain="example.com")
        assert manifest["default_permissions"][permission] == expected_level

    def test_manifest_has_only_expected_permissions(self):
        """Test that manifest has exactly the expected permissions, no more."""
        manifest = build_app_manifest(base_domain="example.com")
        expected = {"actions", "contents", "emails", "issues", "metadata", "organization_events", "pull_requests", "repository_hooks", "statuses", "workflows"}
        assert set(manifest["default_permissions"].keys()) == expected

    def test_manifest_webhook_url(self):
        """Test that hook_attributes webhook URL is https://app.BASE_DOMAIN/integration/github/events."""
        manifest = build_app_manifest(base_domain="mycompany.com")
        assert manifest["hook_attributes"]["url"] == "https://app.mycompany.com/integration/github/events"

    def test_manifest_redirect_url(self):
        """Test that redirect_url is set for GitHub to redirect after app creation."""
        manifest = build_app_manifest(base_domain="example.com")
        assert "redirect_url" in manifest
        assert manifest["redirect_url"] == "http://localhost:9876/callback"

    def test_manifest_requests_oauth_on_install(self):
        """Test that manifest requests OAuth authorization during installation."""
        manifest = build_app_manifest(base_domain="example.com")
        assert manifest["request_oauth_on_install"] is True


class TestGenerateManifestHtml:
    """Tests for generate_manifest_html function."""

    def test_html_contains_post_form_to_github(self):
        """Test that HTML form POSTs to GitHub settings."""
        from create_github_app import generate_manifest_html, build_app_manifest

        manifest = build_app_manifest(base_domain="example.com")
        html = generate_manifest_html(manifest)
        assert 'action="https://github.com/settings/apps/new"' in html
        assert 'method="post"' in html

    def test_html_contains_manifest_with_app_name(self):
        """Test that HTML form contains manifest with app name."""
        from create_github_app import generate_manifest_html, build_app_manifest

        manifest = build_app_manifest(base_domain="example.com", app_name="test-app")
        html = generate_manifest_html(manifest)
        # The app name should be in the HTML (HTML-escaped)
        assert "test-app" in html

    def test_html_escapes_manifest_json_for_attribute(self):
        """Test that manifest JSON is HTML-escaped for safe embedding in attribute."""
        from create_github_app import generate_manifest_html, build_app_manifest

        manifest = build_app_manifest(base_domain="example.com", app_name="test-app")
        html = generate_manifest_html(manifest)
        # Double quotes in JSON should be escaped as &quot; for HTML attribute
        assert "&quot;" in html or 'value="' in html

    def test_html_auto_submits_form(self):
        """Test that HTML includes auto-submit script."""
        from create_github_app import generate_manifest_html, build_app_manifest

        manifest = build_app_manifest(base_domain="example.com")
        html = generate_manifest_html(manifest)
        assert "submit()" in html


class TestOpenManifestInBrowser:
    """Tests for open_manifest_in_browser function."""

    def test_writes_html_to_temp_file(self):
        """Test that HTML is written to a temp file."""
        import os
        from unittest.mock import patch

        from create_github_app import open_manifest_in_browser

        with patch("create_github_app.webbrowser.open"):
            filepath = open_manifest_in_browser(base_domain="example.com")
            assert os.path.exists(filepath)
            assert filepath.endswith(".html")
            with open(filepath) as f:
                content = f.read()
            assert "https://github.com/settings/apps/new" in content
            os.unlink(filepath)

    def test_opens_browser_with_file_url(self):
        """Test that browser is opened with file:// URL."""
        import os
        from unittest.mock import patch

        from create_github_app import open_manifest_in_browser

        with patch("create_github_app.webbrowser.open") as mock_open:
            filepath = open_manifest_in_browser(base_domain="example.com")
            mock_open.assert_called_once_with(f"file://{filepath}")
            os.unlink(filepath)


class TestExchangeCodeForCredentials:
    """Tests for exchange_code_for_credentials function."""

    def test_posts_to_github_api(self):
        """Test that it posts to the correct GitHub API endpoint."""
        from unittest.mock import MagicMock, patch

        from create_github_app import exchange_code_for_credentials

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 123, "client_secret": "secret"}
        mock_response.raise_for_status = MagicMock()

        with patch("create_github_app.requests.post", return_value=mock_response) as mock_post:
            exchange_code_for_credentials("test-code")
            mock_post.assert_called_once_with(
                "https://api.github.com/app-manifests/test-code/conversions",
                headers={"Accept": "application/vnd.github+json"},
            )

    def test_returns_credentials(self):
        """Test that it returns the credentials from the API response."""
        from unittest.mock import MagicMock, patch

        from create_github_app import exchange_code_for_credentials

        expected = {
            "id": 123,
            "client_id": "client-123",
            "client_secret": "secret-456",
            "pem": "-----BEGIN RSA PRIVATE KEY-----",
            "webhook_secret": "webhook-secret",
        }
        mock_response = MagicMock()
        mock_response.json.return_value = expected
        mock_response.raise_for_status = MagicMock()

        with patch("create_github_app.requests.post", return_value=mock_response):
            result = exchange_code_for_credentials("test-code")
            assert result == expected


class TestCreateGithubApp:
    """Tests for create_github_app function."""

    def test_creates_app_via_client(self):
        """Test that create_github_app calls the client with manifest."""
        client = FakeGithubClient()

        result = create_github_app(
            base_domain="test.com",
            github_client=client,
            app_name="test-app",
        )

        assert len(client.created_apps) == 1
        assert client.created_apps[0]["name"] == "test-app"
        assert result["id"] == 12345

    def test_returns_app_details(self):
        """Test that create_github_app returns the created app details."""
        client = FakeGithubClient()

        result = create_github_app(
            base_domain="example.com",
            github_client=client,
            app_name="my-app",
        )

        assert result["name"] == "my-app"
        assert "html_url" in result


class TestDryRun:
    """Tests for dry-run functionality."""

    def test_dry_run_does_not_create_app(self, capsys):
        """Test that dry-run mode does not create a GitHub app."""
        client = FakeGithubClient()

        main(
            base_domain="example.com",
            dry_run=True,
            github_client=client,
            app_name="test-app",
        )

        assert len(client.created_apps) == 0

    def test_dry_run_prints_what_would_be_created(self, capsys):
        """Test that dry-run mode prints intent message."""
        client = FakeGithubClient()

        main(
            base_domain="example.com",
            dry_run=True,
            github_client=client,
            app_name="test-app",
        )

        captured = capsys.readouterr()
        assert "test-app" in captured.out
        assert "example.com" in captured.out
        assert "Would create" in captured.out


class TestMainInteractiveFlow:
    """Tests for main() interactive flow using callback server and user's default browser."""

    def _mock_callback_server(self, code="test-code"):
        """Helper to create mock callback server that returns specified code."""
        import threading
        from unittest.mock import MagicMock

        code_holder = MagicMock()
        code_holder.code = code
        code_holder.code_received = threading.Event()
        code_holder.code_received.set()
        server_handle = MagicMock()
        return server_handle, code_holder

    def test_opens_browser_with_callback_server(self, capsys):
        """Test that main opens browser after starting callback server."""
        from unittest.mock import MagicMock, patch

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 123}
        mock_response.raise_for_status = MagicMock()

        server_handle, code_holder = self._mock_callback_server()

        with patch("create_github_app.start_callback_server", return_value=(server_handle, code_holder)):
            with patch("create_github_app.open_manifest_in_browser") as mock_open:
                with patch("create_github_app.stop_callback_server"):
                    with patch("create_github_app.requests.post", return_value=mock_response):
                        main(base_domain="example.com", dry_run=False, app_name="my-app")

        mock_open.assert_called_once()

    def test_tells_user_to_click_button(self, capsys):
        """Test that main tells user to click the Create GitHub App button."""
        from unittest.mock import MagicMock, patch

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 123}
        mock_response.raise_for_status = MagicMock()

        server_handle, code_holder = self._mock_callback_server()

        with patch("create_github_app.start_callback_server", return_value=(server_handle, code_holder)):
            with patch("create_github_app.open_manifest_in_browser"):
                with patch("create_github_app.stop_callback_server"):
                    with patch("create_github_app.requests.post", return_value=mock_response):
                        main(base_domain="example.com", dry_run=False, app_name="my-app")

        captured = capsys.readouterr()
        assert "Click" in captured.out
        assert "Create GitHub App for" in captured.out

    def test_mentions_waiting_for_callback(self, capsys):
        """Test that main tells user it's waiting for the GitHub callback."""
        from unittest.mock import MagicMock, patch

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 123}
        mock_response.raise_for_status = MagicMock()

        server_handle, code_holder = self._mock_callback_server()

        with patch("create_github_app.start_callback_server", return_value=(server_handle, code_holder)):
            with patch("create_github_app.open_manifest_in_browser"):
                with patch("create_github_app.stop_callback_server"):
                    with patch("create_github_app.requests.post", return_value=mock_response):
                        main(base_domain="example.com", dry_run=False, app_name="my-app")

        captured = capsys.readouterr()
        assert "Waiting" in captured.out

    def test_mentions_button_includes_username(self, capsys):
        """Test that message mentions the button text includes the user's GitHub username."""
        from unittest.mock import MagicMock, patch

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 123}
        mock_response.raise_for_status = MagicMock()

        server_handle, code_holder = self._mock_callback_server()

        with patch("create_github_app.start_callback_server", return_value=(server_handle, code_holder)):
            with patch("create_github_app.open_manifest_in_browser"):
                with patch("create_github_app.stop_callback_server"):
                    with patch("create_github_app.requests.post", return_value=mock_response):
                        main(base_domain="example.com", dry_run=False, app_name="my-app")

        captured = capsys.readouterr()
        # Message should mention that button says "Create GitHub App for <username>"
        assert "Create GitHub App for" in captured.out

    def test_exchanges_code_and_prints_credentials(self, capsys):
        """Test that main exchanges code and prints the credentials."""
        from unittest.mock import MagicMock, patch

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 123,
            "name": "my-app",
            "client_id": "Iv1.abc123",
            "client_secret": "secret456",
            "webhook_secret": "whsec789",
        }
        mock_response.raise_for_status = MagicMock()

        server_handle, code_holder = self._mock_callback_server()

        with patch("create_github_app.start_callback_server", return_value=(server_handle, code_holder)):
            with patch("create_github_app.open_manifest_in_browser"):
                with patch("create_github_app.stop_callback_server"):
                    with patch("create_github_app.requests.post", return_value=mock_response):
                        main(base_domain="example.com", dry_run=False, app_name="my-app")

        captured = capsys.readouterr()
        # Verify labels
        assert "GitHub OAuth Client ID: Iv1.abc123" in captured.out
        assert "GitHub OAuth Client Secret: secret456" in captured.out
        assert "GitHub App ID: 123" in captured.out
        assert "GitHub App Webhook Secret: whsec789" in captured.out

    def test_saves_pem_to_keys_directory_in_script_folder(self, capsys, monkeypatch, tmp_path):
        """Test that pem is saved to keys/ directory in the script's folder, not cwd."""
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        # Change to a different directory to verify keys are NOT created in cwd
        monkeypatch.chdir(tmp_path)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 123,
            "name": "my-app",
            "client_id": "Iv1.abc123",
            "client_secret": "secret456",
            "pem": "-----BEGIN RSA PRIVATE KEY-----\ntest-key-content\n-----END RSA PRIVATE KEY-----",
        }
        mock_response.raise_for_status = MagicMock()

        server_handle, code_holder = self._mock_callback_server()

        # Get the script directory (where create_github_app.py lives)
        import create_github_app
        script_dir = Path(create_github_app.__file__).parent
        keys_dir = script_dir / "keys"
        pem_path = keys_dir / "my-app.pem"

        # Clean up before test
        if pem_path.exists():
            pem_path.unlink()

        try:
            with patch("create_github_app.start_callback_server", return_value=(server_handle, code_holder)):
                with patch("create_github_app.open_manifest_in_browser"):
                    with patch("create_github_app.stop_callback_server"):
                        with patch("create_github_app.requests.post", return_value=mock_response):
                            main(base_domain="example.com", dry_run=False, app_name="my-app")

            # Verify pem file was NOT created in cwd
            assert not (tmp_path / "keys" / "my-app.pem").exists()

            # Verify pem file was created in keys/ directory relative to script
            assert pem_path.exists()
            assert pem_path.read_text() == "-----BEGIN RSA PRIVATE KEY-----\ntest-key-content\n-----END RSA PRIVATE KEY-----"

            # Verify output shows the full path from repo root
            captured = capsys.readouterr()
            assert "GitHub App Private Key: ./scripts/create_github_app/keys/my-app.pem" in captured.out
        finally:
            # Clean up after test
            if pem_path.exists():
                pem_path.unlink()


class TestParseArgs:
    """Tests for parse_args function."""

    def test_dry_run_argument(self, monkeypatch):
        """Test that --dry-run argument works."""
        monkeypatch.setattr(sys, "argv", ["script", "--dry-run", "--base-domain", "example.com"])
        args = parse_args()
        assert args.dry_run is True

    def test_app_name_defaults_to_none(self, monkeypatch):
        """Test that app_name defaults to None when not specified (unique name generated later)."""
        monkeypatch.setattr(sys, "argv", ["script", "--base-domain", "example.com"])
        args = parse_args()
        assert args.app_name is None

    def test_app_name_can_be_overridden(self, monkeypatch):
        """Test that --app-name argument allows custom value."""
        monkeypatch.setattr(sys, "argv", ["script", "--app-name", "custom-app", "--base-domain", "example.com"])
        args = parse_args()
        assert args.app_name == "custom-app"

    def test_base_domain_is_required(self, monkeypatch):
        """Test that --base-domain is required and errors when missing."""
        monkeypatch.setattr(sys, "argv", ["script"])
        with pytest.raises(SystemExit) as exc_info:
            parse_args()
        assert exc_info.value.code == 2  # argparse exits with 2 for missing required args

    def test_base_domain_accepts_value(self, monkeypatch):
        """Test that --base-domain argument accepts a value."""
        monkeypatch.setattr(sys, "argv", ["script", "--base-domain", "mycompany.com"])
        args = parse_args()
        assert args.base_domain == "mycompany.com"


class TestCallbackServer:
    """Tests for the FastAPI callback server that captures the GitHub OAuth code."""

    def test_callback_endpoint_extracts_code_from_query_param(self):
        """Test that /callback extracts the code from query parameter."""
        from fastapi.testclient import TestClient
        from create_github_app import create_callback_app

        app, code_holder = create_callback_app()
        client = TestClient(app)

        response = client.get("/callback?code=test-auth-code-123")

        assert response.status_code == 200
        assert code_holder.code == "test-auth-code-123"

    def test_callback_endpoint_returns_success_html(self):
        """Test that /callback returns a user-friendly success HTML page."""
        from fastapi.testclient import TestClient
        from create_github_app import create_callback_app

        app, _ = create_callback_app()
        client = TestClient(app)

        response = client.get("/callback?code=some-code")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "success" in response.text.lower()

    def test_callback_endpoint_handles_missing_code(self):
        """Test that /callback handles missing code parameter gracefully."""
        from fastapi.testclient import TestClient
        from create_github_app import create_callback_app

        app, code_holder = create_callback_app()
        client = TestClient(app)

        response = client.get("/callback")

        assert response.status_code == 400
        assert code_holder.code is None

    def test_callback_endpoint_signals_code_received(self):
        """Test that /callback sets an event when code is received."""
        from fastapi.testclient import TestClient
        from create_github_app import create_callback_app

        app, code_holder = create_callback_app()
        client = TestClient(app)

        assert not code_holder.code_received.is_set()
        client.get("/callback?code=test-code")
        assert code_holder.code_received.is_set()


class TestCallbackServerLifecycle:
    """Tests for starting and stopping the callback server."""

    def test_start_callback_server_runs_on_specified_port(self):
        """Test that the callback server runs on localhost:port."""
        import time
        import httpx
        from create_github_app import start_callback_server, stop_callback_server

        server_handle, code_holder = start_callback_server(port=18234)
        try:
            time.sleep(0.5)  # Give server time to start
            response = httpx.get("http://localhost:18234/callback?code=test-code")
            assert response.status_code == 200
            assert code_holder.code == "test-code"
        finally:
            stop_callback_server(server_handle)

    def test_stop_callback_server_shuts_down_cleanly(self):
        """Test that stop_callback_server shuts down the server."""
        import time
        import httpx
        from create_github_app import start_callback_server, stop_callback_server

        server_handle, _ = start_callback_server(port=18235)
        time.sleep(0.5)
        stop_callback_server(server_handle)
        time.sleep(0.5)

        with pytest.raises(httpx.ConnectError):
            httpx.get("http://localhost:18235/callback?code=test")


class TestManifestRedirectUrl:
    """Tests for manifest redirect_url with callback port."""

    def test_manifest_redirect_url_uses_callback_port(self):
        """Test that manifest redirect_url points to localhost with specified port."""
        manifest = build_app_manifest(base_domain="example.com", callback_port=18080)
        assert manifest["redirect_url"] == "http://localhost:18080/callback"

    def test_manifest_redirect_url_defaults_to_port_9876(self):
        """Test that manifest redirect_url defaults to port 9876 when no port specified."""
        manifest = build_app_manifest(base_domain="example.com")
        assert manifest["redirect_url"] == "http://localhost:9876/callback"


class TestMainWithCallbackServer:
    """Tests for main() integration with callback server."""

    def test_main_starts_callback_server_before_opening_browser(self):
        """Test that main starts callback server before opening browser."""
        from unittest.mock import MagicMock, patch, call
        import threading

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 123}
        mock_response.raise_for_status = MagicMock()

        call_order = []

        def track_start_server(*args, **kwargs):
            call_order.append("start_server")
            code_holder = MagicMock()
            code_holder.code = "test-code"
            code_holder.code_received = threading.Event()
            code_holder.code_received.set()
            return MagicMock(), code_holder

        def track_open_browser(*args, **kwargs):
            call_order.append("open_browser")
            return "/tmp/test.html"

        with patch("create_github_app.start_callback_server", side_effect=track_start_server) as mock_start:
            with patch("create_github_app.open_manifest_in_browser", side_effect=track_open_browser):
                with patch("create_github_app.stop_callback_server"):
                    with patch("create_github_app.requests.post", return_value=mock_response):
                        main(base_domain="example.com", dry_run=False, app_name="my-app")

        assert call_order == ["start_server", "open_browser"]

    def test_main_waits_for_code_from_callback_server(self, capsys):
        """Test that main waits for code from callback server instead of prompting."""
        from unittest.mock import MagicMock, patch
        import threading

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 123, "client_id": "test-client"}
        mock_response.raise_for_status = MagicMock()

        code_holder = MagicMock()
        code_holder.code = "received-code-from-callback"
        code_holder.code_received = threading.Event()
        code_holder.code_received.set()

        with patch("create_github_app.start_callback_server", return_value=(MagicMock(), code_holder)):
            with patch("create_github_app.open_manifest_in_browser"):
                with patch("create_github_app.stop_callback_server"):
                    with patch("create_github_app.requests.post", return_value=mock_response) as mock_post:
                        # Should NOT need input() - no prompting
                        main(base_domain="example.com", dry_run=False, app_name="my-app")

        # Verify the code from callback was used
        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        assert "received-code-from-callback" in call_url

    def test_main_stops_callback_server_after_receiving_code(self):
        """Test that main stops callback server after receiving the code."""
        from unittest.mock import MagicMock, patch
        import threading

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 123}
        mock_response.raise_for_status = MagicMock()

        code_holder = MagicMock()
        code_holder.code = "test-code"
        code_holder.code_received = threading.Event()
        code_holder.code_received.set()
        server_handle = MagicMock()

        with patch("create_github_app.start_callback_server", return_value=(server_handle, code_holder)):
            with patch("create_github_app.open_manifest_in_browser"):
                with patch("create_github_app.stop_callback_server") as mock_stop:
                    with patch("create_github_app.requests.post", return_value=mock_response):
                        main(base_domain="example.com", dry_run=False, app_name="my-app")

        mock_stop.assert_called_once_with(server_handle)

    def test_main_no_longer_prompts_for_code_input(self):
        """Test that main does not prompt for manual code input."""
        from unittest.mock import MagicMock, patch
        import threading

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 123}
        mock_response.raise_for_status = MagicMock()

        code_holder = MagicMock()
        code_holder.code = "auto-captured-code"
        code_holder.code_received = threading.Event()
        code_holder.code_received.set()

        with patch("create_github_app.start_callback_server", return_value=(MagicMock(), code_holder)):
            with patch("create_github_app.open_manifest_in_browser"):
                with patch("create_github_app.stop_callback_server"):
                    with patch("create_github_app.requests.post", return_value=mock_response):
                        with patch("builtins.input") as mock_input:
                            main(base_domain="example.com", dry_run=False, app_name="my-app")

        # input() should never be called
        mock_input.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
