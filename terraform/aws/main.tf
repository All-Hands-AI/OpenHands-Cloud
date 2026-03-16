# -----------------------------------------------------------------------------
# Providers
# -----------------------------------------------------------------------------

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(
      { Name = var.instance_name },
      var.default_tags,
    )
  }
}

provider "acme" {
  server_url = var.acme_server
}

# -----------------------------------------------------------------------------
# AMI lookup — latest Ubuntu 24.04 LTS (Noble Numbat)
# -----------------------------------------------------------------------------

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# -----------------------------------------------------------------------------
# VPC
# -----------------------------------------------------------------------------

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${var.instance_name}-vpc" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = { Name = "${var.instance_name}-igw" }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.subnet_cidr
  map_public_ip_on_launch = true

  tags = { Name = "${var.instance_name}-public" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = { Name = "${var.instance_name}-rt" }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# -----------------------------------------------------------------------------
# Security Group
# -----------------------------------------------------------------------------

resource "aws_security_group" "instance" {
  name_prefix = "${var.instance_name}-"
  description = "OpenHands Replicated VM"
  vpc_id      = aws_vpc.main.id

  # --- Web traffic (open to all) ---
  ingress {
    description = "HTTP — app + ACME challenges"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS — app traffic"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # --- Admin ports (restricted) ---
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidrs
  }

  ingress {
    description = "KOTS Admin Console"
    from_port   = 30000
    to_port     = 30000
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidrs
  }

  # --- Internal NodePorts (restricted) ---
  ingress {
    description = "Traefik HTTP NodePort"
    from_port   = 30080
    to_port     = 30080
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidrs
  }

  ingress {
    description = "Traefik HTTPS NodePort"
    from_port   = 30443
    to_port     = 30443
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidrs
  }

  # --- Egress ---
  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.instance_name}-sg" }
}

# -----------------------------------------------------------------------------
# Elastic IP
# -----------------------------------------------------------------------------

resource "aws_eip" "instance" {
  domain = "vpc"

  tags = { Name = "${var.instance_name}-eip" }
}

resource "aws_eip_association" "instance" {
  instance_id   = aws_instance.openhands.id
  allocation_id = aws_eip.instance.id
}

# -----------------------------------------------------------------------------
# EC2 Instance
# -----------------------------------------------------------------------------

resource "aws_instance" "openhands" {
  ami           = var.ami_id != "" ? var.ami_id : data.aws_ami.ubuntu.id
  instance_type = var.instance_type
  key_name      = var.ssh_key_name
  subnet_id     = aws_subnet.public.id

  vpc_security_group_ids = [aws_security_group.instance.id]

  root_block_device {
    volume_size = var.root_volume_size
    volume_type = "gp3"
    encrypted   = true
  }

  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  user_data = <<-USERDATA
    #!/bin/bash
    set -euo pipefail

    # Install kubectl
    snap install kubectl --classic

    # Install k9s
    snap install k9s --classic
  USERDATA

  tags = { Name = var.instance_name }

  lifecycle {
    ignore_changes = [ami]
  }
}
