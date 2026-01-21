# Scripts

## update-openhands-chart.py

Updates the `appVersion` in `charts/openhands/Chart.yaml` to the latest semantic version tag from the OpenHands repository.

### Prerequisites

- [uv](https://docs.astral.sh/uv/) must be installed
- A GitHub token with read access to the OpenHands repository

### Usage

1. Set the `GITHUB_TOKEN` environment variable:

   ```bash
   export GITHUB_TOKEN=your_github_token
   ```

   > **Note:** Without a valid `GITHUB_TOKEN`, the script will be subject to GitHub API rate limits (60 requests/hour for unauthenticated requests). Setting a token increases this limit significantly.

2. Run the script:

   ```bash
   ./scripts/update-openhands-chart.py
   ```

   Or using uv directly:

   ```bash
   uv run scripts/update-openhands-chart.py
   ```

The script will fetch the latest semantic version tag (format: `x.y.z`) from the OpenHands repository and update the `appVersion` field in the Helm chart.
