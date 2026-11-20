#!/usr/bin/env bash
set -euo pipefail

# Install only a pinned Xray archive with a user-verified SHA-256 value.
VERSION="${XRAY_VERSION:-v26.10.31}"
EXPECTED_ARCHIVE_SHA256="${XRAY_ARCHIVE_SHA256:-}"
DESTINATION="${XRAY_INSTALL_DIR:-.runtime/xray}"
ARCHIVE="Xray-linux-64.zip"
URL="https://github.com/XTLS/Xray-core/releases/download/${VERSION}/${ARCHIVE}"

if [[ ! "${VERSION}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Invalid Xray version." >&2
  exit 2
fi
if [[ ! "${EXPECTED_ARCHIVE_SHA256}" =~ ^[a-fA-F0-9]{64}$ ]]; then
  echo "Set XRAY_ARCHIVE_SHA256 to the archive checksum from official Xray release metadata." >&2
  exit 2
fi

mkdir -p "${DESTINATION}"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TEMP_DIR}"' EXIT
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 --max-time 120 "${URL}" -o "${TEMP_DIR}/${ARCHIVE}"
ACTUAL_SHA256="$(sha256sum "${TEMP_DIR}/${ARCHIVE}" | awk '{print $1}')"
if [[ "${ACTUAL_SHA256,,}" != "${EXPECTED_ARCHIVE_SHA256,,}" ]]; then
  echo "Xray archive checksum mismatch." >&2
  exit 2
fi
unzip -q "${TEMP_DIR}/${ARCHIVE}" xray -d "${TEMP_DIR}"
install -m 0755 "${TEMP_DIR}/xray" "${DESTINATION}/xray"
"${DESTINATION}/xray" version
printf 'XRAY_BINARY=%s\n' "$(realpath "${DESTINATION}/xray")"
printf 'XRAY_BINARY_SHA256=%s\n' "$(sha256sum "${DESTINATION}/xray" | awk '{print $1}')"
