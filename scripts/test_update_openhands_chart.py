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
update_values = module.update_values
get_short_sha = module.get_short_sha
DeployConfig = module.DeployConfig
SEMVER_PATTERN = module.SEMVER_PATTERN
SHORT_SHA_LENGTH = module.SHORT_SHA_LENGTH


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


class TestGetShortSha:
    """Tests for get_short_sha function."""

    def test_returns_first_seven_chars(self):
        assert get_short_sha("abcdefghijklmnop") == "abcdefg"

    def test_full_sha_length(self):
        sha = "6ccd42bb2975866f1abc21e635c01d2afbdd1acf"
        assert get_short_sha(sha) == "6ccd42b"

    def test_exactly_seven_chars(self):
        assert get_short_sha("1234567") == "1234567"

    def test_short_sha_length_constant(self):
        assert SHORT_SHA_LENGTH == 7

    def test_numeric_sha(self):
        assert get_short_sha("1234567890abcdef") == "1234567"


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


class TestDeployConfig:
    """Tests for DeployConfig dataclass."""

    def test_deploy_config_creation(self):
        """Test that DeployConfig can be created with all fields."""
        config = DeployConfig(
            openhands_sha="abc1234567890",
            openhands_runtime_image_tag="abc1234-nikolaik",
            runtime_api_sha="def5678901234",
        )
        assert config.openhands_sha == "abc1234567890"
        assert config.openhands_runtime_image_tag == "abc1234-nikolaik"
        assert config.runtime_api_sha == "def5678901234"


class TestUpdateValues:
    """Tests for update_values function."""

    @pytest.fixture
    def sample_values_yaml(self):
        """Create a sample values.yaml content."""
        return """\
allowedUsers: null

image:
  repository: ghcr.io/openhands/enterprise-server
  tag: sha-oldsha1

runtime:
  image:
    repository: ghcr.io/openhands/runtime
    tag: oldsha1234567890-nikolaik
  runAsRoot: true

runtime-api:
  enabled: true
  replicaCount: 1
  image:
    tag: sha-oldsha2
  warmRuntimes:
    enabled: true
    count: 1
    configs:
      - name: default
        image: "ghcr.io/openhands/runtime:oldsha1234567890-nikolaik"
        working_dir: "/openhands/code/"
"""

    @pytest.fixture
    def temp_values_file(self, sample_values_yaml):
        """Create a temporary values.yaml file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(sample_values_yaml)
            f.flush()
            yield Path(f.name)
        Path(f.name).unlink(missing_ok=True)

    def test_update_enterprise_server_tag(self, temp_values_file):
        """Test that enterprise-server image tag is updated correctly."""
        update_values(
            temp_values_file,
            openhands_sha="newsha1234567890",
            runtime_api_sha="newapi1234567890",
            runtime_image_tag="newruntime123-nikolaik",
        )

        content = temp_values_file.read_text()
        assert "tag: sha-newsha1" in content

    def test_update_runtime_api_tag(self, temp_values_file):
        """Test that runtime-api image tag is updated correctly."""
        update_values(
            temp_values_file,
            openhands_sha="newsha1234567890",
            runtime_api_sha="newapi1234567890",
            runtime_image_tag="newruntime123-nikolaik",
        )

        content = temp_values_file.read_text()
        assert "tag: sha-newapi1" in content

    def test_update_runtime_tag(self, temp_values_file):
        """Test that runtime image tag is updated correctly."""
        update_values(
            temp_values_file,
            openhands_sha="newsha1234567890",
            runtime_api_sha="newapi1234567890",
            runtime_image_tag="newruntime123-nikolaik",
        )

        content = temp_values_file.read_text()
        assert "tag: newruntime123-nikolaik" in content

    def test_update_warm_runtimes_tag(self, temp_values_file):
        """Test that warmRuntimes image tag is updated correctly."""
        update_values(
            temp_values_file,
            openhands_sha="newsha1234567890",
            runtime_api_sha="newapi1234567890",
            runtime_image_tag="newruntime123-nikolaik",
        )

        content = temp_values_file.read_text()
        assert 'image: "ghcr.io/openhands/runtime:newruntime123-nikolaik"' in content

    def test_unchanged_when_same_values(self, temp_values_file, capsys):
        """Test messages when values are already up to date."""
        # First update to set the values
        update_values(
            temp_values_file,
            openhands_sha="newsha1234567890",
            runtime_api_sha="newapi1234567890",
            runtime_image_tag="newruntime123-nikolaik",
        )

        # Second update with same values
        update_values(
            temp_values_file,
            openhands_sha="newsha1234567890",
            runtime_api_sha="newapi1234567890",
            runtime_image_tag="newruntime123-nikolaik",
        )

        captured = capsys.readouterr()
        assert "enterprise-server image tag unchanged" in captured.out
        assert "runtime-api image tag unchanged" in captured.out
        assert "runtime image tag unchanged" in captured.out
        assert "warmRuntimes image tag unchanged" in captured.out

    def test_short_sha_format(self, temp_values_file):
        """Test that SHA is correctly shortened to 7 characters."""
        update_values(
            temp_values_file,
            openhands_sha="abcdefghijklmnop",  # 16 chars
            runtime_api_sha="1234567890abcdef",  # 16 chars
            runtime_image_tag="full-tag-unchanged",
        )

        content = temp_values_file.read_text()
        # enterprise-server should have sha-abcdefg (7 chars)
        assert "tag: sha-abcdefg" in content
        # runtime-api should have sha-1234567 (7 chars)
        assert "tag: sha-1234567" in content

    def test_preserves_other_content(self, temp_values_file):
        """Test that other content in values.yaml is preserved."""
        update_values(
            temp_values_file,
            openhands_sha="newsha1234567890",
            runtime_api_sha="newapi1234567890",
            runtime_image_tag="newruntime123-nikolaik",
        )

        content = temp_values_file.read_text()
        assert "allowedUsers: null" in content
        assert "runAsRoot: true" in content
        assert "replicaCount: 1" in content
        assert 'working_dir: "/openhands/code/"' in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
