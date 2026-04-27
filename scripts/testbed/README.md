# OpenHands Cloud Testbed

Deploy OpenHands Cloud to an **internal testbed environment** for testing and development.

> ⚠️ **Private Environment**: This testbed is NOT publicly accessible. It runs in the
> Platform Team Sandbox GCP project and uses `/etc/hosts` for DNS resolution.

## Overview

The testbed provides two deployment modes:

1. **Shared Testbed** - Multiple developers deploy to namespaces on a shared GKE cluster
2. **Isolated Testbed** - Create your own GKE cluster for complete isolation

## Quick Start (For Team Members)

### Prerequisites

- `gcloud` CLI authenticated (`gcloud auth login`)
- `kubectl` installed  
- `helm` v3 installed
- Access to `platform-team-sandbox-62793` GCP project (request via Platform Team)
- An Anthropic API key (get from 1Password or request from team lead)

### Step 1: Connect to the Shared Cluster

```bash
# Authenticate with GCP
gcloud auth login
gcloud config set project platform-team-sandbox-62793

# Connect to the testbed cluster
gcloud container clusters get-credentials openhands-testbed --region us-central1
```

### Step 2: Deploy Your Instance

```bash
# Set your API keys
export ANTHROPIC_API_KEY="sk-ant-..."     # Required for LLM
export GITHUB_TOKEN="ghp_..."              # Optional: for pulling latest images

# Deploy to your own namespace (use your name or feature name)
./deploy.sh --name <your-name>

# Examples:
./deploy.sh --name saurya
./deploy.sh --name feature-xyz
```

This creates:
- Namespace: `testbed-<name>`
- App hostname: `testbed-<name>.sandbox.all-hands.dev`
- Auth hostname: `auth-testbed-<name>.sandbox.all-hands.dev`
- Runtime hostname: `runtime-testbed-<name>.sandbox.all-hands.dev`

### Step 3: Configure Local Access

Since this is a private environment, add entries to your `/etc/hosts`:

```bash
# Get the LoadBalancer IP
TRAEFIK_IP=$(kubectl get svc -n traefik traefik -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "LoadBalancer IP: $TRAEFIK_IP"

# Add to /etc/hosts (replace <name> with your testbed name)
sudo bash -c "echo '$TRAEFIK_IP testbed-<name>.sandbox.all-hands.dev auth-testbed-<name>.sandbox.all-hands.dev runtime-testbed-<name>.sandbox.all-hands.dev' >> /etc/hosts"

# Example for testbed-saurya:
# sudo bash -c "echo '34.28.75.102 testbed-saurya.sandbox.all-hands.dev auth-testbed-saurya.sandbox.all-hands.dev runtime-testbed-saurya.sandbox.all-hands.dev' >> /etc/hosts"
```

### Step 4: Access Your Testbed

**Option A: Browser with /etc/hosts (recommended)**

After adding `/etc/hosts` entries, open Chrome/Firefox:
```
https://testbed-<name>.sandbox.all-hands.dev
```

> 💡 **Chrome HTTPS Warning**: When you see the certificate warning, click anywhere on the page
> and type `thisisunsafe` (you won't see it appear). This bypasses the self-signed cert warning.

**Option B: Port Forward (simplest, but limited)**

```bash
kubectl port-forward svc/openhands-service 3000:3000 -n testbed-<name>
# Open http://localhost:3000
```

Note: Port forwarding won't work with OAuth callbacks. Use /etc/hosts for full functionality.

### Step 5: Clean Up When Done

```bash
./deploy.sh --name <your-name> --destroy
```

**Important**: Please destroy your testbed when you're done to save cluster resources!

## Deployment Modes

### Shared Cluster (Default)

Multiple developers share one GKE cluster with separate namespaces:

```bash
./deploy.sh --name alice   # Creates testbed-alice namespace
./deploy.sh --name bob     # Creates testbed-bob namespace
```

**Pros:**
- Faster deployment (cluster already exists)
- Lower cost (shared infrastructure)
- Simpler DNS setup (one wildcard domain)

**Cons:**
- Shared cluster resources
- Potential resource contention

### Isolated Cluster

Create your own GKE cluster:

```bash
./deploy.sh --name mytest --create-cluster
```

**Pros:**
- Complete isolation
- Can test cluster-level changes
- No resource contention

**Cons:**
- Slower setup (~10 minutes for cluster creation)
- Higher cost
- Requires separate DNS setup

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes* | Anthropic API key for LLM |
| `OPENAI_API_KEY` | No | OpenAI API key (alternative) |
| `GITHUB_TOKEN` | Recommended | For pulling images from ghcr.io |
| `GCP_PROJECT` | No | GCP project (default: platform-team-sandbox-62793) |
| `GCP_REGION` | No | GCP region (default: us-central1) |

*At least one LLM API key is required for the agent to function.

### Custom Values

Override values by creating a custom values file:

```bash
# Generate default values
./deploy.sh --name mytest --dry-run

# Edit the generated values
vim values-testbed-mytest.yaml

# Deploy with custom values
./deploy.sh --name mytest
```

## Troubleshooting

### Check Deployment Status

```bash
# View all pods
kubectl get pods -n testbed-<name>

# View logs
kubectl logs -f deployment/openhands -n testbed-<name>

# View events
kubectl get events -n testbed-<name> --sort-by=.lastTimestamp
```

### Certificate Issues

```bash
# Check certificate status
kubectl get certificates -n testbed-<name>
kubectl describe certificate -n testbed-<name>

# Check cert-manager logs
kubectl logs -n cert-manager deployment/cert-manager
```

### Database Issues

```bash
# Check PostgreSQL
kubectl get pods -n testbed-<name> -l app.kubernetes.io/name=postgresql

# Connect to database
kubectl exec -it -n testbed-<name> \
  $(kubectl get pod -n testbed-<name> -l app.kubernetes.io/name=postgresql -o name) \
  -- psql -U postgres
```

### Ingress Issues

```bash
# Check Traefik
kubectl get svc -n traefik
kubectl logs -n traefik deployment/traefik

# Check ingress
kubectl get ingress -n testbed-<name>
kubectl describe ingress -n testbed-<name>
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Platform Team Sandbox GCP                     │
│                    (platform-team-sandbox-62793)                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                 GKE: openhands-testbed                      │ │
│  │                                                              │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │ │
│  │  │ traefik     │  │ cert-manager│  │ DNS zone    │        │ │
│  │  │ (ingress)   │  │ (TLS certs) │  │ sandbox.    │        │ │
│  │  │             │  │             │  │ all-hands.  │        │ │
│  │  │             │  │             │  │ dev         │        │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘        │ │
│  │                                                              │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │              Namespace: testbed-alice                 │  │ │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │  │ │
│  │  │  │openhands│ │keycloak │ │litellm  │ │postgres │    │  │ │
│  │  │  │         │ │ (auth)  │ │ (llm)   │ │ (db)    │    │  │ │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘    │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  │                                                              │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │              Namespace: testbed-bob                   │  │ │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │  │ │
│  │  │  │openhands│ │keycloak │ │litellm  │ │postgres │    │  │ │
│  │  │  │         │ │ (auth)  │ │ (llm)   │ │ (db)    │    │  │ │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘    │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  │                                                              │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Cost Considerations

### Shared Cluster (Recommended)

- GKE cluster: ~$72/month (control plane) + ~$100/month (nodes)
- Split across all users

### Isolated Cluster

- Same costs per cluster
- Consider deleting when not in use:
  ```bash
  ./deploy.sh --name mytest --destroy  # Includes cluster deletion
  ```

## Network Access (Private by Design)

This testbed is intentionally **NOT publicly accessible**. Access requires:

1. GCP project access (`platform-team-sandbox-62793`)
2. kubectl credentials for the cluster
3. Local `/etc/hosts` configuration pointing to the LoadBalancer IP

### Why No Public DNS?

- **Security**: Experimental features and internal testing shouldn't be public
- **Simplicity**: No need to manage SSL certificates via Let's Encrypt
- **Isolation**: Each developer's /etc/hosts is independent

### Getting the LoadBalancer IP

```bash
# Current LoadBalancer IP
kubectl get svc -n traefik traefik -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
# Output: 34.28.75.102 (as of last deployment)
```

### /etc/hosts Configuration

Add entries for your testbed:

```bash
# For testbed named "mytest"
34.28.75.102 testbed-mytest.sandbox.all-hands.dev auth-testbed-mytest.sandbox.all-hands.dev runtime-testbed-mytest.sandbox.all-hands.dev

# For testbed named "saurya" 
34.28.75.102 testbed-saurya.sandbox.all-hands.dev auth-testbed-saurya.sandbox.all-hands.dev runtime-testbed-saurya.sandbox.all-hands.dev
```

### Optional: Future Public DNS

If we ever want to make this publicly accessible (with proper authentication), there's
a prepared DNS delegation in the infra repo that can be merged:
- PR: [Add sandbox.all-hands.dev DNS delegation](https://github.com/All-Hands-AI/infra/pull/1165)

This would enable Let's Encrypt certificates and public DNS resolution.

## Contributing

When adding features to the testbed scripts:

1. Test with `--dry-run` first
2. Ensure cleanup works properly
3. Update this README
4. Consider backwards compatibility with existing testbeds
