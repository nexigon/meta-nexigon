#!/usr/bin/env bash
set -euo pipefail

cd -- "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
: "${KAS_WORK_DIR:?KAS_WORK_DIR must be set by mise}"
: "${KAS_BUILD_DIR:?KAS_BUILD_DIR must be set by mise}"
: "${KAS_TMP_DIR:?KAS_TMP_DIR must be set by mise}"
if [[ "$KAS_TMP_DIR" =~ [[:space:]] ]]; then
    echo "kas-container runtime options cannot contain whitespace. Set KAS_TMP_DIR to a path without whitespace." >&2
    exit 1
fi

mkdir -p "$KAS_WORK_DIR" "$KAS_BUILD_DIR" "$KAS_TMP_DIR"
chmod 1777 "$KAS_TMP_DIR"
exec kas-container --runtime-args \
    "-e IMAGE_VERSION -e NEXIGON_OTA_REPOSITORY -e NEXIGON_OTA_PACKAGE -e NEXIGON_OTA_TAG -e RAUC_KEYS_DIR -e SI_RUNNERS_PREMIRRORS -v $KAS_TMP_DIR:/tmp:rw" \
    "$@"
