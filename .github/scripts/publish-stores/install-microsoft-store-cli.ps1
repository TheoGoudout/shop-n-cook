# Install the Microsoft Store CLI onto the runner's PATH.
#
# MSSTORE_CLI_VERSION comes from the calling step's env: a tag such as `v1.6.0`,
# or `latest`. It is a variable rather than a hardcoded `releases/latest` call
# so the version that publishes to the Store can be pinned from the workflow —
# unpinned, this downloaded and executed whatever had been released that
# morning, with no version recorded anywhere and no checksum.
$ErrorActionPreference = "Stop"

$version = $env:MSSTORE_CLI_VERSION
$endpoint = if ($version -eq "latest") { "releases/latest" } else { "releases/tags/$version" }
$release = Invoke-RestMethod "https://api.github.com/repos/microsoft/msstore-cli/$endpoint"

Write-Host "msstore-cli $($release.tag_name)"

$url = ($release.assets |
    Where-Object { $_.name -match 'win-x64' -and $_.name -match '\.zip$' }).browser_download_url
if (-not $url) {
    Write-Host "::error::No win-x64 zip asset on msstore-cli $($release.tag_name)."
    exit 1
}

Invoke-WebRequest -Uri $url -OutFile "$env:RUNNER_TEMP\msstore.zip"
Expand-Archive -Path "$env:RUNNER_TEMP\msstore.zip" -DestinationPath "$env:RUNNER_TEMP\msstore"
Add-Content -Path $env:GITHUB_PATH -Value "$env:RUNNER_TEMP\msstore"
