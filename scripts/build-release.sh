#!/usr/bin/env bash
#
# Build an image using the version pinned by prepare-release.sh.

set -euo pipefail

if [ -f .env ]; then
    . .env
fi

if [ ! -f .release.env ]; then
    echo "[ERROR] .release.env not found — run ./scripts/prepare-release.sh first"
    exit 1
fi

. .release.env

if [ $# -eq 0 ]; then
    echo "[ERROR] no KAS config specified"
    echo "usage: $0 <kas-config>"
    exit 1
fi

export IMAGE_VERSION="$VERSION"

kas-container \
    --runtime-args "-e IMAGE_VERSION -e NEXIGON_HUB_URL -e NEXIGON_TOKEN -e NEXIGON_OTA_REPOSITORY -e NEXIGON_OTA_PACKAGE -e NEXIGON_OTA_TAG -e RAUC_KEYS_DIR" \
    build "$@"
