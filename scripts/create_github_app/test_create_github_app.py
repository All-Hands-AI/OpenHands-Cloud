#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest", "requests"]
# ///
"""Unit tests for create_github_app.py."""

import sys
from pathlib import Path

import pytest

# Add the script's directory to sys.path so we can import it directly
sys.path.insert(0, str(Path(__file__).parent))

import create_github_app
from create_github_app import (
    build_app_manifest,
    create_github_app,
    main,
    parse_args,
)


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
            ("issues", "write"),
            ("metadata", "read"),
            ("pull_requests", "write"),
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
        expected = {"actions", "contents", "issues", "metadata", "pull_requests", "statuses", "workflows"}
        assert set(manifest["default_permissions"].keys()) == expected

    def test_manifest_webhook_url(self):
        """Test that hook_attributes webhook URL is https://app.BASE_DOMAIN/integration/github/events."""
        manifest = build_app_manifest(base_domain="mycompany.com")
        assert manifest["hook_attributes"]["url"] == "https://app.mycompany.com/integration/github/events"

    def test_manifest_redirect_url(self):
        """Test that redirect_url is set for GitHub to redirect after app creation."""
        manifest = build_app_manifest(base_domain="example.com")
        assert "redirect_url" in manifest
        assert manifest["redirect_url"] == "http://localhost/callback"


class TestGenerateManifestHtml:
    """Tests for generate_manifest_html function."""

    def test_html_contains_post_form_to_github(self):
        """Test that HTML form POSTs to GitHub settings."""
        from create_github_app import generate_manifest_html

        html = generate_manifest_html(base_domain="example.com")
        assert 'action="https://github.com/settings/apps/new"' in html
        assert 'method="post"' in html

    def test_html_contains_manifest_with_app_name(self):
        """Test that HTML form contains manifest with app name."""
        from create_github_app import generate_manifest_html

        html = generate_manifest_html(base_domain="example.com", app_name="test-app")
        assert '"name": "test-app"' in html

    def test_html_auto_submits_form(self):
        """Test that HTML includes auto-submit script."""
        from create_github_app import generate_manifest_html

        html = generate_manifest_html(base_domain="example.com")
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
    """Tests for main() interactive flow when not in dry-run mode."""

    def test_opens_browser(self, capsys, monkeypatch):
        """Test that main opens browser with manifest."""
        import os
        from unittest.mock import MagicMock, patch

        monkeypatch.setattr("builtins.input", lambda _: "test-code")
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 123, "name": "my-app"}
        mock_response.raise_for_status = MagicMock()

        with patch("create_github_app.webbrowser.open") as mock_browser:
            with patch("create_github_app.requests.post", return_value=mock_response):
                main(base_domain="example.com", dry_run=False, app_name="my-app")

        assert mock_browser.called
        call_arg = mock_browser.call_args[0][0]
        assert call_arg.startswith("file://")
        # Cleanup temp file
        filepath = call_arg.replace("file://", "")
        if os.path.exists(filepath):
            os.unlink(filepath)

    def test_prompts_for_code(self, monkeypatch):
        """Test that main prompts user to enter the code."""
        import os
        from unittest.mock import MagicMock, patch

        input_calls = []

        def mock_input(prompt):
            input_calls.append(prompt)
            return "test-code"

        monkeypatch.setattr("builtins.input", mock_input)
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 123}
        mock_response.raise_for_status = MagicMock()

        with patch("create_github_app.webbrowser.open") as mock_browser:
            with patch("create_github_app.requests.post", return_value=mock_response):
                main(base_domain="example.com", dry_run=False, app_name="my-app")
            # Cleanup temp file
            if mock_browser.called:
                filepath = mock_browser.call_args[0][0].replace("file://", "")
                if os.path.exists(filepath):
                    os.unlink(filepath)

        assert len(input_calls) == 1
        assert "code" in input_calls[0].lower()

    def test_exchanges_code_and_prints_credentials(self, capsys, monkeypatch):
        """Test that main exchanges code and prints the credentials."""
        import os
        from unittest.mock import MagicMock, patch

        monkeypatch.setattr("builtins.input", lambda _: "test-code")
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 123,
            "name": "my-app",
            "client_id": "Iv1.abc123",
            "client_secret": "secret456",
            "webhook_secret": "whsec789",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("create_github_app.webbrowser.open") as mock_browser:
            with patch("create_github_app.requests.post", return_value=mock_response):
                main(base_domain="example.com", dry_run=False, app_name="my-app")
            # Cleanup temp file
            if mock_browser.called:
                filepath = mock_browser.call_args[0][0].replace("file://", "")
                if os.path.exists(filepath):
                    os.unlink(filepath)

        captured = capsys.readouterr()
        # Verify order: Client ID, Client secret, App ID, Webhook secret
        lines = captured.out.strip().split("\n")
        credential_lines = [l.strip() for l in lines if l.strip().startswith(("Client ID", "Client secret", "App ID", "Webhook secret"))]
        assert credential_lines[0].startswith("Client ID:")
        assert credential_lines[1].startswith("Client secret:")
        assert credential_lines[2].startswith("App ID:")
        assert credential_lines[3].startswith("Webhook secret:")

    def test_saves_pem_to_keys_directory_in_script_folder(self, capsys, monkeypatch, tmp_path):
        """Test that pem is saved to keys/ directory in the script's folder, not cwd."""
        import os
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        monkeypatch.setattr("builtins.input", lambda _: "test-code")
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

        # Get the script directory (where create_github_app.py lives)
        import create_github_app
        script_dir = Path(create_github_app.__file__).parent
        keys_dir = script_dir / "keys"
        pem_path = keys_dir / "my-app.pem"

        # Clean up before test
        if pem_path.exists():
            pem_path.unlink()

        try:
            with patch("create_github_app.webbrowser.open") as mock_browser:
                with patch("create_github_app.requests.post", return_value=mock_response):
                    main(base_domain="example.com", dry_run=False, app_name="my-app")
                if mock_browser.called:
                    filepath = mock_browser.call_args[0][0].replace("file://", "")
                    if os.path.exists(filepath):
                        os.unlink(filepath)

            # Verify pem file was NOT created in cwd
            assert not (tmp_path / "keys" / "my-app.pem").exists()

            # Verify pem file was created in keys/ directory relative to script
            assert pem_path.exists()
            assert pem_path.read_text() == "-----BEGIN RSA PRIVATE KEY-----\ntest-key-content\n-----END RSA PRIVATE KEY-----"

            # Verify output shows the full path from repo root
            captured = capsys.readouterr()
            assert "Private key file: ./scripts/create_github_app/keys/my-app.pem" in captured.out
            # Verify Private key file comes after other credentials
            lines = captured.out.strip().split("\n")
            credential_lines = [l.strip() for l in lines if l.strip().startswith(("Client ID", "Client secret", "App ID", "Webhook secret", "Private key file"))]
            assert credential_lines[-1].startswith("Private key file:")
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
