#!/usr/bin/env bash
# Self-signed keystore for YouTrack built-in HTTPS (optional; Caddy usually terminates TLS).
set -euo pipefail

CN="${1:-pm.eve-emu.com}"
STORE_PASS="${YOUTRACK_KEYSTORE_PASSWORD:-change-me}"
KEY_PASS="${YOUTRACK_KEYSTORE_KEY_PASSWORD:-$STORE_PASS}"
VALIDITY_DAYS="${YOUTRACK_KEYSTORE_VALIDITY_DAYS:-3650}"
OUT_DIR="$(cd "$(dirname "$0")" && pwd)"
P12="${OUT_DIR}/youtrack.p12"
JKS="${OUT_DIR}/youtrack.jks"

command -v keytool >/dev/null || { echo "keytool not found; install a JDK." >&2; exit 1; }

rm -f "$P12" "$JKS"
DNAME="CN=${CN}, OU=EVE-EMU, O=EVE-EMU, L=Unknown, ST=Unknown, C=US"
SAN="SAN=dns:${CN},dns:localhost,ip:127.0.0.1"

echo "Generating PKCS#12: $P12"
keytool -genkeypair \
  -alias youtrack \
  -keyalg RSA \
  -keysize 2048 \
  -validity "$VALIDITY_DAYS" \
  -storetype PKCS12 \
  -keystore "$P12" \
  -storepass "$STORE_PASS" \
  -keypass "$KEY_PASS" \
  -dname "$DNAME" \
  -ext "$SAN"

echo "Converting to JKS: $JKS"
keytool -importkeystore \
  -noprompt \
  -srckeystore "$P12" \
  -srcstoretype PKCS12 \
  -srcstorepass "$STORE_PASS" \
  -destkeystore "$JKS" \
  -deststoretype JKS \
  -deststorepass "$STORE_PASS"

echo "Done: $P12 and $JKS (alias youtrack, storepass from YOUTRACK_KEYSTORE_PASSWORD)"
