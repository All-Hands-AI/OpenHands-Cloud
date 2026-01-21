#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyGithub", "ruamel.yaml", "requests", "pytest"]
# ///
"""Unit tests for update-openhands-chart.py."""

import importlib.util
import tempfile
from pathlib import Path

import pytest
from ruamel.yaml import YAML

# Load the script as a module
spec = importlib.util.spec_from_file_location(
    "update_openhands_chart",
    Path(__file__).parent / "update-openhands-chart.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

bump_patch_version = module.bump_patch_version
update_chart = module.update_chart
SEMVER_PATTERN = module.SEMVER_PATTERN


class TestSemverPattern:
    """Tests for SEMVER_PATTERN regex."""

    def test_valid_semver(self):
        assert SEMVER_PATTERN.match("1.2.3")
        assert SEMVER_PATTERN.match("0.0.0")
        assert SEMVER_PATTERN.match("10.20.30")
        assert SEMVER_PATTERN.match("123.456.789")

    def test_invalid_semver(self):
        assert not SEMVER_PATTERN.match("v1.2.3")
        assert not SEMVER_PATTERN.match("1.2")
        assert not SEMVER_PATTERN.match("1.2.3.4")
        assert not SEMVER_PATTERN.match("1.2.3-beta")
        assert not SEMVER_PATTERN.match("1.2.3+build")
        assert not SEMVER_PATTERN.match("latest")
        assert not SEMVER_PATTERN.match("")


class TestBumpPatchVersion:
    """Tests for bump_patch_version function."""

    def test_bump_simple_version(self):
        assert bump_patch_version("1.2.3") == "1.2.4"

    def test_bump_zero_patch(self):
        assert bump_patch_version("1.0.0") == "1.0.1"

    def test_bump_high_patch(self):
        assert bump_patch_version("1.2.99") == "1.2.100"

    def test_bump_preserves_major_minor(self):
        assert bump_patch_version("5.10.15") == "5.10.16"


class TestUpdateChart:
    """Tests for update_chart function."""

    @pytest.fixture
    def sample_chart_yaml(self):
        """Create a sample Chart.yaml content."""
        return """\
apiVersion: v2
description: Test chart
name: test-chart
appVersion: 1.0.0
version: 0.1.0
maintainers:
  - name: test
dependencies:
  - name: runtime-api
    repository: oci://ghcr.io/all-hands-ai/helm-charts
    version: 0.1.10
    condition: runtime-api.enabled
  - name: other-dep
    version: 1.0.0
"""

    @pytest.fixture
    def temp_chart_file(self, sample_chart_yaml):
        """Create a temporary Chart.yaml file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(sample_chart_yaml)
            f.flush()
            yield Path(f.name)
        Path(f.name).unlink(missing_ok=True)

    def test_update_app_version(self, temp_chart_file):
        """Test that appVersion is updated correctly."""
        update_chart(temp_chart_file, "2.0.0", None)

        yaml = YAML()
        chart_data = yaml.load(temp_chart_file)
        assert chart_data["appVersion"] == "2.0.0"

    def test_bump_chart_version(self, temp_chart_file):
        """Test that version is bumped correctly."""
        update_chart(temp_chart_file, "2.0.0", None)

        yaml = YAML()
        chart_data = yaml.load(temp_chart_file)
        assert chart_data["version"] == "0.1.1"

    def test_update_runtime_api_version(self, temp_chart_file):
        """Test that runtime-api dependency version is updated."""
        update_chart(temp_chart_file, "2.0.0", "0.2.0")

        yaml = YAML()
        chart_data = yaml.load(temp_chart_file)
        runtime_api_dep = next(
            d for d in chart_data["dependencies"] if d["name"] == "runtime-api"
        )
        assert runtime_api_dep["version"] == "0.2.0"

    def test_runtime_api_unchanged_when_same_version(self, temp_chart_file, capsys):
        """Test that runtime-api is not updated when version is the same."""
        update_chart(temp_chart_file, "2.0.0", "0.1.10")

        yaml = YAML()
        chart_data = yaml.load(temp_chart_file)
        runtime_api_dep = next(
            d for d in chart_data["dependencies"] if d["name"] == "runtime-api"
        )
        assert runtime_api_dep["version"] == "0.1.10"

        captured = capsys.readouterr()
        assert "runtime-api version unchanged" in captured.out

    def test_other_dependencies_unchanged(self, temp_chart_file):
        """Test that other dependencies are not affected."""
        update_chart(temp_chart_file, "2.0.0", "0.2.0")

        yaml = YAML()
        chart_data = yaml.load(temp_chart_file)
        other_dep = next(
            d for d in chart_data["dependencies"] if d["name"] == "other-dep"
        )
        assert other_dep["version"] == "1.0.0"

    def test_preserves_yaml_structure(self, temp_chart_file):
        """Test that YAML structure is preserved."""
        update_chart(temp_chart_file, "2.0.0", "0.2.0")

        yaml = YAML()
        chart_data = yaml.load(temp_chart_file)

        # Verify structure is preserved
        assert chart_data["apiVersion"] == "v2"
        assert chart_data["description"] == "Test chart"
        assert chart_data["name"] == "test-chart"
        assert len(chart_data["maintainers"]) == 1
        assert len(chart_data["dependencies"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
