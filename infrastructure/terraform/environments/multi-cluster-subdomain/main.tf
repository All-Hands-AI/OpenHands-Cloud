# -----------------------------------------------------------------------------
# Multi Cluster - Subdomain-Based Routing Environment
# -----------------------------------------------------------------------------
# This environment deploys OpenHands to separate GKE clusters:
# - Core cluster: UI, API, and supporting services
# - Runtime cluster: OpenHands agent runtimes
#
# Traffic is routed using subdomains:
#   - app.domain.com (main app)
#   - auth.domain.com (keycloak)
#   - api.domain.com (runtime API)
#   - branch-name.domain.com (branch deploys)
# -----------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0.0"
    }
  }

  # Uncomment and configure for remote state
  # backend "gcs" {
  #   bucket = "your-terraform-state-bucket"
  #   prefix = "openhands/multi-cluster-subdomain"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# -----------------------------------------------------------------------------
# VPC Network (shared by both clusters)
# -----------------------------------------------------------------------------

module "vpc" {
  source = "../../modules/vpc-network"

  project_id    = var.project_id
  region        = var.region
  network_name  = "${var.environment_name}-vpc"
  subnet_name   = "${var.environment_name}-core-subnet"
  subnet_cidr   = var.core_subnet_cidr
  pods_cidr     = var.core_pods_cidr
  services_cidr = var.core_services_cidr

  # Create additional subnet for runtime cluster
  additional_subnets = [
    {
      name          = "${var.environment_name}-runtime-subnet"
      cidr          = var.runtime_subnet_cidr
      pods_cidr     = var.runtime_pods_cidr
      services_cidr = var.runtime_services_cidr
      region        = var.runtime_region
    }
  ]
}

# -----------------------------------------------------------------------------
# Core GKE Cluster
# -----------------------------------------------------------------------------

module "core_cluster" {
  source = "../../modules/gke-cluster"

  project_id   = var.project_id
  location     = var.region
  cluster_name = "${var.environment_name}-core"

  network_name        = module.vpc.network_name
  subnet_name         = module.vpc.subnet_name
  pods_range_name     = module.vpc.pods_range_name
  services_range_name = module.vpc.services_range_name

  enable_autopilot        = var.core_enable_autopilot
  enable_private_nodes    = var.enable_private_nodes
  enable_private_endpoint = false
  master_ipv4_cidr_block  = var.core_master_ipv4_cidr_block

  master_authorized_networks = var.master_authorized_networks

  # Core cluster nodes
  node_machine_type       = var.core_node_machine_type
  node_disk_size_gb       = var.core_node_disk_size_gb
  node_pool_min_count     = var.core_node_pool_min_count
  node_pool_max_count     = var.core_node_pool_max_count
  node_pool_initial_count = var.core_node_pool_initial_count

  # No runtime node pool in core cluster
  create_runtime_node_pool = false

  deletion_protection = var.deletion_protection

  labels = merge(var.labels, {
    environment  = var.environment_name
    routing-type = "subdomain-based"
    cluster-type = "multi"
    cluster-role = "core"
  })
}

# -----------------------------------------------------------------------------
# Runtime GKE Cluster
# -----------------------------------------------------------------------------

module "runtime_cluster" {
  source = "../../modules/gke-cluster"

  project_id   = var.project_id
  location     = var.runtime_region
  cluster_name = "${var.environment_name}-runtime"

  network_name        = module.vpc.network_name
  subnet_name         = module.vpc.additional_subnet_names[0]
  pods_range_name     = module.vpc.additional_pods_range_names[0]
  services_range_name = module.vpc.additional_services_range_names[0]

  enable_autopilot        = var.runtime_enable_autopilot
  enable_private_nodes    = var.enable_private_nodes
  enable_private_endpoint = false
  master_ipv4_cidr_block  = var.runtime_master_ipv4_cidr_block

  master_authorized_networks = var.master_authorized_networks

  # Runtime cluster optimized for agent workloads
  node_machine_type       = var.runtime_node_machine_type
  node_disk_size_gb       = var.runtime_node_disk_size_gb
  node_pool_min_count     = var.runtime_node_pool_min_count
  node_pool_max_count     = var.runtime_node_pool_max_count
  node_pool_initial_count = var.runtime_node_pool_initial_count

  create_runtime_node_pool = false

  deletion_protection = var.deletion_protection

  labels = merge(var.labels, {
    environment  = var.environment_name
    routing-type = "subdomain-based"
    cluster-type = "multi"
    cluster-role = "runtime"
  })
}

# -----------------------------------------------------------------------------
# Static IP for Ingress (Core cluster)
# -----------------------------------------------------------------------------

resource "google_compute_global_address" "ingress_ip" {
  name    = "${var.environment_name}-ingress-ip"
  project = var.project_id
}

# -----------------------------------------------------------------------------
# DNS Zone (optional)
# -----------------------------------------------------------------------------

resource "google_dns_managed_zone" "zone" {
  count = var.create_dns_zone ? 1 : 0

  name        = "${var.environment_name}-zone"
  project     = var.project_id
  dns_name    = "${var.domain}."
  description = "DNS zone for ${var.environment_name} OpenHands deployment"
}

# -----------------------------------------------------------------------------
# DNS Records for Subdomain Routing
# -----------------------------------------------------------------------------

# Root domain record
resource "google_dns_record_set" "root" {
  count = var.create_dns_zone ? 1 : 0

  name         = "${var.domain}."
  project      = var.project_id
  managed_zone = google_dns_managed_zone.zone[0].name
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_global_address.ingress_ip.address]
}

# Wildcard for all subdomains (app, auth, api, branches, etc.)
resource "google_dns_record_set" "wildcard" {
  count = var.create_dns_zone ? 1 : 0

  name         = "*.${var.domain}."
  project      = var.project_id
  managed_zone = google_dns_managed_zone.zone[0].name
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_global_address.ingress_ip.address]
}

# Double wildcard for nested subdomains (e.g., branch.auth.domain.com)
resource "google_dns_record_set" "double_wildcard" {
  count = var.create_dns_zone ? 1 : 0

  name         = "*.*.${var.domain}."
  project      = var.project_id
  managed_zone = google_dns_managed_zone.zone[0].name
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_global_address.ingress_ip.address]
}
