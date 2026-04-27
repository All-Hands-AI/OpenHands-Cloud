# OpenHands Staging Infrastructure

This directory contains Terraform modules and Helm configurations for deploying OpenHands to GKE in the staging GCP project (`staging-092324`).

## Overview

Four independent deployment environments are supported:

| Environment | Clusters | Routing | Use Case |
|------------|----------|---------|----------|
| `single-cluster-path` | 1 | Path-based (`domain.com/api/`, `/runtime/`) | Simple deployments |
| `single-cluster-subdomain` | 1 | Subdomain-based (`api.domain.com`, `runtime.domain.com`) | Branch deployments |
| `multi-cluster-path` | 2 (core + runtime) | Path-based | Production-like isolation |
| `multi-cluster-subdomain` | 2 (core + runtime) | Subdomain-based | Full production parity |

## Directory Structure

```
infrastructure/
├── terraform/
│   ├── modules/
│   │   ├── gke-cluster/      # GKE cluster module
│   │   └── vpc-network/      # VPC network module
│   └── environments/
│       ├── single-cluster-path/
│       ├── single-cluster-subdomain/
│       ├── multi-cluster-path/
│       └── multi-cluster-subdomain/
├── helm/
│   ├── cert-manager/         # TLS certificate management
│   ├── external-dns/         # DNS record automation
│   └── traefik/              # Ingress controller
└── scripts/                  # Deployment scripts
```

## Prerequisites

- GCP project: `staging-092324`
- Terraform >= 1.5.0
- Helm >= 3.0
- `gcloud` CLI configured
- `kubectl` configured

## Deployment

### 1. Terraform Infrastructure

```bash
cd terraform/environments/<environment-name>

# Initialize
terraform init

# Configure variables
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values

# Plan and apply
terraform plan
terraform apply
```

### 2. Configure kubectl

```bash
gcloud container clusters get-credentials <cluster-name> \
  --region <region> \
  --project staging-092324
```

### 3. Install Helm Charts

```bash
# Install cert-manager
helm install cert-manager jetstack/cert-manager \
  -n cert-manager --create-namespace \
  -f helm/cert-manager/values.yaml

# Install external-dns
helm install external-dns bitnami/external-dns \
  -n external-dns --create-namespace \
  -f helm/external-dns/values.yaml \
  -f helm/external-dns/values-<routing-type>.yaml \
  --set google.project=staging-092324 \
  --set domainFilters[0]=your-domain.com

# Install traefik
helm install traefik traefik/traefik \
  -n traefik --create-namespace \
  -f helm/traefik/values.yaml \
  -f helm/traefik/values-<routing-type>.yaml
```

### 4. Deploy OpenHands

Use the main OpenHands Helm chart with environment-specific values:

```bash
helm install openhands ../charts/openhands \
  -n openhands --create-namespace \
  -f <environment-values.yaml>
```

## Routing Strategies

### Path-Based Routing

All services accessible via URL paths on a single domain:

```
https://domain.com/              # Main UI
https://domain.com/api/          # API endpoints
https://domain.com/runtime/      # Runtime API
https://domain.com/auth/         # Keycloak
https://domain.com/llm/          # LiteLLM proxy
```

**Advantages:**
- Single TLS certificate (HTTP-01 challenge)
- Simple DNS setup
- Lower cost (one load balancer)

**Requirements:**
- Apply path-stripping middlewares
- Configure backend services for path prefix handling

### Subdomain-Based Routing

Each service on its own subdomain:

```
https://app.domain.com           # Main UI
https://api.domain.com           # API endpoints
https://runtime.domain.com       # Runtime API
https://auth.domain.com          # Keycloak
https://llm.domain.com           # LiteLLM proxy
https://branch.domain.com        # Branch deployments
```

**Advantages:**
- Clean service separation
- Native branch deployment support
- No path rewriting needed

**Requirements:**
- Wildcard TLS certificate (DNS-01 challenge)
- Cloud DNS zone for external-dns
- Wildcard DNS record

## Multi-Cluster Environments

Multi-cluster setups separate the core OpenHands services from runtime pods:

- **Core Cluster**: OpenHands UI, API, Keycloak, LiteLLM, databases
- **Runtime Cluster**: Runtime API, runtime pods, warm pool

This provides:
- Resource isolation
- Independent scaling
- Security boundaries
- Production parity

## Existing Staging Environment

The existing `staging.all-hands.dev` deployment is **not affected** by this infrastructure. These environments use separate:
- VPC networks
- GKE clusters  
- DNS zones
- Static IPs
