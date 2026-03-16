apiVersion: kots.io/v1beta1
kind: ConfigValues
metadata:
  name: openhands-config
spec:
  values:
    anthropic_api_key:
      value: "${anthropic_api_key}"
    base_domain:
      value: "${base_domain}"
    postgres_type:
      value: "${postgres_type}"
    github_oauth_client_id:
      value: "${github_oauth_client_id}"
    github_oauth_client_secret:
      value: "${github_oauth_client_secret}"
    github_app_id:
      value: "${github_app_id}"
    github_app_webhook_secret:
      value: "${github_app_webhook_secret}"
    github_app_private_key:
      value: "${github_app_private_key}"
    tls_certificate:
      value: "${tls_certificate}"
    tls_private_key:
      value: "${tls_private_key}"
    tls_ca_certificate:
      value: "${tls_ca_certificate}"
