# Description

Updates the OpenHands helm charts to cut a new release.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) must be installed
- A GitHub token with read access to the OpenHands repository

## Usage

1. Set the `GITHUB_TOKEN` environment variable:

   ```bash
   export GITHUB_TOKEN=your_github_token
   ```

   > Try getting with: `gh auth status --show-token`

2. Run the script:

   ```bash
   ./scripts/update-openhands-chart.py
   ```

   Or using uv directly:

   ```bash
   uv run scripts/update-openhands-chart.py
   ```

### DRY RUN mode

```bash
./scripts/update-openhands-chart.py --dry-run
```

Or using uv directly:

```bash
uv run scripts/update-openhands-chart.py --dry-run
```

## Tests

Run the tests:

```bash
./scripts/test_update_openhands_chart.py
```

Or using uv directly:

```bash
uv run scripts/test_update_openhands_chart.py
```
