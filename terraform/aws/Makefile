TFVARS ?= terraform.tfvars

.PHONY: init plan apply destroy destroy-vm ssh copy-files urls fmt validate clean

init:
	terraform init

plan:
	terraform plan -var-file=$(TFVARS)

apply:
	terraform apply -var-file=$(TFVARS)

destroy:
	terraform destroy -var-file=$(TFVARS)

destroy-vm:
	terraform destroy -var-file=$(TFVARS) \
		-target=aws_eip_association.instance \
		-target=aws_instance.openhands \
		-target=aws_security_group.instance \
		-target=aws_route_table_association.public \
		-target=aws_route_table.public \
		-target=aws_subnet.public \
		-target=aws_internet_gateway.main \
		-target=aws_vpc.main

ssh:
	@terraform output -raw ssh_command

copy-files:
	scp \
		$$(terraform output -raw config_values_file) \
		$$(terraform output -raw certificate_file) \
		$$(terraform output -raw private_key_file) \
		ubuntu@$$(terraform output -raw instance_public_ip):~/

urls:
	@echo "Admin Console: $$(terraform output -raw admin_console_url)"
	@echo "App URL:       $$(terraform output -raw app_url)"
	@echo "Base URL:      $$(terraform output -raw base_url)"

fmt:
	terraform fmt -recursive

validate:
	terraform validate

clean:
	rm -rf .terraform .terraform.lock.hcl
	rm -f terraform.tfstate terraform.tfstate.backup
	rm -f *.pem *.config-values.yaml
