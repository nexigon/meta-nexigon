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

# Next to the build, so that collecting links the artifacts instead of copying them.
ARTIFACTS_DIR=$(mktemp -d build/release.XXXXXX)
trap 'rm -rf "$ARTIFACTS_DIR"' EXIT
"$(dirname "$0")/collect-release.sh" "$MACHINE" "$ARTIFACTS_DIR"

upload_asset() {
    local file="$1"
    local metadata="${2:-}"
    local filename
    filename=$(basename "$file")

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

# Upload the SBOM first, so that the image and update bundles can link it.
# Nexigon Hub indexes SBOMs linked through `relations.sbom`.
SBOM_FILE="$ARTIFACTS_DIR/$IMAGE_ID.spdx.json"
if [ -e "$SBOM_FILE" ]; then
    upload_asset "$SBOM_FILE"
fi

# Print the metadata of an artifact: the given metadata with a link to the SBOM.
artifact_metadata() {
    local metadata="$1"
    if [ -e "$SBOM_FILE" ]; then
        jq -nc --argjson m "$metadata" --arg sbom "$(basename "$SBOM_FILE")" \
            '$m + {relations: {sbom: [$sbom]}}'
    elif [ "$metadata" != "{}" ]; then
        echo "$metadata"
    fi
}

for image_file in "$ARTIFACTS_DIR/$IMAGE_ID".img.*; do
    if [ -e "$image_file" ]; then
        upload_asset "$image_file" "$(artifact_metadata '{}')"
    fi
done

RUGIX_BUNDLE="$ARTIFACTS_DIR/$IMAGE_ID.rugixb"
if [ -e "$RUGIX_BUNDLE" ]; then
    bundle_metadata="{}"
    if [ -e "$RUGIX_BUNDLE.hash" ]; then
        bundle_metadata=$(jq -nc --arg h "$(cat "$RUGIX_BUNDLE.hash")" '{rugix: {bundleHash: $h}}')
    fi
    upload_asset "$RUGIX_BUNDLE" "$(artifact_metadata "$bundle_metadata")"
fi

RAUC_BUNDLE="$ARTIFACTS_DIR/$IMAGE_ID.raucb"
if [ -e "$RAUC_BUNDLE" ]; then
    upload_asset "$RAUC_BUNDLE" "$(artifact_metadata '{}')"
fi

echo "[INFO] upload complete"
