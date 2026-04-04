"""Shared pytest fixtures for update_openhands_charts tests.

This module provides reusable fixtures for creating temporary YAML files
used across multiple test classes, reducing duplication and improving
maintainability.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def assert_file_contains_all(file_path: Path, expected_strings: list[str]) -> None:
    """Assert that a file contains all expected strings.

    This helper is useful for testing that YAML/config file modifications
    preserve expected content that should not be changed.

    Args:
        file_path: Path to the file to check
        expected_strings: List of strings that must appear in the file

    Raises:
        AssertionError: If any expected string is not found in the file
    """
    content = file_path.read_text()
    for expected in expected_strings:
        assert expected in content, f"Expected '{expected}' not found in file"


@pytest.fixture
def make_temp_yaml_file():
    """Factory fixture that creates temporary YAML files with cleanup.

    Returns a function that accepts YAML content and returns a Path to a
    temporary file. The file is automatically cleaned up after the test.

    Usage:
        def test_something(make_temp_yaml_file):
            yaml_content = '''
            apiVersion: v2
            name: test
            '''
            temp_file = make_temp_yaml_file(yaml_content)
            # Use temp_file...
    """
    created_files = []

    def _make_temp_file(content: str) -> Path:
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        f.write(content)
        f.flush()
        f.close()
        path = Path(f.name)
        created_files.append(path)
        return path

    yield _make_temp_file

    # Cleanup all created files
    for path in created_files:
        path.unlink(missing_ok=True)


# =============================================================================
# Common Chart.yaml fixtures
# =============================================================================

@pytest.fixture
def sample_openhands_chart_with_deps():
    """Sample openhands Chart.yaml with runtime-api dependency."""
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
def sample_openhands_chart_minimal():
    """Minimal openhands Chart.yaml for simple tests."""
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
def sample_runtime_api_chart_full():
    """Sample runtime-api Chart.yaml with all fields."""
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
def sample_runtime_api_chart_minimal():
    """Minimal runtime-api Chart.yaml for version bump tests."""
    return """\
apiVersion: v2
appVersion: 0.1.0
version: 0.2.6
name: runtime-api
"""


# =============================================================================
# Common values.yaml fixtures
# =============================================================================

@pytest.fixture
def sample_openhands_values_full():
    """Sample openhands values.yaml with all image tags."""
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
def sample_openhands_values_minimal():
    """Minimal openhands values.yaml for dry-run tests."""
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
def sample_runtime_api_values():
    """Sample runtime-api values.yaml."""
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


# =============================================================================
# GitHub API mock fixtures
# =============================================================================

def _make_mock_tag(name: str) -> MagicMock:
    """Create a mock tag with the given name.

    MagicMock uses 'name' for its own purposes, so we must set it explicitly
    after creation.
    """
    tag = MagicMock()
    tag.name = name
    return tag


@pytest.fixture
def mock_github_tags(monkeypatch):
    """Factory fixture for mocking GitHub API with tags.

    Returns a function that sets up the GitHub mock and returns the mock objects
    for additional assertions.

    Usage:
        def test_something(mock_github_tags):
            mock_github, mock_repo = mock_github_tags(["cloud-1.0.0", "latest"])
            # ... test code ...
            mock_repo.get_tags.assert_called_once()
    """
    def _mock_github(tag_names: list[str] | None = None, repo_error: Exception | None = None):
        mock_github = MagicMock()

        if repo_error:
            mock_github.get_repo.side_effect = repo_error
        else:
            mock_tags = [_make_mock_tag(name) for name in (tag_names or [])]
            mock_repo = MagicMock()
            mock_repo.get_tags.return_value = mock_tags
            mock_github.get_repo.return_value = mock_repo

        monkeypatch.setattr("update_openhands_charts.Github", lambda auth: mock_github)

        # Return mock objects for assertions
        if repo_error:
            return mock_github, None
        return mock_github, mock_github.get_repo.return_value

    return _mock_github


@pytest.fixture
def mock_github_ref(monkeypatch):
    """Factory fixture for mocking GitHub API git ref lookups.

    Returns a function that sets up the GitHub mock for tag existence checks.

    Usage:
        def test_tag_exists(mock_github_ref):
            mock_github, mock_repo = mock_github_ref(tag_exists=True)
            # ... test code ...
            mock_repo.get_git_ref.assert_called_once_with("tags/cloud-1.0.0")
    """
    def _mock_github(
        tag_exists: bool = True,
        repo_error: Exception | None = None,
        ref_error: Exception | None = None,
    ):
        mock_github = MagicMock()

        if repo_error:
            mock_github.get_repo.side_effect = repo_error
        else:
            mock_repo = MagicMock()
            if ref_error or not tag_exists:
                mock_repo.get_git_ref.side_effect = ref_error or Exception("Not found")
            else:
                mock_repo.get_git_ref.return_value = MagicMock()
            mock_github.get_repo.return_value = mock_repo

        monkeypatch.setattr("update_openhands_charts.Github", lambda auth: mock_github)

        if repo_error:
            return mock_github, None
        return mock_github, mock_github.get_repo.return_value

    return _mock_github
