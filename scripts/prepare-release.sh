#!/usr/bin/env bash
#
# Prepare a new release: generate a version, create it in Nexigon Hub, and
# write a .release.env file that pins the version for subsequent build and
# upload steps.

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

NEXIGON_CLI="${NEXIGON_CLI:-nexigon-cli}"

TIMESTAMP=$(date +"%Y%m%d%H%M%S")
GIT_COMMIT=$(git rev-parse --short HEAD)
GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

BUILD_TAG=${BUILD_TAG:-"build-${TIMESTAMP}-${GIT_COMMIT}"}
FLOATING_TAG=${FLOATING_TAG:-"latest-build-${GIT_BRANCH//\//-}"}

# The release version is the build tag itself. It gets baked into the image
# as IMAGE_VERSION and is used as a locked tag in the Nexigon repository.
VERSION="$BUILD_TAG"

PACKAGE_PATH="$NEXIGON_OTA_REPOSITORY/$NEXIGON_OTA_PACKAGE"
VERSION_PATH="$PACKAGE_PATH/$BUILD_TAG"

# Create the build version, if it doesn't exist.
BUILD_VERSION_INFO=$($NEXIGON_CLI repositories versions resolve "$VERSION_PATH")
if [ "$(echo "$BUILD_VERSION_INFO" | jq -r '.result')" == "Found" ]; then
    echo "[INFO] build version already exists, reusing it"
    VERSION_ID=$(echo "$BUILD_VERSION_INFO" | jq -r '.versionId')
else
    echo "[INFO] creating build version"
    VERSION_ID=$($NEXIGON_CLI repositories versions create "$PACKAGE_PATH" \
        --tag "$BUILD_TAG,locked" --tag "$FLOATING_TAG,reassign" | jq -r '.versionId')
fi

echo "[INFO] BUILD_TAG=$BUILD_TAG"
echo "[INFO] VERSION=$VERSION"
echo "[INFO] VERSION_ID=$VERSION_ID"

cat > .release.env <<EOF
BUILD_TAG=$BUILD_TAG
FLOATING_TAG=$FLOATING_TAG
VERSION=$VERSION
VERSION_ID=$VERSION_ID
EOF

echo "[INFO] wrote .release.env"
