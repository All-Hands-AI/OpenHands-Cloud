#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

# Go into docs folder if we're not already there.
cd docs || true

which d2 || (echo "d2 command not found, see: https://github.com/terrastruct/d2" ; exit 1)
export D2_LAYOUT=elk

d2 assets/fig1.d2 assets/fig1.svg
