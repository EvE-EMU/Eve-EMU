# Self-signed keystore for YouTrack built-in HTTPS (optional; Caddy usually terminates TLS).
# Output: youtrack.p12 (PKCS#12) and youtrack.jks (Java KeyStore)
# Default passwords: change-me — set YOUTRACK_KEYSTORE_PASSWORD in .env for production.

param(
    [string]$Cn = "pm.eve-emu.com",
    [string]$StorePass = "change-me",
    [string]$KeyPass = "change-me",
    [int]$ValidityDays = 3650,
    [string]$OutDir = $PSScriptRoot
)

$ErrorActionPreference = "Stop"
$p12 = Join-Path $OutDir "youtrack.p12"
$jks = Join-Path $OutDir "youtrack.jks"

if (-not (Get-Command keytool -ErrorAction SilentlyContinue)) {
    throw "keytool not found. Install a JDK (Java 17+) and ensure keytool is on PATH."
}

$dname = "CN=$Cn, OU=EVE-EMU, O=EVE-EMU, L=Unknown, ST=Unknown, C=US"
$san = "SAN=dns:$Cn,dns:localhost,ip:127.0.0.1"

if (Test-Path $p12) { Remove-Item -Force $p12 }
if (Test-Path $jks) { Remove-Item -Force $jks }

Write-Host "Generating PKCS#12: $p12"
keytool -genkeypair `
    -alias youtrack `
    -keyalg RSA `
    -keysize 2048 `
    -validity $ValidityDays `
    -storetype PKCS12 `
    -keystore $p12 `
    -storepass $StorePass `
    -keypass $KeyPass `
    -dname $dname `
    -ext $san

Write-Host "Converting to JKS: $jks"
keytool -importkeystore `
    -noprompt `
    -srckeystore $p12 `
    -srcstoretype PKCS12 `
    -srcstorepass $StorePass `
    -destkeystore $jks `
    -deststoretype JKS `
    -deststorepass $StorePass

Write-Host ""
Write-Host "Done."
Write-Host "  PKCS#12 : $p12"
Write-Host "  JKS     : $jks"
Write-Host "  Alias   : youtrack"
Write-Host "  Store password : $StorePass"
Write-Host ""
Write-Host "Verify:"
Write-Host "  keytool -list -keystore `"$p12`" -storetype PKCS12 -storepass $StorePass"
