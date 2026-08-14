[CmdletBinding()]
param(
  [switch]$KeepCurrentLocation,
  [switch]$SkipVTextPackages
)

$ErrorActionPreference = 'Stop'
$sourceRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$desktopPath = [Environment]::GetFolderPath('Desktop')
$installRoot = $sourceRoot

function Write-Step([string]$message) {
  Write-Host "`n== $message ==" -ForegroundColor Cyan
}

function Refresh-ProcessPath {
  $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
  $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
  $env:Path = "$machinePath;$userPath"
}

function Ensure-WinGet {
  if (Get-Command winget.exe -ErrorAction SilentlyContinue) { return }
  throw 'WinGet is missing. Install or update Microsoft App Installer from the Microsoft Store, reopen PowerShell, and run this script again.'
}

function Test-RealCommand([string]$command) {
  $found = Get-Command $command -ErrorAction SilentlyContinue
  if (-not $found) { return $false }
  if ($command -eq 'python.exe' -and $found.Source -like '*\WindowsApps\python.exe') { return $false }
  try {
    & $command --version *> $null
    return $LASTEXITCODE -eq 0
  } catch { return $false }
}

function Ensure-Package([string]$command, [string]$packageId, [string]$displayName) {
  if (Test-RealCommand $command) {
    Write-Host "$displayName already available." -ForegroundColor Green
    return
  }
  Write-Step "Installing $displayName"
  & winget.exe install --id $packageId --exact --silent --accept-source-agreements --accept-package-agreements
  if ($LASTEXITCODE -ne 0) { throw "$displayName installation failed with WinGet exit code $LASTEXITCODE." }
  Refresh-ProcessPath
  if (-not (Test-RealCommand $command)) { throw "$displayName installed, but '$command' is not visible yet. Restart Windows and run this script again." }
}

Write-Host 'ResearchCut Editor 2.1 - new Windows PC setup' -ForegroundColor Green
Ensure-WinGet
Ensure-Package 'node.exe' 'OpenJS.NodeJS.LTS' 'Node.js LTS'
Ensure-Package 'ffmpeg.exe' 'Gyan.FFmpeg' 'FFmpeg and FFprobe'
Ensure-Package 'python.exe' 'Python.Python.3.13' 'Python 3.13 (for optional VText)'

if (-not $KeepCurrentLocation -and -not $sourceRoot.StartsWith($desktopPath, [System.StringComparison]::OrdinalIgnoreCase)) {
  Write-Step 'Copying ResearchCut Editor to the Desktop'
  $candidate = Join-Path $desktopPath 'ResearchCut Editor'
  $suffix = 2
  while (Test-Path -LiteralPath $candidate) {
    $candidate = Join-Path $desktopPath "ResearchCut Editor $suffix"
    $suffix++
  }
  $resolvedDesktop = [System.IO.Path]::GetFullPath($desktopPath).TrimEnd('\') + '\'
  $resolvedCandidate = [System.IO.Path]::GetFullPath($candidate)
  if (-not $resolvedCandidate.StartsWith($resolvedDesktop, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Refusing to copy outside the current user Desktop.' }
  New-Item -ItemType Directory -Path $resolvedCandidate | Out-Null
  Get-ChildItem -LiteralPath $sourceRoot -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $resolvedCandidate -Recurse -Force
  }
  $installRoot = $resolvedCandidate
  Write-Host "Installed at: $installRoot" -ForegroundColor Green
}

if (-not $SkipVTextPackages) {
  Write-Step 'Installing narration-synced VText Python packages'
  & python.exe -m pip install --upgrade pip
  if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
  & python.exe -m pip install -r (Join-Path $installRoot 'tools\vtext\requirements.txt')
  if ($LASTEXITCODE -ne 0) { throw 'VText Python package installation failed.' }
}

Write-Step 'Verifying the complete system'
& node.exe --version
& ffmpeg.exe -version | Select-Object -First 1
& ffprobe.exe -version | Select-Object -First 1
if (-not $SkipVTextPackages) {
  Push-Location (Join-Path $installRoot 'tools\vtext')
  try {
    & python.exe check.py
    if ($LASTEXITCODE -ne 0) { throw 'VText readiness check failed.' }
  } finally { Pop-Location }
}

$shortcutPath = Join-Path $desktopPath 'ResearchCut Editor.lnk'
$launcherPath = Join-Path $installRoot 'START_EDITOR.bat'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $launcherPath
$shortcut.WorkingDirectory = $installRoot
$shortcut.Description = 'Start ResearchCut Editor 2.1'
$shortcut.Save()

Write-Host "`nSETUP COMPLETE" -ForegroundColor Green
Write-Host "Editor folder: $installRoot"
Write-Host "Desktop shortcut: $shortcutPath"
Write-Host 'Double-click ResearchCut Editor on the Desktop to start.'
Write-Host 'The first VText render may download its English speech model and therefore takes longer.'
