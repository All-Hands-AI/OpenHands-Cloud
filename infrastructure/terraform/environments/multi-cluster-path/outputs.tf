# -----------------------------------------------------------------------------
# Core Cluster Outputs
# -----------------------------------------------------------------------------

output "core_cluster_name" {
  description = "Name of the core GKE cluster"
  value       = module.core_cluster.cluster_name
}

output "core_cluster_endpoint" {
  description = "Endpoint of the core GKE cluster"
  value       = module.core_cluster.cluster_endpoint
  sensitive   = true
}

output "core_get_credentials_command" {
  description = "Command to get core cluster credentials"
  value       = module.core_cluster.get_credentials_command
}

# -----------------------------------------------------------------------------
# Runtime Cluster Outputs
# -----------------------------------------------------------------------------

output "runtime_cluster_name" {
  description = "Name of the runtime GKE cluster"
  value       = module.runtime_cluster.cluster_name
}

output "runtime_cluster_endpoint" {
  description = "Endpoint of the runtime GKE cluster"
  value       = module.runtime_cluster.cluster_endpoint
  sensitive   = true
}

output "runtime_get_credentials_command" {
  description = "Command to get runtime cluster credentials"
  value       = module.runtime_cluster.get_credentials_command
}

# -----------------------------------------------------------------------------
# Network Outputs
# -----------------------------------------------------------------------------

output "network_name" {
  description = "Name of the VPC network"
  value       = module.vpc.network_name
}

output "ingress_ip" {
  description = "Static IP address for ingress"
  value       = google_compute_global_address.ingress_ip.address
}

# -----------------------------------------------------------------------------
# DNS Outputs
# -----------------------------------------------------------------------------

output "dns_zone_name" {
  description = "Name of the DNS zone (if created)"
  value       = var.create_dns_zone ? google_dns_managed_zone.zone[0].name : null
}

output "dns_name_servers" {
  description = "DNS name servers (if zone created)"
  value       = var.create_dns_zone ? google_dns_managed_zone.zone[0].name_servers : null
}

# -----------------------------------------------------------------------------
# Environment Summary
# -----------------------------------------------------------------------------

output "environment_info" {
  description = "Summary of the environment"
  value = {
    environment_name     = var.environment_name
    routing_type         = "path-based"
    cluster_type         = "multi"
    domain               = var.domain
    core_cluster_name    = module.core_cluster.cluster_name
    runtime_cluster_name = module.runtime_cluster.cluster_name
    ingress_ip           = google_compute_global_address.ingress_ip.address
  }
}
