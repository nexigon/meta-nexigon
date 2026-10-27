#!/usr/bin/env bash
#
# Collect the release artifacts of a build under the filenames that Nexigon Hub
# and GitHub releases use:
#
#   <image-id>.img.<ext>     System image, such as `.img.wic.xz`.
#   <image-id>.rugixb        Rugix update bundle, with `<image-id>.rugixb.hash`.
#   <image-id>.raucb         RAUC update bundle.
#   <image-id>.spdx.json     SPDX 3 SBOM of the image.
#   <image-id>.vex.spdx.json SPDX 3 VEX document from sbom-cve-check.
#
# Usage:
#   ./scripts/collect-release.sh <machine> <output-dir>

set -euo pipefail

if [ $# -ne 2 ]; then
    echo "[ERROR] usage: $0 <machine> <output-dir>"
    exit 1
fi

MACHINE="$1"
OUTPUT_DIR="$2"

DEPLOY_DIR="build/tmp/deploy/images/$MACHINE"

if [ ! -d "$DEPLOY_DIR" ]; then
    echo "[ERROR] deploy directory not found: $DEPLOY_DIR"
    exit 1
fi

IMAGE_ID="$MACHINE"
OS_RELEASE_FILE="$DEPLOY_DIR/os-release"
if [ -e "$OS_RELEASE_FILE" ]; then
    FILE_IMAGE_ID=$(grep "^IMAGE_ID=" "$OS_RELEASE_FILE" | cut -d= -f2 | tr -d '"')
    if [ -n "$FILE_IMAGE_ID" ]; then
        IMAGE_ID="$FILE_IMAGE_ID"
    fi
fi

mkdir -p "$OUTPUT_DIR"

# Collect the file a deploy symlink points to, without copying it if possible.
collect() {
    local link="$1"
    local filename="$2"
    local target
    target=$(readlink -f "$link")
    echo "[INFO] collecting '$filename'"
    ln -f "$target" "$OUTPUT_DIR/$filename" 2>/dev/null || cp "$target" "$OUTPUT_DIR/$filename"
}

# The system image, preferring compressed images.
IMAGE_FOUND=false
for ext in wic.xz wic.bz2 wic.gz wic; do
    for link in "$DEPLOY_DIR"/*-"$MACHINE".rootfs."$ext"; do
        if [ -L "$link" ]; then
            collect "$link" "$IMAGE_ID.img.$ext"
            IMAGE_FOUND=true
            break 2
        fi
    done
done
if [ "$IMAGE_FOUND" = false ]; then
    echo "[WARN] no system image found in $DEPLOY_DIR"
fi

BUNDLE_FOUND=false
for link in "$DEPLOY_DIR"/*-"$MACHINE".rootfs.rugixb; do
    if [ -L "$link" ]; then
        collect "$link" "$IMAGE_ID.rugixb"
        if [ -e "$link.hash" ]; then
            collect "$link.hash" "$IMAGE_ID.rugixb.hash"
        fi
        BUNDLE_FOUND=true
        break
    fi
done
for link in "$DEPLOY_DIR"/*-"$MACHINE".raucb; do
    if [ -L "$link" ]; then
        collect "$link" "$IMAGE_ID.raucb"
        BUNDLE_FOUND=true
        break
    fi
done
if [ "$BUNDLE_FOUND" = false ]; then
    echo "[WARN] no update bundle found (neither .rugixb nor .raucb)"
fi

for link in "$DEPLOY_DIR"/*-"$MACHINE".rootfs.spdx.json; do
    if [ -L "$link" ]; then
        collect "$link" "$IMAGE_ID.spdx.json"
        break
    fi
done
if [ ! -e "$OUTPUT_DIR/$IMAGE_ID.spdx.json" ]; then
    echo "[WARN] no SPDX SBOM found in $DEPLOY_DIR"
fi

for link in "$DEPLOY_DIR"/*-"$MACHINE".rootfs.sbom-cve-check.spdx.json; do
    if [ -L "$link" ]; then
        collect "$link" "$IMAGE_ID.vex.spdx.json"
        break
    fi
done
