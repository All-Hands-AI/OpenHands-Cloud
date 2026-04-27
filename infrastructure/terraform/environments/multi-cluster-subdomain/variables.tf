# -----------------------------------------------------------------------------
# Project Configuration
# -----------------------------------------------------------------------------

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for core cluster"
  type        = string
  default     = "us-central1"
}

variable "runtime_region" {
  description = "GCP region for runtime cluster (can be same or different)"
  type        = string
  default     = "us-central1"
}

variable "environment_name" {
  description = "Name of the environment (used as prefix for all resources)"
  type        = string
  default     = "oh-multi-subdomain"
}

# -----------------------------------------------------------------------------
# Core Cluster Network Configuration
# -----------------------------------------------------------------------------

variable "core_subnet_cidr" {
  description = "CIDR range for the core cluster subnet"
  type        = string
  default     = "10.0.0.0/20"
}

variable "core_pods_cidr" {
  description = "CIDR range for core cluster pods"
  type        = string
  default     = "10.48.0.0/14"
}

variable "core_services_cidr" {
  description = "CIDR range for core cluster services"
  type        = string
  default     = "10.52.0.0/20"
}

variable "core_master_ipv4_cidr_block" {
  description = "CIDR block for the core cluster master"
  type        = string
  default     = "172.16.0.0/28"
}

# -----------------------------------------------------------------------------
# Runtime Cluster Network Configuration
# -----------------------------------------------------------------------------

variable "runtime_subnet_cidr" {
  description = "CIDR range for the runtime cluster subnet"
  type        = string
  default     = "10.1.0.0/20"
}

variable "runtime_pods_cidr" {
  description = "CIDR range for runtime cluster pods"
  type        = string
  default     = "10.56.0.0/14"
}

variable "runtime_services_cidr" {
  description = "CIDR range for runtime cluster services"
  type        = string
  default     = "10.60.0.0/20"
}

variable "runtime_master_ipv4_cidr_block" {
  description = "CIDR block for the runtime cluster master"
  type        = string
  default     = "172.16.1.0/28"
}

# -----------------------------------------------------------------------------
# Shared Network Configuration
# -----------------------------------------------------------------------------

variable "enable_private_nodes" {
  description = "Enable private nodes (no public IPs on nodes)"
  type        = bool
  default     = true
}

variable "master_authorized_networks" {
  description = "CIDR blocks authorized to access the Kubernetes master"
  type = list(object({
    cidr_block   = string
    display_name = string
  }))
  default = [
    {
      cidr_block   = "0.0.0.0/0"
      display_name = "All (update for production)"
    }
  ]
}

# -----------------------------------------------------------------------------
# Core Cluster Configuration
# -----------------------------------------------------------------------------

variable "core_enable_autopilot" {
  description = "Enable GKE Autopilot mode for core cluster"
  type        = bool
  default     = false
}

variable "core_node_machine_type" {
  description = "Machine type for core cluster nodes"
  type        = string
  default     = "e2-standard-4"
}

variable "core_node_disk_size_gb" {
  description = "Disk size in GB for core cluster nodes"
  type        = number
  default     = 100
}

variable "core_node_pool_min_count" {
  description = "Minimum nodes in core cluster pool"
  type        = number
  default     = 1
}

variable "core_node_pool_max_count" {
  description = "Maximum nodes in core cluster pool"
  type        = number
  default     = 5
}

variable "core_node_pool_initial_count" {
  description = "Initial nodes in core cluster pool"
  type        = number
  default     = 2
}

# -----------------------------------------------------------------------------
# Runtime Cluster Configuration
# -----------------------------------------------------------------------------

variable "runtime_enable_autopilot" {
  description = "Enable GKE Autopilot mode for runtime cluster"
  type        = bool
  default     = false
}

variable "runtime_node_machine_type" {
  description = "Machine type for runtime cluster nodes"
  type        = string
  default     = "e2-standard-8"
}

variable "runtime_node_disk_size_gb" {
  description = "Disk size in GB for runtime cluster nodes"
  type        = number
  default     = 200
}

variable "runtime_node_pool_min_count" {
  description = "Minimum nodes in runtime cluster pool"
  type        = number
  default     = 0
}

variable "runtime_node_pool_max_count" {
  description = "Maximum nodes in runtime cluster pool"
  type        = number
  default     = 20
}

variable "runtime_node_pool_initial_count" {
  description = "Initial nodes in runtime cluster pool"
  type        = number
  default     = 2
}

# -----------------------------------------------------------------------------
# General Cluster Settings
# -----------------------------------------------------------------------------

variable "deletion_protection" {
  description = "Enable deletion protection for the clusters"
  type        = bool
  default     = false
}

# -----------------------------------------------------------------------------
# Domain Configuration
# -----------------------------------------------------------------------------

variable "domain" {
  description = "Domain for the environment (e.g., multi-subdomain.openhands-dev.com)"
  type        = string
}

variable "create_dns_zone" {
  description = "Create a Cloud DNS zone for the domain"
  type        = bool
  default     = false
}

# -----------------------------------------------------------------------------
# Labels
# -----------------------------------------------------------------------------

variable "labels" {
  description = "Labels to apply to all resources"
  type        = map(string)
  default     = {}
}
