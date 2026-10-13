param([string]$Version = "1.0.0")

$ErrorActionPreference = "Stop"
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Use a version such as 1.0.0" }
$projectRoot = Split-Path -Parent $PSScriptRoot
$distRoot = Join-Path $projectRoot "dist"
$exePath = Join-Path $distRoot "CRC32Checker.exe"
if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) { throw "Build the EXE first" }
$actualVersion = (Get-Item -LiteralPath $exePath).VersionInfo.ProductVersion
if ($actualVersion -ne $Version) { throw "EXE version $actualVersion does not match $Version" }
$packageName = "CRC32Checker-$Version-windows-x64-portable"
$stageRoot = Join-Path $distRoot $packageName
New-Item -ItemType Directory -Path $stageRoot -Force | Out-Null
Copy-Item -LiteralPath $exePath -Destination (Join-Path $stageRoot "CRC32Checker.exe")
foreach ($filename in @("README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "CHANGELOG.md")) {
    Copy-Item -LiteralPath (Join-Path $projectRoot $filename) -Destination (Join-Path $stageRoot $filename)
}
Copy-Item -LiteralPath (Join-Path $projectRoot "licenses") -Destination $stageRoot -Recurse -Force
$zipPath = Join-Path $distRoot "$packageName.zip"
Compress-Archive -LiteralPath $stageRoot -DestinationPath $zipPath -Force
$checksumLines = foreach ($asset in @($exePath, $zipPath)) {
    $hash = (Get-FileHash -LiteralPath $asset -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $([IO.Path]::GetFileName($asset))"
}
$checksumPath = Join-Path $distRoot "SHA256SUMS.txt"
[IO.File]::WriteAllLines($checksumPath, [string[]]$checksumLines, [Text.Encoding]::ASCII)
Write-Output "Release assets:"
Get-Item -LiteralPath $exePath, $zipPath, $checksumPath | Select-Object Name, Length
