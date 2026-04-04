#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyGithub", "ruamel.yaml", "requests", "pytest"]
# ///
"""Unit tests for update_openhands_charts.py."""

import sys
from pathlib import Path

import pytest
from ruamel.yaml import YAML

# Add the script's directory to sys.path so we can import it directly
sys.path.insert(0, str(Path(__file__).parent))

import update_openhands_charts
from update_openhands_charts import (
    DeployConfig,
    SHORT_SHA_LENGTH,
    bump_patch_version,
    extract_version_from_cloud_tag,
    format_sha_tag,
    get_deploy_config,
    get_short_sha,
    update_openhands_chart,
    update_openhands_values,
    update_runtime_api_chart,
    update_runtime_api_values,
)


class TestExtractVersionFromCloudTag:
    """Tests for extract_version_from_cloud_tag function.

    These tests verify cloud tag parsing through the public interface rather
    than testing internal regex patterns directly. This approach is more
    maintainable as it tests behavior, not implementation.
    """

    def test_extracts_version_from_valid_cloud_tags(self):
        """Test that version is extracted from valid cloud-X.Y.Z formats."""
        # Standard versions
        assert extract_version_from_cloud_tag("cloud-1.1.0") == "1.1.0"
        assert extract_version_from_cloud_tag("cloud-2.0.0") == "2.0.0"
        assert extract_version_from_cloud_tag("cloud-0.0.0") == "0.0.0"

        # Multi-digit versions
        assert extract_version_from_cloud_tag("cloud-10.20.30") == "10.20.30"
        assert extract_version_from_cloud_tag("cloud-123.456.789") == "123.456.789"

    def test_returns_none_for_invalid_cloud_tag_formats(self):
        """Test that None is returned for strings that aren't cloud-X.Y.Z."""
        # Missing cloud- prefix
        assert extract_version_from_cloud_tag("1.1.0") is None
        assert extract_version_from_cloud_tag("v1.1.0") is None

        # Wrong prefix format
        assert extract_version_from_cloud_tag("Cloud-1.2.3") is None  # Wrong case
        assert extract_version_from_cloud_tag("cloud1.2.3") is None   # Missing hyphen

        # Invalid version parts
        assert extract_version_from_cloud_tag("cloud-1.2") is None      # Missing patch
        assert extract_version_from_cloud_tag("cloud-1.2.3.4") is None  # Extra part
        assert extract_version_from_cloud_tag("cloud-1.2.3-beta") is None  # Pre-release
        assert extract_version_from_cloud_tag("cloud-1.2.3+build") is None  # Build metadata

        # Edge cases
        assert extract_version_from_cloud_tag("") is None
        assert extract_version_from_cloud_tag("latest") is None
        assert extract_version_from_cloud_tag("cloud-") is None


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

    def test_returns_app_version(self, make_temp_yaml_file):
        """Test that function returns the appVersion from chart."""
        from update_openhands_charts import get_current_app_version

        chart_content = """\
apiVersion: v2
appVersion: cloud-1.1.0
version: 0.3.11
name: openhands
"""
        temp_chart_file = make_temp_yaml_file(chart_content)
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

    def test_raises_error_for_invalid_semver_format(self):
        """Test that invalid semver strings raise ValueError."""
        with pytest.raises(ValueError, match="Invalid semver format"):
            bump_patch_version("1.2")  # Missing patch

        with pytest.raises(ValueError, match="Invalid semver format"):
            bump_patch_version("1.2.3.4")  # Too many parts

        with pytest.raises(ValueError, match="Invalid semver format"):
            bump_patch_version("v1.2.3")  # Has prefix

        with pytest.raises(ValueError, match="Invalid semver format"):
            bump_patch_version("")  # Empty string

    def test_raises_error_for_non_numeric_parts(self):
        """Test that non-numeric version parts raise ValueError."""
        with pytest.raises(ValueError, match="Invalid semver format"):
            bump_patch_version("1.2.abc")  # Non-numeric patch

        with pytest.raises(ValueError, match="Invalid semver format"):
            bump_patch_version("a.b.c")  # All non-numeric


class TestUpdateChart:
    """Tests for update_chart function."""

    @pytest.fixture
    def temp_chart_file(self, make_temp_yaml_file, sample_openhands_chart_with_deps):
        """Create a temporary Chart.yaml file using shared fixtures."""
        return make_temp_yaml_file(sample_openhands_chart_with_deps)

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

    def test_runtime_api_unchanged_when_same_version(self, temp_chart_file):
        """Test that runtime-api is not updated when version is the same."""
        result = update_openhands_chart(temp_chart_file, "2.0.0", "0.1.10")

        yaml = YAML()
        chart_data = yaml.load(temp_chart_file)
        runtime_api_dep = next(
            d for d in chart_data["dependencies"] if d["name"] == "runtime-api"
        )
        assert runtime_api_dep["version"] == "0.1.10"

        # Verify it was recorded as unchanged
        assert ("runtime-api version", "0.1.10") in result.unchanged

    def test_app_version_unchanged_when_same_version(self, temp_chart_file):
        """Test that appVersion shows unchanged when same."""
        result = update_openhands_chart(temp_chart_file, "1.0.0", "0.2.0")

        assert ("appVersion", "1.0.0") in result.unchanged

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


class TestGetDeployConfig:
    """Tests for get_deploy_config function.

    Uses parameterized tests for comprehensive error path coverage.
    All error scenarios should return None and print an error message.
    """

    import base64
    from unittest.mock import MagicMock, Mock

    # Valid workflow YAML for success case tests
    VALID_WORKFLOW_YAML = """\
env:
  RUNTIME_API_SHA: abc123def456
  OTHER_VAR: value
"""

    @pytest.fixture
    def mock_successful_response(self):
        """Create a mock response with valid workflow content."""
        import base64
        from unittest.mock import Mock

        encoded_content = base64.b64encode(self.VALID_WORKFLOW_YAML.encode()).decode()
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"content": encoded_content}
        return mock_response

    def test_returns_deploy_config_on_success(self, monkeypatch, mock_successful_response):
        """Test that valid response returns DeployConfig with correct values."""
        from unittest.mock import Mock

        monkeypatch.setattr(
            "update_openhands_charts.requests.get",
            Mock(return_value=mock_successful_response)
        )

        result = get_deploy_config("fake-token", "owner/repo", ref="1.0.0")

        assert result is not None
        assert isinstance(result, DeployConfig)
        assert result.runtime_api_sha == "abc123def456"

    def test_constructs_correct_url_without_ref(self, monkeypatch, mock_successful_response):
        """Test that URL is constructed correctly without ref parameter."""
        from unittest.mock import Mock

        mock_get = Mock(return_value=mock_successful_response)
        monkeypatch.setattr("update_openhands_charts.requests.get", mock_get)

        get_deploy_config("fake-token", "owner/repo")

        called_url = mock_get.call_args[0][0]
        assert called_url == "https://api.github.com/repos/owner/repo/contents/.github/workflows/deploy.yaml"
        assert "?ref=" not in called_url

    def test_constructs_correct_url_with_ref(self, monkeypatch, mock_successful_response):
        """Test that URL includes ref parameter when provided."""
        from unittest.mock import Mock

        mock_get = Mock(return_value=mock_successful_response)
        monkeypatch.setattr("update_openhands_charts.requests.get", mock_get)

        get_deploy_config("fake-token", "owner/repo", ref="v1.2.3")

        called_url = mock_get.call_args[0][0]
        assert "?ref=v1.2.3" in called_url

    def test_includes_authorization_header(self, monkeypatch, mock_successful_response):
        """Test that Authorization header is included with token."""
        from unittest.mock import Mock

        mock_get = Mock(return_value=mock_successful_response)
        monkeypatch.setattr("update_openhands_charts.requests.get", mock_get)

        get_deploy_config("my-secret-token", "owner/repo")

        called_headers = mock_get.call_args[1]["headers"]
        assert called_headers["Authorization"] == "Bearer my-secret-token"

    def test_returns_empty_string_when_env_key_missing(self, monkeypatch):
        """Test that missing RUNTIME_API_SHA returns empty string (not None)."""
        import base64
        from unittest.mock import Mock

        # Workflow without RUNTIME_API_SHA
        workflow_yaml = "env:\n  OTHER_VAR: value\n"
        encoded = base64.b64encode(workflow_yaml.encode()).decode()

        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"content": encoded}

        monkeypatch.setattr(
            "update_openhands_charts.requests.get",
            Mock(return_value=mock_response)
        )

        result = get_deploy_config("token", "owner/repo")

        assert result is not None
        assert result.runtime_api_sha == ""

    def test_returns_empty_string_when_env_section_missing(self, monkeypatch):
        """Test that missing env section returns empty string."""
        import base64
        from unittest.mock import Mock

        # Workflow without env section
        workflow_yaml = "name: deploy\njobs: {}\n"
        encoded = base64.b64encode(workflow_yaml.encode()).decode()

        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"content": encoded}

        monkeypatch.setattr(
            "update_openhands_charts.requests.get",
            Mock(return_value=mock_response)
        )

        result = get_deploy_config("token", "owner/repo")

        assert result is not None
        assert result.runtime_api_sha == ""

    # =========================================================================
    # Parameterized error path tests
    # =========================================================================

    @pytest.mark.parametrize("error_name,setup_mock", [
        # Network-level errors
        (
            "connection_timeout",
            lambda Mock, _: Mock(side_effect=Exception("Connection timed out")),
        ),
        (
            "connection_refused",
            lambda Mock, _: Mock(side_effect=Exception("Connection refused")),
        ),
        (
            "dns_resolution_failed",
            lambda Mock, _: Mock(side_effect=Exception("Name resolution failed")),
        ),
        # HTTP error responses
        (
            "http_401_unauthorized",
            lambda Mock, _: _make_http_error_response(Mock, 401, "Unauthorized"),
        ),
        (
            "http_403_forbidden",
            lambda Mock, _: _make_http_error_response(Mock, 403, "Forbidden"),
        ),
        (
            "http_404_not_found",
            lambda Mock, _: _make_http_error_response(Mock, 404, "Not Found"),
        ),
        (
            "http_500_server_error",
            lambda Mock, _: _make_http_error_response(Mock, 500, "Internal Server Error"),
        ),
        (
            "http_502_bad_gateway",
            lambda Mock, _: _make_http_error_response(Mock, 502, "Bad Gateway"),
        ),
        (
            "http_503_unavailable",
            lambda Mock, _: _make_http_error_response(Mock, 503, "Service Unavailable"),
        ),
        # Response parsing errors
        (
            "invalid_json_response",
            lambda Mock, _: _make_json_error_response(Mock),
        ),
        (
            "missing_content_key",
            lambda Mock, _: _make_missing_key_response(Mock, {}),
        ),
        (
            "null_content_value",
            lambda Mock, _: _make_missing_key_response(Mock, {"content": None}),
        ),
        # Base64 decoding errors
        (
            "invalid_base64_content",
            lambda Mock, _: _make_invalid_base64_response(Mock, "not-valid-base64!!!"),
        ),
        (
            "corrupted_base64_content",
            lambda Mock, _: _make_invalid_base64_response(Mock, "YWJj==="),  # Invalid padding
        ),
        # YAML parsing errors
        (
            "invalid_yaml_syntax",
            lambda Mock, base64: _make_invalid_yaml_response(Mock, base64, "{{invalid: yaml: ::"),
        ),
        (
            "yaml_with_tabs",
            lambda Mock, base64: _make_invalid_yaml_response(Mock, base64, "env:\n\t\tinvalid_indent: true"),
        ),
    ])
    def test_returns_none_and_prints_error(self, error_name, setup_mock, monkeypatch, capsys):
        """Test that error scenarios return None and print an error message.

        All error paths in get_deploy_config should:
        1. Return None (not raise an exception)
        2. Print an error message containing "Error fetching deploy config"
        """
        import base64
        from unittest.mock import Mock

        mock_get = setup_mock(Mock, base64)
        monkeypatch.setattr("update_openhands_charts.requests.get", mock_get)

        result = get_deploy_config("fake-token", "owner/repo")

        assert result is None, f"Expected None for {error_name}, got {result}"
        captured = capsys.readouterr()
        assert "Error fetching deploy config" in captured.out, (
            f"Expected error message for {error_name}, got: {captured.out}"
        )


# Helper functions for parameterized test setup
def _make_http_error_response(Mock, status_code, message):
    """Create a mock that raises HTTPError on raise_for_status()."""
    mock_response = Mock()
    mock_response.status_code = status_code
    mock_response.raise_for_status.side_effect = Exception(f"HTTP {status_code}: {message}")
    return Mock(return_value=mock_response)


def _make_json_error_response(Mock):
    """Create a mock that raises error on .json() call."""
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.side_effect = Exception("Invalid JSON")
    return Mock(return_value=mock_response)


def _make_missing_key_response(Mock, json_data):
    """Create a mock with JSON response missing required keys."""
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = json_data
    return Mock(return_value=mock_response)


def _make_invalid_base64_response(Mock, invalid_content):
    """Create a mock with invalid base64 content."""
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {"content": invalid_content}
    return Mock(return_value=mock_response)


def _make_invalid_yaml_response(Mock, base64_module, invalid_yaml):
    """Create a mock with valid base64 but invalid YAML content."""
    encoded = base64_module.b64encode(invalid_yaml.encode()).decode()
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {"content": encoded}
    return Mock(return_value=mock_response)


class TestUpdateValues:
    """Tests for update_values function."""

    @pytest.fixture
    def temp_values_file(self, make_temp_yaml_file, sample_openhands_values_full):
        """Create a temporary values.yaml file using shared fixtures."""
        return make_temp_yaml_file(sample_openhands_values_full)

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

    def test_unchanged_when_same_values(self, temp_values_file):
        """Test messages when values are already up to date."""
        # First update to set the values
        update_openhands_values(
            temp_values_file,
            openhands_version="cloud-1.0.0",
        )

        # Second update with same values
        result = update_openhands_values(
            temp_values_file,
            openhands_version="cloud-1.0.0",
        )

        assert not result.has_changes
        unchanged_keys = [u[0] for u in result.unchanged]
        assert "enterprise-server image tag" in unchanged_keys
        assert "runtime image tag" in unchanged_keys
        assert "warmRuntimes image tag" in unchanged_keys

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

        assert result.has_changes is True

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

        assert result.has_changes is False


class TestUpdateOpenhandsChartConditional:
    """Tests for conditional openhands chart version update."""

    @pytest.fixture
    def temp_chart_file(self, make_temp_yaml_file, sample_openhands_chart_minimal):
        """Create a temporary openhands Chart.yaml file using shared fixtures."""
        return make_temp_yaml_file(sample_openhands_chart_minimal)

    def test_no_version_bump_when_no_changes(self, temp_chart_file):
        """Test that chart version is not bumped when has_changes is False."""
        from update_openhands_charts import update_openhands_chart

        result = update_openhands_chart(
            temp_chart_file,
            new_app_version="cloud-1.0.0",
            new_runtime_api_version="0.2.6",
            has_changes=False,
        )

        yaml = YAML()
        chart_data = yaml.load(temp_chart_file)
        assert chart_data["version"] == "0.3.11"  # Unchanged
        assert chart_data["appVersion"] == "cloud-1.0.0"  # Unchanged

        unchanged_keys = [u[0] for u in result.unchanged]
        assert "openhands chart version" in unchanged_keys

    def test_version_bump_when_has_changes(self, temp_chart_file):
        """Test that chart version is bumped when has_changes is True."""
        from update_openhands_charts import update_openhands_chart

        result = update_openhands_chart(
            temp_chart_file,
            new_app_version="cloud-1.1.0",
            new_runtime_api_version="0.2.7",
            has_changes=True,
        )

        yaml = YAML()
        chart_data = yaml.load(temp_chart_file)
        assert chart_data["version"] == "0.3.12"  # Bumped
        assert chart_data["appVersion"] == "cloud-1.1.0"  # Updated

        changed_keys = [c[0] for c in result.changes]
        assert "appVersion" in changed_keys
        assert "version" in changed_keys


class TestDryRun:
    """Tests for dry-run functionality."""

    @pytest.fixture
    def sample_chart_yaml(self):
        """Create a sample Chart.yaml content for dry-run tests."""
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
    def temp_chart_file(self, make_temp_yaml_file, sample_chart_yaml):
        """Create a temporary Chart.yaml file using shared fixture."""
        return make_temp_yaml_file(sample_chart_yaml)

    @pytest.fixture
    def temp_values_file(self, make_temp_yaml_file, sample_openhands_values_minimal):
        """Create a temporary values.yaml file using shared fixtures."""
        return make_temp_yaml_file(sample_openhands_values_minimal)

    def test_update_chart_dry_run_no_file_changes(self, temp_chart_file):
        """Test that dry-run doesn't modify Chart.yaml."""
        original_content = temp_chart_file.read_text()

        update_openhands_chart(temp_chart_file, "2.0.0", "0.2.0", dry_run=True)

        assert temp_chart_file.read_text() == original_content

    def test_update_chart_dry_run_prints_changes(self, temp_chart_file):
        """Test that dry-run still records what would be changed."""
        result = update_openhands_chart(temp_chart_file, "2.0.0", "0.2.0", dry_run=True)

        changed_keys = [c[0] for c in result.changes]
        assert "appVersion" in changed_keys
        assert "version" in changed_keys
        assert "runtime-api version" in changed_keys

    def test_update_values_dry_run_no_file_changes(self, temp_values_file):
        """Test that dry-run doesn't modify values.yaml."""
        original_content = temp_values_file.read_text()

        update_openhands_values(
            temp_values_file,
            openhands_version="cloud-1.1.0",
            dry_run=True,
        )

        assert temp_values_file.read_text() == original_content

    def test_update_values_dry_run_prints_changes(self, temp_values_file):
        """Test that dry-run still records what would be changed."""
        result = update_openhands_values(
            temp_values_file,
            openhands_version="cloud-1.1.0",
            dry_run=True,
        )

        changed_keys = [c[0] for c in result.changes]
        assert "enterprise-server image tag" in changed_keys
        assert "runtime image tag" in changed_keys
        assert "warmRuntimes image tag" in changed_keys

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
    def temp_runtime_api_chart_file(self, make_temp_yaml_file, sample_runtime_api_chart_full):
        """Create a temporary runtime-api Chart.yaml file using shared fixtures."""
        return make_temp_yaml_file(sample_runtime_api_chart_full)

    def test_bump_runtime_api_version(self, temp_runtime_api_chart_file):
        """Test that runtime-api chart version is bumped correctly."""
        new_version, result = update_runtime_api_chart(temp_runtime_api_chart_file)

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
        new_version, result = update_runtime_api_chart(temp_runtime_api_chart_file, dry_run=True)
        assert new_version == "0.1.21"


class TestUpdateRuntimeApiValues:
    """Tests for update_runtime_api_values function."""

    @pytest.fixture
    def temp_runtime_api_values_file(self, make_temp_yaml_file, sample_runtime_api_values):
        """Create a temporary runtime-api values.yaml file using shared fixtures."""
        return make_temp_yaml_file(sample_runtime_api_values)

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

    def test_unchanged_when_same_value(self, temp_runtime_api_values_file):
        """Test message when value is already up to date."""
        # First update
        update_runtime_api_values(
            temp_runtime_api_values_file,
            runtime_api_sha="abc1234567890def",
            openhands_version="cloud-1.1.0",
        )

        # Second update with same value
        result = update_runtime_api_values(
            temp_runtime_api_values_file,
            runtime_api_sha="abc1234567890def",
            openhands_version="cloud-1.1.0",
        )

        assert not result.has_changes
        unchanged_keys = [u[0] for u in result.unchanged]
        assert "runtime-api image tag" in unchanged_keys
        assert "runtime-api warmRuntimes image tag" in unchanged_keys

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

        assert result.has_changes is True

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

        assert result.has_changes is False


class TestUpdateRuntimeApiChartConditional:
    """Tests for conditional runtime-api chart version update."""

    @pytest.fixture
    def temp_runtime_api_chart_file(self, make_temp_yaml_file, sample_runtime_api_chart_minimal):
        """Create a temporary runtime-api Chart.yaml file using shared fixtures."""
        return make_temp_yaml_file(sample_runtime_api_chart_minimal)

    def test_no_version_bump_when_no_changes(self, temp_runtime_api_chart_file):
        """Test that chart version is not bumped when has_changes is False."""
        from update_openhands_charts import update_runtime_api_chart

        new_version, result = update_runtime_api_chart(temp_runtime_api_chart_file, has_changes=False)

        assert new_version == "0.2.6"  # Version unchanged
        unchanged_keys = [u[0] for u in result.unchanged]
        assert "runtime-api chart version" in unchanged_keys

    def test_version_bump_when_has_changes(self, temp_runtime_api_chart_file):
        """Test that chart version is bumped when has_changes is True."""
        from update_openhands_charts import update_runtime_api_chart

        new_version, result = update_runtime_api_chart(temp_runtime_api_chart_file, has_changes=True)

        assert new_version == "0.2.7"  # Version bumped
        changed_keys = [c[0] for c in result.changes]
        assert "runtime-api chart version" in changed_keys


class TestMainOutputMessages:
    """Tests for main() output message formatting."""

    # Use a test constant to avoid magic strings scattered throughout tests
    MOCK_CLOUD_TAG = "cloud-1.20.0"

    def test_latest_cloud_tag_message_format(self, capsys, monkeypatch):
        """Test that the latest cloud tag message uses correct format."""
        from update_openhands_charts import main

        mock_tag = self.MOCK_CLOUD_TAG

        # Mock GITHUB_TOKEN environment variable
        monkeypatch.setenv("GITHUB_TOKEN", "dummy-token")

        # Mock get_latest_cloud_tag to return a known value
        monkeypatch.setattr(
            "update_openhands_charts.get_latest_cloud_tag",
            lambda token, repo: mock_tag
        )
        # Mock cloud_tag_exists
        monkeypatch.setattr(
            "update_openhands_charts.cloud_tag_exists",
            lambda token, repo, tag: True
        )
        # Mock get_current_app_version to return matching version (early exit)
        monkeypatch.setattr(
            "update_openhands_charts.get_current_app_version",
            lambda path: mock_tag
        )

        main(dry_run=True)

        captured = capsys.readouterr()
        assert f"OpenHands cloud tag: {mock_tag}" in captured.out

    def test_current_app_version_message_format(self, capsys, monkeypatch):
        """Test that the current appVersion message uses correct format."""
        from update_openhands_charts import main

        mock_tag = self.MOCK_CLOUD_TAG

        # Mock GITHUB_TOKEN environment variable
        monkeypatch.setenv("GITHUB_TOKEN", "dummy-token")

        # Mock get_latest_cloud_tag to return a known value
        monkeypatch.setattr(
            "update_openhands_charts.get_latest_cloud_tag",
            lambda token, repo: mock_tag
        )
        # Mock cloud_tag_exists
        monkeypatch.setattr(
            "update_openhands_charts.cloud_tag_exists",
            lambda token, repo, tag: True
        )
        # Mock get_current_app_version to return matching version (early exit)
        monkeypatch.setattr(
            "update_openhands_charts.get_current_app_version",
            lambda path: mock_tag
        )

        main(dry_run=True)

        captured = capsys.readouterr()
        assert f"OpenHands-Cloud openhands chart appVersion: {mock_tag}" in captured.out


class TestGetLatestCloudTag:
    """Tests for get_latest_cloud_tag function.

    Uses mocked GitHub API responses for fast, deterministic tests.
    """

    def test_returns_first_matching_cloud_tag(self, mock_github_tags):
        """Test that function returns the first cloud-X.Y.Z formatted tag."""
        from update_openhands_charts import get_latest_cloud_tag

        mock_github_tags(["latest", "cloud-1.20.0", "cloud-1.19.0"])

        result = get_latest_cloud_tag("fake-token", "All-Hands-AI/OpenHands")

        assert result == "cloud-1.20.0"
        assert result.startswith("cloud-")
        assert extract_version_from_cloud_tag(result) == "1.20.0"

    def test_skips_non_cloud_tags(self, mock_github_tags):
        """Test that non-cloud tags are skipped."""
        from update_openhands_charts import get_latest_cloud_tag

        mock_github_tags(["v1.0.0", "release-2.0", "cloud-1.5.0"])

        result = get_latest_cloud_tag("fake-token", "owner/repo")

        assert result == "cloud-1.5.0"

    def test_returns_none_when_no_cloud_tags(self, mock_github_tags):
        """Test that None is returned when no cloud tags exist."""
        from update_openhands_charts import get_latest_cloud_tag

        mock_github_tags(["v1.0.0", "latest"])

        result = get_latest_cloud_tag("fake-token", "owner/repo")

        assert result is None

    def test_returns_none_for_invalid_repo(self, mock_github_tags, capsys):
        """Test that None is returned and error is printed for invalid repository."""
        from update_openhands_charts import get_latest_cloud_tag

        mock_github_tags(repo_error=Exception("Repository not found"))

        result = get_latest_cloud_tag("fake-token", "nonexistent/repo")

        assert result is None
        captured = capsys.readouterr()
        assert "Error fetching tags" in captured.out

    def test_no_redirect_message_in_output(self, mock_github_tags, capsys):
        """Test that PyGithub redirect messages are suppressed."""
        from update_openhands_charts import get_latest_cloud_tag

        mock_github_tags(["cloud-1.0.0"])

        get_latest_cloud_tag("fake-token", "owner/repo")

        captured = capsys.readouterr()
        assert "redirect" not in captured.out.lower()
        assert "following" not in captured.out.lower()


class TestCloudTagExists:
    """Tests for cloud_tag_exists function.

    Uses mocked GitHub API responses for fast, deterministic tests.
    """

    def test_returns_true_when_tag_exists(self, mock_github_ref):
        """Test that function returns True when the tag reference is found."""
        from update_openhands_charts import cloud_tag_exists

        _, mock_repo = mock_github_ref(tag_exists=True)

        result = cloud_tag_exists("fake-token", "All-Hands-AI/OpenHands", "cloud-1.20.0")

        assert result is True
        mock_repo.get_git_ref.assert_called_once_with("tags/cloud-1.20.0")

    def test_returns_false_when_tag_not_found(self, mock_github_ref):
        """Test that function returns False when get_git_ref raises exception."""
        from update_openhands_charts import cloud_tag_exists

        mock_github_ref(tag_exists=False)

        result = cloud_tag_exists("fake-token", "All-Hands-AI/OpenHands", "cloud-99999.0.0")

        assert result is False

    def test_returns_false_for_invalid_repo(self, mock_github_ref):
        """Test that function returns False when repository doesn't exist."""
        from update_openhands_charts import cloud_tag_exists

        mock_github_ref(repo_error=Exception("Repository not found"))

        result = cloud_tag_exists("fake-token", "nonexistent/repo", "cloud-1.0.0")

        assert result is False

    def test_handles_various_tag_formats(self, mock_github_ref):
        """Test that function correctly queries different tag formats."""
        from update_openhands_charts import cloud_tag_exists

        _, mock_repo = mock_github_ref(tag_exists=True)

        # Test various tag formats
        cloud_tag_exists("fake-token", "owner/repo", "cloud-1.0.0")
        cloud_tag_exists("fake-token", "owner/repo", "cloud-10.20.30")

        # Verify correct ref format is used
        calls = mock_repo.get_git_ref.call_args_list
        assert calls[0][0][0] == "tags/cloud-1.0.0"
        assert calls[1][0][0] == "tags/cloud-10.20.30"


class TestParseArgs:
    """Tests for parse_args function."""

    def test_cloud_tag_argument_exists(self, monkeypatch):
        """Test that --cloud-tag argument is accepted."""
        from update_openhands_charts import parse_args

        monkeypatch.setattr(sys, "argv", ["script", "--cloud-tag", "cloud-1.2.0"])
        args = parse_args()
        assert args.cloud_tag == "cloud-1.2.0"

    def test_cloud_tag_default_is_none(self, monkeypatch):
        """Test that --cloud-tag defaults to None."""
        from update_openhands_charts import parse_args

        monkeypatch.setattr(sys, "argv", ["script"])
        args = parse_args()
        assert args.cloud_tag is None

    def test_dry_run_argument(self, monkeypatch):
        """Test that --dry-run argument works."""
        from update_openhands_charts import parse_args

        monkeypatch.setattr(sys, "argv", ["script", "--dry-run"])
        args = parse_args()
        assert args.dry_run is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
