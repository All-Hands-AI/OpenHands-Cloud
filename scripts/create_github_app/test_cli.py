#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest"]
# ///
"""Unit tests for cli.py."""

import sys
from pathlib import Path

import pytest

# Add the script's directory to sys.path so we can import it directly
sys.path.insert(0, str(Path(__file__).parent))

import cli
from cli import (
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

    def test_manifest_contains_app_name(self):
        """Test that manifest includes the app name."""
        manifest = build_app_manifest(app_name="my-app", base_domain="example.com")
        assert manifest["name"] == "my-app"

    def test_manifest_contains_urls_with_base_domain(self):
        """Test that manifest URLs use the base domain."""
        manifest = build_app_manifest(app_name="my-app", base_domain="mycompany.com")
        assert "mycompany.com" in manifest["url"]
        assert "mycompany.com" in manifest["callback_urls"][0]


class TestCreateGithubApp:
    """Tests for create_github_app function."""

    def test_creates_app_via_client(self):
        """Test that create_github_app calls the client with manifest."""
        client = FakeGithubClient()

        result = create_github_app(
            app_name="test-app",
            base_domain="test.com",
            github_client=client,
        )

        assert len(client.created_apps) == 1
        assert client.created_apps[0]["name"] == "test-app"
        assert result["id"] == 12345

    def test_returns_app_details(self):
        """Test that create_github_app returns the created app details."""
        client = FakeGithubClient()

        result = create_github_app(
            app_name="my-app",
            base_domain="example.com",
            github_client=client,
        )

        assert result["name"] == "my-app"
        assert "html_url" in result


class TestDryRun:
    """Tests for dry-run functionality."""

    def test_dry_run_does_not_create_app(self, capsys):
        """Test that dry-run mode does not create a GitHub app."""
        client = FakeGithubClient()

        main(
            app_name="test-app",
            base_domain="example.com",
            dry_run=True,
            github_client=client,
        )

        assert len(client.created_apps) == 0

    def test_dry_run_prints_what_would_be_created(self, capsys):
        """Test that dry-run mode prints intent message."""
        client = FakeGithubClient()

        main(
            app_name="test-app",
            base_domain="example.com",
            dry_run=True,
            github_client=client,
        )

        captured = capsys.readouterr()
        assert "test-app" in captured.out
        assert "example.com" in captured.out
        assert "Would create" in captured.out


class TestMainCreatesApp:
    """Tests for main() when not in dry-run mode."""

    def test_creates_app_when_not_dry_run(self):
        """Test that main creates app when dry_run=False."""
        client = FakeGithubClient()

        main(
            app_name="prod-app",
            base_domain="production.com",
            dry_run=False,
            github_client=client,
        )

        assert len(client.created_apps) == 1
        assert client.created_apps[0]["name"] == "prod-app"

    def test_prints_success_message_after_creation(self, capsys):
        """Test that main prints success message after creating app."""
        client = FakeGithubClient()

        main(
            app_name="my-app",
            base_domain="example.com",
            dry_run=False,
            github_client=client,
        )

        captured = capsys.readouterr()
        assert "Created" in captured.out
        assert "my-app" in captured.out


class TestParseArgs:
    """Tests for parse_args function."""

    def test_dry_run_argument(self, monkeypatch):
        """Test that --dry-run argument works."""
        monkeypatch.setattr(sys, "argv", ["script", "--dry-run", "--base-domain", "example.com"])
        args = parse_args()
        assert args.dry_run is True

    def test_app_name_defaults_to_openhands(self, monkeypatch):
        """Test that app_name defaults to 'openhands' when not specified."""
        monkeypatch.setattr(sys, "argv", ["script", "--base-domain", "example.com"])
        args = parse_args()
        assert args.app_name == "openhands"

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
