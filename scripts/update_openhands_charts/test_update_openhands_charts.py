#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyGithub", "ruamel.yaml", "requests", "pytest"]
# ///
"""Unit tests for update_openhands_charts.py."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

# Add the script's directory to sys.path so we can import it directly
sys.path.insert(0, str(Path(__file__).parent))

import update_openhands_charts
from conftest import (
    assert_file_contains_all,
    assert_version_bumped,
    get_chart_value,
    get_dependency_version,
    # Fixture baseline constants for self-documenting assertions
    OPENHANDS_CHART_VERSION,
    OPENHANDS_CHART_APP_VERSION,
    OPENHANDS_CHART_RUNTIME_API_VERSION,
    OPENHANDS_CHART_WITH_DEPS_OTHER_DEP_VERSION,
    RUNTIME_API_CHART_FULL_VERSION,
    RUNTIME_API_CHART_FULL_APP_VERSION,
    RUNTIME_API_CHART_MINIMAL_VERSION,
    # Test input constants for update operations
    NEW_APP_VERSION,
    NEW_RUNTIME_API_VERSION,
)
from update_openhands_charts import (
    DeployConfig,
    bump_patch_version,
    cloud_tag_exists,
    extract_version_from_cloud_tag,
    format_sha_tag,
    get_current_app_version,
    get_deploy_config,
    get_latest_cloud_tag,
    get_short_sha,
    main,
    parse_args,
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

    @pytest.mark.parametrize("cloud_tag,expected", [
        # Happy path: typical production versions
        ("cloud-1.1.0", "1.1.0"),
        ("cloud-2.0.0", "2.0.0"),
        # Boundary: minimum valid version (all zeros)
        ("cloud-0.0.0", "0.0.0"),
        # Boundary: multi-digit components (regex must not limit to single digits)
        ("cloud-10.20.30", "10.20.30"),
        # Stress test: very large version numbers (ensures no arbitrary limits)
        ("cloud-123.456.789", "123.456.789"),
    ])
    def test_extracts_version_from_valid_cloud_tags(self, cloud_tag, expected):
        """Test that version is extracted from valid cloud-X.Y.Z formats."""
        assert extract_version_from_cloud_tag(cloud_tag) == expected

    @pytest.mark.parametrize("invalid_tag", [
        # Prefix validation: must be exactly "cloud-"
        pytest.param("1.1.0", id="missing cloud- prefix"),
        pytest.param("v1.1.0", id="wrong prefix (v instead of cloud-)"),
        pytest.param("Cloud-1.2.3", id="wrong case"),
        pytest.param("cloud1.2.3", id="missing hyphen"),
        # Semver structure: must be exactly X.Y.Z (three parts)
        pytest.param("cloud-1.2", id="missing patch"),
        pytest.param("cloud-1.2.3.4", id="extra part"),
        # Semver extensions: pre-release and build metadata not supported
        pytest.param("cloud-1.2.3-beta", id="pre-release suffix"),
        pytest.param("cloud-1.2.3+build", id="build metadata suffix"),
        # Edge cases: empty/malformed input
        pytest.param("", id="empty string"),
        pytest.param("latest", id="non-version tag"),
        pytest.param("cloud-", id="missing version"),
    ])
    def test_returns_none_for_invalid_cloud_tag_formats(self, invalid_tag):
        """Test that None is returned for strings that aren't cloud-X.Y.Z."""
        assert extract_version_from_cloud_tag(invalid_tag) is None


class TestGetShortSha:
    """Tests for get_short_sha function.

    Git short SHAs are conventionally 7 characters for readability while
    maintaining uniqueness in most repositories.
    """

    @pytest.mark.parametrize("sha,expected", [
        # Happy path: typical input longer than 7 chars
        ("abcdefghijklmnop", "abcdefg"),
        # Real-world: full 40-character git SHA (most common input)
        ("6ccd42bb2975866f1abc21e635c01d2afbdd1acf", "6ccd42b"),
        # Boundary: input exactly 7 chars (no truncation needed)
        ("a1b2c3d", "a1b2c3d"),
        # Boundary: input shorter than 7 chars (returns full input)
        pytest.param("abc", "abc", id="input shorter than 7 chars"),
    ])
    def test_short_sha_is_first_seven_characters_of_full_sha(self, sha, expected):
        """Verify short SHA extraction returns exactly 7 characters or full input if shorter."""
        assert get_short_sha(sha) == expected


class TestFormatShaTag:
    """Tests for format_sha_tag function.

    Note: Truncation behavior is tested in TestGetShortSha.
    These tests focus on the sha- prefix formatting.
    """

    @pytest.mark.parametrize("sha,expected", [
        # Happy path: verifies "sha-" prefix is prepended
        ("abcdefghijklmnop", "sha-abcdefg"),
        # Real-world: actual GitHub Actions workflow SHA (ensures production compatibility)
        ("743f6256a690efc388af6e960ad8009f5952e721", "sha-743f625"),
    ])
    def test_sha_tag_format_is_sha_prefix_followed_by_short_sha(self, sha, expected):
        """Verify SHA tag format follows the 'sha-<7-char-hash>' convention used in container registries."""
        assert format_sha_tag(sha) == expected


class TestGetCurrentAppVersion:
    """Tests for get_current_app_version function.

    Reads the appVersion field from Helm Chart.yaml files to determine
    the currently deployed OpenHands version.
    """

    def test_reads_app_version_from_chart_yaml(self, make_temp_yaml_file):
        """Verify appVersion is correctly extracted from a valid Chart.yaml file."""
        chart_content = """\
apiVersion: v2
appVersion: cloud-1.1.0
version: 0.3.11
name: openhands
"""
        temp_chart_file = make_temp_yaml_file(chart_content)
        result = get_current_app_version(temp_chart_file)
        assert result == "cloud-1.1.0"

    def test_missing_chart_file_returns_none(self):
        """Verify graceful handling when Chart.yaml does not exist."""
        result = get_current_app_version(Path("/nonexistent/Chart.yaml"))
        assert result is None


class TestBumpPatchVersion:
    """Tests for bump_patch_version function.

    Semantic versioning (semver) uses MAJOR.MINOR.PATCH format where
    patch bumps indicate backwards-compatible bug fixes.
    """

    @pytest.mark.parametrize("version,expected", [
        # Happy path: typical version increment
        ("1.2.3", "1.2.4"),
        # Boundary: patch starts at zero (common for new minor releases)
        ("1.0.0", "1.0.1"),
        # Boundary: 99→100 rollover (ensures no single/double digit assumptions)
        ("1.2.99", "1.2.100"),
        # Verification: major/minor preserved during patch bump
        ("5.10.15", "5.10.16"),
    ])
    def test_patch_version_increments_by_one_preserving_major_minor(self, version, expected):
        """Verify patch bump increments only the patch component while preserving major.minor."""
        assert bump_patch_version(version) == expected

    @pytest.mark.parametrize("invalid_version", [
        # Structure: must have exactly 3 parts (major.minor.patch)
        pytest.param("1.2", id="missing patch"),
        pytest.param("1.2.3.4", id="too many parts"),
        # Format: no prefixes allowed (unlike git tags)
        pytest.param("v1.2.3", id="has prefix"),
        # Edge cases: empty and non-numeric inputs
        pytest.param("", id="empty string"),
        pytest.param("1.2.abc", id="non-numeric patch"),
        pytest.param("a.b.c", id="all non-numeric"),
    ])
    def test_invalid_semver_format_raises_value_error(self, invalid_version):
        """Verify non-semver strings are rejected with clear error message."""
        with pytest.raises(ValueError, match="Invalid semver format"):
            bump_patch_version(invalid_version)


class TestUpdateChartAcrossVariants:
    """Tests for update_chart that verify behavior across both chart variants.

    Uses the parameterized openhands_chart_variant fixture to ensure core
    functionality works with both rich (with_deps) and minimal chart structures.
    """

    @pytest.fixture
    def temp_chart_file(self, make_temp_yaml_file, openhands_chart_variant):
        """Create a temporary Chart.yaml from the parameterized variant."""
        return make_temp_yaml_file(openhands_chart_variant["content"])

    def test_chart_app_version_updates_to_new_cloud_tag(self, temp_chart_file):
        """Verify appVersion field is updated to the new OpenHands cloud tag."""
        update_openhands_chart(temp_chart_file, NEW_APP_VERSION, None)

        assert get_chart_value(temp_chart_file, "appVersion") == NEW_APP_VERSION

    def test_chart_version_bumps_patch_on_update(self, temp_chart_file):
        """Verify chart version patch is incremented when changes are made."""
        update_openhands_chart(temp_chart_file, NEW_APP_VERSION, None)

        assert_version_bumped(temp_chart_file, OPENHANDS_CHART_VERSION)

    def test_runtime_api_dependency_version_updates(self, temp_chart_file):
        """Verify runtime-api dependency version is updated in Chart.yaml."""
        update_openhands_chart(temp_chart_file, NEW_APP_VERSION, NEW_RUNTIME_API_VERSION)

        assert get_dependency_version(temp_chart_file, "runtime-api") == NEW_RUNTIME_API_VERSION

    def test_app_version_unchanged_when_already_current(self, temp_chart_file):
        """Verify no change is recorded when appVersion already matches target."""
        result = update_openhands_chart(temp_chart_file, OPENHANDS_CHART_APP_VERSION, NEW_RUNTIME_API_VERSION)

        assert result.is_unchanged("appVersion")

    def test_runtime_api_version_unchanged_when_already_current(self, temp_chart_file):
        """Verify no change is recorded when runtime-api version already matches target."""
        result = update_openhands_chart(temp_chart_file, NEW_APP_VERSION, OPENHANDS_CHART_RUNTIME_API_VERSION)

        assert result.is_unchanged("runtime-api version")


class TestUpdateChart:
    """Tests for update_chart function with specific fixture requirements.

    These tests require the with_deps fixture specifically because they test
    features only present in that variant (e.g., multiple dependencies, maintainers).
    """

    @pytest.fixture
    def temp_chart_file(self, make_temp_yaml_file, sample_openhands_chart_with_deps):
        """Create a temporary Chart.yaml file using shared fixtures."""
        return make_temp_yaml_file(sample_openhands_chart_with_deps)

    def test_non_runtime_api_dependencies_remain_unchanged(self, temp_chart_file):
        """Verify only runtime-api dependency is modified; other deps are preserved."""
        update_openhands_chart(temp_chart_file, NEW_APP_VERSION, NEW_RUNTIME_API_VERSION)

        assert get_dependency_version(temp_chart_file, "other-dep") == OPENHANDS_CHART_WITH_DEPS_OTHER_DEP_VERSION

    def test_yaml_structure_and_metadata_preserved_after_update(self, temp_chart_file):
        """Verify YAML structure, metadata, and non-version fields are preserved."""
        update_openhands_chart(temp_chart_file, NEW_APP_VERSION, NEW_RUNTIME_API_VERSION)

        # Verify structure is preserved
        assert get_chart_value(temp_chart_file, "apiVersion") == "v2"
        assert get_chart_value(temp_chart_file, "description") == "Test chart"
        assert get_chart_value(temp_chart_file, "name") == "test-chart"
        assert len(get_chart_value(temp_chart_file, "maintainers")) == 1
        assert len(get_chart_value(temp_chart_file, "dependencies")) == 2


class TestDeployConfig:
    """Tests for DeployConfig dataclass.

    DeployConfig holds configuration values extracted from the deploy workflow,
    used to synchronize chart versions with deployed infrastructure.
    """

    def test_deploy_config_stores_runtime_api_sha(self):
        """Verify DeployConfig correctly stores the runtime-api commit SHA."""
        config = DeployConfig(
            runtime_api_sha="def5678901234",
            openhands_runtime_image_tag="cloud-1.21.0-nikolaik",
        )
        assert config.runtime_api_sha == "def5678901234"

    def test_deploy_config_stores_openhands_runtime_image_tag(self):
        """Verify DeployConfig correctly stores the runtime image tag from deploy config."""
        config = DeployConfig(
            runtime_api_sha="def5678901234",
            openhands_runtime_image_tag="cloud-1.21.0-nikolaik",
        )
        assert config.openhands_runtime_image_tag == "cloud-1.21.0-nikolaik"

class TestUpdateResultHelpers:
    """Tests for UpdateResult helper methods.

    These helpers provide a cleaner API for checking if specific keys
    were changed or unchanged, reducing coupling to internal data structures.
    """

    @pytest.mark.parametrize("key,expected", [
        # Happy path: first key in list should be found
        ("appVersion", True),
        # Happy path: key with special chars (hyphen, space) should be found
        ("runtime-api version", True),
        # Boundary: key not in list returns False (not None or error)
        ("nonexistent-key", False),
    ])
    def test_is_unchanged_finds_keys_in_unchanged_list(self, key, expected):
        """Verify is_unchanged correctly identifies presence/absence of keys."""
        result = update_openhands_charts.UpdateResult(
            unchanged=[("appVersion", "1.0.0"), ("runtime-api version", "0.2.6")]
        )
        assert result.is_unchanged(key) is expected

    def test_is_unchanged_returns_false_for_empty_list(self):
        """Verify is_unchanged returns False when unchanged list is empty."""
        # Edge case: empty state after initialization (no updates performed yet)
        result = update_openhands_charts.UpdateResult()
        assert result.is_unchanged("any-key") is False

    @pytest.mark.parametrize("key,expected", [
        # Happy path: first key in changes list should be found
        ("appVersion", True),
        # Happy path: additional keys in list should also be found
        ("version", True),
        # Boundary: key not in list returns False (not None or error)
        ("nonexistent-key", False),
    ])
    def test_has_change_for_finds_keys_in_changes_list(self, key, expected):
        """Verify has_change_for correctly identifies presence/absence of keys."""
        result = update_openhands_charts.UpdateResult(
            has_changes=True,
            changes=[("appVersion", "1.0.0", "2.0.0"), ("version", "0.1.0", "0.1.1")]
        )
        assert result.has_change_for(key) is expected

    def test_has_change_for_returns_false_for_empty_list(self):
        """Verify has_change_for returns False when changes list is empty."""
        # Edge case: no changes made (dry run or values already current)
        result = update_openhands_charts.UpdateResult()
        assert result.has_change_for("any-key") is False


class TestAssertVersionBumped:
    """Tests for assert_version_bumped helper function.

    This helper verifies that a chart's version was correctly bumped,
    encapsulating the common pattern of bump_patch_version + get_chart_value.
    """

    def test_passes_when_version_correctly_bumped(self, make_temp_yaml_file):
        """Test helper passes when version is incremented by one patch."""
        # Boundary: exact +1 increment is the only valid bump
        chart_content = """\
apiVersion: v2
name: test-chart
version: 1.2.4
"""
        temp_file = make_temp_yaml_file(chart_content)

        # Should not raise - version 1.2.4 is exactly one patch bump from 1.2.3
        assert_version_bumped(temp_file, original_version="1.2.3")

    def test_fails_when_version_not_bumped(self, make_temp_yaml_file):
        """Test helper raises AssertionError when version unchanged."""
        # Edge case: version unchanged (forgot to bump) should be caught
        chart_content = """\
apiVersion: v2
name: test-chart
version: 1.2.3
"""
        temp_file = make_temp_yaml_file(chart_content)

        with pytest.raises(AssertionError, match="Expected version 1.2.4"):
            assert_version_bumped(temp_file, original_version="1.2.3")

    def test_fails_when_version_bumped_incorrectly(self, make_temp_yaml_file):
        """Test helper raises AssertionError when version bumped by wrong amount."""
        # Edge case: over-bumping (e.g., +2 instead of +1) should be caught
        # This prevents accidental double-bumps or manual version edits
        chart_content = """\
apiVersion: v2
name: test-chart
version: 1.2.5
"""
        temp_file = make_temp_yaml_file(chart_content)

        with pytest.raises(AssertionError, match="Expected version 1.2.4, got 1.2.5"):
            assert_version_bumped(temp_file, original_version="1.2.3")


class TestGetDependencyVersion:
    """Tests for get_dependency_version helper function.

    This helper extracts dependency versions from Chart.yaml files,
    reducing coupling to internal YAML data structures in tests.
    """

    @pytest.mark.parametrize("dep_name,expected_version", [
        # Existing dependencies return their version
        ("runtime-api", OPENHANDS_CHART_RUNTIME_API_VERSION),
        ("other-dep", OPENHANDS_CHART_WITH_DEPS_OTHER_DEP_VERSION),
        # Non-existent dependency returns None
        ("nonexistent-dep", None),
    ])
    def test_dependency_version_lookup_by_name(self, make_temp_yaml_file, sample_openhands_chart_with_deps, dep_name, expected_version):
        """Verify dependency versions are correctly extracted by name, or None if not found."""
        temp_file = make_temp_yaml_file(sample_openhands_chart_with_deps)
        assert get_dependency_version(temp_file, dep_name) == expected_version

    def test_returns_none_when_chart_has_no_dependencies(self, make_temp_yaml_file):
        """Verify None is returned when chart has no dependencies section."""
        chart_content = """\
apiVersion: v2
name: test-chart
version: 1.0.0
"""
        temp_file = make_temp_yaml_file(chart_content)
        assert get_dependency_version(temp_file, "any-dep") is None


class TestGetChartValue:
    """Tests for get_chart_value helper function.

    This helper extracts top-level values from Chart.yaml files,
    reducing coupling to internal YAML data structures in tests.
    """

    def test_returns_value_when_key_exists(self, make_temp_yaml_file):
        """Test that value is returned when key exists."""
        chart_content = """\
apiVersion: v2
appVersion: cloud-1.0.0
version: 0.3.11
name: openhands
"""
        temp_file = make_temp_yaml_file(chart_content)
        assert get_chart_value(temp_file, "appVersion") == "cloud-1.0.0"

    def test_returns_value_for_any_top_level_key(self, make_temp_yaml_file):
        """Test that value is returned for any top-level key."""
        chart_content = """\
apiVersion: v2
appVersion: cloud-2.0.0
version: 0.1.0
name: test-chart
description: A test chart
"""
        temp_file = make_temp_yaml_file(chart_content)
        assert get_chart_value(temp_file, "name") == "test-chart"
        assert get_chart_value(temp_file, "version") == "0.1.0"
        assert get_chart_value(temp_file, "description") == "A test chart"

    def test_returns_none_when_key_not_found(self, make_temp_yaml_file):
        """Test that None is returned when key doesn't exist."""
        chart_content = """\
apiVersion: v2
name: test-chart
version: 1.0.0
"""
        temp_file = make_temp_yaml_file(chart_content)
        assert get_chart_value(temp_file, "nonexistent-key") is None


class TestGetDeployConfig:
    """Tests for get_deploy_config function.

    Uses parameterized tests for comprehensive error path coverage.
    All error scenarios should return None and print an error message.
    """

    import base64

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

        encoded_content = base64.b64encode(self.VALID_WORKFLOW_YAML.encode()).decode()
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"content": encoded_content}
        return mock_response

    def test_returns_deploy_config_on_success(self, monkeypatch, mock_successful_response):
        """Test that valid response returns DeployConfig with correct values."""
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
        mock_get = Mock(return_value=mock_successful_response)
        monkeypatch.setattr("update_openhands_charts.requests.get", mock_get)

        get_deploy_config("fake-token", "owner/repo")

        called_url = mock_get.call_args[0][0]
        assert called_url == "https://api.github.com/repos/owner/repo/contents/.github/workflows/deploy.yaml"
        assert "?ref=" not in called_url

    def test_constructs_correct_url_with_ref(self, monkeypatch, mock_successful_response):
        """Test that URL includes ref parameter when provided."""
        mock_get = Mock(return_value=mock_successful_response)
        monkeypatch.setattr("update_openhands_charts.requests.get", mock_get)

        get_deploy_config("fake-token", "owner/repo", ref="v1.2.3")

        called_url = mock_get.call_args[0][0]
        assert "?ref=v1.2.3" in called_url

    def test_includes_authorization_header(self, monkeypatch, mock_successful_response):
        """Test that Authorization header is included with token."""
        mock_get = Mock(return_value=mock_successful_response)
        monkeypatch.setattr("update_openhands_charts.requests.get", mock_get)

        get_deploy_config("my-secret-token", "owner/repo")

        called_headers = mock_get.call_args[1]["headers"]
        assert called_headers["Authorization"] == "Bearer my-secret-token"

    def test_returns_empty_string_when_env_key_missing(self, monkeypatch):
        """Test that missing RUNTIME_API_SHA returns empty string (not None)."""
        import base64

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
        assert result.is_unchanged("enterprise-server image tag")
        assert result.is_unchanged("runtime image tag")
        assert result.is_unchanged("warmRuntimes image tag")

    def test_preserves_other_content(self, temp_values_file):
        """Test that other content in values.yaml is preserved."""
        update_openhands_values(
            temp_values_file,
            openhands_version="cloud-1.1.0",
        )

        assert_file_contains_all(temp_values_file, [
            "allowedUsers: null",
            "runAsRoot: true",
            "replicaCount: 1",
            'working_dir: "/openhands/code/"',
        ])

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

    def test_reports_error_when_enterprise_server_tag_missing(self, make_temp_yaml_file):
        """Test that error is reported when enterprise-server image tag pattern not found."""
        # YAML without enterprise-server image section
        values_content = """\
image:
  repository: ghcr.io/other/image
  tag: v1.0.0

runtime:
  image:
    repository: ghcr.io/openhands/runtime
    tag: cloud-1.0.0-nikolaik

runtime-api:
  warmRuntimes:
    configs:
      - name: default
        image: "ghcr.io/openhands/runtime:cloud-1.0.0-nikolaik"
"""
        temp_file = make_temp_yaml_file(values_content)

        result = update_openhands_values(temp_file, openhands_version="cloud-1.1.0")

        assert "Could not find enterprise-server image tag" in result.errors[0]

    def test_reports_error_when_runtime_tag_missing(self, make_temp_yaml_file):
        """Test that error is reported when runtime image tag pattern not found."""
        # YAML without runtime image section
        values_content = """\
image:
  repository: ghcr.io/openhands/enterprise-server
  tag: cloud-1.0.0

runtime-api:
  warmRuntimes:
    configs:
      - name: default
        image: "ghcr.io/openhands/runtime:cloud-1.0.0-nikolaik"
"""
        temp_file = make_temp_yaml_file(values_content)

        result = update_openhands_values(temp_file, openhands_version="cloud-1.1.0")

        assert "Could not find runtime image tag" in result.errors[0]

    def test_reports_error_when_warm_runtimes_tag_missing(self, make_temp_yaml_file):
        """Test that error is reported when warmRuntimes image tag pattern not found."""
        # YAML without warmRuntimes image
        values_content = """\
image:
  repository: ghcr.io/openhands/enterprise-server
  tag: cloud-1.0.0

runtime:
  image:
    repository: ghcr.io/openhands/runtime
    tag: cloud-1.0.0-nikolaik

runtime-api:
  warmRuntimes:
    enabled: false
"""
        temp_file = make_temp_yaml_file(values_content)

        result = update_openhands_values(temp_file, openhands_version="cloud-1.1.0")

        assert "Could not find warmRuntimes image tag" in result.errors[0]

    def test_collects_multiple_errors_when_multiple_patterns_missing(self, make_temp_yaml_file):
        """Test that all missing patterns are reported as errors."""
        # Minimal YAML with none of the expected patterns
        values_content = """\
replicaCount: 1
serviceAccount:
  create: true
"""
        temp_file = make_temp_yaml_file(values_content)

        result = update_openhands_values(temp_file, openhands_version="cloud-1.1.0")

        assert len(result.errors) == 3
        error_messages = " ".join(result.errors)
        assert "enterprise-server" in error_messages
        assert "runtime image tag" in error_messages
        assert "warmRuntimes" in error_messages


class TestUpdateOpenhandsChartConditional:
    """Tests for conditional openhands chart version update."""

    @pytest.fixture
    def temp_chart_file(self, make_temp_yaml_file, sample_openhands_chart_minimal):
        """Create a temporary openhands Chart.yaml file using shared fixtures."""
        return make_temp_yaml_file(sample_openhands_chart_minimal)

    def test_no_version_bump_when_no_changes(self, temp_chart_file):
        """Test that chart version is not bumped when has_changes is False."""
        result = update_openhands_chart(
            temp_chart_file,
            new_app_version=OPENHANDS_CHART_APP_VERSION,
            new_runtime_api_version=OPENHANDS_CHART_RUNTIME_API_VERSION,
            has_changes=False,
        )

        assert get_chart_value(temp_chart_file, "version") == OPENHANDS_CHART_VERSION
        assert get_chart_value(temp_chart_file, "appVersion") == OPENHANDS_CHART_APP_VERSION

        assert result.is_unchanged("openhands chart version")

    def test_version_bump_when_has_changes(self, temp_chart_file):
        """Test that chart version is bumped when has_changes is True."""
        result = update_openhands_chart(
            temp_chart_file,
            new_app_version="cloud-1.1.0",
            new_runtime_api_version="0.2.7",
            has_changes=True,
        )

        assert get_chart_value(temp_chart_file, "version") == "0.1.1"  # Bumped from 0.1.0
        assert get_chart_value(temp_chart_file, "appVersion") == "cloud-1.1.0"  # Updated

        assert result.has_change_for("appVersion")
        assert result.has_change_for("version")


        assert result.has_changes is True

    @pytest.fixture
    def temp_chart_file(self, make_temp_yaml_file, sample_openhands_chart_with_deps):
        """Create a temporary Chart.yaml file using shared fixture."""
        return make_temp_yaml_file(sample_openhands_chart_with_deps)

    @pytest.fixture
    def temp_values_file(self, make_temp_yaml_file, sample_openhands_values_minimal):
        """Create a temporary values.yaml file using shared fixtures."""
        return make_temp_yaml_file(sample_openhands_values_minimal)

    def test_update_chart_dry_run_no_file_changes(self, temp_chart_file):
        """Test that dry-run doesn't modify Chart.yaml."""
        # Arrange: capture original state
        original_content = temp_chart_file.read_text()

        update_openhands_chart(temp_chart_file, NEW_APP_VERSION, NEW_RUNTIME_API_VERSION, dry_run=True)

        # Assert: file unchanged
        assert temp_chart_file.read_text() == original_content

    def test_update_chart_dry_run_prints_changes(self, temp_chart_file):
        """Test that dry-run still records what would be changed."""
        result = update_openhands_chart(temp_chart_file, NEW_APP_VERSION, NEW_RUNTIME_API_VERSION, dry_run=True)

        assert result.has_change_for("appVersion")
        assert result.has_change_for("version")
        assert result.has_change_for("runtime-api version")

    def test_update_values_dry_run_no_file_changes(self, temp_values_file):
        """Test that dry-run doesn't modify values.yaml."""
        # Arrange: capture original state
        original_content = temp_values_file.read_text()

        # Act: run update with dry_run=True
        update_openhands_values(
            temp_values_file,
            openhands_version="cloud-1.1.0",
            dry_run=True,
        )

        # Assert: file unchanged
        assert temp_values_file.read_text() == original_content

    def test_update_values_dry_run_prints_changes(self, temp_values_file):
        """Test that dry-run still records what would be changed."""
        result = update_openhands_values(
            temp_values_file,
            openhands_version="cloud-1.1.0",
            dry_run=True,
        )

        assert result.has_change_for("enterprise-server image tag")
        assert result.has_change_for("runtime image tag")
        assert result.has_change_for("warmRuntimes image tag")

    def test_update_chart_without_dry_run_modifies_file(self, temp_chart_file):
        """Test that without dry-run, Chart.yaml is modified."""
        # Arrange: capture original state
        original_content = temp_chart_file.read_text()

        update_openhands_chart(temp_chart_file, NEW_APP_VERSION, NEW_RUNTIME_API_VERSION, dry_run=False)

        # Assert: file was modified
        assert temp_chart_file.read_text() != original_content

    def test_update_values_without_dry_run_modifies_file(self, temp_values_file):
        """Test that without dry-run, values.yaml is modified."""
        # Arrange: capture original state
        original_content = temp_values_file.read_text()

        # Act: run update with dry_run=False (default behavior)
        update_openhands_values(
            temp_values_file,
            openhands_version="cloud-1.1.0",
            dry_run=False,
        )

        # Assert: file was modified
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

        assert get_chart_value(temp_runtime_api_chart_file, "version") == "0.1.21"
        assert new_version == "0.1.21"

    def test_preserves_other_fields(self, temp_runtime_api_chart_file):
        """Test that other fields are preserved."""
        update_runtime_api_chart(temp_runtime_api_chart_file)

        assert get_chart_value(temp_runtime_api_chart_file, "apiVersion") == "v2"
        assert get_chart_value(temp_runtime_api_chart_file, "name") == "runtime-api"
        assert get_chart_value(temp_runtime_api_chart_file, "appVersion") == "1.0.0"
        assert len(get_chart_value(temp_runtime_api_chart_file, "dependencies")) == 1

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

        assert_file_contains(temp_runtime_api_values_file, "tag: sha-abc1234")

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
        assert result.is_unchanged("runtime-api image tag")
        assert result.is_unchanged("runtime-api warmRuntimes image tag")

    def test_preserves_other_content(self, temp_runtime_api_values_file):
        """Test that other content is preserved."""
        update_runtime_api_values(
            temp_runtime_api_values_file,
            runtime_api_sha="abc1234567890def",
            openhands_version="cloud-1.1.0",
        )

        assert_file_contains_all(temp_runtime_api_values_file, [
            "replicaCount: 1",
            'working_dir: "/openhands/code/"',
        ])

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
        new_version, result = update_runtime_api_chart(temp_runtime_api_chart_file, has_changes=False)

        assert new_version == RUNTIME_API_CHART_MINIMAL_VERSION  # Version unchanged
        assert result.is_unchanged("runtime-api chart version")

    def test_version_bump_when_has_changes(self, temp_runtime_api_chart_file):
        """Test that chart version is bumped when has_changes is True."""
        new_version, result = update_runtime_api_chart(temp_runtime_api_chart_file, has_changes=True)

        expected_version = bump_patch_version(RUNTIME_API_CHART_MINIMAL_VERSION)
        assert new_version == expected_version  # Version bumped
        assert result.has_change_for("runtime-api chart version")


class TestMainOutputMessages:
    """Tests for main() output message formatting."""

    # Use a test constant to avoid magic strings scattered throughout tests
    MOCK_CLOUD_TAG = "cloud-1.20.0"

    def test_latest_cloud_tag_message_format(self, capsys, mock_main_early_exit):
        """Test that the latest cloud tag message uses correct format."""
        mock_tag = self.MOCK_CLOUD_TAG
        mock_main_early_exit(mock_tag)

        main(dry_run=True)

        captured = capsys.readouterr()
        assert f"OpenHands cloud tag: {mock_tag}" in captured.out

    def test_current_app_version_message_format(self, capsys, mock_main_early_exit):
        """Test that the current appVersion message uses correct format."""
        mock_tag = self.MOCK_CLOUD_TAG
        mock_main_early_exit(mock_tag)

        main(dry_run=True)

        captured = capsys.readouterr()
        assert f"OpenHands-Cloud openhands chart appVersion: {mock_tag}" in captured.out


class TestGetLatestCloudTag:
    """Tests for get_latest_cloud_tag function.

    Uses mocked GitHub API responses for fast, deterministic tests.
    """

    def test_returns_first_matching_cloud_tag(self, mock_github_tags):
        """Test that function returns the first cloud-X.Y.Z formatted tag."""
        mock_github_tags(["latest", "cloud-1.20.0", "cloud-1.19.0"])

        result = get_latest_cloud_tag("fake-token", "All-Hands-AI/OpenHands")

        assert result == "cloud-1.20.0"
        assert result.startswith("cloud-")
        assert extract_version_from_cloud_tag(result) == "1.20.0"

    def test_skips_non_cloud_tags(self, mock_github_tags):
        """Test that non-cloud tags are skipped."""
        mock_github_tags(["v1.0.0", "release-2.0", "cloud-1.5.0"])

        result = get_latest_cloud_tag("fake-token", "owner/repo")

        assert result == "cloud-1.5.0"

    def test_returns_none_when_no_cloud_tags(self, mock_github_tags):
        """Test that None is returned when no cloud tags exist."""
        mock_github_tags(["v1.0.0", "latest"])

        result = get_latest_cloud_tag("fake-token", "owner/repo")

        assert result is None

    def test_returns_none_for_invalid_repo(self, mock_github_tags, capsys):
        """Test that None is returned and error is printed for invalid repository."""
        mock_github_tags(repo_error=Exception("Repository not found"))

        result = get_latest_cloud_tag("fake-token", "nonexistent/repo")

        assert result is None
        captured = capsys.readouterr()
        assert "Error fetching tags" in captured.out

    def test_no_redirect_message_in_output(self, mock_github_tags, capsys):
        """Test that PyGithub redirect messages are suppressed."""
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
        _, mock_repo = mock_github_ref(tag_exists=True)

        result = cloud_tag_exists("fake-token", "All-Hands-AI/OpenHands", "cloud-1.20.0")

        assert result is True
        mock_repo.get_git_ref.assert_called_once_with("tags/cloud-1.20.0")

    def test_returns_false_when_tag_not_found(self, mock_github_ref):
        """Test that function returns False when get_git_ref raises exception."""
        mock_github_ref(tag_exists=False)

        result = cloud_tag_exists("fake-token", "All-Hands-AI/OpenHands", "cloud-99999.0.0")

        assert result is False

    def test_returns_false_for_invalid_repo(self, mock_github_ref):
        """Test that function returns False when repository doesn't exist."""
        mock_github_ref(repo_error=Exception("Repository not found"))

        result = cloud_tag_exists("fake-token", "nonexistent/repo", "cloud-1.0.0")

        assert result is False

    def test_handles_various_tag_formats(self, mock_github_ref):
        """Test that function correctly queries different tag formats."""
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
        monkeypatch.setattr(sys, "argv", ["script", "--cloud-tag", "cloud-1.2.0"])
        args = parse_args()
        assert args.cloud_tag == "cloud-1.2.0"

    def test_cloud_tag_default_is_none(self, monkeypatch):
        """Test that --cloud-tag defaults to None."""
        monkeypatch.setattr(sys, "argv", ["script"])
        args = parse_args()
        assert args.cloud_tag is None

    def test_dry_run_argument(self, monkeypatch):
        """Test that --dry-run argument works."""
        monkeypatch.setattr(sys, "argv", ["script", "--dry-run"])
        args = parse_args()
        assert args.dry_run is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
