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
  value       = "ssh -i ${local_sensitive_file.ssh_private_key.filename} ubuntu@${aws_eip.instance.public_ip}"
}

output "ssh_key_file" {
  description = "Path to the generated SSH private key"
  value       = local_sensitive_file.ssh_private_key.filename
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

output "scp_command" {
  description = "SCP command to copy certificates to the instance"
  value       = "scp -i ${local_sensitive_file.ssh_private_key.filename} ${local_file.certificate_pem.filename} ${local_sensitive_file.private_key_pem.filename} ubuntu@${aws_eip.instance.public_ip}:~/"
}

output "certificate_file" {
  description = "Path to the generated certificate PEM"
  value       = local_file.certificate_pem.filename
}

output "private_key_file" {
  description = "Path to the generated private key PEM"
  value       = local_sensitive_file.private_key_pem.filename
}
