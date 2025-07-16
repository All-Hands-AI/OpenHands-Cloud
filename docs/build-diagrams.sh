#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

which d2 || (echo "d2 command not found, see: https://github.com/terrastruct/d2" ; exit 1)
export D2_LAYOUT=elk

d2 assets/fig1.d2 assets/fig1.svg
