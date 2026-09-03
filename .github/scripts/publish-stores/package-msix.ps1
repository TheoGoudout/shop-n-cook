# Pack the TWA payload into an MSIX.
#
# makeappx.exe lives under a versioned Windows Kits directory, so it is located
# rather than hardcoded: the newest one on the runner wins.
$ErrorActionPreference = "Stop"

$makeAppx = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin" `
    -Recurse -Filter "makeappx.exe" |
    Sort-Object FullName -Descending |
    Select-Object -First 1 -ExpandProperty FullName

& $makeAppx pack /d windows /p "$env:RUNNER_TEMP\ShopNCook.msix" /nv
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
