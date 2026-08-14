param(
  [Parameter(Mandatory = $true)]
  [string]$Target
)

$ErrorActionPreference = 'Stop'
$expectedVersion = '2.1.0'
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$payloadRoot = Join-Path $scriptRoot 'payload'
$targetRoot = [System.IO.Path]::GetFullPath($Target).TrimEnd([System.IO.Path]::DirectorySeparatorChar)
$localAppProjects = [System.IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'ResearchCut Editor'))

Write-Host 'ResearchCut Editor 2.1 updater' -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath $payloadRoot -PathType Container)) {
  throw "Update payload is missing: $payloadRoot"
}
if (-not (Test-Path -LiteralPath $targetRoot -PathType Container)) {
  throw "Target folder does not exist: $targetRoot"
}
if ($targetRoot.StartsWith($localAppProjects, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw 'Target must be the ResearchCut program folder, not LocalAppData or a project folder.'
}
if (-not (Test-Path -LiteralPath (Join-Path $targetRoot 'server.js') -PathType Leaf) -or
    -not (Test-Path -LiteralPath (Join-Path $targetRoot 'START_EDITOR.bat') -PathType Leaf)) {
  throw 'Target is not a valid ResearchCut program folder (server.js / START_EDITOR.bat not found).'
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupRoot = Join-Path $targetRoot ("updates\backup-before-2.1-$timestamp")
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

$payloadFiles = Get-ChildItem -LiteralPath $payloadRoot -Recurse -File
if ($payloadFiles.Count -eq 0) {
  throw 'Update payload contains no files.'
}

foreach ($payloadFile in $payloadFiles) {
  $relative = $payloadFile.FullName.Substring($payloadRoot.Length).TrimStart('\')
  $destination = Join-Path $targetRoot $relative
  $destinationDir = Split-Path -Parent $destination
  $backup = Join-Path $backupRoot $relative

  if (Test-Path -LiteralPath $destination -PathType Leaf) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $backup) -Force | Out-Null
    Copy-Item -LiteralPath $destination -Destination $backup -Force
  }
  New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null
  Copy-Item -LiteralPath $payloadFile.FullName -Destination $destination -Force
  Write-Host "Updated $relative"
}

$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCommand) {
  throw 'Files were copied, but Node.js is unavailable for validation. Install Node.js LTS and run CHECK_SYSTEM.bat.'
}

$jsChecks = @('server.js', 'renderer.js', 'automation-catalog.js', 'public\app.js')
foreach ($relative in $jsChecks) {
  $file = Join-Path $targetRoot $relative
  & $nodeCommand.Source --check $file
  if ($LASTEXITCODE -ne 0) { throw "Node syntax validation failed: $relative" }
}

$package = Get-Content -LiteralPath (Join-Path $targetRoot 'package.json') -Raw | ConvertFrom-Json
if ($package.version -ne $expectedVersion) {
  throw "Version validation failed. Expected $expectedVersion, found $($package.version)."
}

Write-Host ''
Write-Host "Update complete: ResearchCut Editor $expectedVersion" -ForegroundColor Green
Write-Host "Backup: $backupRoot"
Write-Host 'Your LocalAppData projects and backgrounds folder were not modified.'
