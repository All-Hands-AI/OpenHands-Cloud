TFVARS ?= terraform.tfvars

.PHONY: init plan apply destroy ssh urls fmt validate clean

init:
	terraform init

plan:
	terraform plan -var-file=$(TFVARS)

apply:
	terraform apply -var-file=$(TFVARS)

destroy:
	terraform destroy -var-file=$(TFVARS)

ssh:
	@terraform output -raw ssh_command

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
