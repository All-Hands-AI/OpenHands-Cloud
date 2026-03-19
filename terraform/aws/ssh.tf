# -----------------------------------------------------------------------------
# SSH Key Pair — auto-generated
# -----------------------------------------------------------------------------

resource "tls_private_key" "ssh" {
  algorithm = "ED25519"
}

resource "aws_key_pair" "generated" {
  key_name   = "${var.instance_name}-ssh"
  public_key = tls_private_key.ssh.public_key_openssh
}

resource "local_sensitive_file" "ssh_private_key" {
  content         = tls_private_key.ssh.private_key_openssh
  filename        = "${path.module}/ssh/${var.instance_name}.pem"
  file_permission = "0600"
}
