# Give the MSIX the release's own name before it is attached.
#
# VERSION comes from the calling step's env.
$ErrorActionPreference = "Stop"

Copy-Item "$env:RUNNER_TEMP\ShopNCook.msix" "shop-n-cook-$env:VERSION.msix"
