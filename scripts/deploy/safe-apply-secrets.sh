#!/bin/bash
# Safely apply Kubernetes secrets (create or update without overwriting unchanged data)
set -eo pipefail

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <secret_file> [kubectl_args...]"
    exit 1
fi

secret_file="$1"
shift
kubectl_args="$@"

if [ ! -f "$secret_file" ]; then
    echo "Error: File $secret_file not found"
    exit 1
fi

# Apply the secret using server-side apply for idempotent updates
kubectl apply -f "$secret_file" $kubectl_args

echo "Secret applied successfully"
