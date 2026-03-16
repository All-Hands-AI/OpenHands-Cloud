# AWS Terraform for Replicated OpenHands VM

Provisions a single AWS EC2 instance with all supporting infrastructure needed to install OpenHands via Replicated's embedded cluster.

## What Gets Created

- **VPC** with a public subnet, internet gateway, and route table
- **EC2 instance** (default `m6i.4xlarge` — 16 vCPU, 64 GB) with 200 GB encrypted gp3 volume
- **Elastic IP** for a stable public address across stop/start cycles
- **Security group** with tiered access (web open, admin restricted)
- **Route 53 A records** for the base domain + all subdomains
- **TLS certificate** via Let's Encrypt (or bring your own)
- **config-values.yaml** ready for the Replicated installer

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5.0
- AWS CLI configured with credentials (`aws configure` or environment variables)
- An existing **EC2 key pair** in the target region
- A **Route 53 hosted zone** for your domain
- A Replicated license file (`.yaml`)

## Quick Start

1. **Clone the repo and navigate here:**

   ```bash
   cd terraform/aws
   ```

2. **Copy the example variables file:**

   ```bash
   cp example.tfvars terraform.tfvars
   ```

3. **Edit `terraform.tfvars`** with your values. At minimum set:

   - `instance_name` — a name for your instance
   - `ssh_key_name` — your EC2 key pair name
   - `route53_zone_id` — your hosted zone ID
   - `base_domain` — e.g. `openhands.example.com`
   - `acme_email` — for Let's Encrypt registration
   - `allowed_cidrs` — restrict to your IP for security

4. **Initialize Terraform:**

   ```bash
   make init
   ```

5. **Preview the plan:**

   ```bash
   make plan
   ```

6. **Apply:**

   ```bash
   make apply
   ```

7. **SSH into the instance:**

   ```bash
   $(terraform output -raw ssh_command)
   ```

8. **Install Replicated embedded cluster** (on the VM):

   ```bash
   curl -f https://replicated.app/embedded/YOUR_APP_SLUG/YOUR_CHANNEL | sudo bash -s join
   ```

9. **Open the KOTS Admin Console:**

   ```
   http://<instance-ip>:30000
   ```

10. **Upload your license and config-values.yaml**, then deploy OpenHands.

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `instance_name` | *(required)* | Name tag for EC2 instance and resources |
| `ssh_key_name` | *(required)* | Existing EC2 key pair name |
| `route53_zone_id` | *(required)* | Route 53 hosted zone ID |
| `base_domain` | *(required)* | Base domain (e.g. `openhands.example.com`) |
| `aws_region` | `us-east-1` | AWS region |
| `instance_type` | `m6i.4xlarge` | EC2 instance type |
| `root_volume_size` | `200` | Root volume size in GB |
| `ami_id` | *(auto)* | AMI override; defaults to Ubuntu 24.04 LTS |
| `allowed_cidrs` | `["0.0.0.0/0"]` | CIDRs for SSH + admin access |
| `vpc_cidr` | `10.0.0.0/16` | VPC CIDR block |
| `subnet_cidr` | `10.0.1.0/24` | Public subnet CIDR block |
| `dns_ttl` | `300` | DNS record TTL in seconds |
| `provision_cert` | `true` | Use Let's Encrypt; set `false` for BYO cert |
| `acme_email` | `""` | Email for Let's Encrypt account |
| `acme_server` | LE production | ACME directory URL |
| `anthropic_api_key` | `""` | Anthropic API key |
| `github_oauth_client_id` | `""` | GitHub OAuth client ID |
| `github_oauth_client_secret` | `""` | GitHub OAuth client secret |
| `github_app_id` | `""` | GitHub App ID |
| `github_app_webhook_secret` | `""` | GitHub App webhook secret |
| `github_app_private_key` | `""` | GitHub App private key (PEM) |
| `default_tags` | `{}` | Additional tags for all AWS resources |

## Certificate Modes

### Let's Encrypt (default)

Set `provision_cert = true` and provide `acme_email`. The ACME provider uses Route 53 DNS challenges — your AWS credentials are reused automatically. Ports 80/443 must be open (they are by default).

### Bring Your Own Certificate

Set `provision_cert = false` and provide paths to your certificate files:

```hcl
provision_cert        = false
user_cert_path        = "/path/to/certificate.pem"
user_private_key_path = "/path/to/private-key.pem"
user_ca_path          = "/path/to/ca.pem"
```

The certificate must cover the base domain and all subdomains: `app.`, `auth.app.`, `llm-proxy.`, `runtime-api.`, and `*.runtime.`.

## Cleanup

```bash
make destroy
```

This removes all AWS resources created by Terraform.

## Troubleshooting

**`terraform plan` fails with credential errors:**
Ensure AWS credentials are configured (`aws sts get-caller-identity` should succeed).

**ACME certificate fails:**
- Verify the Route 53 zone ID is correct
- Ensure `acme_email` is set
- Check that DNS records are resolvable: `dig app.<your-domain>`
- If hitting rate limits, switch to the staging server: `acme_server = "https://acme-staging-v02.api.letsencrypt.org/directory"`

**Cannot SSH into instance:**
- Verify `ssh_key_name` matches a key pair in the target region
- Check `allowed_cidrs` includes your IP
- The default user is `ubuntu`

**KOTS Admin Console not reachable:**
- Port 30000 must be allowed from your IP (check `allowed_cidrs`)
- The Replicated installer must have completed on the VM first

**Instance not reachable after stop/start:**
The Elastic IP remains associated across stop/start cycles, so the IP should not change. If networking issues persist, check the security group and route table.
