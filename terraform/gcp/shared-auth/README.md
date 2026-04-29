# Shared Keycloak for Staging Environments

This Terraform module deploys a shared Keycloak instance that can be used by multiple branch deployments in the staging environment.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Shared Infrastructure                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Keycloak (auth.ohe-staging.platform-team.all-hands.dev) │  │
│  │  - Single SAML config with Google Workspace              │  │
│  │  - allhands realm with identity providers                │  │
│  │  - Shared PostgreSQL database                            │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
            ▲                    ▲                    ▲
            │                    │                    │
┌───────────┴───┐    ┌───────────┴───┐    ┌───────────┴───┐
│ branch-a      │    │ branch-b      │    │ branch-c      │
│ deployment    │    │ deployment    │    │ deployment    │
│ (no keycloak) │    │ (no keycloak) │    │ (no keycloak) │
└───────────────┘    └───────────────┘    └───────────────┘
```

## Benefits

1. **Single Identity Provider Configuration**: Configure Google SAML (or other IdPs) once
2. **Consistent Authentication**: All branches share the same authentication setup
3. **Resource Efficiency**: One Keycloak instance instead of one per branch
4. **Simplified Management**: Single place to manage users, roles, and IdP settings

## Prerequisites

1. Kubernetes cluster with:
   - Traefik ingress controller
   - cert-manager with wildcard certificate
   - PostgreSQL (from openhands namespace)

2. Wildcard TLS certificate secret in the shared-auth namespace

## Deployment

### 1. Configure Variables

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
```

### 2. Copy TLS Secret (if needed)

The shared-auth namespace needs access to the wildcard TLS certificate:

```bash
# Copy from openhands namespace
kubectl get secret ohe-staging-wildcard-tls -n openhands -o yaml | \
  sed 's/namespace: openhands/namespace: shared-auth/' | \
  kubectl apply -f -
```

### 3. Create Keycloak Database

Create the database in the shared PostgreSQL:

```bash
kubectl exec -it openhands-postgresql-0 -n openhands -- \
  psql -U postgres -c "CREATE DATABASE shared_keycloak;"
```

### 4. Apply Terraform

```bash
terraform init
terraform plan
terraform apply
```

## Configuring Branch Deployments

To use the shared Keycloak, update your branch deployment's helm values:

```yaml
keycloak:
  enabled: false  # Disable embedded Keycloak
  
  # External Keycloak configuration
  external:
    enabled: true
    url: "https://auth.ohe-staging.platform-team.all-hands.dev"
    realm: "allhands"
```

## Adding a New Branch Client

Each branch deployment needs a client configured in Keycloak. This is handled automatically by the init container in the openhands chart.

The client will be created with:
- Client ID: `openhands-<branch-name>`
- Valid Redirect URIs: `https://<branch>.ohe-staging.platform-team.all-hands.dev/*`

## Configuring Google SAML

1. Go to Keycloak Admin Console: https://auth.ohe-staging.platform-team.all-hands.dev/auth/admin
2. Select the `allhands` realm
3. Go to Identity Providers → Add Provider → SAML v2.0
4. Configure with your Google Workspace SAML settings:
   - Alias: `google`
   - Service Provider Entity ID: `https://auth.ohe-staging.platform-team.all-hands.dev/auth/realms/allhands`
   - Single Sign-On Service URL: (from Google)
   - NameID Policy Format: Email
   - Principal Type: Subject NameID

## Outputs

After deployment, Terraform provides these outputs:

- `keycloak_url`: Public URL for Keycloak
- `keycloak_admin_console`: Admin console URL
- `keycloak_internal_url`: Internal cluster URL for branch deployments
- `branch_deployment_config`: Configuration values to use in branch helm values
