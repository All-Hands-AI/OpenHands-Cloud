# Staging Path-Route Environment Configuration

This directory contains the configuration for deploying OpenHands to the **staging-pathroute** environment.

## Environment Overview

This environment uses **path-based routing**:
- Main app: `https://staging-pathroute.all-hands.dev/`
- Automation API: `https://staging-pathroute.all-hands.dev/api/automation`
- Integrations: `https://staging-pathroute.all-hands.dev/integration/*`
- MCP: `https://staging-pathroute.all-hands.dev/mcp/mcp`

## Directory Structure

```
envs/staging-pathroute/
├── README.md           # This file
├── values.yaml         # Helm values (non-secret configuration)
└── secrets/            # SOPS-encrypted Kubernetes secrets
    └── *.yaml          # Individual secret files
```

## Kubernetes Details

- **Namespace:** `openhands-pathroute`
- **Helm Release:** `openhands-pathroute`
- **GCP Project:** `staging-092324`
- **GKE Cluster:** `staging-core-application`
- **Zone:** `us-central1`

## Secrets Management

Secrets are encrypted using [SOPS](https://github.com/getsops/sops) with GCP KMS encryption.

### Required Secrets

The following secrets must be created in `secrets/` before deployment:

| Secret Name | Description | Required Keys |
|-------------|-------------|---------------|
| `ghcr-login-secret` | GitHub Container Registry pull credentials | `.dockerconfigjson` |
| `lite-llm-api-key` | LiteLLM API key | `api-key` |
| `stripe-api-key` | Stripe API key | `api-key` |
| `resend-api-key` | Resend email API key | `api-key` |
| `bitbucket-app` | Bitbucket OAuth app credentials | `client-id`, `client-secret` |
| `automation-service-key` | Automation service authentication key | `automation-service-key` |
| `automation-db-secret` | Automation database password | `db-password` |
| `keycloak-realm` | Keycloak realm credentials | `client-id`, `client-secret` |

### Creating/Editing Secrets

```bash
# Create a new SOPS-encrypted secret
cat <<EOF > /tmp/my-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: my-secret
type: Opaque
stringData:
  key: "value"
EOF
sops --encrypt /tmp/my-secret.yaml > envs/staging-pathroute/secrets/my-secret.yaml

# Edit (decrypts, opens editor, re-encrypts on save)
sops envs/staging-pathroute/secrets/my-secret.yaml

# View decrypted content
sops --decrypt envs/staging-pathroute/secrets/my-secret.yaml
```

## Deployment

Use the GitHub Actions workflow:

1. Go to **Actions** → **Deploy to Staging**
2. Click **Run workflow**
3. Select environment: `pathroute` or `both`
4. Enter the image tag to deploy

### Workflow Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image_tag` | OpenHands image tag to deploy | `main` |
| `environment` | Which environment(s) to deploy | `both` |
| `skip_secrets` | Skip applying secrets | `false` |
| `dry_run` | Template only, don't deploy | `false` |

## Troubleshooting

```bash
# Check pods
kubectl get pods -n openhands-pathroute

# Check Helm release
helm history openhands-pathroute -n openhands-pathroute

# Check ingress
kubectl get ingress -n openhands-pathroute

# GCP auth for SOPS
gcloud auth application-default login
```
