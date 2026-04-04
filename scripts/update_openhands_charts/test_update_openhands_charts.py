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
from update_openhands_charts import (
    DeployConfig,
    SHORT_SHA_LENGTH,
    bump_patch_version,
    extract_version_from_cloud_tag,
    format_sha_tag,
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
    """Tests for get_short_sha function.

    Git short SHAs are conventionally 7 characters for readability while
    maintaining uniqueness in most repositories.

    TDD Rationale: Tests drive a simple slice operation. Boundary cases
    (exactly 7 chars, shorter than 7) ensure the implementation handles
    edge cases gracefully without raising IndexError.
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

    Container registries use 'sha-<hash>' tags to identify images built from
    specific commits. Note: Truncation behavior is tested in TestGetShortSha.
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
    """Tests for bump_patch_version function.

    Semantic versioning (semver) uses MAJOR.MINOR.PATCH format where
    patch bumps indicate backwards-compatible bug fixes.

    TDD Rationale: Tests drive a split-increment-join implementation.
    Invalid format tests ensure ValueError is raised early with clear
    messages, preventing silent corruption of chart versions.
    """

    @pytest.mark.parametrize("version,expected", [
        # Happy path: typical version increment
        ("1.2.3", "1.2.4"),
        # Boundary: patch starts at zero (common for new minor releases)
        ("1.0.0", "1.0.1"),
        # Boundary: 99→100 rollover - implementation must use int() not string ops
        ("1.2.99", "1.2.100"),
        # Verification: major/minor preserved during patch bump
        ("5.10.15", "5.10.16"),
    ])
    def test_patch_version_increments_by_one_preserving_major_minor(self, version, expected):
        """Verify patch bump increments only the patch component while preserving major.minor."""
        assert bump_patch_version(version) == expected

    @pytest.mark.parametrize("invalid_version", [
        # Structure: must have exactly 3 parts - fail fast on malformed input
        pytest.param("1.2", id="missing patch"),
        pytest.param("1.2.3.4", id="too many parts"),
        # Format: no prefixes allowed - caller must strip prefix first
        pytest.param("v1.2.3", id="has prefix"),
        # Edge cases: defensive handling prevents int() conversion errors
        pytest.param("", id="empty string"),
        pytest.param("1.2.abc", id="non-numeric patch"),
        pytest.param("a.b.c", id="all non-numeric"),
    ])
    def test_invalid_semver_format_raises_value_error(self, invalid_version):
        """Verify non-semver strings are rejected with clear error message."""
        with pytest.raises(ValueError, match="Invalid semver format"):
            bump_patch_version(invalid_version)


# =============================================================================
# CHART AND VALUES UPDATE TESTS
# Tests for functions that modify Chart.yaml and values.yaml files.
# These use temporary file fixtures and verify file content changes.
# =============================================================================


class TestUpdateChartAcrossVariants:
    """Tests for update_chart that verify behavior across both chart variants.

    Uses the parameterized openhands_chart_variant fixture to ensure core
    functionality works with both rich (with_deps) and minimal chart structures.

    Test Structure:
    - test_chart_app_version_updates: Core update behavior
    - test_chart_version_bumps: Version increment on change
    - test_runtime_api_dependency: Dependency update
    - test_version_unchanged_when_already_current: Consolidated idempotency checks

    TDD Rationale: Tests drive the update_openhands_chart function to handle
    both minimal and full Chart.yaml structures. Parameterized variants ensure
    the implementation doesn't accidentally depend on optional fields (like
    maintainers or extra dependencies) that may not exist in all chart files.
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

    @pytest.mark.parametrize("app_version,runtime_api_version,unchanged_key", [
        # When appVersion already matches target, it should be reported as unchanged
        pytest.param(
            OPENHANDS_CHART_APP_VERSION, NEW_RUNTIME_API_VERSION, "appVersion",
            id="appVersion unchanged when already current"
        ),
        # When runtime-api version already matches target, it should be reported as unchanged
        pytest.param(
            NEW_APP_VERSION, OPENHANDS_CHART_RUNTIME_API_VERSION, "runtime-api version",
            id="runtime-api version unchanged when already current"
        ),
    ])
    def test_version_unchanged_when_already_current(
        self, temp_chart_file, app_version, runtime_api_version, unchanged_key
    ):
        """Verify no change is recorded when a version already matches target.

        Idempotency verification: Ensures the update function correctly identifies
        when values are already at their target state, preventing spurious version
        bumps and unnecessary commits in CI/CD pipelines.
        """
        result = update_openhands_chart(temp_chart_file, app_version, runtime_api_version)

        assert result.is_unchanged(unchanged_key)

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
    """Tests for update_chart function with specific fixture requirements.

    These tests require the with_deps fixture specifically because they test
    features only present in that variant (e.g., multiple dependencies, maintainers).

    TDD Rationale: Tests drive selective dependency updates - only runtime-api
    should be modified while other dependencies remain untouched. This prevents
    accidental side effects when updating charts with multiple dependencies.
    """

    @pytest.fixture
    def temp_chart_file(self, make_temp_yaml_file, sample_openhands_chart_with_deps):
        """Create a temporary Chart.yaml file using shared fixtures."""
        return make_temp_yaml_file(sample_openhands_chart_with_deps)

        assert get_dependency_version(temp_chart_file, "other-dep") == OPENHANDS_CHART_WITH_DEPS_OTHER_DEP_VERSION

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
        assert get_chart_value(temp_chart_file, "apiVersion") == "v2"
        assert get_chart_value(temp_chart_file, "description") == "Test chart"
        assert get_chart_value(temp_chart_file, "name") == "test-chart"
        assert len(get_chart_value(temp_chart_file, "maintainers")) == 1
        assert len(get_chart_value(temp_chart_file, "dependencies")) == 2


class TestDeployConfig:
    """Tests for DeployConfig dataclass.

    def test_deploy_config_creation(self):
        """Test that DeployConfig can be created with runtime_api_sha field."""
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


        assert result.has_changes is True

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
        # Arrange: capture original state
        original_content = temp_chart_file.read_text()

        # Act: run update with dry_run=True
        update_openhands_chart(temp_chart_file, NEW_APP_VERSION, NEW_RUNTIME_API_VERSION, dry_run=True)

        # Assert: file unchanged
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

        changed_keys = [c[0] for c in result.changes]
        assert "enterprise-server image tag" in changed_keys
        assert "runtime image tag" in changed_keys
        assert "warmRuntimes image tag" in changed_keys

    def test_update_chart_without_dry_run_modifies_file(self, temp_chart_file):
        """Test that without dry-run, Chart.yaml is modified."""
        # Arrange: capture original state
        original_content = temp_chart_file.read_text()

        # Act: run update with dry_run=False (default behavior)
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

    def test_returns_first_matching_cloud_tag(self, monkeypatch):
        """Test that function returns the first cloud-X.Y.Z formatted tag."""
        from unittest.mock import MagicMock

        from update_openhands_charts import get_latest_cloud_tag

        # Create mock tags - first matching cloud tag should be returned
        mock_tags = [
            MagicMock(name="latest"),
            MagicMock(name="cloud-1.20.0"),
            MagicMock(name="cloud-1.19.0"),
        ]
        # MagicMock uses 'name' for its own purposes, so set it explicitly
        mock_tags[0].name = "latest"
        mock_tags[1].name = "cloud-1.20.0"
        mock_tags[2].name = "cloud-1.19.0"

        mock_repo = MagicMock()
        mock_repo.get_tags.return_value = mock_tags

        mock_github = MagicMock()
        mock_github.get_repo.return_value = mock_repo

        monkeypatch.setattr("update_openhands_charts.Github", lambda auth: mock_github)

        result = get_latest_cloud_tag("fake-token", "All-Hands-AI/OpenHands")

        assert result == "cloud-1.20.0"
        assert result.startswith("cloud-")
        assert extract_version_from_cloud_tag(result) == "1.20.0"

    def test_skips_non_cloud_tags(self, monkeypatch):
        """Test that non-cloud tags are skipped."""
        from unittest.mock import MagicMock

        from update_openhands_charts import get_latest_cloud_tag

        mock_tags = [
            MagicMock(name="v1.0.0"),
            MagicMock(name="release-2.0"),
            MagicMock(name="cloud-1.5.0"),
        ]
        mock_tags[0].name = "v1.0.0"
        mock_tags[1].name = "release-2.0"
        mock_tags[2].name = "cloud-1.5.0"

        mock_repo = MagicMock()
        mock_repo.get_tags.return_value = mock_tags

        mock_github = MagicMock()
        mock_github.get_repo.return_value = mock_repo

        monkeypatch.setattr("update_openhands_charts.Github", lambda auth: mock_github)

        result = get_latest_cloud_tag("fake-token", "owner/repo")

        assert result == "cloud-1.5.0"

    def test_returns_none_when_no_cloud_tags(self, monkeypatch):
        """Test that None is returned when no cloud tags exist."""
        from unittest.mock import MagicMock

        from update_openhands_charts import get_latest_cloud_tag

        mock_tags = [
            MagicMock(name="v1.0.0"),
            MagicMock(name="latest"),
        ]
        mock_tags[0].name = "v1.0.0"
        mock_tags[1].name = "latest"

        mock_repo = MagicMock()
        mock_repo.get_tags.return_value = mock_tags

        mock_github = MagicMock()
        mock_github.get_repo.return_value = mock_repo

        monkeypatch.setattr("update_openhands_charts.Github", lambda auth: mock_github)

        result = get_latest_cloud_tag("fake-token", "owner/repo")

        assert result is None

    def test_returns_none_for_invalid_repo(self, monkeypatch, capsys):
        """Test that None is returned and error is printed for invalid repository."""
        from unittest.mock import MagicMock

        from update_openhands_charts import get_latest_cloud_tag

        mock_github = MagicMock()
        mock_github.get_repo.side_effect = Exception("Repository not found")

        monkeypatch.setattr("update_openhands_charts.Github", lambda auth: mock_github)

        result = get_latest_cloud_tag("fake-token", "nonexistent/repo")

        assert result is None
        captured = capsys.readouterr()
        assert "Error fetching tags" in captured.out

    def test_no_redirect_message_in_output(self, monkeypatch, capsys):
        """Test that PyGithub redirect messages are suppressed."""
        from unittest.mock import MagicMock

        from update_openhands_charts import get_latest_cloud_tag

        mock_tags = [MagicMock(name="cloud-1.0.0")]
        mock_tags[0].name = "cloud-1.0.0"

        mock_repo = MagicMock()
        mock_repo.get_tags.return_value = mock_tags

        mock_github = MagicMock()
        mock_github.get_repo.return_value = mock_repo

        monkeypatch.setattr("update_openhands_charts.Github", lambda auth: mock_github)

        get_latest_cloud_tag("fake-token", "owner/repo")

        captured = capsys.readouterr()
        assert "redirect" not in captured.out.lower()
        assert "following" not in captured.out.lower()


class TestCloudTagExists:
    """Tests for cloud_tag_exists function.

    Uses mocked GitHub API responses for fast, deterministic tests.
    """

    def test_returns_true_when_tag_exists(self, monkeypatch):
        """Test that function returns True when the tag reference is found."""
        from unittest.mock import MagicMock

        from update_openhands_charts import cloud_tag_exists

        mock_repo = MagicMock()
        mock_repo.get_git_ref.return_value = MagicMock()  # Success - tag exists

        mock_github = MagicMock()
        mock_github.get_repo.return_value = mock_repo

        monkeypatch.setattr("update_openhands_charts.Github", lambda auth: mock_github)

        result = cloud_tag_exists("fake-token", "All-Hands-AI/OpenHands", "cloud-1.20.0")

        assert result is True
        mock_repo.get_git_ref.assert_called_once_with("tags/cloud-1.20.0")

    def test_returns_false_when_tag_not_found(self, monkeypatch):
        """Test that function returns False when get_git_ref raises exception."""
        from unittest.mock import MagicMock

        from update_openhands_charts import cloud_tag_exists

        mock_repo = MagicMock()
        mock_repo.get_git_ref.side_effect = Exception("Not found")

        mock_github = MagicMock()
        mock_github.get_repo.return_value = mock_repo

        monkeypatch.setattr("update_openhands_charts.Github", lambda auth: mock_github)

        result = cloud_tag_exists("fake-token", "All-Hands-AI/OpenHands", "cloud-99999.0.0")

        assert result is False

    def test_returns_false_for_invalid_repo(self, monkeypatch):
        """Test that function returns False when repository doesn't exist."""
        from unittest.mock import MagicMock

        from update_openhands_charts import cloud_tag_exists

        mock_github = MagicMock()
        mock_github.get_repo.side_effect = Exception("Repository not found")

        monkeypatch.setattr("update_openhands_charts.Github", lambda auth: mock_github)

        result = cloud_tag_exists("fake-token", "nonexistent/repo", "cloud-1.0.0")

        assert result is False

    def test_handles_various_tag_formats(self, monkeypatch):
        """Test that function correctly queries different tag formats."""
        from unittest.mock import MagicMock

        from update_openhands_charts import cloud_tag_exists

        mock_repo = MagicMock()
        mock_repo.get_git_ref.return_value = MagicMock()

        mock_github = MagicMock()
        mock_github.get_repo.return_value = mock_repo

        monkeypatch.setattr("update_openhands_charts.Github", lambda auth: mock_github)

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
