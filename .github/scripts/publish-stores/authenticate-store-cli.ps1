# Point the Store CLI at the partner account.
#
# The four credentials come from the calling step's env. All of them used to be
# interpolated onto this command line, which put the client secret into the
# process's argv.
$ErrorActionPreference = "Stop"

msstore reconfigure `
    --tenantId     $env:AZURE_TENANT_ID `
    --sellerId     $env:AZURE_SELLER_ID `
    --clientId     $env:AZURE_CLIENT_ID `
    --clientSecret $env:AZURE_CLIENT_SECRET
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
