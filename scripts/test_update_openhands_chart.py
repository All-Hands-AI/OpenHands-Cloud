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
update_runtime_api_chart = module.update_runtime_api_chart
update_runtime_api_values = module.update_runtime_api_values
get_short_sha = module.get_short_sha
format_sha_tag = module.format_sha_tag
get_branch_name = module.get_branch_name
has_uncommitted_changes = module.has_uncommitted_changes
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


class TestFormatShaTag:
    """Tests for format_sha_tag function."""

    def test_formats_with_sha_prefix(self):
        assert format_sha_tag("abcdefghijklmnop") == "sha-abcdefg"

    def test_full_sha_to_tag(self):
        sha = "6ccd42bb2975866f1abc21e635c01d2afbdd1acf"
        assert format_sha_tag(sha) == "sha-6ccd42b"

    def test_numeric_sha_to_tag(self):
        assert format_sha_tag("1234567890abcdef") == "sha-1234567"

    def test_exactly_seven_chars(self):
        assert format_sha_tag("abcdefg") == "sha-abcdefg"

    def test_real_world_sha(self):
        # Test with actual SHA from deploy workflow
        sha = "743f6256a690efc388af6e960ad8009f5952e721"
        assert format_sha_tag(sha) == "sha-743f625"


class TestGetBranchName:
    """Tests for get_branch_name function."""

    def test_branch_name_format(self):
        assert get_branch_name("1.2.3") == "update-openhands-chart-1.2.3"

    def test_branch_name_with_different_version(self):
        assert get_branch_name("2.0.0") == "update-openhands-chart-2.0.0"

    def test_branch_name_real_version(self):
        assert get_branch_name("1.2.1") == "update-openhands-chart-1.2.1"


class TestHasUncommittedChanges:
    """Tests for has_uncommitted_changes function."""

    def test_returns_bool(self):
        # Function should return a boolean
        result = has_uncommitted_changes()
        assert isinstance(result, bool)


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


class TestDryRun:
    """Tests for dry-run functionality."""

    @pytest.fixture
    def sample_chart_yaml(self):
        """Create a sample Chart.yaml content."""
        return """\
apiVersion: v2
description: Test chart
name: test-chart
appVersion: 1.0.0
version: 0.1.0
dependencies:
  - name: runtime-api
    version: 0.1.10
"""

    @pytest.fixture
    def sample_values_yaml(self):
        """Create a sample values.yaml content."""
        return """\
image:
  repository: ghcr.io/openhands/enterprise-server
  tag: sha-oldsha1

runtime:
  image:
    repository: ghcr.io/openhands/runtime
    tag: oldsha1234567890-nikolaik

runtime-api:
  enabled: true
  image:
    tag: sha-oldsha2
  warmRuntimes:
    configs:
      - name: default
        image: "ghcr.io/openhands/runtime:oldsha1234567890-nikolaik"
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

    def test_update_chart_dry_run_no_file_changes(self, temp_chart_file):
        """Test that dry-run doesn't modify Chart.yaml."""
        original_content = temp_chart_file.read_text()

        update_chart(temp_chart_file, "2.0.0", "0.2.0", dry_run=True)

        assert temp_chart_file.read_text() == original_content

    def test_update_chart_dry_run_prints_changes(self, temp_chart_file, capsys):
        """Test that dry-run still prints what would be changed."""
        update_chart(temp_chart_file, "2.0.0", "0.2.0", dry_run=True)

        captured = capsys.readouterr()
        assert "Updated appVersion: 1.0.0 -> 2.0.0" in captured.out
        assert "Updated version: 0.1.0 -> 0.1.1" in captured.out
        assert "Updated runtime-api version: 0.1.10 -> 0.2.0" in captured.out

    def test_update_values_dry_run_no_file_changes(self, temp_values_file):
        """Test that dry-run doesn't modify values.yaml."""
        original_content = temp_values_file.read_text()

        update_values(
            temp_values_file,
            openhands_sha="newsha1234567890",
            runtime_api_sha="newapi1234567890",
            runtime_image_tag="newruntime123-nikolaik",
            dry_run=True,
        )

        assert temp_values_file.read_text() == original_content

    def test_update_values_dry_run_prints_changes(self, temp_values_file, capsys):
        """Test that dry-run still prints what would be changed."""
        update_values(
            temp_values_file,
            openhands_sha="newsha1234567890",
            runtime_api_sha="newapi1234567890",
            runtime_image_tag="newruntime123-nikolaik",
            dry_run=True,
        )

        captured = capsys.readouterr()
        assert "Updated enterprise-server image tag:" in captured.out
        assert "Updated runtime-api image tag:" in captured.out
        assert "Updated runtime image tag:" in captured.out
        assert "Updated warmRuntimes image tag:" in captured.out

    def test_update_chart_without_dry_run_modifies_file(self, temp_chart_file):
        """Test that without dry-run, Chart.yaml is modified."""
        original_content = temp_chart_file.read_text()

        update_chart(temp_chart_file, "2.0.0", "0.2.0", dry_run=False)

        assert temp_chart_file.read_text() != original_content

    def test_update_values_without_dry_run_modifies_file(self, temp_values_file):
        """Test that without dry-run, values.yaml is modified."""
        original_content = temp_values_file.read_text()

        update_values(
            temp_values_file,
            openhands_sha="newsha1234567890",
            runtime_api_sha="newapi1234567890",
            runtime_image_tag="newruntime123-nikolaik",
            dry_run=False,
        )

        assert temp_values_file.read_text() != original_content


class TestUpdateRuntimeApiChart:
    """Tests for update_runtime_api_chart function."""

    @pytest.fixture
    def sample_runtime_api_chart_yaml(self):
        """Create a sample runtime-api Chart.yaml content."""
        return """\
apiVersion: v2
name: runtime-api
description: A Helm chart for the Flask application
version: 0.1.20 # Change this to trigger a new helm chart version being published
appVersion: "1.0.0"
dependencies:
  - name: postgresql
    version: 15.x.x
    repository: https://charts.bitnami.com/bitnami
    condition: postgresql.enabled
"""

    @pytest.fixture
    def temp_runtime_api_chart_file(self, sample_runtime_api_chart_yaml):
        """Create a temporary runtime-api Chart.yaml file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(sample_runtime_api_chart_yaml)
            f.flush()
            yield Path(f.name)
        Path(f.name).unlink(missing_ok=True)

    def test_bump_runtime_api_version(self, temp_runtime_api_chart_file):
        """Test that runtime-api chart version is bumped correctly."""
        new_version = update_runtime_api_chart(temp_runtime_api_chart_file)

        yaml = YAML()
        chart_data = yaml.load(temp_runtime_api_chart_file)
        assert chart_data["version"] == "0.1.21"
        assert new_version == "0.1.21"

    def test_preserves_other_fields(self, temp_runtime_api_chart_file):
        """Test that other fields are preserved."""
        update_runtime_api_chart(temp_runtime_api_chart_file)

        yaml = YAML()
        chart_data = yaml.load(temp_runtime_api_chart_file)
        assert chart_data["apiVersion"] == "v2"
        assert chart_data["name"] == "runtime-api"
        assert chart_data["appVersion"] == "1.0.0"
        assert len(chart_data["dependencies"]) == 1

    def test_dry_run_no_file_changes(self, temp_runtime_api_chart_file):
        """Test that dry-run doesn't modify the file."""
        original_content = temp_runtime_api_chart_file.read_text()

        update_runtime_api_chart(temp_runtime_api_chart_file, dry_run=True)

        assert temp_runtime_api_chart_file.read_text() == original_content

    def test_dry_run_returns_new_version(self, temp_runtime_api_chart_file):
        """Test that dry-run still returns the new version."""
        new_version = update_runtime_api_chart(temp_runtime_api_chart_file, dry_run=True)
        assert new_version == "0.1.21"


class TestUpdateRuntimeApiValues:
    """Tests for update_runtime_api_values function."""

    @pytest.fixture
    def sample_runtime_api_values_yaml(self):
        """Create a sample runtime-api values.yaml content."""
        return """\
nameOverride: ""
fullnameOverride: ""

replicaCount: 1

image:
  repository: ghcr.io/openhands/runtime-api
  tag: sha-0c907c9
  pullPolicy: Always

warmRuntimes:
  enabled: false
  configMapName: warm-runtimes-config
  count: 0
  configs:
    - name: default
      image: "ghcr.io/openhands/runtime:4ea3e4b1fd850ae07e7b972feb36fca6e789d7eb-nikolaik"
      working_dir: "/openhands/code/"
      environment: {}
"""

    @pytest.fixture
    def temp_runtime_api_values_file(self, sample_runtime_api_values_yaml):
        """Create a temporary runtime-api values.yaml file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(sample_runtime_api_values_yaml)
            f.flush()
            yield Path(f.name)
        Path(f.name).unlink(missing_ok=True)

    def test_update_warm_runtimes_image(self, temp_runtime_api_values_file):
        """Test that warmRuntimes image tag is updated correctly."""
        update_runtime_api_values(
            temp_runtime_api_values_file,
            runtime_image_tag="9d0a19cf8f9b45af4d42eb0534cfb9fab18342f2-nikolaik",
        )

        content = temp_runtime_api_values_file.read_text()
        assert 'image: "ghcr.io/openhands/runtime:9d0a19cf8f9b45af4d42eb0534cfb9fab18342f2-nikolaik"' in content

    def test_unchanged_when_same_value(self, temp_runtime_api_values_file, capsys):
        """Test message when value is already up to date."""
        # First update
        update_runtime_api_values(
            temp_runtime_api_values_file,
            runtime_image_tag="newruntime123-nikolaik",
        )

        # Second update with same value
        update_runtime_api_values(
            temp_runtime_api_values_file,
            runtime_image_tag="newruntime123-nikolaik",
        )

        captured = capsys.readouterr()
        assert "runtime-api warmRuntimes image tag unchanged" in captured.out

    def test_preserves_other_content(self, temp_runtime_api_values_file):
        """Test that other content is preserved."""
        update_runtime_api_values(
            temp_runtime_api_values_file,
            runtime_image_tag="newruntime123-nikolaik",
        )

        content = temp_runtime_api_values_file.read_text()
        assert "replicaCount: 1" in content
        assert "tag: sha-0c907c9" in content
        assert 'working_dir: "/openhands/code/"' in content

    def test_dry_run_no_file_changes(self, temp_runtime_api_values_file):
        """Test that dry-run doesn't modify the file."""
        original_content = temp_runtime_api_values_file.read_text()

        update_runtime_api_values(
            temp_runtime_api_values_file,
            runtime_image_tag="newruntime123-nikolaik",
            dry_run=True,
        )

        assert temp_runtime_api_values_file.read_text() == original_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
