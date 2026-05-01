# Description

Create a Slack app configured for the Replicated self-hosted install of OpenHands Enterprise (OHE).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) installed
- A Slack workspace where you have permission to create apps
- A Slack App Configuration Token (see [Getting a Token](#getting-a-token))

## Getting a Token

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. In the **Your App Configuration Tokens** section, click **Generate Token**
3. Select your workspace and click **Generate**
4. Copy the **access token** (starts with `xoxe.xoxp-`)

## Usage

```bash
./create_slack_app.py --base-domain <your-domain> --slack-token <xoxe.xoxp-...>
```

The token can also be provided via the `SLACK_CONFIG_TOKEN` environment variable:

```bash
export SLACK_CONFIG_TOKEN=xoxe.xoxp-...
./create_slack_app.py --base-domain <your-domain>
```

### Options

| Option | Description |
|--------|-------------|
| `--base-domain` | **(Required)** Base domain for your OHE installation (e.g., `mycompany.com`) |
| `--slack-token` | Slack App Configuration Token (`xoxe.xoxp-...`). Falls back to `SLACK_CONFIG_TOKEN` env var |
| `--app-name` | Display name for the Slack app (default: `OpenHands`) |
| `--dry-run` | Show what would be created without calling the Slack API |

### Example

```bash
./create_slack_app.py --base-domain mycompany.com --slack-token xoxe.xoxp-...
```

### Output

After successful creation, you'll receive:

- **Slack Client ID** - Used to configure the Slack integration in OHE
- **Slack Client Secret** - Keep this secret!
- **Slack Signing Secret** - Used to verify incoming Slack requests

## Permissions

### Bot Token Scopes

| Scope | Description |
|-------|-------------|
| `app_mentions:read` | View messages that directly mention the bot |
| `chat:write` | Send messages as the bot |
| `users:read` | View people in the workspace |
| `channels:history` | View messages in public channels |
| `groups:history` | View messages in private channels |
| `mpim:history` | View messages in group direct messages |
| `im:history` | View messages in direct messages |

## Configuration

The app is configured with:

- **Redirect URL**: `https://app.<base-domain>/slack/install-callback`
- **Event Subscription URL**: `https://app.<base-domain>/slack/on-event`
- **Interactivity Request URL**: `https://app.<base-domain>/slack/on-form-interaction`
- **Options Load URL**: `https://app.<base-domain>/slack/on-options-load`
- **Bot Events**: `app_mention`
- **Socket Mode**: Disabled
- **Org Deploy**: Disabled
