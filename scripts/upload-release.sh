#!/usr/bin/env bash
#
# Upload build artifacts to Nexigon Hub for the version pinned by prepare-release.sh.
#
# Usage:
#   ./scripts/upload-release.sh <machine>
#
# Examples:
#   ./scripts/upload-release.sh qemux86-64
#   ./scripts/upload-release.sh raspberrypi-armv8

set -euo pipefail

if [ -f .env ]; then
    . .env
fi

if [ -z "${NEXIGON_OTA_REPOSITORY:-}" ]; then
    echo "[ERROR] NEXIGON_OTA_REPOSITORY is not set"
    exit 1
fi

if [ -z "${NEXIGON_OTA_PACKAGE:-}" ]; then
    echo "[ERROR] NEXIGON_OTA_PACKAGE is not set"
    exit 1
fi

if [ ! -f .release.env ]; then
    echo "[ERROR] .release.env not found — run ./scripts/prepare-release.sh first"
    exit 1
fi

. .release.env

if [ $# -eq 0 ]; then
    echo "[ERROR] no machine specified"
    echo "usage: $0 <machine>"
    exit 1
fi

MACHINE="$1"

NEXIGON_CLI="${NEXIGON_CLI:-nexigon-cli}"

DEPLOY_DIR="build/tmp/deploy/images/$MACHINE"

if [ ! -d "$DEPLOY_DIR" ]; then
    echo "[ERROR] deploy directory not found: $DEPLOY_DIR"
    exit 1
fi

# Read IMAGE_ID from `os-release` and check version.
IMAGE_ID="$MACHINE"
OS_RELEASE_FILE="$DEPLOY_DIR/os-release"
if [ -e "$OS_RELEASE_FILE" ]; then
    FILE_IMAGE_ID=$(grep "^IMAGE_ID=" "$OS_RELEASE_FILE" | cut -d= -f2 | tr -d '"')
    if [ -n "$FILE_IMAGE_ID" ]; then
        IMAGE_ID="$FILE_IMAGE_ID"
    fi

    IMAGE_VERSION=$(grep "^IMAGE_VERSION=" "$OS_RELEASE_FILE" | cut -d= -f2 | tr -d '"')
    if [ -n "$IMAGE_VERSION" ] && [ "$IMAGE_VERSION" != "$VERSION" ]; then
        echo "[ERROR] version mismatch: os-release has '$IMAGE_VERSION' but .release.env has '$VERSION'"
        echo "[ERROR] the image was likely built with a different version; rebuild with ./scripts/build-release.sh"
        exit 1
    fi
fi

echo "[INFO] uploading artifacts for '$IMAGE_ID' (machine: $MACHINE) to version $VERSION_ID (tag: $BUILD_TAG)"

upload_asset() {
    local file="$1"
    local filename="$2"
    local metadata="${3:-}"

    echo "[INFO] uploading '$filename'"
    local asset_info
    asset_info=$($NEXIGON_CLI repositories assets upload "$NEXIGON_OTA_REPOSITORY" "$file")
    local asset_id
    asset_id=$(echo "$asset_info" | jq -r '.assetId')

    if [ -n "$metadata" ]; then
        $NEXIGON_CLI repositories versions assets add "$VERSION_ID" "$asset_id" "$filename" \
            --metadata "$metadata"
    else
        $NEXIGON_CLI repositories versions assets add "$VERSION_ID" "$asset_id" "$filename"
    fi
}

# Upload the system image (try common compression formats).
IMAGE_UPLOADED=false
for pattern in "$DEPLOY_DIR"/*-"$MACHINE".rootfs.wic.xz \
               "$DEPLOY_DIR"/*-"$MACHINE".rootfs.wic.bz2 \
               "$DEPLOY_DIR"/*-"$MACHINE".rootfs.wic.gz \
               "$DEPLOY_DIR"/*-"$MACHINE".rootfs.wic; do
    for img_file in $pattern; do
        if [ -e "$img_file" ] && [ -L "$img_file" -o ! "$img_file" != *-20* ]; then
            ext="${img_file#*.rootfs.}"
            upload_asset "$img_file" "$IMAGE_ID.img.$ext"
            IMAGE_UPLOADED=true
            break 2
        fi
    done
done

if [ "$IMAGE_UPLOADED" = false ]; then
    echo "[WARN] no system image found in $DEPLOY_DIR"
fi

# Upload the Rugix update bundle.
RUGIX_UPLOADED=false
for bundle_file in "$DEPLOY_DIR"/*-"$MACHINE".rootfs.rugixb; do
    if [ -e "$bundle_file" ] && [ -L "$bundle_file" ]; then
        bundle_metadata=$(jq -nc --arg version "$VERSION" '{version: $version}')
        hash_file="$bundle_file.hash"
        if [ -e "$hash_file" ]; then
            BUNDLE_HASH=$(cat "$hash_file")
            bundle_metadata=$(echo "$bundle_metadata" | jq -c --arg h "$BUNDLE_HASH" '.rugix = {bundleHash: $h}')
        fi
        upload_asset "$bundle_file" "$IMAGE_ID.rugixb" "$bundle_metadata"
        RUGIX_UPLOADED=true
        break
    fi
done

# Upload the RAUC update bundle.
RAUC_UPLOADED=false
for bundle_file in "$DEPLOY_DIR"/*-"$MACHINE".raucb; do
    if [ -e "$bundle_file" ] && [ -L "$bundle_file" ]; then
        bundle_metadata=$(jq -nc --arg version "$VERSION" '{version: $version}')
        upload_asset "$bundle_file" "$IMAGE_ID.raucb" "$bundle_metadata"
        RAUC_UPLOADED=true
        break
    fi
done

if [ "$RUGIX_UPLOADED" = false ] && [ "$RAUC_UPLOADED" = false ]; then
    echo "[WARN] no update bundle found (neither .rugixb nor .raucb)"
fi

echo "[INFO] upload complete"
