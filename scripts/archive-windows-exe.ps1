param(
    [Parameter(Mandatory = $true)]
    [string]$TargetPath
)

$ErrorActionPreference = "Stop"

$resolvedTarget = (Resolve-Path -LiteralPath $TargetPath).Path
$target = Get-Item -LiteralPath $resolvedTarget
$applicationName = [System.IO.Path]::GetFileNameWithoutExtension($target.Name)
$version = $target.VersionInfo.ProductVersion

if ([string]::IsNullOrWhiteSpace($version)) {
    throw "The existing executable has no ProductVersion: $resolvedTarget"
}

$version = $version.Trim()
if ($version.IndexOfAny([System.IO.Path]::GetInvalidFileNameChars()) -ge 0) {
    throw "The existing executable has an invalid ProductVersion: $version"
}

$candidate = Join-Path $target.DirectoryName "${applicationName}-v${version}.exe"
$suffix = 1
while (Test-Path -LiteralPath $candidate) {
    $candidate = Join-Path $target.DirectoryName "${applicationName}-v${version}.${suffix}.exe"
    $suffix += 1
}

Move-Item -LiteralPath $resolvedTarget -Destination $candidate
Write-Host "Previous standalone executable: $candidate"
