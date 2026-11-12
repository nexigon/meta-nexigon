#!/usr/bin/env bash
set -euo pipefail

cd -- "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
destination="${1:-$PWD/rauc-keys}"
use_shared_keys=false

# Shared development keys, for example from CI secrets, take precedence.
if [[ -n "${RAUC_DEV_CA_CERT:-}${RAUC_DEV_SIGNING_CERT:-}${RAUC_DEV_SIGNING_KEY:-}" ]]; then
    if [[ -z "${RAUC_DEV_CA_CERT:-}" || -z "${RAUC_DEV_SIGNING_CERT:-}" || -z "${RAUC_DEV_SIGNING_KEY:-}" ]]; then
        echo "Set all of RAUC_DEV_CA_CERT, RAUC_DEV_SIGNING_CERT, and RAUC_DEV_SIGNING_KEY." >&2
        exit 1
    fi
    use_shared_keys=true
elif [[ -e "$destination/ca.cert.pem" || -e "$destination/development-1.cert.pem" || -e "$destination/development-1.key.pem" ]]; then
    if [[ -s "$destination/ca.cert.pem" && -s "$destination/development-1.cert.pem" && -s "$destination/development-1.key.pem" ]]; then
        echo "Keys already exist in $destination. Delete the directory to regenerate."
        exit 0
    fi
    echo "Incomplete RAUC keys in $destination. Remove or restore the files before generating keys." >&2
    exit 1
fi

umask 077
staging_directory="$(mktemp -d)"
trap 'rm -rf -- "$staging_directory"' EXIT

if [[ "$use_shared_keys" == true ]]; then
    printf '%s\n' "$RAUC_DEV_CA_CERT" > "$staging_directory/ca.cert.pem"
    printf '%s\n' "$RAUC_DEV_SIGNING_CERT" > "$staging_directory/development-1.cert.pem"
    printf '%s\n' "$RAUC_DEV_SIGNING_KEY" > "$staging_directory/development-1.key.pem"
else
    if ! command -v openssl >/dev/null 2>&1; then
        echo "OpenSSL is required to generate RAUC development keys." >&2
        exit 1
    fi
    openssl req -x509 -newkey rsa:4096 -nodes \
        -keyout "$staging_directory/ca.key.pem" -out "$staging_directory/ca.cert.pem" \
        -subj "/CN=Nexigon Dev CA" -days 3650
    openssl req -newkey rsa:4096 -nodes \
        -keyout "$staging_directory/development-1.key.pem" -out "$staging_directory/development-1.csr.pem" \
        -subj "/CN=Nexigon Dev Signing Key"
    openssl x509 -req -CAkey "$staging_directory/ca.key.pem" -CA "$staging_directory/ca.cert.pem" \
        -CAserial "$staging_directory/ca.srl" -CAcreateserial \
        -in "$staging_directory/development-1.csr.pem" \
        -out "$staging_directory/development-1.cert.pem" -days 3650
    rm -- "$staging_directory/development-1.csr.pem" "$staging_directory/ca.srl"
fi

mkdir -p "$destination"
for key_file in "$staging_directory"/*.pem; do
    mv -f -- "$key_file" "$destination/"
done
echo "RAUC development keys written to $destination"
