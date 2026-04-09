# Description

Create a GitHub App configured for OpenHands Enterprise (OHE).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) installed
- A GitHub account (you'll need to be signed in)

## Usage

```bash
./create_github_app.py --base-domain <your-domain>
```

### Options

| Option | Description |
|--------|-------------|
| `--base-domain` | **(Required)** Base domain for your OHE installation (e.g., `mycompany.com`) |
| `--app-name` | Custom name for the GitHub App (default: `openhands-<random>`) |

### Example

```bash
./create_github_app.py --base-domain mycompany.com
```

## How It Works

1. **Opens your browser** to GitHub's app creation page with a pre-configured manifest
2. **Click "Create GitHub App for \<your-username\>"** to create the app
3. **You'll see a 404 page** - this is expected! Copy the `code` parameter from the URL
4. **Paste the code** back into the terminal
5. **Credentials are displayed** and the private key is saved to `./keys/`

### Output

After successful creation, you'll receive:

- **GitHub App ID** - The numeric ID of your app
- **GitHub OAuth Client ID** - For OAuth authentication
- **GitHub OAuth Client Secret** - Keep this secret!
- **GitHub App Webhook Secret** - For webhook verification
- **Private Key** - Saved to `./keys/<app-name>.pem`

## Permissions

The created GitHub App requests the following permissions:

| Permission | Access | Description |
|------------|--------|-------------|
| Actions | Write | Manage GitHub Actions workflows |
| Contents | Write | Read and write repository contents |
| Email addresses | Read | Access user email addresses |
| Issues | Write | Manage issues |
| Metadata | Read | Access repository metadata |
| Organization events | Read | View organization activity |
| Pull requests | Write | Manage pull requests |
| Repository webhooks | Write | Manage repository webhooks |
| Commit statuses | Write | Update commit statuses |
| Workflows | Write | Manage workflow files |

## Configuration

The app is configured with:

- **Homepage URL**: `https://app.<base-domain>`
- **Callback URL**: `https://auth.app.<base-domain>/realms/allhands/broker/github/endpoint`
- **Webhook URL**: `https://app.<base-domain>/integration/github/events`
- **OAuth on install**: Enabled (users authorize during installation)
