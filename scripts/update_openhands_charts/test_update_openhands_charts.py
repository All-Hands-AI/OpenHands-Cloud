#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyGithub", "ruamel.yaml", "requests", "pytest"]
# ///
"""Unit tests for update_openhands_charts.py."""

import importlib.util
import tempfile
from pathlib import Path

import pytest
from ruamel.yaml import YAML

# Load the script as a module
spec = importlib.util.spec_from_file_location(
    "update_openhands_charts",
    Path(__file__).parent / "update_openhands_charts.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

bump_patch_version = module.bump_patch_version
update_openhands_chart = module.update_openhands_chart
update_openhands_values = module.update_openhands_values
update_runtime_api_chart = module.update_runtime_api_chart
update_runtime_api_values = module.update_runtime_api_values
get_short_sha = module.get_short_sha
format_sha_tag = module.format_sha_tag
DeployConfig = module.DeployConfig
SEMVER_PATTERN = module.SEMVER_PATTERN
CLOUD_SEMVER_PATTERN = module.CLOUD_SEMVER_PATTERN
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


class TestCloudSemverPattern:
    """Tests for CLOUD_SEMVER_PATTERN regex."""

    def test_valid_cloud_semver(self):
        assert CLOUD_SEMVER_PATTERN.match("cloud-1.2.3")
        assert CLOUD_SEMVER_PATTERN.match("cloud-0.0.0")
        assert CLOUD_SEMVER_PATTERN.match("cloud-10.20.30")
        assert CLOUD_SEMVER_PATTERN.match("cloud-1.1.0")

    def test_extracts_version_group(self):
        match = CLOUD_SEMVER_PATTERN.match("cloud-1.1.0")
        assert match.group(1) == "1.1.0"

    def test_invalid_cloud_semver(self):
        assert not CLOUD_SEMVER_PATTERN.match("1.2.3")
        assert not CLOUD_SEMVER_PATTERN.match("v1.2.3")
        assert not CLOUD_SEMVER_PATTERN.match("cloud-1.2")
        assert not CLOUD_SEMVER_PATTERN.match("cloud-1.2.3.4")
        assert not CLOUD_SEMVER_PATTERN.match("Cloud-1.2.3")
        assert not CLOUD_SEMVER_PATTERN.match("cloud1.2.3")
        assert not CLOUD_SEMVER_PATTERN.match("")


class TestExtractVersionFromCloudTag:
    """Tests for extract_version_from_cloud_tag function."""

    def test_extracts_version_from_cloud_tag(self):
        """Test that version is extracted from cloud-X.Y.Z format."""
        from update_openhands_charts import extract_version_from_cloud_tag

        assert extract_version_from_cloud_tag("cloud-1.1.0") == "1.1.0"
        assert extract_version_from_cloud_tag("cloud-2.0.0") == "2.0.0"
        assert extract_version_from_cloud_tag("cloud-10.20.30") == "10.20.30"

    def test_returns_none_for_invalid_format(self):
        """Test that None is returned for invalid formats."""
        from update_openhands_charts import extract_version_from_cloud_tag

        assert extract_version_from_cloud_tag("1.1.0") is None
        assert extract_version_from_cloud_tag("v1.1.0") is None
        assert extract_version_from_cloud_tag("cloud-1.1") is None
        assert extract_version_from_cloud_tag("") is None


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


class TestGetCurrentAppVersion:
    """Tests for get_current_app_version function."""

    @pytest.fixture
    def sample_chart_yaml(self):
        """Create a sample Chart.yaml content."""
        return """\
apiVersion: v2
appVersion: cloud-1.1.0
version: 0.3.11
name: openhands
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

    def test_returns_app_version(self, temp_chart_file):
        """Test that function returns the appVersion from chart."""
        from update_openhands_charts import get_current_app_version

        result = get_current_app_version(temp_chart_file)
        assert result == "cloud-1.1.0"

    def test_returns_none_for_missing_file(self):
        """Test that function returns None for missing file."""
        from update_openhands_charts import get_current_app_version

        result = get_current_app_version(Path("/nonexistent/Chart.yaml"))
        assert result is None


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
        update_openhands_chart(temp_chart_file, "2.0.0", None)

        yaml = YAML()
        chart_data = yaml.load(temp_chart_file)
        assert chart_data["appVersion"] == "2.0.0"

    def test_bump_chart_version(self, temp_chart_file):
        """Test that version is bumped correctly."""
        update_openhands_chart(temp_chart_file, "2.0.0", None)

        yaml = YAML()
        chart_data = yaml.load(temp_chart_file)
        assert chart_data["version"] == "0.1.1"

    def test_update_runtime_api_version(self, temp_chart_file):
        """Test that runtime-api dependency version is updated."""
        update_openhands_chart(temp_chart_file, "2.0.0", "0.2.0")

        yaml = YAML()
        chart_data = yaml.load(temp_chart_file)
        runtime_api_dep = next(
            d for d in chart_data["dependencies"] if d["name"] == "runtime-api"
        )
        assert runtime_api_dep["version"] == "0.2.0"

    def test_runtime_api_unchanged_when_same_version(self, temp_chart_file, capsys):
        """Test that runtime-api is not updated when version is the same."""
        update_openhands_chart(temp_chart_file, "2.0.0", "0.1.10")

        yaml = YAML()
        chart_data = yaml.load(temp_chart_file)
        runtime_api_dep = next(
            d for d in chart_data["dependencies"] if d["name"] == "runtime-api"
        )
        assert runtime_api_dep["version"] == "0.1.10"

        captured = capsys.readouterr()
        assert "runtime-api version unchanged" in captured.out

    def test_app_version_unchanged_when_same_version(self, temp_chart_file, capsys):
        """Test that appVersion shows unchanged when same."""
        update_openhands_chart(temp_chart_file, "1.0.0", "0.2.0")

        captured = capsys.readouterr()
        assert "appVersion unchanged: 1.0.0" in captured.out

    def test_other_dependencies_unchanged(self, temp_chart_file):
        """Test that other dependencies are not affected."""
        update_openhands_chart(temp_chart_file, "2.0.0", "0.2.0")

        yaml = YAML()
        chart_data = yaml.load(temp_chart_file)
        other_dep = next(
            d for d in chart_data["dependencies"] if d["name"] == "other-dep"
        )
        assert other_dep["version"] == "1.0.0"

    def test_preserves_yaml_structure(self, temp_chart_file):
        """Test that YAML structure is preserved."""
        update_openhands_chart(temp_chart_file, "2.0.0", "0.2.0")

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
        """Test that DeployConfig can be created with runtime_api_sha field."""
        config = DeployConfig(
            runtime_api_sha="def5678901234",
        )
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
  tag: cloud-1.0.0

runtime:
  image:
    repository: ghcr.io/openhands/runtime
    tag: cloud-1.0.0-nikolaik
  runAsRoot: true

runtime-api:
  enabled: true
  replicaCount: 1
  warmRuntimes:
    enabled: true
    count: 1
    configs:
      - name: default
        image: "ghcr.io/openhands/runtime:cloud-1.0.0-nikolaik"
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

    def test_update_enterprise_server_tag_uses_cloud_version(self, temp_values_file):
        """Test that enterprise-server image tag uses cloud version format."""
        update_openhands_values(
            temp_values_file,
            openhands_version="cloud-1.1.0",
        )

        content = temp_values_file.read_text()
        assert "tag: cloud-1.1.0" in content

    def test_update_runtime_tag_uses_cloud_version(self, temp_values_file):
        """Test that runtime image tag uses cloud version format."""
        update_openhands_values(
            temp_values_file,
            openhands_version="cloud-1.1.0",
        )

        content = temp_values_file.read_text()
        assert "tag: cloud-1.1.0-nikolaik" in content

    def test_update_warm_runtimes_tag_uses_cloud_version(self, temp_values_file):
        """Test that warmRuntimes image tag uses cloud version format."""
        update_openhands_values(
            temp_values_file,
            openhands_version="cloud-1.1.0",
        )

        content = temp_values_file.read_text()
        assert 'image: "ghcr.io/openhands/runtime:cloud-1.1.0-nikolaik"' in content

    def test_unchanged_when_same_values(self, temp_values_file, capsys):
        """Test messages when values are already up to date."""
        # First update to set the values
        update_openhands_values(
            temp_values_file,
            openhands_version="cloud-1.0.0",
        )

        # Second update with same values
        update_openhands_values(
            temp_values_file,
            openhands_version="cloud-1.0.0",
        )

        captured = capsys.readouterr()
        assert "enterprise-server image tag unchanged" in captured.out
        assert "runtime image tag unchanged" in captured.out
        assert "warmRuntimes image tag unchanged" in captured.out

    def test_preserves_other_content(self, temp_values_file):
        """Test that other content in values.yaml is preserved."""
        update_openhands_values(
            temp_values_file,
            openhands_version="cloud-1.1.0",
        )

        content = temp_values_file.read_text()
        assert "allowedUsers: null" in content
        assert "runAsRoot: true" in content
        assert "replicaCount: 1" in content
        assert 'working_dir: "/openhands/code/"' in content

    def test_returns_true_when_changes_made(self, temp_values_file):
        """Test that function returns True when changes are made."""
        result = update_openhands_values(
            temp_values_file,
            openhands_version="cloud-1.1.0",
        )

        assert result is True

    def test_returns_false_when_no_changes(self, temp_values_file):
        """Test that function returns False when no changes are needed."""
        # First update
        update_openhands_values(
            temp_values_file,
            openhands_version="cloud-1.1.0",
        )

        # Second update with same values
        result = update_openhands_values(
            temp_values_file,
            openhands_version="cloud-1.1.0",
        )

        assert result is False


class TestUpdateOpenhandsChartConditional:
    """Tests for conditional openhands chart version update."""

    @pytest.fixture
    def sample_chart_yaml(self):
        """Create a sample openhands Chart.yaml content."""
        return """\
apiVersion: v2
appVersion: cloud-1.0.0
version: 0.3.11
name: openhands
dependencies:
  - name: runtime-api
    version: 0.2.6
"""

    @pytest.fixture
    def temp_chart_file(self, sample_chart_yaml):
        """Create a temporary openhands Chart.yaml file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(sample_chart_yaml)
            f.flush()
            yield Path(f.name)
        Path(f.name).unlink(missing_ok=True)

    def test_no_version_bump_when_no_changes(self, temp_chart_file, capsys):
        """Test that chart version is not bumped when has_changes is False."""
        from update_openhands_charts import update_openhands_chart

        update_openhands_chart(
            temp_chart_file,
            new_app_version="cloud-1.0.0",
            new_runtime_api_version="0.2.6",
            has_changes=False,
        )

        yaml = YAML()
        chart_data = yaml.load(temp_chart_file)
        assert chart_data["version"] == "0.3.11"  # Unchanged
        assert chart_data["appVersion"] == "cloud-1.0.0"  # Unchanged

        captured = capsys.readouterr()
        assert "openhands chart version unchanged" in captured.out

    def test_version_bump_when_has_changes(self, temp_chart_file, capsys):
        """Test that chart version is bumped when has_changes is True."""
        from update_openhands_charts import update_openhands_chart

        update_openhands_chart(
            temp_chart_file,
            new_app_version="cloud-1.1.0",
            new_runtime_api_version="0.2.7",
            has_changes=True,
        )

        yaml = YAML()
        chart_data = yaml.load(temp_chart_file)
        assert chart_data["version"] == "0.3.12"  # Bumped
        assert chart_data["appVersion"] == "cloud-1.1.0"  # Updated

        captured = capsys.readouterr()
        assert "Updated appVersion: cloud-1.0.0 -> cloud-1.1.0" in captured.out
        assert "Updated version: 0.3.11 -> 0.3.12" in captured.out


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
  tag: cloud-1.0.0

runtime:
  image:
    repository: ghcr.io/openhands/runtime
    tag: cloud-1.0.0-nikolaik

runtime-api:
  enabled: true
  warmRuntimes:
    configs:
      - name: default
        image: "ghcr.io/openhands/runtime:cloud-1.0.0-nikolaik"
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

        update_openhands_chart(temp_chart_file, "2.0.0", "0.2.0", dry_run=True)

        assert temp_chart_file.read_text() == original_content

    def test_update_chart_dry_run_prints_changes(self, temp_chart_file, capsys):
        """Test that dry-run still prints what would be changed."""
        update_openhands_chart(temp_chart_file, "2.0.0", "0.2.0", dry_run=True)

        captured = capsys.readouterr()
        assert "Updated appVersion: 1.0.0 -> 2.0.0" in captured.out
        assert "Updated version: 0.1.0 -> 0.1.1" in captured.out
        assert "Updated runtime-api version: 0.1.10 -> 0.2.0" in captured.out

    def test_update_values_dry_run_no_file_changes(self, temp_values_file):
        """Test that dry-run doesn't modify values.yaml."""
        original_content = temp_values_file.read_text()

        update_openhands_values(
            temp_values_file,
            openhands_version="cloud-1.1.0",
            dry_run=True,
        )

        assert temp_values_file.read_text() == original_content

    def test_update_values_dry_run_prints_changes(self, temp_values_file, capsys):
        """Test that dry-run still prints what would be changed."""
        update_openhands_values(
            temp_values_file,
            openhands_version="cloud-1.1.0",
            dry_run=True,
        )

        captured = capsys.readouterr()
        assert "Updated enterprise-server image tag:" in captured.out
        assert "Updated runtime image tag:" in captured.out
        assert "Updated warmRuntimes image tag:" in captured.out

    def test_update_chart_without_dry_run_modifies_file(self, temp_chart_file):
        """Test that without dry-run, Chart.yaml is modified."""
        original_content = temp_chart_file.read_text()

        update_openhands_chart(temp_chart_file, "2.0.0", "0.2.0", dry_run=False)

        assert temp_chart_file.read_text() != original_content

    def test_update_values_without_dry_run_modifies_file(self, temp_values_file):
        """Test that without dry-run, values.yaml is modified."""
        original_content = temp_values_file.read_text()

        update_openhands_values(
            temp_values_file,
            openhands_version="cloud-1.1.0",
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
      image: "ghcr.io/openhands/runtime:cloud-1.0.0-nikolaik"
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

    def test_update_image_tag(self, temp_runtime_api_values_file):
        """Test that runtime-api image tag is updated correctly."""
        update_runtime_api_values(
            temp_runtime_api_values_file,
            runtime_api_sha="abc1234567890def",
            openhands_version="cloud-1.1.0",
        )

        content = temp_runtime_api_values_file.read_text()
        assert "tag: sha-abc1234" in content

    def test_update_warm_runtimes_image_uses_cloud_version(self, temp_runtime_api_values_file):
        """Test that warmRuntimes image tag uses cloud version format, not full SHA."""
        update_runtime_api_values(
            temp_runtime_api_values_file,
            runtime_api_sha="abc1234567890def",
            openhands_version="cloud-1.1.0",
        )

        content = temp_runtime_api_values_file.read_text()
        # Should use cloud version format for warmRuntimes
        assert 'image: "ghcr.io/openhands/runtime:cloud-1.1.0-nikolaik"' in content

    def test_unchanged_when_same_value(self, temp_runtime_api_values_file, capsys):
        """Test message when value is already up to date."""
        # First update
        update_runtime_api_values(
            temp_runtime_api_values_file,
            runtime_api_sha="abc1234567890def",
            openhands_version="cloud-1.1.0",
        )

        # Second update with same value
        update_runtime_api_values(
            temp_runtime_api_values_file,
            runtime_api_sha="abc1234567890def",
            openhands_version="cloud-1.1.0",
        )

        captured = capsys.readouterr()
        assert "runtime-api image tag unchanged" in captured.out
        assert "runtime-api warmRuntimes image tag unchanged" in captured.out

    def test_preserves_other_content(self, temp_runtime_api_values_file):
        """Test that other content is preserved."""
        update_runtime_api_values(
            temp_runtime_api_values_file,
            runtime_api_sha="abc1234567890def",
            openhands_version="cloud-1.1.0",
        )

        content = temp_runtime_api_values_file.read_text()
        assert "replicaCount: 1" in content
        assert 'working_dir: "/openhands/code/"' in content

    def test_dry_run_no_file_changes(self, temp_runtime_api_values_file):
        """Test that dry-run doesn't modify the file."""
        original_content = temp_runtime_api_values_file.read_text()

        update_runtime_api_values(
            temp_runtime_api_values_file,
            runtime_api_sha="abc1234567890def",
            openhands_version="cloud-1.1.0",
            dry_run=True,
        )

        assert temp_runtime_api_values_file.read_text() == original_content

    def test_returns_true_when_changes_made(self, temp_runtime_api_values_file):
        """Test that function returns True when changes are made."""
        result = update_runtime_api_values(
            temp_runtime_api_values_file,
            runtime_api_sha="abc1234567890def",
            openhands_version="cloud-1.1.0",
        )

        assert result is True

    def test_returns_false_when_no_changes(self, temp_runtime_api_values_file):
        """Test that function returns False when no changes are needed."""
        # First update
        update_runtime_api_values(
            temp_runtime_api_values_file,
            runtime_api_sha="abc1234567890def",
            openhands_version="cloud-1.1.0",
        )

        # Second update with same values
        result = update_runtime_api_values(
            temp_runtime_api_values_file,
            runtime_api_sha="abc1234567890def",
            openhands_version="cloud-1.1.0",
        )

        assert result is False


class TestUpdateRuntimeApiChartConditional:
    """Tests for conditional runtime-api chart version update."""

    @pytest.fixture
    def sample_runtime_api_chart_yaml(self):
        """Create a sample runtime-api Chart.yaml content."""
        return """\
apiVersion: v2
appVersion: 0.1.0
version: 0.2.6
name: runtime-api
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

    def test_no_version_bump_when_no_changes(self, temp_runtime_api_chart_file, capsys):
        """Test that chart version is not bumped when has_changes is False."""
        from update_openhands_charts import update_runtime_api_chart

        result = update_runtime_api_chart(temp_runtime_api_chart_file, has_changes=False)

        assert result == "0.2.6"  # Version unchanged
        captured = capsys.readouterr()
        assert "runtime-api chart version unchanged" in captured.out

    def test_version_bump_when_has_changes(self, temp_runtime_api_chart_file, capsys):
        """Test that chart version is bumped when has_changes is True."""
        from update_openhands_charts import update_runtime_api_chart

        result = update_runtime_api_chart(temp_runtime_api_chart_file, has_changes=True)

        assert result == "0.2.7"  # Version bumped
        captured = capsys.readouterr()
        assert "Updated runtime-api chart version: 0.2.6 -> 0.2.7" in captured.out


class TestMainOutputMessages:
    """Tests for main() output message formatting."""

    def test_latest_cloud_tag_message_format(self, capsys, monkeypatch):
        """Test that the latest cloud tag message uses correct format."""
        from update_openhands_charts import main

        # Mock get_latest_cloud_tag to return a known value
        monkeypatch.setattr(
            "update_openhands_charts.get_latest_cloud_tag",
            lambda token, repo: "cloud-1.20.0"
        )
        # Mock cloud_tag_exists
        monkeypatch.setattr(
            "update_openhands_charts.cloud_tag_exists",
            lambda token, repo, tag: True
        )
        # Mock get_current_app_version to return matching version (early exit)
        monkeypatch.setattr(
            "update_openhands_charts.get_current_app_version",
            lambda path: "cloud-1.20.0"
        )

        main(dry_run=True)

        captured = capsys.readouterr()
        assert "OpenHands cloud tag: cloud-1.20.0" in captured.out


class TestGetLatestCloudTag:
    """Tests for get_latest_cloud_tag function."""

    def test_returns_cloud_tag_format(self):
        """Test that function returns a cloud-X.Y.Z formatted tag."""
        # This is an integration test that requires GITHUB_TOKEN
        import os
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            pytest.skip("GITHUB_TOKEN not set")

        from update_openhands_charts import get_latest_cloud_tag
        result = get_latest_cloud_tag(token, "All-Hands-AI/OpenHands")

        assert result is not None
        assert CLOUD_SEMVER_PATTERN.match(result)

    def test_returns_none_for_invalid_repo(self):
        """Test that function returns None for invalid repository."""
        import os
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            pytest.skip("GITHUB_TOKEN not set")

        from update_openhands_charts import get_latest_cloud_tag
        result = get_latest_cloud_tag(token, "nonexistent/repo-that-does-not-exist")

        assert result is None

    def test_no_redirect_message_in_output(self, capsys):
        """Test that PyGithub redirect messages are suppressed."""
        import os
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            pytest.skip("GITHUB_TOKEN not set")

        from update_openhands_charts import get_latest_cloud_tag
        get_latest_cloud_tag(token, "All-Hands-AI/OpenHands")

        captured = capsys.readouterr()
        assert "redirect" not in captured.out.lower()
        assert "following" not in captured.out.lower()


class TestCloudTagExists:
    """Tests for cloud_tag_exists function."""

    def test_returns_true_for_existing_tag(self):
        """Test that function returns True for an existing cloud tag."""
        import os
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            pytest.skip("GITHUB_TOKEN not set")

        from update_openhands_charts import cloud_tag_exists

        # cloud-1.19.0 is a known existing tag
        result = cloud_tag_exists(token, "All-Hands-AI/OpenHands", "cloud-1.19.0")
        assert result is True

    def test_returns_false_for_nonexistent_tag(self):
        """Test that function returns False for a non-existent tag."""
        import os
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            pytest.skip("GITHUB_TOKEN not set")

        from update_openhands_charts import cloud_tag_exists

        result = cloud_tag_exists(token, "All-Hands-AI/OpenHands", "cloud-99.99.99")
        assert result is False

    def test_returns_false_for_invalid_repo(self):
        """Test that function returns False for an invalid repository."""
        import os
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            pytest.skip("GITHUB_TOKEN not set")

        from update_openhands_charts import cloud_tag_exists

        result = cloud_tag_exists(token, "nonexistent/repo", "cloud-1.0.0")
        assert result is False


class TestParseArgs:
    """Tests for parse_args function."""

    def test_cloud_tag_argument_exists(self):
        """Test that --cloud-tag argument is accepted."""
        from update_openhands_charts import parse_args
        import sys

        original_argv = sys.argv
        try:
            sys.argv = ["script", "--cloud-tag", "cloud-1.2.0"]
            args = parse_args()
            assert args.cloud_tag == "cloud-1.2.0"
        finally:
            sys.argv = original_argv

    def test_cloud_tag_default_is_none(self):
        """Test that --cloud-tag defaults to None."""
        from update_openhands_charts import parse_args
        import sys

        original_argv = sys.argv
        try:
            sys.argv = ["script"]
            args = parse_args()
            assert args.cloud_tag is None
        finally:
            sys.argv = original_argv

    def test_dry_run_argument(self):
        """Test that --dry-run argument works."""
        from update_openhands_charts import parse_args
        import sys

        original_argv = sys.argv
        try:
            sys.argv = ["script", "--dry-run"]
            args = parse_args()
            assert args.dry_run is True
        finally:
            sys.argv = original_argv


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
