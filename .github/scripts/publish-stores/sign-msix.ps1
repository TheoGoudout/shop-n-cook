# Sign the MSIX with the Windows code-signing certificate.
#
# CERT_BASE64 and CERT_PASSWORD come from the calling step's env.
$ErrorActionPreference = "Stop"

$certPath = "$env:RUNNER_TEMP\cert.pfx"
[IO.File]::WriteAllBytes($certPath, [Convert]::FromBase64String($env:CERT_BASE64))

$signtool = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin" `
    -Recurse -Filter "signtool.exe" |
    Sort-Object FullName -Descending |
    Select-Object -First 1 -ExpandProperty FullName

& $signtool sign /fd SHA256 /p $env:CERT_PASSWORD /f $certPath "$env:RUNNER_TEMP\ShopNCook.msix"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Remove-Item $certPath -Force
