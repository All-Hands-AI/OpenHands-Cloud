# =============================================================================
# Required for Quick Start
# =============================================================================

instance_name   = "my-openhands"
base_domain     = "openhands.example.com"
route53_zone_id = "Z0123456789ABCDEFGHIJ"
acme_email      = "admin@example.com"

# =============================================================================
# Security — strongly recommended
# =============================================================================

# Restrict SSH and admin console access to your IP (or office CIDR).
# allowed_cidrs = ["203.0.113.0/32"]

# =============================================================================
# AWS
# =============================================================================

# aws_region = "us-east-1"

# =============================================================================
# EC2
# =============================================================================

# instance_type    = "m6i.4xlarge"   # 16 vCPU, 64 GB RAM
# root_volume_size = 200             # GB, gp3 encrypted
# ami_id           = ""              # Leave empty for latest Ubuntu 24.04 LTS

# =============================================================================
# Network
# =============================================================================

# Use an existing VPC and subnet instead of creating new ones.
# vpc_id    = "vpc-0123456789abcdef0"
# subnet_id = "subnet-0123456789abcdef0"

# Only used when creating a new VPC (vpc_id is not set).
# vpc_cidr    = "10.0.0.0/16"
# subnet_cidr = "10.0.1.0/24"

# =============================================================================
# DNS
# =============================================================================

# dns_ttl = 300

# =============================================================================
# Certificate
# =============================================================================

# provision_cert = true              # Set to false to use your own certificate
# acme_server    = "https://acme-v02.api.letsencrypt.org/directory"

# User-provided certificate paths (only when provision_cert = false)
# user_cert_path        = "/path/to/certificate.pem"
# user_private_key_path = "/path/to/private-key.pem"
# user_ca_path          = "/path/to/ca.pem"

# =============================================================================
# Tags
# =============================================================================

# default_tags = {
#   Environment = "dev"
#   Team        = "platform"
# }
