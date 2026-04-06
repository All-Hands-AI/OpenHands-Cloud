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
)

class TestMainOutputMessages:
    """Tests for main() output message formatting."""

    def test_hello_world(self, capsys):
        main()

        captured = capsys.readouterr()
        assert "Hello World" in captured.out

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
