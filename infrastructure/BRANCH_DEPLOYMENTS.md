# Deploying Your Branch to Staging

This guide explains how to deploy your own branch of OpenHands to the shared staging clusters.

## Overview

The staging infrastructure supports multiple simultaneous deployments using **Helm release isolation**. Each developer can deploy their own branch with a unique release name, and the ingress controller routes traffic based on subdomain or path prefixes.

### How It Works

1. **Helm Release Isolation**: Each deployment uses a unique Helm release name (e.g., `openhands-yourname`)
2. **Namespace Isolation**: Each deployment gets its own Kubernetes namespace
3. **Subdomain Routing**: For subdomain-based clusters, your deployment is accessible at `your-branch.staging.example.com`
4. **Path Routing**: For path-based clusters, services are differentiated by release name

## Prerequisites

1. **Cluster Access**: Get kubectl credentials for the staging cluster:
   ```bash
   gcloud container clusters get-credentials ohe-staging-path \
     --region us-central1 \
     --project staging-092324
   ```

2. **Helm**: Install Helm 3.x: https://helm.sh/docs/intro/install/

3. **Docker Image**: Your branch must have a published Docker image. The CI/CD pipeline publishes images to:
   ```
   ghcr.io/all-hands-ai/openhands:your-branch-name
   ```

## Quick Start

### 1. Create Your Namespace

```bash
# Use your name or branch name as identifier
export BRANCH_NAME="your-branch-name"
export NAMESPACE="openhands-${BRANCH_NAME}"

kubectl create namespace ${NAMESPACE}
```

### 2. Create a Values Override File

Create a file `my-branch-values.yaml`:

```yaml
# Image configuration - point to your branch's image
image:
  repository: ghcr.io/all-hands-ai/openhands
  tag: "your-branch-name"  # Your branch's image tag

# Ingress configuration for subdomain-based routing
ingress:
  enabled: true
  host: staging.example.com
  prefixWithBranch: true

# REQUIRED: Sanitized branch name (lowercase, alphanumeric, hyphens only)
# This becomes your subdomain: your-branch.staging.example.com
branchSanitized: "your-branch"

# Use shared databases (or create your own)
postgresql:
  host: "shared-postgres.default.svc.cluster.local"
  auth:
    existingSecret: "openhands-shared-db-credentials"
    secretKeys:
      userPasswordKey: "password"
  database: "openhands_yourbranch"  # Use unique DB name

redis:
  host: "shared-redis.default.svc.cluster.local"

# Disable components you don't need for testing
automation:
  enabled: false

# Scale down for development
deployment:
  replicas: 1
  resources:
    requests:
      memory: 512Mi
      cpu: 100m
    limits:
      memory: 1Gi
```

### 3. Deploy with Helm

```bash
# From the repository root
helm install openhands-${BRANCH_NAME} ./charts/openhands \
  --namespace ${NAMESPACE} \
  --values infrastructure/helm/base-values.yaml \
  --values my-branch-values.yaml
```

### 4. Access Your Deployment

For **subdomain-based** clusters:
```
https://your-branch.staging.example.com
```

For **path-based** clusters:
```
https://staging.example.com/  (routed by ingress to your release)
```

## Deployment Patterns

### Minimal Development Deployment

For quick iteration with minimal resources:

```yaml
# dev-values.yaml
image:
  tag: "your-branch"

branchSanitized: "yourname"

ingress:
  enabled: true
  host: staging.example.com
  prefixWithBranch: true

deployment:
  replicas: 1
  resources:
    requests:
      memory: 512Mi
      cpu: 50m

# Disable non-essential services
automation:
  enabled: false
integrationEvents:
  deployment:
    replicas: 0
mcpEvents:
  deployment:
    replicas: 0
```

### Full Stack Deployment

For testing the complete system:

```yaml
# full-stack-values.yaml
image:
  tag: "your-branch"

branchSanitized: "yourname-full"

ingress:
  enabled: true
  host: staging.example.com
  prefixWithBranch: true

deployment:
  replicas: 2

automation:
  enabled: true

integrationEvents:
  deployment:
    replicas: 1

# Point to your own databases if needed
postgresql:
  host: "your-postgres-instance"
  database: "openhands_yourname"
```

## Runtime API Deployment

If you're also testing changes to the Runtime API:

```bash
helm install runtime-api-${BRANCH_NAME} ./charts/runtime-api \
  --namespace ${NAMESPACE} \
  --set image.tag="${BRANCH_NAME}" \
  --set ingress.enabled=true \
  --set ingress.host=staging.example.com \
  --set ingress.prefixWithBranch=true \
  --set branchSanitized="${BRANCH_NAME}"
```

## Managing Your Deployment

### View Status

```bash
# Check pods
kubectl get pods -n ${NAMESPACE}

# Check ingress
kubectl get ingress -n ${NAMESPACE}

# View logs
kubectl logs -n ${NAMESPACE} -l app=openhands -f
```

### Update Deployment

```bash
# After pushing new changes and image is built
helm upgrade openhands-${BRANCH_NAME} ./charts/openhands \
  --namespace ${NAMESPACE} \
  --values my-branch-values.yaml \
  --set image.tag="${NEW_TAG}"
```

### Delete Deployment

```bash
# Remove Helm release
helm uninstall openhands-${BRANCH_NAME} --namespace ${NAMESPACE}

# Optionally delete namespace (removes all resources)
kubectl delete namespace ${NAMESPACE}
```

## Shared Resources

The staging clusters provide shared resources that branch deployments can use:

| Resource | Service Address | Notes |
|----------|-----------------|-------|
| PostgreSQL | `shared-postgres.default.svc.cluster.local` | Request DB credentials from team |
| Redis | `shared-redis.default.svc.cluster.local` | Shared cache |
| LiteLLM Proxy | `litellm.default.svc.cluster.local` | Shared LLM gateway |

## Troubleshooting

### Ingress Not Working

1. Check ingress resource:
   ```bash
   kubectl describe ingress -n ${NAMESPACE}
   ```

2. Verify TLS certificate:
   ```bash
   kubectl get certificate -n ${NAMESPACE}
   ```

3. Check Traefik logs:
   ```bash
   kubectl logs -n traefik -l app.kubernetes.io/name=traefik
   ```

### Pod Crashes

1. Check pod events:
   ```bash
   kubectl describe pod -n ${NAMESPACE} -l app=openhands
   ```

2. Check for missing secrets:
   ```bash
   kubectl get secrets -n ${NAMESPACE}
   ```

### Database Connection Issues

1. Verify database secret exists:
   ```bash
   kubectl get secret -n ${NAMESPACE} | grep postgres
   ```

2. Test connectivity:
   ```bash
   kubectl run -n ${NAMESPACE} pg-test --rm -it --image=postgres:15 -- \
     psql -h shared-postgres.default.svc.cluster.local -U openhands -d openhands_yourdb
   ```

## Best Practices

1. **Use descriptive branch names**: Your `branchSanitized` value becomes your subdomain
2. **Clean up after yourself**: Delete deployments when done to free cluster resources
3. **Don't modify shared resources**: Use your own databases for destructive testing
4. **Coordinate with team**: Communicate on Slack when deploying large changes
5. **Resource limits**: Keep resource requests minimal for dev deployments

## CI/CD Integration

For automated deployments from CI, see the GitHub Actions workflow examples in `.github/workflows/`. Key environment variables:

```yaml
env:
  BRANCH_NAME: ${{ github.head_ref || github.ref_name }}
  BRANCH_SANITIZED: ${{ steps.sanitize.outputs.branch }}
  NAMESPACE: openhands-${{ steps.sanitize.outputs.branch }}
```
