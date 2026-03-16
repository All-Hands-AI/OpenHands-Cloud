# =============================================================================
# Required
# =============================================================================

instance_name   = "my-openhands"
ssh_key_name    = "my-key-pair"
route53_zone_id = "Z0123456789ABCDEFGHIJ"
base_domain     = "openhands.example.com"
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
# App credentials (optional)
# =============================================================================

# anthropic_api_key = ""

# GitHub OAuth App
# github_oauth_client_id     = ""
# github_oauth_client_secret = ""

# GitHub App
# github_app_id              = ""
# github_app_webhook_secret  = ""
# github_app_private_key     = ""

# =============================================================================
# Tags
# =============================================================================

# default_tags = {
#   Environment = "dev"
#   Team        = "platform"
# }
