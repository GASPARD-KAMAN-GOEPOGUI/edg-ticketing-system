param(
  [int]$Port = 8000,
  [string]$BindHost = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

$BackendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $BackendDir

$HealthUrl = "http://${BindHost}:${Port}/health"

function Test-BackendHealth {
  param([string]$Url)

  try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
    return $response.StatusCode -eq 200
  } catch {
    return $false
  }
}

function Get-PortListeners {
  param([int]$Port)

  $pattern = "LISTENING\s+\d+$"
  @(netstat -ano | Select-String -Pattern $pattern | Where-Object {
    $_.Line -match "[:\]]$Port\s+"
  })
}

if (Test-BackendHealth -Url $HealthUrl) {
  Write-Host "Backend deja actif: $HealthUrl" -ForegroundColor Green
  Write-Host "Ne relance pas uvicorn sur le meme port; garde ce serveur ouvert." -ForegroundColor Yellow
  exit 0
}

$listeners = Get-PortListeners -Port $Port
if ($listeners.Count -gt 0) {
  Write-Host "Le port $Port est deja occupe, mais /health ne repond pas." -ForegroundColor Red
  foreach ($line in $listeners) {
    $pidValue = if ($line.Line -match "\s+(\d+)\s*$") { $Matches[1] } else { $null }
    if ($pidValue) {
      $process = Get-Process -Id ([int]$pidValue) -ErrorAction SilentlyContinue
      $name = if ($process) { $process.ProcessName } else { "inconnu" }
      Write-Host "PID $pidValue - $name - $($line.Line.Trim())"
    } else {
      Write-Host $line.Line.Trim()
    }
  }
  Write-Host "Ferme le processus qui occupe ce port ou lance: .\start-dev.ps1 -Port 8001" -ForegroundColor Yellow
  exit 1
}

$venvPython = Join-Path $BackendDir "venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

# --reload-dir limite la surveillance au code source. Sans lui, uvicorn surveille
# aussi venv/, __pycache__/ et uploads/ : le rechargement finit par se figer en
# gardant le port, et le serveur devient injoignable sans qu'aucune erreur ne le
# signale (cf. CLAUDE.md, section Commandes dev). UVICORN_RELOAD_DIRS permet d'en
# surveiller d'autres, separes par des virgules.
$reloadDirs = if ($env:UVICORN_RELOAD_DIRS) { $env:UVICORN_RELOAD_DIRS -split "," } else { @("api") }
$reloadArgs = @()
foreach ($dir in $reloadDirs) {
  $trimmed = $dir.Trim()
  if ($trimmed) { $reloadArgs += @("--reload-dir", $trimmed) }
}

Write-Host "Demarrage backend: http://${BindHost}:${Port}" -ForegroundColor Green
& $python -m uvicorn api.main:app --host $BindHost --port $Port --reload @reloadArgs
