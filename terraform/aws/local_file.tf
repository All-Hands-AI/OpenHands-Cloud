# -----------------------------------------------------------------------------
# Certificate files written to disk
# -----------------------------------------------------------------------------

resource "local_file" "certificate_pem" {
  content  = local.certificate_pem
  filename = "${path.module}/${var.instance_name}.certificate.pem"
}

resource "local_sensitive_file" "private_key_pem" {
  content         = local.private_key_pem
  filename        = "${path.module}/${var.instance_name}.private-key.pem"
  file_permission = "0600"
}

resource "local_file" "ca_pem" {
  content  = local.ca_pem
  filename = "${path.module}/${var.instance_name}.ca.pem"
}

# -----------------------------------------------------------------------------
# Replicated config-values.yaml
# -----------------------------------------------------------------------------

resource "local_sensitive_file" "config_values" {
  content = templatefile("${path.module}/config-values.yaml.tpl", {
    anthropic_api_key          = var.anthropic_api_key
    base_domain                = var.base_domain
    postgres_type              = "embedded_postgres"
    github_oauth_client_id     = var.github_oauth_client_id
    github_oauth_client_secret = var.github_oauth_client_secret
    github_app_id              = var.github_app_id
    github_app_webhook_secret  = var.github_app_webhook_secret
    github_app_private_key     = local.github_app_private_key_b64
    tls_certificate            = base64encode(local.certificate_pem)
    tls_private_key            = base64encode(local.private_key_pem)
    tls_ca_certificate         = base64encode(local.ca_pem)
  })
  filename        = "${path.module}/${var.instance_name}.config-values.yaml"
  file_permission = "0600"
}
