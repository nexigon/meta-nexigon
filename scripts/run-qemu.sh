#!/usr/bin/env bash
set -euo pipefail

repository_root="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$repository_root"
: "${RUGIX_TESTKIT:?RUGIX_TESTKIT must be set by mise}"
: "${KAS_BUILD_DIR:?KAS_BUILD_DIR must be set by mise}"

ovmf="$(nix build --inputs-from "$repository_root" --no-link --print-out-paths nixpkgs#legacyPackages.x86_64-linux.OVMF.fd)"
exec uv run --with "$RUGIX_TESTKIT" \
    --with 'nexigon-hub-sdk @ git+https://github.com/nexigon/nexigon-sdk-python.git' \
    --with pytest --with pytest-timeout \
    rugix-testkit run --arch x86_64 --ssh-port 2222 \
    --drive "$KAS_BUILD_DIR/tmp/deploy/images/qemux86-64/core-image-minimal-qemux86-64.rootfs.wic,overlay=true,size=16G" \
    --pflash "$ovmf/FV/OVMF_CODE.fd,format=raw,readonly=true" \
    --pflash "$ovmf/FV/OVMF_VARS.fd,format=raw" \
    "$@"
