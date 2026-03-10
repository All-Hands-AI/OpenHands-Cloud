# OpenHands Secrets Chart

This Helm chart creates Kubernetes `Secret` resources for all sensitive OpenHands configuration: database passwords, API keys, OAuth credentials, TLS certificates, and more.

## When is this chart used?

This chart is **only** used when deploying OpenHands with [Replicated](https://www.replicated.com/). In a Replicated deployment, secrets are materialized from the Replicated config screen _before_ the main `openhands` chart is installed.

If you are **not** using Replicated, you do not need this chart. Instead, create the required secrets directly via `kubectl create secret` or your own automation (e.g., Terraform, External Secrets Operator, sealed-secrets).

## Configuration

All configurable values are defined in:

| File | Description |
|------|-------------|
| [`values.yaml`](values.yaml) | Default values for every secret field |
| [`values.schema.json`](values.schema.json) | JSON Schema used by Replicated to render the config screen |

## Templates

The chart includes templates for the following secrets:

| Template | Secret |
|----------|--------|
| `admin-password.yaml` | OpenHands admin password |
| `bitbucket-data-center-app.yaml` | Bitbucket Data Center app credentials |
| `clickhouse-password.yaml` | ClickHouse database password |
| `default-api-key.yaml` | Default API key |
| `github-app.yaml` | GitHub App credentials |
| `jwt-secret.yaml` | JWT signing secret |
| `keycloak-admin.yaml` | Keycloak admin credentials |
| `keycloak-realm.yaml` | Keycloak realm configuration |
| `langfuse-nextauth.yaml` | Langfuse NextAuth secret |
| `langfuse-salt.yaml` | Langfuse encryption salt |
| `lite-llm-api-key.yaml` | LiteLLM API key |
| `litellm-env-secrets.yaml` | LiteLLM environment secrets |
| `openhands-env-secrets.yaml` | OpenHands environment secrets |
| `postgres-password.yaml` | PostgreSQL password |
| `redis.yaml` | Redis credentials |
| `s3-credentials.yaml` | S3-compatible storage credentials |
| `sandbox-api-key.yaml` | Sandbox API key |
| `tls-certificate.yaml` | TLS certificate and private key |
