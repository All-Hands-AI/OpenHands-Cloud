# PRD: Developer Staging Deployment Infrastructure

**Author:** Saurya Velagapudi  
**Date:** 2026-04-13  
**Status:** Draft  
**Branch:** `SV-OHE-staging-Deploy-Infra`  
**Related:** [infra PR #1064](https://github.com/All-Hands-AI/infra/pull/1064) (base domains)

---

## Executive Summary

We need a developer-friendly staging infrastructure where engineers can deploy their `openhands-cloud` feature branches to publicly accessible environments with valid TLS certificates and SAML authentication. This enables rapid debugging of customer issues and validation of enterprise features before merge.

---

## Problem Statement

### Current Pain Points

1. **No feature branch testing environment** - Engineers cannot deploy their branches to a production-like environment to test changes.

2. **Customer issue reproduction is slow** - When a customer reports an issue with their Enterprise deployment, we have no environment that mirrors their setup (SAML, TLS, HA).

3. **Let's Encrypt rate limits** - Creating certificates on-demand for arbitrary branch names hits Let's Encrypt rate limits (50 certs/week per registered domain).

4. **Manual certificate management** - Current Terraform approach provisions certs once; we need dynamic cert provisioning for developer deployments.

### Goal

Enable any engineer to deploy their feature branch to a publicly accessible staging environment within 15 minutes, with:
- Valid TLS certificate (HTTPS)
- SAML authentication enabled
- Full OpenHands functionality
- Automatic cleanup after testing

---

## Proposed Solution

### Base Domain Pool Architecture

Instead of creating certificates for arbitrary branch names (which would hit rate limits), we maintain a **pool of pre-provisioned base domains** that developers can claim for their deployments.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Base Domain Pool (Pre-provisioned)               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ dev1.staging.    │  │ dev2.staging.    │  │ dev3.staging.    │  │
│  │ all-hands.dev    │  │ all-hands.dev    │  │ all-hands.dev    │  │
│  │                  │  │                  │  │                  │  │
│  │ Status: IN USE   │  │ Status: FREE     │  │ Status: FREE     │  │
│  │ Branch: fix-saml │  │                  │  │                  │  │
│  │ User: @engineer1 │  │                  │  │                  │  │
│  │ Expires: 24h     │  │                  │  │                  │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐                        │
│  │ dev4.staging.    │  │ dev5.staging.    │   ... up to N slots    │
│  │ all-hands.dev    │  │ all-hands.dev    │                        │
│  │                  │  │                  │                        │
│  │ Status: FREE     │  │ Status: IN USE   │                        │
│  │                  │  │ Branch: runtime  │                        │
│  │                  │  │ User: @engineer2 │                        │
│  └──────────────────┘  └──────────────────┘                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### What Stays Constant (Cluster-Level)

These components are installed **once per cluster** and shared across all developer deployments:

| Component | Notes |
|-----------|-------|
| **Ingress Controller** | Traefik, shared across all namespaces |
| **cert-manager** | ClusterIssuer for Let's Encrypt |
| **external-dns** | Manages DNS records automatically |
| **StorageClasses** | `standard-rwo`, etc. - cluster-level |
| **Operators** | CloudNativePG or similar - installed once |
| **Keycloak** | Shared SAML IdP at `auth.staging.all-hands.dev` |
| **Base Domain Certs** | Wildcard certs for each base domain slot |

### What Varies (Per-Deployment)

| Component | Notes |
|-----------|-------|
| **Namespace** | One per deployment (`dev1-staging`, `dev2-staging`, etc.) |
| **OpenHands Chart** | Deployed from feature branch |
| **Runtime-API** | Per-namespace deployment |
| **PostgreSQL** | Per-namespace database (CloudNativePG) |
| **Redis** | Per-namespace instance |
| **Ingress Resources** | Point to pre-provisioned wildcard cert |

---

## Technical Requirements

### 1. Let's Encrypt Certificate Strategy

**Challenge:** Let's Encrypt has rate limits:
- 50 certificates per registered domain per week
- 5 duplicate certificates per week
- 300 new orders per account per 3 hours

**Solution:** Pre-provision wildcard certificates for each base domain slot.

```yaml
# Pre-provisioned certificate for dev1.staging.all-hands.dev
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: dev1-staging-wildcard
  namespace: cert-manager  # Or a dedicated certs namespace
spec:
  secretName: dev1-staging-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - "dev1.staging.all-hands.dev"
    - "*.dev1.staging.all-hands.dev"
  # Certificate valid for 90 days, auto-renewed at 30 days remaining
```

**Why Wildcard?** A single wildcard cert covers:
- `dev1.staging.all-hands.dev` (main app)
- `auth.dev1.staging.all-hands.dev` (Keycloak)
- `llm.dev1.staging.all-hands.dev` (LiteLLM proxy)
- `runtime.dev1.staging.all-hands.dev` (Runtime API)
- `*.runtime.dev1.staging.all-hands.dev` (Runtime pods)

**DNS-01 Challenge Required:** Wildcard certs require DNS-01 challenge (HTTP-01 won't work).

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: devops@all-hands.dev
    privateKeySecretRef:
      name: letsencrypt-prod-account-key
    solvers:
      - dns01:
          cloudDNS:
            project: staging-092324
            serviceAccountSecretRef:
              name: clouddns-dns01-solver-svc-acct
              key: key.json
        selector:
          dnsZones:
            - "staging.all-hands.dev"
```

**Complexity: MEDIUM**
- One-time setup of ClusterIssuer with DNS provider credentials
- Pre-provision N certificates (one per slot)
- Certificates auto-renew; no ongoing maintenance

---

### 2. Base Domain Pool Management

**Option A: Static Pool (Recommended for MVP)**

Pre-define 5-10 slots in a ConfigMap or similar:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: staging-slots
  namespace: staging-system
data:
  slots: |
    - name: dev1
      domain: dev1.staging.all-hands.dev
      status: free
    - name: dev2
      domain: dev2.staging.all-hands.dev
      status: free
    - name: dev3
      domain: dev3.staging.all-hands.dev
      status: free
    - name: dev4
      domain: dev4.staging.all-hands.dev
      status: free
    - name: dev5
      domain: dev5.staging.all-hands.dev
      status: free
```

**Option B: Dynamic Allocation (Future)**

Build a simple "slot manager" service that:
- Tracks which slots are in use
- Assigns slots on deployment request
- Reclaims slots after TTL expires
- Integrates with GitHub Actions

**Complexity: LOW (static) / MEDIUM (dynamic)**

---

### 3. Developer Deployment Workflow

**GitHub Actions Workflow:**

```yaml
# .github/workflows/deploy-feature-branch.yml
name: Deploy Feature Branch to Staging

on:
  workflow_dispatch:
    inputs:
      slot:
        description: 'Staging slot (dev1-dev5)'
        required: true
        type: choice
        options: [dev1, dev2, dev3, dev4, dev5]
      ttl_hours:
        description: 'Hours until auto-cleanup'
        required: false
        default: '24'

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up kubectl
        uses: azure/setup-kubectl@v3
        
      - name: Configure kubeconfig
        run: |
          echo "${{ secrets.STAGING_KUBECONFIG }}" | base64 -d > kubeconfig
          export KUBECONFIG=kubeconfig
          
      - name: Deploy to slot
        env:
          SLOT: ${{ inputs.slot }}
          BRANCH: ${{ github.ref_name }}
          DOMAIN: ${{ inputs.slot }}.staging.all-hands.dev
        run: |
          NAMESPACE="${SLOT}-staging"
          
          # Create namespace if not exists
          kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
          
          # Copy wildcard cert secret to namespace
          kubectl get secret ${SLOT}-staging-tls -n cert-manager -o yaml | \
            sed "s/namespace: cert-manager/namespace: $NAMESPACE/" | \
            kubectl apply -f -
          
          # Deploy OpenHands
          helm upgrade --install openhands ./charts/openhands \
            -n $NAMESPACE \
            -f envs/staging-dev/values.yaml \
            --set ingress.host=$DOMAIN \
            --set branchSanitized=$BRANCH \
            --set "annotations.deployed-by=${{ github.actor }}" \
            --set "annotations.deployed-at=$(date -Iseconds)" \
            --set "annotations.ttl-hours=${{ inputs.ttl_hours }}"
            
      - name: Post deployment URL
        run: |
          echo "## 🚀 Deployment Complete" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "**URL:** https://${{ inputs.slot }}.staging.all-hands.dev" >> $GITHUB_STEP_SUMMARY
          echo "**Branch:** ${{ github.ref_name }}" >> $GITHUB_STEP_SUMMARY
          echo "**Slot:** ${{ inputs.slot }}" >> $GITHUB_STEP_SUMMARY
          echo "**Expires:** ${{ inputs.ttl_hours }} hours" >> $GITHUB_STEP_SUMMARY
```

**Complexity: LOW**
- Standard GitHub Actions
- Helm-based deployment
- Manual slot selection (automated allocation is future scope)

---

### 4. SAML Identity Provider

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    Shared Keycloak Instance                      │
│                  auth.staging.all-hands.dev                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Realm: openhands-staging                                        │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ SAML Client │  │ SAML Client │  │ SAML Client │  ... x N    │
│  │ dev1-staging│  │ dev2-staging│  │ dev3-staging│             │
│  │             │  │             │  │             │             │
│  │ Entity ID:  │  │ Entity ID:  │  │ Entity ID:  │             │
│  │ https://    │  │ https://    │  │ https://    │             │
│  │ dev1.stag.. │  │ dev2.stag.. │  │ dev3.stag.. │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                  │
│  Test Users:                                                     │
│  - admin@test.local (Admin role)                                │
│  - user@test.local (User role)                                  │
│  - enterprise@test.local (Enterprise features)                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Pre-configured SAML Clients:**

Each base domain slot gets a pre-configured SAML client in Keycloak:

```json
{
  "clientId": "https://dev1.staging.all-hands.dev",
  "name": "OpenHands Dev1 Staging",
  "protocol": "saml",
  "enabled": true,
  "redirectUris": [
    "https://dev1.staging.all-hands.dev/*",
    "https://*.dev1.staging.all-hands.dev/*"
  ],
  "attributes": {
    "saml.assertion.signature": "true",
    "saml.server.signature": "true",
    "saml_name_id_format": "email"
  }
}
```

**OpenHands Configuration:**

```yaml
# envs/staging-dev/values.yaml
keycloak:
  enabled: true
  # Shared Keycloak instance
  url: "https://auth.staging.all-hands.dev"
  realm: "openhands-staging"
  
  # SAML configuration
  saml:
    enabled: true
    # Entity ID will be set dynamically based on slot domain
    # entityId: "https://${DOMAIN}"
    
env:
  # Auth settings
  AUTH_TYPE: "saml"
  SAML_IDP_METADATA_URL: "https://auth.staging.all-hands.dev/realms/openhands-staging/protocol/saml/descriptor"
```

**Optional: GitHub/GitLab OAuth**

Keycloak can be configured as an identity broker to allow login via:
- GitHub OAuth
- GitLab OAuth
- Google OAuth

This is additive to SAML and requires registering OAuth apps with each provider.

**Complexity: MEDIUM**
- Deploy shared Keycloak once
- Pre-configure SAML clients for each slot
- Create test users with various roles
- Document SAML metadata URLs for each slot

---

### 5. Incremental Deployment (Deploy Only Changed Charts)

**Problem:** Full deployment takes 10+ minutes. We want to deploy only what changed.

**Solution:** Use Helm's `--reuse-values` and change detection.

```yaml
# In GitHub Actions
- name: Detect chart changes
  id: changes
  uses: dorny/paths-filter@v2
  with:
    filters: |
      openhands:
        - 'charts/openhands/**'
      runtime-api:
        - 'charts/runtime-api/**'
      automation:
        - 'charts/automation/**'

- name: Deploy OpenHands (if changed)
  if: steps.changes.outputs.openhands == 'true'
  run: |
    helm upgrade openhands ./charts/openhands \
      -n $NAMESPACE \
      --reuse-values \
      --set image.tag=${{ github.sha }}

- name: Deploy Runtime API (if changed)
  if: steps.changes.outputs.runtime-api == 'true'
  run: |
    helm upgrade runtime-api ./charts/runtime-api \
      -n $NAMESPACE \
      --reuse-values \
      --set image.tag=${{ github.sha }}
```

**For application code changes (not chart changes):**

If only application code changed (not Helm charts), we just need to update the image tag:

```bash
# Fast path: just update image tag
kubectl set image deployment/openhands \
  openhands=ghcr.io/all-hands-ai/openhands:$NEW_TAG \
  -n $NAMESPACE
```

**Complexity: LOW**
- Standard Helm upgrade patterns
- Change detection via `dorny/paths-filter`
- ~2-3 minutes for incremental deploys

---

### 6. External DNS

**Requirement:** DNS records should be created automatically when Ingress resources are created.

**Implementation:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: external-dns
  namespace: kube-system
spec:
  template:
    spec:
      containers:
        - name: external-dns
          image: registry.k8s.io/external-dns/external-dns:v0.14.0
          args:
            - --source=ingress
            - --domain-filter=staging.all-hands.dev
            - --provider=google
            - --google-project=staging-092324
            - --registry=txt
            - --txt-owner-id=staging-cluster
            - --txt-prefix=externaldns-
```

**DNS Records Created Automatically:**

When an Ingress is created with host `dev1.staging.all-hands.dev`, external-dns creates:

```
dev1.staging.all-hands.dev.    A    <load-balancer-ip>
```

**Complexity: LOW**
- Standard external-dns deployment
- Works with GCP Cloud DNS, AWS Route53, etc.
- One-time setup

---

## Complexity Assessment Summary

| Component | Complexity | One-Time vs Ongoing | Estimated Effort |
|-----------|------------|---------------------|------------------|
| cert-manager + ClusterIssuer | Medium | One-time | 1 day |
| Wildcard certificates (N slots) | Low | One-time | 0.5 day |
| Base domain pool (static) | Low | One-time | 0.5 day |
| GitHub Actions workflow | Low | One-time | 1 day |
| Keycloak shared instance | Medium | One-time | 1-2 days |
| SAML clients per slot | Low | One-time | 0.5 day |
| external-dns | Low | One-time | 0.5 day |
| Incremental deployment logic | Low | One-time | 0.5 day |
| **Total initial setup** | | | **5-7 days** |

### Ongoing Maintenance

| Task | Frequency | Effort |
|------|-----------|--------|
| Certificate renewal | Automatic | None |
| Keycloak updates | Quarterly | 2 hours |
| Slot cleanup | Automatic (TTL) | None |
| Troubleshooting | As needed | Variable |

---

## Implementation Plan

### Phase 1: Infrastructure Foundation (Days 1-2)

1. [ ] Deploy cert-manager to staging cluster
2. [ ] Configure ClusterIssuer with DNS-01 solver for `staging.all-hands.dev`
3. [ ] Deploy external-dns
4. [ ] Create 5 wildcard certificates (dev1-dev5)
5. [ ] Verify certificates are issued and valid

### Phase 2: Identity Provider (Days 3-4)

1. [ ] Deploy Keycloak to `auth.staging.all-hands.dev`
2. [ ] Create `openhands-staging` realm
3. [ ] Pre-configure SAML clients for dev1-dev5
4. [ ] Create test users with various roles
5. [ ] Document SAML metadata URLs

### Phase 3: Deployment Automation (Days 5-6)

1. [ ] Create `deploy-feature-branch.yml` workflow
2. [ ] Create `envs/staging-dev/values.yaml` template
3. [ ] Implement slot selection UI in workflow
4. [ ] Add deployment status to GitHub Step Summary
5. [ ] Test end-to-end deployment flow

### Phase 4: Cleanup & Polish (Day 7)

1. [ ] Implement TTL-based namespace cleanup CronJob
2. [ ] Add Slack notifications for deployments
3. [ ] Document developer workflow in README
4. [ ] Create troubleshooting guide

---

## Open Questions

1. **How many slots do we need initially?**
   - Recommendation: Start with 5, expand to 10 if needed
   
2. **What TTL should be default?**
   - Recommendation: 24 hours, max 72 hours

3. **Should we integrate with Slack for slot claiming?**
   - Nice-to-have, not MVP

4. **Do we need database seeding for testing?**
   - Depends on test requirements

5. **Should slots have dedicated or shared databases?**
   - Recommendation: Dedicated (CloudNativePG per namespace) for isolation

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Time from "deploy" to "accessible URL" | < 15 minutes |
| Certificate validity | 100% (auto-renewed) |
| SAML login success rate | > 99% |
| Developer satisfaction | Survey feedback |

---

## Appendix

### A. Example Developer Flow

```bash
# 1. Engineer wants to test their SAML fix
$ gh workflow run deploy-feature-branch.yml \
    -f slot=dev3 \
    -f ttl_hours=48

# 2. Workflow assigns dev3.staging.all-hands.dev
# 3. Deployment completes in ~10 minutes
# 4. Engineer receives URL in workflow summary

# 5. Access the deployment
$ open https://dev3.staging.all-hands.dev

# 6. Login with SAML test user
#    - Navigate to login
#    - Redirected to auth.staging.all-hands.dev
#    - Login as user@test.local / password
#    - Redirected back to app

# 7. Test the fix, verify it works

# 8. Slot automatically cleaned up after 48 hours
#    (or manually via cleanup workflow)
```

### B. Certificate Troubleshooting

```bash
# Check certificate status
kubectl get certificates -A

# Check certificate details
kubectl describe certificate dev1-staging-wildcard -n cert-manager

# Check cert-manager logs
kubectl logs -n cert-manager -l app=cert-manager

# Check DNS-01 challenge
kubectl get challenges -A
```

### C. Related Links

- [cert-manager DNS-01 docs](https://cert-manager.io/docs/configuration/acme/dns01/)
- [Let's Encrypt rate limits](https://letsencrypt.org/docs/rate-limits/)
- [external-dns docs](https://github.com/kubernetes-sigs/external-dns)
- [infra PR #1064](https://github.com/All-Hands-AI/infra/pull/1064) - Base domain setup
