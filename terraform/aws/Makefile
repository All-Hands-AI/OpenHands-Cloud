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

ssh:
	@$$(terraform output -raw ssh_command)

copy-files:
	@$$(terraform output -raw scp_command)

ip:
	@terraform output -raw instance_public_ip

fmt:
	terraform fmt -recursive

validate:
	terraform validate

clean:
	rm -rf .terraform .terraform.lock.hcl
	rm -f terraform.tfstate terraform.tfstate.backup
	rm -rf certs/
	rm -rf ssh/
