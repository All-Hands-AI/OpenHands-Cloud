#!/bin/bash
set -euo pipefail

# Setup Shared OpenHands Testbed Cluster
# ======================================
# One-time setup script to create the shared testbed infrastructure
# in Platform Team Sandbox. Run this once to set up the cluster,
# then use deploy.sh for individual deployments.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration
GCP_PROJECT="${GCP_PROJECT:-platform-team-sandbox-62793}"
GCP_REGION="${GCP_REGION:-us-central1}"
CLUSTER_NAME="${CLUSTER_NAME:-openhands-testbed}"
DNS_ZONE_NAME="sandbox-all-hands-dev"
DNS_DOMAIN="sandbox.all-hands.dev"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

show_usage() {
    cat << EOF
Setup Shared OpenHands Testbed Cluster

This script creates the shared GKE cluster and DNS infrastructure
for the OpenHands testbed environment. Run this once before using
deploy.sh for individual deployments.

Usage: $(basename "$0") [OPTIONS]

Options:
  --skip-cluster        Skip GKE cluster creation (only setup addons)
  --skip-dns            Skip DNS zone creation
  --destroy             Destroy the shared cluster (CAUTION!)
  --help                Show this help message

Environment Variables:
  GCP_PROJECT           GCP project ID (default: $GCP_PROJECT)
  GCP_REGION            GCP region (default: $GCP_REGION)
  CLUSTER_NAME          GKE cluster name (default: $CLUSTER_NAME)

EOF
    exit 0
}

SKIP_CLUSTER=false
SKIP_DNS=false
DESTROY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-cluster)
            SKIP_CLUSTER=true
            shift
            ;;
        --skip-dns)
            SKIP_DNS=true
            shift
            ;;
        --destroy)
            DESTROY=true
            shift
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

# Enable required APIs
enable_apis() {
    log_info "Enabling required GCP APIs..."
    
    local apis=(
        "container.googleapis.com"
        "dns.googleapis.com"
        "compute.googleapis.com"
        "iam.googleapis.com"
        "cloudresourcemanager.googleapis.com"
    )
    
    for api in "${apis[@]}"; do
        gcloud services enable "$api" --project="$GCP_PROJECT" 2>/dev/null || true
    done
    
    log_success "APIs enabled"
}

# Create GKE cluster
create_cluster() {
    log_info "Creating GKE cluster '$CLUSTER_NAME'..."
    
    if gcloud container clusters describe "$CLUSTER_NAME" \
        --project="$GCP_PROJECT" \
        --region="$GCP_REGION" >/dev/null 2>&1; then
        log_warn "Cluster '$CLUSTER_NAME' already exists"
        return 0
    fi
    
    # Create VPC network
    local network_name="${CLUSTER_NAME}-network"
    if ! gcloud compute networks describe "$network_name" --project="$GCP_PROJECT" >/dev/null 2>&1; then
        log_info "Creating VPC network '$network_name'..."
        gcloud compute networks create "$network_name" \
            --project="$GCP_PROJECT" \
            --subnet-mode=auto
    fi
    
    # Create GKE cluster
    gcloud container clusters create "$CLUSTER_NAME" \
        --project="$GCP_PROJECT" \
        --region="$GCP_REGION" \
        --network="$network_name" \
        --machine-type=e2-standard-4 \
        --num-nodes=1 \
        --enable-autoscaling \
        --min-nodes=1 \
        --max-nodes=10 \
        --disk-size=100 \
        --disk-type=pd-standard \
        --enable-ip-alias \
        --workload-pool="${GCP_PROJECT}.svc.id.goog" \
        --release-channel=regular \
        --no-enable-basic-auth \
        --metadata disable-legacy-endpoints=true \
        --addons=HttpLoadBalancing,HorizontalPodAutoscaling \
        --labels=environment=testbed,team=platform
    
    log_success "Cluster '$CLUSTER_NAME' created"
}

# Connect to cluster
connect_cluster() {
    log_info "Connecting to cluster..."
    gcloud container clusters get-credentials "$CLUSTER_NAME" \
        --project="$GCP_PROJECT" \
        --region="$GCP_REGION"
    log_success "Connected to cluster"
}

# Create DNS zone
create_dns_zone() {
    log_info "Setting up DNS zone for '$DNS_DOMAIN'..."
    
    if gcloud dns managed-zones describe "$DNS_ZONE_NAME" \
        --project="$GCP_PROJECT" >/dev/null 2>&1; then
        log_warn "DNS zone '$DNS_ZONE_NAME' already exists"
        return 0
    fi
    
    gcloud dns managed-zones create "$DNS_ZONE_NAME" \
        --project="$GCP_PROJECT" \
        --description="DNS zone for OpenHands testbed" \
        --dns-name="${DNS_DOMAIN}."
    
    log_success "DNS zone created"
    
    # Show NS records
    log_info "DNS zone NS records (delegate these from parent zone):"
    gcloud dns managed-zones describe "$DNS_ZONE_NAME" \
        --project="$GCP_PROJECT" \
        --format="value(nameServers)"
}

# Install Traefik
install_traefik() {
    log_info "Installing Traefik ingress controller..."
    
    if helm list -n traefik 2>/dev/null | grep -q traefik; then
        log_warn "Traefik already installed"
        return 0
    fi
    
    helm repo add traefik https://traefik.github.io/charts 2>/dev/null || true
    helm repo update
    
    kubectl create namespace traefik 2>/dev/null || true
    
    helm upgrade --install traefik traefik/traefik \
        --namespace traefik \
        --set service.type=LoadBalancer \
        --set service.annotations."cloud\.google\.com/load-balancer-type"=External \
        --set ingressClass.enabled=true \
        --set ingressClass.isDefaultClass=true \
        --set providers.kubernetesIngress.publishedService.enabled=true \
        --wait
    
    log_success "Traefik installed"
    
    # Wait for LoadBalancer IP
    log_info "Waiting for LoadBalancer IP..."
    local max_wait=120
    local waited=0
    local lb_ip=""
    
    while [[ -z "$lb_ip" ]] && [[ $waited -lt $max_wait ]]; do
        lb_ip=$(kubectl get svc traefik -n traefik -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
        if [[ -z "$lb_ip" ]]; then
            sleep 5
            waited=$((waited + 5))
        fi
    done
    
    if [[ -n "$lb_ip" ]]; then
        log_success "LoadBalancer IP: $lb_ip"
        echo ""
        echo "Add wildcard DNS record: *.${DNS_DOMAIN} -> $lb_ip"
    else
        log_warn "LoadBalancer IP not yet assigned. Check later with:"
        log_warn "  kubectl get svc traefik -n traefik"
    fi
}

# Install cert-manager
install_cert_manager() {
    log_info "Installing cert-manager..."
    
    if helm list -n cert-manager 2>/dev/null | grep -q cert-manager; then
        log_warn "cert-manager already installed"
    else
        helm repo add jetstack https://charts.jetstack.io 2>/dev/null || true
        helm repo update
        
        kubectl create namespace cert-manager 2>/dev/null || true
        
        helm upgrade --install cert-manager jetstack/cert-manager \
            --namespace cert-manager \
            --set crds.enabled=true \
            --wait
        
        log_success "cert-manager installed"
    fi
    
    # Create ClusterIssuers
    log_info "Creating ClusterIssuers..."
    
    kubectl apply -f - << 'EOF'
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
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: platform-team@all-hands.dev
    privateKeySecretRef:
      name: letsencrypt-staging-account-key
    solvers:
    - http01:
        ingress:
          class: traefik
EOF
    
    log_success "ClusterIssuers created"
}

# Create storage class
create_storage_class() {
    log_info "Checking storage classes..."
    
    # Check if standard-rwo already exists (it's created by default in GKE)
    if kubectl get storageclass standard-rwo >/dev/null 2>&1; then
        log_info "Storage class 'standard-rwo' already exists"
    else
        log_info "Creating storage class 'standard-rwo'..."
        kubectl apply -f - << 'EOF'
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: standard-rwo
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: pd.csi.storage.gke.io
parameters:
  type: pd-standard
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
EOF
    fi
    
    log_success "Storage classes ready"
}

# Destroy everything
destroy_cluster() {
    log_warn "This will destroy the shared testbed cluster and all deployments!"
    read -p "Are you sure? (type 'yes' to confirm): " confirm
    
    if [[ "$confirm" != "yes" ]]; then
        log_info "Aborted"
        exit 1
    fi
    
    log_info "Destroying cluster '$CLUSTER_NAME'..."
    
    # Delete cluster
    gcloud container clusters delete "$CLUSTER_NAME" \
        --project="$GCP_PROJECT" \
        --region="$GCP_REGION" \
        --quiet || true
    
    # Delete DNS zone
    log_info "Deleting DNS zone..."
    gcloud dns managed-zones delete "$DNS_ZONE_NAME" \
        --project="$GCP_PROJECT" \
        --quiet || true
    
    # Delete VPC network
    local network_name="${CLUSTER_NAME}-network"
    log_info "Deleting VPC network..."
    gcloud compute networks delete "$network_name" \
        --project="$GCP_PROJECT" \
        --quiet || true
    
    log_success "Shared cluster destroyed"
}

# Show status
show_status() {
    echo ""
    log_success "=========================================="
    log_success "Shared Testbed Cluster Ready!"
    log_success "=========================================="
    echo ""
    echo "Cluster:      $CLUSTER_NAME"
    echo "Project:      $GCP_PROJECT"
    echo "Region:       $GCP_REGION"
    echo "DNS Domain:   $DNS_DOMAIN"
    echo ""
    
    local lb_ip
    lb_ip=$(kubectl get svc traefik -n traefik -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending")
    echo "LoadBalancer IP: $lb_ip"
    echo ""
    
    if [[ "$lb_ip" != "pending" ]]; then
        echo "DNS Setup Required:"
        echo "  Add wildcard A record: *.${DNS_DOMAIN} -> $lb_ip"
        echo ""
    fi
    
    echo "Next Steps:"
    echo "  1. Set up DNS wildcard record (see above)"
    echo "  2. Deploy your testbed:"
    echo "     cd $(dirname "$SCRIPT_DIR")"
    echo "     ./testbed/deploy.sh --name <your-name>"
    echo ""
}

# Main
main() {
    log_info "Setting up shared OpenHands testbed cluster..."
    log_info "Project: $GCP_PROJECT"
    log_info "Region:  $GCP_REGION"
    log_info "Cluster: $CLUSTER_NAME"
    echo ""
    
    if [[ "$DESTROY" == "true" ]]; then
        destroy_cluster
        exit 0
    fi
    
    enable_apis
    
    if [[ "$SKIP_DNS" != "true" ]]; then
        create_dns_zone
    fi
    
    if [[ "$SKIP_CLUSTER" != "true" ]]; then
        create_cluster
    fi
    
    connect_cluster
    create_storage_class
    install_traefik
    install_cert_manager
    
    show_status
}

main
