# -----------------------------------------------------------------------------
# Certificate files written to disk
# -----------------------------------------------------------------------------

resource "local_file" "certificate_pem" {
  content  = local.certificate_pem
  filename = "${path.module}/certs/${var.instance_name}.certificate.pem"
}

resource "local_sensitive_file" "private_key_pem" {
  content         = local.private_key_pem
  filename        = "${path.module}/certs/${var.instance_name}.private-key.pem"
  file_permission = "0600"
}

resource "local_file" "ca_pem" {
  content  = local.ca_pem
  filename = "${path.module}/certs/${var.instance_name}.ca.pem"
}
