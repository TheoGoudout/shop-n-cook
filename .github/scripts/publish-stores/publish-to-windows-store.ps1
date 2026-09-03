# Submit the signed MSIX to the Microsoft Store.
#
# PRODUCT_ID, FLIGHT_ID and WINDOWS_BETA come from the calling step's env. A
# pre-release goes to the flight (the Store's beta channel) instead of the
# public listing.
$ErrorActionPreference = "Stop"

$msix = "$env:RUNNER_TEMP\ShopNCook.msix"

if ($env:WINDOWS_BETA -eq "true") {
    if (-not $env:FLIGHT_ID) {
        Write-Host "::error::WINDOWS_FLIGHT_ID is not set, so this pre-release has nowhere to go."
        exit 1
    }
    msstore publish -i $msix --id $env:PRODUCT_ID --flightId $env:FLIGHT_ID
} else {
    msstore publish -i $msix --id $env:PRODUCT_ID
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
