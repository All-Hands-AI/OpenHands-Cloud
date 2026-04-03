#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyGithub", "ruamel.yaml", "requests", "pytest"]
# ///
"""Unit tests for update_openhands_charts.py."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

# Add the script's directory to sys.path so we can import it directly
sys.path.insert(0, str(Path(__file__).parent))

import update_openhands_charts
from update_openhands_charts import (
    CLOUD_SEMVER_PATTERN,
    DeployConfig,
    SEMVER_PATTERN,
    SHORT_SHA_LENGTH,
    bump_patch_version,
    format_sha_tag,
    get_short_sha,
    update_openhands_chart,
    update_openhands_values,
    update_runtime_api_chart,
    update_runtime_api_values,
)


# =============================================================================
# PURE FUNCTION TESTS
# Tests for stateless utility functions with no external dependencies.
# These tests are fast, deterministic, and test behavior through public APIs.
# =============================================================================


class TestExtractVersionFromCloudTag:
    """Tests for extract_version_from_cloud_tag function.

    OpenHands uses 'cloud-X.Y.Z' tags to identify production releases.
    These tests verify cloud tag parsing through the public interface rather
    than testing internal regex patterns directly. This approach is more
    maintainable as it tests behavior, not implementation.

    TDD Rationale: Tests were designed to drive a simple regex pattern that
    accepts only the strict 'cloud-X.Y.Z' format. Edge cases ensure the
    implementation rejects common variations (v-prefix, pre-release suffixes)
    that could cause version comparison bugs in production.
    """

    @pytest.mark.parametrize("cloud_tag,expected", [
        # Happy path: typical production versions
        ("cloud-1.1.0", "1.1.0"),
        ("cloud-2.0.0", "2.0.0"),
        # Boundary: minimum valid version (all zeros) - ensures 0.0.0 is valid
        ("cloud-0.0.0", "0.0.0"),
        # Boundary: multi-digit components - regex must use \d+ not \d
        ("cloud-10.20.30", "10.20.30"),
        # Stress test: very large versions - ensures no arbitrary numeric limits
        ("cloud-123.456.789", "123.456.789"),
    ])
    def test_extracts_version_from_valid_cloud_tags(self, cloud_tag, expected):
        """Verify semver is correctly extracted from 'cloud-X.Y.Z' format tags."""
        assert extract_version_from_cloud_tag(cloud_tag) == expected

    @pytest.mark.parametrize("invalid_tag", [
        # Prefix validation: must be exactly "cloud-" (case-sensitive, with hyphen)
        pytest.param("1.1.0", id="missing cloud- prefix"),
        pytest.param("v1.1.0", id="wrong prefix (v instead of cloud-)"),
        pytest.param("Cloud-1.2.3", id="wrong case"),
        pytest.param("cloud1.2.3", id="missing hyphen"),
        # Semver structure: must be exactly X.Y.Z (three numeric parts)
        pytest.param("cloud-1.2", id="missing patch"),
        pytest.param("cloud-1.2.3.4", id="extra part"),
        # Semver extensions: pre-release/build metadata breaks version comparison
        pytest.param("cloud-1.2.3-beta", id="pre-release suffix"),
        pytest.param("cloud-1.2.3+build", id="build metadata suffix"),
        # Edge cases: defensive handling of malformed input
        pytest.param("", id="empty string"),
        pytest.param("latest", id="non-version tag"),
        pytest.param("cloud-", id="missing version"),
    ])
    def test_returns_none_for_invalid_cloud_tag_formats(self, invalid_tag):
        """Verify invalid formats return None rather than raising exceptions.

        TDD Rationale: Returning None (instead of raising) allows callers to
        safely filter cloud tags from mixed tag lists without try/except blocks.
        """
        assert extract_version_from_cloud_tag(invalid_tag) is None


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

    def test_non_runtime_api_dependencies_remain_unchanged(self, temp_chart_file):
        """Verify only runtime-api dependency is modified; other deps are preserved."""
        update_openhands_chart(temp_chart_file, NEW_APP_VERSION, NEW_RUNTIME_API_VERSION)

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


# =============================================================================
# TEST HELPER FUNCTION TESTS
# Tests for helper functions defined in conftest.py that are used by other tests.
# These verify the test infrastructure itself works correctly.
# =============================================================================

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
    def mock_successful_response(self):
        """Create a mock response with valid workflow content."""
        encoded_content = base64.b64encode(self.VALID_WORKFLOW_YAML.encode()).decode()
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"content": encoded_content}
        return mock_response

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

    def test_reports_error_when_enterprise_server_tag_missing(self, make_temp_yaml_file):
        """Test that error is reported when enterprise-server image tag pattern not found.

        Edge case rationale: The enterprise-server image is the main OpenHands backend.
        If this pattern is missing, the chart update would silently skip updating the
        core application version, leading to version drift between Chart.yaml appVersion
        and the actual deployed container. Early error reporting prevents silent failures.
        """
        # YAML without enterprise-server image section - simulates misconfigured values.yaml
        values_content = """\
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
        temp_file = make_temp_yaml_file(values_content)

        result = update_openhands_values(
            temp_file,
            openhands_version="cloud-1.1.0",
            runtime_image_tag="cloud-1.1.0-nikolaik",
        )

        assert result.has_error_containing("Could not find enterprise-server image tag")

    def test_reports_error_when_runtime_tag_missing(self, make_temp_yaml_file):
        """Test that error is reported when runtime image tag pattern not found.

        Edge case rationale: The runtime image runs user code in sandboxed containers.
        Version mismatch between enterprise-server and runtime can cause compatibility
        issues (API changes, protocol mismatches). Detecting missing runtime patterns
        ensures both images stay synchronized during updates.
        """
        # YAML without runtime image section - enterprise-server present but runtime missing
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

        result = update_openhands_values(
            temp_file,
            openhands_version="cloud-1.1.0",
            runtime_image_tag="cloud-1.1.0-nikolaik",
        )

        assert result.has_error_containing("Could not find runtime image tag")

    def test_reports_error_when_warm_runtimes_tag_missing(self, make_temp_yaml_file):
        """Test that error is reported when warmRuntimes image tag pattern not found.

        Edge case rationale: warmRuntimes pre-provisions runtime containers for faster
        cold starts. If this image isn't updated but runtime is, pre-warmed containers
        would run stale versions until recycled. This creates inconsistent behavior
        where some requests use new runtime and others use old pre-warmed instances.
        """
        # YAML with warmRuntimes disabled - pattern missing but section exists
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

        result = update_openhands_values(
            temp_file,
            openhands_version="cloud-1.1.0",
            runtime_image_tag="cloud-1.1.0-nikolaik",
        )

        assert result.has_error_containing("Could not find warmRuntimes image tag")

    def test_collects_multiple_errors_when_multiple_patterns_missing(self, make_temp_yaml_file):
        """Test that all missing patterns are reported as errors.

        Edge case rationale: When values.yaml is severely malformed or from an
        incompatible chart version, multiple patterns will be missing. Collecting
        ALL errors (not just the first) allows operators to fix all issues in one
        pass rather than discovering them one-by-one through repeated runs.
        """
        # Minimal YAML with none of the expected patterns - completely wrong structure
        values_content = """\
replicaCount: 1
serviceAccount:
  create: true
"""
        temp_file = make_temp_yaml_file(values_content)

        result = update_openhands_values(
            temp_file,
            openhands_version="cloud-1.1.0",
            runtime_image_tag="cloud-1.1.0-nikolaik",
        )

        assert result.error_count == 3
        assert result.has_error_containing("enterprise-server")
        assert result.has_error_containing("runtime image tag")
        assert result.has_error_containing("warmRuntimes")


class TestConditionalChartVersionBump:
    """Tests for conditional chart version bumping across both chart types.

    Both openhands and runtime-api charts use the same pattern: only bump
    the chart version when has_changes=True. This consolidates testing of
    that behavior to reduce redundancy (Necessary property).

    TDD Rationale: These tests drive the has_changes flag behavior that
    prevents unnecessary version bumps when only checking for updates.
    """

    @pytest.fixture
    def temp_openhands_chart_file(self, make_temp_yaml_file, sample_openhands_chart_minimal):
        """Create a temporary openhands Chart.yaml file."""
        return make_temp_yaml_file(sample_openhands_chart_minimal)

    @pytest.fixture
    def temp_runtime_api_chart_file(self, make_temp_yaml_file, sample_runtime_api_chart_minimal):
        """Create a temporary runtime-api Chart.yaml file."""
        return make_temp_yaml_file(sample_runtime_api_chart_minimal)

    # --- Openhands chart tests ---

    def test_openhands_no_version_bump_when_no_changes(self, temp_openhands_chart_file):
        """Test that openhands chart version is not bumped when has_changes is False."""
        result = update_openhands_chart(
            temp_openhands_chart_file,
            new_app_version=OPENHANDS_CHART_APP_VERSION,
            new_runtime_api_version=OPENHANDS_CHART_RUNTIME_API_VERSION,
            has_changes=False,
        )

        assert get_chart_value(temp_openhands_chart_file, "version") == OPENHANDS_CHART_VERSION
        assert get_chart_value(temp_openhands_chart_file, "appVersion") == OPENHANDS_CHART_APP_VERSION
        assert result.is_unchanged("openhands chart version")

    def test_openhands_version_bump_when_has_changes(self, temp_openhands_chart_file):
        """Test that openhands chart version is bumped when has_changes is True."""
        result = update_openhands_chart(
            temp_openhands_chart_file,
            new_app_version="cloud-1.1.0",
            new_runtime_api_version="0.2.7",
            has_changes=True,
        )

        assert get_chart_value(temp_openhands_chart_file, "version") == "0.1.1"  # Bumped from 0.1.0
        assert get_chart_value(temp_openhands_chart_file, "appVersion") == "cloud-1.1.0"
        assert result.has_change_for("appVersion")
        assert result.has_change_for("version")

    # --- Runtime-api chart tests ---

    def test_runtime_api_no_version_bump_when_no_changes(self, temp_runtime_api_chart_file):
        """Test that runtime-api chart version is not bumped when has_changes is False."""
        new_version, result = update_runtime_api_chart(temp_runtime_api_chart_file, has_changes=False)

        assert new_version == RUNTIME_API_CHART_MINIMAL_VERSION  # Version unchanged
        assert result.is_unchanged("runtime-api chart version")

    def test_runtime_api_version_bump_when_has_changes(self, temp_runtime_api_chart_file):
        """Test that runtime-api chart version is bumped when has_changes is True."""
        new_version, result = update_runtime_api_chart(temp_runtime_api_chart_file, has_changes=True)

        expected_version = bump_patch_version(RUNTIME_API_CHART_MINIMAL_VERSION)
        assert new_version == expected_version  # Version bumped
        assert result.has_change_for("runtime-api chart version")


class TestDryRun:
    """Tests for dry-run functionality.

    Dry-run mode allows users to preview changes without modifying files.
    These tests verify that:
    1. Files remain unchanged when dry_run=True
    2. Return values still reflect what *would* change
    3. Files are modified when dry_run=False (control tests)

    Test Structure:
    - test_*_dry_run_no_file_changes: File content unchanged
    - test_*_dry_run_prints_changes: Return value reflects changes
    - test_*_without_dry_run_modifies_file: Control to verify normal behavior

    TDD Rationale: Tests drive the dry_run parameter behavior, ensuring
    separation between change detection (always happens) and file writing
    (only when dry_run=False). Control tests verify the default behavior
    hasn't regressed.
    """

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

    def test_latest_cloud_tag_message_format(self, capsys, monkeypatch):
        """Test that the latest cloud tag message uses correct format."""
        from update_openhands_charts import main

        # Mock GITHUB_TOKEN environment variable
        monkeypatch.setenv("GITHUB_TOKEN", "dummy-token")

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

    def test_current_app_version_message_format(self, capsys, monkeypatch):
        """Test that the current appVersion message uses correct format."""
        from update_openhands_charts import main

        # Mock GITHUB_TOKEN environment variable
        monkeypatch.setenv("GITHUB_TOKEN", "dummy-token")

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
        assert "OpenHands-Cloud openhands chart appVersion: cloud-1.20.0" in captured.out


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
