#!/bin/bash
# Decrypt a SOPS-encrypted file
set -eo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <file_to_decrypt>"
    exit 1
fi

input_file="$1"
decrypted_file="decrypted.yaml"

if [ ! -f "$input_file" ]; then
    echo "Error: File $input_file not found"
    exit 1
fi

sops --decrypt "$input_file" > "$decrypted_file"

echo "File decrypted and saved as $decrypted_file"
