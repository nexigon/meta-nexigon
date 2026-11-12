#!/usr/bin/env bash
set -euo pipefail

repository_root="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$repository_root"
: "${RUGIX_TESTKIT:?RUGIX_TESTKIT must be set by mise}"

OVMF_DIR="$(nix build --inputs-from "$repository_root" --no-link --print-out-paths nixpkgs#legacyPackages.x86_64-linux.OVMF.fd)"
export OVMF_DIR
exec uv run --with "$RUGIX_TESTKIT" \
    --with 'nexigon-hub-sdk @ git+https://github.com/nexigon/nexigon-sdk-python.git' \
    --with pytest --with pytest-timeout \
    pytest "$@"
