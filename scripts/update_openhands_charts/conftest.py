"""Shared pytest fixtures for update_openhands_charts tests.

This module provides reusable fixtures for creating temporary YAML files
used across multiple test classes, reducing duplication and improving
maintainability.
"""

import tempfile
from pathlib import Path

import pytest


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
