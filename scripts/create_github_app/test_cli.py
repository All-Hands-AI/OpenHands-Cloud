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
    main,
    parse_args,
)

class TestDryRun:
    """Tests for dry-run functionality.

    Dry-run mode allows users to preview changes without creating a GitHub app.

    Test Structure:
    - test_*_dry_run_prints_changes: Return value reflects changes

    TDD Rationale: Tests drive the dry_run parameter behavior, ensuring
    separation between change detection (always happens) and app creating
    (only when dry_run=False). Control tests verify the default behavior
    hasn't regressed.
    """
    def test_cli_dry_run_prints_changes(self, capsys):
        """Test that dry-run still records what would be changed."""
        # Act
        main(dry_run=True)

        # Assert: changes are tracked even though file wasn't modified
        captured = capsys.readouterr()
        assert "Hello World" in captured.out


class TestMainOutputMessages:
    """Tests for main() output message formatting."""

    def test_hello_world(self, capsys):
        main()

        captured = capsys.readouterr()
        assert "Hello World" in captured.out


class TestParseArgs:
    """Tests for parse_args function."""

    def test_dry_run_argument(self, monkeypatch):
        """Test that --dry-run argument works."""
        monkeypatch.setattr(sys, "argv", ["script", "--dry-run"])
        args = parse_args()
        assert args.dry_run is True

    def test_app_name_defaults_to_openhands(self, monkeypatch):
        """Test that app_name defaults to 'openhands' when not specified."""
        monkeypatch.setattr(sys, "argv", ["script"])
        args = parse_args()
        assert args.app_name == "openhands"

    def test_app_name_can_be_overridden(self, monkeypatch):
        """Test that --app-name argument allows custom value."""
        monkeypatch.setattr(sys, "argv", ["script", "--app-name", "custom-app"])
        args = parse_args()
        assert args.app_name == "custom-app"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
