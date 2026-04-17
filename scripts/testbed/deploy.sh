#!/bin/bash
set -euo pipefail

# OpenHands Cloud Testbed Deployment Script
# ==========================================
# Deploy OpenHands Cloud to a testbed environment in Platform Team Sandbox
#
# Usage:
#   ./deploy.sh                    # Deploy to shared testbed
#   ./deploy.sh --name mytest      # Deploy to isolated environment "mytest"
#   ./deploy.sh --create-cluster   # Create new GKE cluster and deploy
#   ./deploy.sh --destroy          # Destroy your testbed environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Defaults
GCP_PROJECT="${GCP_PROJECT:-platform-team-sandbox-62793}"
GCP_REGION="${GCP_REGION:-us-central1}"
SHARED_CLUSTER_NAME="openhands-testbed"
NAMESPACE_PREFIX="testbed"
DNS_DOMAIN="sandbox.all-hands.dev"
CREATE_CLUSTER=false
DESTROY=false
TESTBED_NAME=""
DRY_RUN=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

show_usage() {
    cat << EOF
OpenHands Cloud Testbed Deployment

Usage: $(basename "$0") [OPTIONS]

Options:
  --name NAME           Deploy to isolated namespace 'testbed-NAME' (default: shared testbed)
  --create-cluster      Create a new GKE cluster for this testbed
  --destroy             Destroy the testbed environment
  --dry-run             Show what would be done without making changes
  --cluster NAME        Use specific cluster name (default: $SHARED_CLUSTER_NAME)
  --project PROJECT     GCP project ID (default: $GCP_PROJECT)
  --region REGION       GCP region (default: $GCP_REGION)
  --help                Show this help message

Examples:
  # Deploy current changes to the shared testbed
  ./deploy.sh

  # Deploy to your own isolated namespace
  ./deploy.sh --name saurya

  # Create a new cluster and deploy (for completely isolated testing)
  ./deploy.sh --name mytest --create-cluster

  # Destroy your isolated testbed
  ./deploy.sh --name saurya --destroy

Environment Variables:
  GCP_PROJECT           GCP project ID (default: platform-team-sandbox-62793)
  GCP_REGION            GCP region (default: us-central1)
  ANTHROPIC_API_KEY     API key for Anthropic (required for LLM)
  OPENAI_API_KEY        API key for OpenAI (optional)
  GITHUB_TOKEN          GitHub token for image pulls

EOF
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --name)
            TESTBED_NAME="$2"
            shift 2
            ;;
        --create-cluster)
            CREATE_CLUSTER=true
            shift
            ;;
        --destroy)
            DESTROY=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --cluster)
            SHARED_CLUSTER_NAME="$2"
            shift 2
            ;;
        --project)
            GCP_PROJECT="$2"
            shift 2
            ;;
        --region)
            GCP_REGION="$2"
            shift 2
            ;;
        --help|-h)
            show_usage
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            ;;
    esac
done

# Determine namespace and cluster names
if [[ -n "$TESTBED_NAME" ]]; then
    NAMESPACE="${NAMESPACE_PREFIX}-${TESTBED_NAME}"
    if [[ "$CREATE_CLUSTER" == "true" ]]; then
        CLUSTER_NAME="testbed-${TESTBED_NAME}"
    else
        CLUSTER_NAME="$SHARED_CLUSTER_NAME"
    fi
else
    NAMESPACE="${NAMESPACE_PREFIX}-shared"
    CLUSTER_NAME="$SHARED_CLUSTER_NAME"
fi

HOST_PREFIX="${NAMESPACE}"
APP_HOST="${HOST_PREFIX}.${DNS_DOMAIN}"
RUNTIME_HOST="runtime-${HOST_PREFIX}.${DNS_DOMAIN}"
AUTH_HOST="auth-${HOST_PREFIX}.${DNS_DOMAIN}"

log_info "Configuration:"
log_info "  GCP Project:  $GCP_PROJECT"
log_info "  GCP Region:   $GCP_REGION"
log_info "  Cluster:      $CLUSTER_NAME"
log_info "  Namespace:    $NAMESPACE"
log_info "  App URL:      https://$APP_HOST"

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local missing=()
    
    command -v gcloud >/dev/null 2>&1 || missing+=("gcloud")
    command -v kubectl >/dev/null 2>&1 || missing+=("kubectl")
    command -v helm >/dev/null 2>&1 || missing+=("helm")
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing required tools: ${missing[*]}"
        exit 1
    fi
    
    # Check gcloud auth
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        log_error "Not authenticated with gcloud. Run: gcloud auth login"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Create GKE cluster
create_cluster() {
    log_info "Creating GKE cluster '$CLUSTER_NAME'..."
    
    if gcloud container clusters describe "$CLUSTER_NAME" --project="$GCP_PROJECT" --region="$GCP_REGION" >/dev/null 2>&1; then
        log_warn "Cluster '$CLUSTER_NAME' already exists"
        return 0
    fi
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would create cluster '$CLUSTER_NAME'"
        return 0
    fi
    
    gcloud container clusters create "$CLUSTER_NAME" \
        --project="$GCP_PROJECT" \
        --region="$GCP_REGION" \
        --machine-type=e2-standard-4 \
        --num-nodes=1 \
        --enable-autoscaling \
        --min-nodes=1 \
        --max-nodes=5 \
        --disk-size=100 \
        --disk-type=pd-standard \
        --enable-ip-alias \
        --workload-pool="${GCP_PROJECT}.svc.id.goog" \
        --release-channel=regular \
        --no-enable-basic-auth \
        --metadata disable-legacy-endpoints=true
    
    log_success "Cluster '$CLUSTER_NAME' created"
}

# Connect to cluster
connect_cluster() {
    log_info "Connecting to cluster '$CLUSTER_NAME'..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would connect to cluster '$CLUSTER_NAME'"
        return 0
    fi
    
    gcloud container clusters get-credentials "$CLUSTER_NAME" \
        --project="$GCP_PROJECT" \
        --region="$GCP_REGION"
    
    log_success "Connected to cluster"
}

# Install third-party dependencies (Traefik, cert-manager)
install_dependencies() {
    log_info "Installing cluster dependencies..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would install Traefik and cert-manager"
        return 0
    fi
    
    # Check if Traefik is already installed
    if ! helm list -n traefik 2>/dev/null | grep -q traefik; then
        log_info "Installing Traefik..."
        helm repo add traefik https://traefik.github.io/charts 2>/dev/null || true
        helm repo update
        kubectl create namespace traefik 2>/dev/null || true
        helm upgrade --install traefik traefik/traefik \
            --namespace traefik \
            --set service.type=LoadBalancer \
            --wait
    else
        log_info "Traefik already installed"
    fi
    
    # Check if cert-manager is already installed
    if ! helm list -n cert-manager 2>/dev/null | grep -q cert-manager; then
        log_info "Installing cert-manager..."
        helm repo add jetstack https://charts.jetstack.io 2>/dev/null || true
        helm repo update
        kubectl create namespace cert-manager 2>/dev/null || true
        helm upgrade --install cert-manager jetstack/cert-manager \
            --namespace cert-manager \
            --set crds.enabled=true \
            --wait
        
        # Create ClusterIssuer for Let's Encrypt
        kubectl apply -f - << 'ISSUER_EOF'
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: platform-team@all-hands.dev
    privateKeySecretRef:
      name: letsencrypt-account-key
    solvers:
    - http01:
        ingress:
          class: traefik
ISSUER_EOF
    else
        log_info "cert-manager already installed"
    fi
    
    log_success "Dependencies installed"
}

# Create namespace and secrets
setup_namespace() {
    log_info "Setting up namespace '$NAMESPACE'..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would create namespace and secrets"
        return 0
    fi
    
    kubectl create namespace "$NAMESPACE" 2>/dev/null || log_info "Namespace already exists"
    
    # Generate random secrets
    GLOBAL_SECRET=$(head /dev/urandom | LC_ALL=C tr -dc 'A-Za-z0-9' | head -c 32)
    
    # Create secrets if they don't exist
    kubectl get secret jwt-secret -n "$NAMESPACE" >/dev/null 2>&1 || \
        kubectl create secret generic jwt-secret -n "$NAMESPACE" \
            --from-literal=jwt-secret="$GLOBAL_SECRET"
    
    kubectl get secret keycloak-realm -n "$NAMESPACE" >/dev/null 2>&1 || \
        kubectl create secret generic keycloak-realm -n "$NAMESPACE" \
            --from-literal=realm-name=allhands \
            --from-literal=server-url=http://keycloak \
            --from-literal=client-id=allhands \
            --from-literal=client-secret="$GLOBAL_SECRET" \
            --from-literal=smtp-password=""
    
    kubectl get secret keycloak-admin -n "$NAMESPACE" >/dev/null 2>&1 || \
        kubectl create secret generic keycloak-admin -n "$NAMESPACE" \
            --from-literal=admin-password="$GLOBAL_SECRET"
    
    kubectl get secret postgres-password -n "$NAMESPACE" >/dev/null 2>&1 || \
        kubectl create secret generic postgres-password -n "$NAMESPACE" \
            --from-literal=username=postgres \
            --from-literal=password="$GLOBAL_SECRET" \
            --from-literal=postgres-password="$GLOBAL_SECRET"
    
    kubectl get secret redis -n "$NAMESPACE" >/dev/null 2>&1 || \
        kubectl create secret generic redis -n "$NAMESPACE" \
            --from-literal=redis-password="$GLOBAL_SECRET"
    
    kubectl get secret lite-llm-api-key -n "$NAMESPACE" >/dev/null 2>&1 || \
        kubectl create secret generic lite-llm-api-key -n "$NAMESPACE" \
            --from-literal=lite-llm-api-key="$GLOBAL_SECRET"
    
    kubectl get secret admin-password -n "$NAMESPACE" >/dev/null 2>&1 || \
        kubectl create secret generic admin-password -n "$NAMESPACE" \
            --from-literal=admin-password="$GLOBAL_SECRET"
    
    kubectl get secret default-api-key -n "$NAMESPACE" >/dev/null 2>&1 || \
        kubectl create secret generic default-api-key -n "$NAMESPACE" \
            --from-literal=default-api-key="$GLOBAL_SECRET"
    
    kubectl get secret sandbox-api-key -n "$NAMESPACE" >/dev/null 2>&1 || \
        kubectl create secret generic sandbox-api-key -n "$NAMESPACE" \
            --from-literal=sandbox-api-key="$GLOBAL_SECRET"
    
    # Create LiteLLM env secrets if API keys are provided
    if [[ -n "${ANTHROPIC_API_KEY:-}" ]] || [[ -n "${OPENAI_API_KEY:-}" ]]; then
        local litellm_args=()
        [[ -n "${ANTHROPIC_API_KEY:-}" ]] && litellm_args+=(--from-literal=ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY")
        [[ -n "${OPENAI_API_KEY:-}" ]] && litellm_args+=(--from-literal=OPENAI_API_KEY="$OPENAI_API_KEY")
        
        kubectl delete secret litellm-env-secrets -n "$NAMESPACE" 2>/dev/null || true
        kubectl create secret generic litellm-env-secrets -n "$NAMESPACE" "${litellm_args[@]}"
        log_info "Created LiteLLM secrets with provided API keys"
    else
        log_warn "No ANTHROPIC_API_KEY or OPENAI_API_KEY provided. LLM functionality will not work."
        log_warn "Set environment variables and re-run, or create secret manually:"
        log_warn "  kubectl create secret generic litellm-env-secrets -n $NAMESPACE --from-literal=ANTHROPIC_API_KEY=<key>"
    fi
    
    # Create GitHub image pull secret if token provided
    if [[ -n "${GITHUB_TOKEN:-}" ]]; then
        kubectl delete secret ghcr-login-secret -n "$NAMESPACE" 2>/dev/null || true
        kubectl create secret docker-registry ghcr-login-secret -n "$NAMESPACE" \
            --docker-server=ghcr.io \
            --docker-username=openhands \
            --docker-password="$GITHUB_TOKEN"
        log_info "Created GitHub container registry secret"
    fi
    
    log_success "Namespace and secrets configured"
}

# Generate values file for this deployment
generate_values() {
    log_info "Generating Helm values..." >&2
    
    local values_file="$SCRIPT_DIR/values-${NAMESPACE}.yaml"
    
    cat > "$values_file" << YAML_EOF
# Auto-generated testbed values for $NAMESPACE
# Generated: $(date)

# Use in-cluster databases (no external dependencies)
postgresql:
  enabled: true
  primary:
    persistence:
      enabled: true
      size: 10Gi

redis:
  enabled: true

# Keycloak for authentication (no GitHub App required)
keycloak:
  enabled: true
  url: "https://${AUTH_HOST}"
  ingress:
    enabled: true
    hostname: "${AUTH_HOST}"
    annotations:
      cert-manager.io/cluster-issuer: letsencrypt

# Disable GitHub auth (use Keycloak email auth instead)
github:
  enabled: false

gitlab:
  enabled: false

bitbucket:
  enabled: false

# Main application ingress
ingress:
  enabled: true
  host: "${APP_HOST}"
  class: traefik
  root:
    annotations:
      cert-manager.io/cluster-issuer: letsencrypt

tls:
  enabled: true

# Runtime API (for sandbox execution)
runtime-api:
  enabled: true
  runtimeInSameCluster: true
  ingress:
    enabled: true
    host: "${RUNTIME_HOST}"
    annotations:
      cert-manager.io/cluster-issuer: letsencrypt
  env:
    RUNTIME_BASE_URL: "${HOST_PREFIX}.${DNS_DOMAIN}"
    STORAGE_CLASS: "standard-rwo"
    GCP_PROJECT: "${GCP_PROJECT}"
    GCP_REGION: "${GCP_REGION}"

sandbox:
  apiHostname: "https://${RUNTIME_HOST}"

# LiteLLM proxy for LLM access
litellm:
  enabled: true
  url: "http://litellm:4000"

litellm-helm:
  enabled: true
  ingress:
    enabled: false  # Internal only for testbed
  proxy_config:
    environment_variables:
      OR_APP_NAME: "OpenHands Testbed"
    model_list:
      - model_name: "anthropic/claude-sonnet-4-20250514"
        litellm_params:
          model: "anthropic/claude-sonnet-4-20250514"
          api_key: "os.environ/ANTHROPIC_API_KEY"

# Simplified environment for testbed
env:
  OH_APP_MODE: "saas"
  LITELLM_DEFAULT_MODEL: "litellm_proxy/anthropic/claude-sonnet-4-20250514"
  HIDE_LLM_SETTINGS: "false"
  GCP_PROJECT: "${GCP_PROJECT}"
  GCP_REGION: "${GCP_REGION}"

# Filestore - use ephemeral for testbed (simpler)
filestore:
  ephemeral: true

# Minimal resources for testbed
deployment:
  replicas: 1
  resources:
    requests:
      memory: 1Gi
      cpu: 500m
    limits:
      memory: 2Gi
      cpu: 1000m

# Disable production features
datadog:
  enabled: false

stripe:
  enabled: false

resend:
  enabled: false

automation:
  enabled: false

laminar:
  enabled: false
YAML_EOF
    
    log_success "Values file generated: $values_file" >&2
    echo "$values_file"
}

# Deploy OpenHands
deploy_openhands() {
    log_info "Deploying OpenHands..."
    
    local values_file
    values_file=$(generate_values)
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would deploy OpenHands with values:"
        cat "$values_file"
        return 0
    fi
    
    # Build helm dependencies
    cd "$REPO_ROOT/charts/openhands"
    helm dependency update
    
    # Deploy
    helm upgrade --install openhands . \
        --namespace "$NAMESPACE" \
        --values "$values_file" \
        --wait \
        --timeout 10m
    
    log_success "OpenHands deployed!"
}

# Destroy testbed
destroy_testbed() {
    log_info "Destroying testbed '$NAMESPACE'..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would destroy namespace '$NAMESPACE'"
        if [[ "$CREATE_CLUSTER" == "true" ]] && [[ -n "$TESTBED_NAME" ]]; then
            log_info "[DRY-RUN] Would delete cluster '$CLUSTER_NAME'"
        fi
        return 0
    fi
    
    # Delete helm release
    helm uninstall openhands --namespace "$NAMESPACE" 2>/dev/null || true
    
    # Delete namespace (this deletes all resources in it)
    kubectl delete namespace "$NAMESPACE" --wait=true 2>/dev/null || true
    
    # Delete cluster if it was created for this testbed
    if [[ "$CREATE_CLUSTER" == "true" ]] && [[ -n "$TESTBED_NAME" ]]; then
        log_info "Deleting cluster '$CLUSTER_NAME'..."
        gcloud container clusters delete "$CLUSTER_NAME" \
            --project="$GCP_PROJECT" \
            --region="$GCP_REGION" \
            --quiet
    fi
    
    # Clean up values file
    rm -f "$SCRIPT_DIR/values-${NAMESPACE}.yaml"
    
    log_success "Testbed destroyed"
}

# Show deployment info
show_info() {
    log_success "=========================================="
    log_success "OpenHands Testbed Deployed!"
    log_success "=========================================="
    echo ""
    echo "Application URL:  https://$APP_HOST"
    echo "Auth (Keycloak):  https://$AUTH_HOST"
    echo "Runtime API:      https://$RUNTIME_HOST"
    echo ""
    echo "Namespace:        $NAMESPACE"
    echo "Cluster:          $CLUSTER_NAME"
    echo ""
    echo "To access:"
    echo "  1. Wait for LoadBalancer IP: kubectl get svc -n traefik"
    echo "  2. Add DNS records pointing to the LoadBalancer IP"
    echo "     Or use port-forward: kubectl port-forward svc/openhands-service 3000:3000 -n $NAMESPACE"
    echo ""
    echo "To destroy:"
    echo "  ./deploy.sh --name $TESTBED_NAME --destroy"
    echo ""
    echo "To view logs:"
    echo "  kubectl logs -f deployment/openhands -n $NAMESPACE"
}

# Main
main() {
    check_prerequisites
    
    if [[ "$DESTROY" == "true" ]]; then
        connect_cluster
        destroy_testbed
        exit 0
    fi
    
    if [[ "$CREATE_CLUSTER" == "true" ]]; then
        create_cluster
    fi
    
    connect_cluster
    
    if [[ "$CREATE_CLUSTER" == "true" ]]; then
        install_dependencies
    fi
    
    setup_namespace
    deploy_openhands
    show_info
}

main
