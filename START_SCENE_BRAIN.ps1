$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$logs = Join-Path $root 'runtime\production_editor\logs'
$launcherLog = Join-Path $logs 'launcher.log'
$serverLog = Join-Path $logs 'researchcut-server.log'
$url = 'http://127.0.0.1:43127'
$appUrl = $url
function Log($message) { Add-Content -LiteralPath $launcherLog -Value "[$(Get-Date -Format o)] $message" }
function Healthy { try { $h = Invoke-RestMethod "$url/api/health" -TimeoutSec 1; return $h.status -eq 'ok' } catch { return $false } }
New-Item -ItemType Directory -Force -Path $logs | Out-Null
if (-not (Healthy)) {
  Log 'Starting production backend'
  $adapter = Join-Path $root 'runtime\researchcut_integration\migrate_projects.py'
  & python $adapter | Out-Null
  $engine = Join-Path $root 'runtime\researchcut_integration\production'
  $data = 'E:\Movies\.scene_brain\projects\researchcut_editor'
  $command = "`$env:RCE_DATA_DIR='$data'; `$env:RCE_PORT='43127'; Set-Location '$($engine.Replace("'","''"))'; node server.js --no-open *>> '$($serverLog.Replace("'","''"))'"
  Start-Process powershell.exe -ArgumentList '-NoProfile','-Command',$command -WindowStyle Hidden
}
$ready = $false
for ($i=0; $i -lt 40; $i++) { if (Healthy) { $ready=$true; break }; Start-Sleep -Milliseconds 500 }
if (-not $ready) { Log 'ERROR backend readiness timeout'; Write-Error "Backend did not become healthy. See $serverLog"; exit 1 }
Log 'Backend healthy; opening browser'
Start-Process $appUrl
exit 0
