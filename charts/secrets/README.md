# OpenHands Secrets Chart

This Helm chart creates Kubernetes `Secret` resources for all sensitive OpenHands configuration: database passwords, API keys, OAuth credentials, TLS certificates, and more.

## When is this chart used?

This chart is **only** used when deploying OpenHands with [Replicated](https://www.replicated.com/). In a Replicated deployment, secrets are materialized from the Replicated config screen _before_ the main `openhands` chart is installed.

If you are **not** using Replicated, you do not need this chart. Instead, create the required secrets directly via `kubectl create secret` or your own automation (e.g., Terraform, External Secrets Operator, sealed-secrets).

## Configuration

All configurable values are defined in: `values.yaml`