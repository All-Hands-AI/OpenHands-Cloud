output "instance_public_ip" {
  description = "Elastic IP address of the EC2 instance"
  value       = aws_eip.instance.public_ip
}

output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.openhands.id
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh ubuntu@${aws_eip.instance.public_ip}"
}

output "admin_console_url" {
  description = "KOTS Admin Console URL"
  value       = "http://${aws_eip.instance.public_ip}:30000"
}

output "app_url" {
  description = "OpenHands application URL"
  value       = "https://app.${var.base_domain}"
}

output "base_url" {
  description = "OpenHands base URL"
  value       = "https://${var.base_domain}"
}

output "config_values_file" {
  description = "Path to the generated config-values.yaml"
  value       = local_sensitive_file.config_values.filename
}
