# -----------------------------------------------------------------------------
# Route 53 A Records
# -----------------------------------------------------------------------------

locals {
  dns_records = {
    base         = var.base_domain
    app          = "app.${var.base_domain}"
    analytics    = "analytics.app.${var.base_domain}"
    auth         = "auth.app.${var.base_domain}"
    llm_proxy    = "llm-proxy.${var.base_domain}"
    runtime_api  = "runtime-api.${var.base_domain}"
    runtime_wild = "*.runtime.${var.base_domain}"
  }
}

resource "aws_route53_record" "records" {
  for_each = var.route53_zone_id != "" ? local.dns_records : {}

  zone_id = var.route53_zone_id
  name    = each.value
  type    = "A"
  ttl     = var.dns_ttl
  records = [aws_eip.instance.public_ip]
}
