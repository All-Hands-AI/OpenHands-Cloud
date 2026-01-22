# Scripts

## update-openhands-chart.py

Updates the OpenHands helm charts to cut a new release.

### Prerequisites

- [uv](https://docs.astral.sh/uv/) must be installed
- A GitHub token with read access to the OpenHands repository

### Usage

1. Set the `GITHUB_TOKEN` environment variable:

   ```bash
   export GITHUB_TOKEN=your_github_token
   ```

2. Run the script:

   ```bash
   ./scripts/update-openhands-chart.py
   ```

   Or using uv directly:

   ```bash
   uv run scripts/update-openhands-chart.py
   ```

The script will fetch the latest semantic version tag (format: `x.y.z`) from the OpenHands repository and update the `appVersion` field in the Helm chart.
