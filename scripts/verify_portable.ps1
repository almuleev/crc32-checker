param([string]$Executable = "dist\CRC32Checker.exe")

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$executablePath = if ([IO.Path]::IsPathRooted($Executable)) {
    [IO.Path]::GetFullPath($Executable)
} else {
    [IO.Path]::GetFullPath((Join-Path $projectRoot $Executable))
}
if (-not (Test-Path -LiteralPath $executablePath -PathType Leaf)) {
    throw "Executable not found: $executablePath"
}
$testRoot = Join-Path $projectRoot (".portable-test\Isolated folder " + [Guid]::NewGuid())
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
$copiedExe = Join-Path $testRoot "CRC32Checker.exe"
Copy-Item -LiteralPath $executablePath -Destination $copiedExe

# Only the EXE is copied. Its process cannot discover an installed Python via PATH.
$startInfo = New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName = $copiedExe
$startInfo.WorkingDirectory = $testRoot
$startInfo.Arguments = "--self-test portable-check.json"
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$startInfo.EnvironmentVariables["PATH"] = Join-Path $env:SystemRoot "System32"
$startInfo.EnvironmentVariables.Remove("PYTHONHOME")
$startInfo.EnvironmentVariables.Remove("PYTHONPATH")
$process = [System.Diagnostics.Process]::Start($startInfo)
if (-not $process.WaitForExit(30000)) {
    & "$env:SystemRoot\System32\taskkill.exe" /PID $process.Id /T /F | Out-Null
    throw "Portable executable check timed out"
}
$exitCode = $process.ExitCode
$reportPath = Join-Path $testRoot "portable-check.json"
if (-not (Test-Path -LiteralPath $reportPath)) {
    throw "Portable executable exited with code $exitCode without a report"
}
$report = Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($exitCode -ne 0 -or -not $report.ok -or -not $report.frozen) {
    throw "Portable executable check failed: $($report | ConvertTo-Json -Depth 5)"
}
Write-Output "Portable executable check passed: $reportPath"
$report | ConvertTo-Json -Depth 5
