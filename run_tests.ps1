# run_tests.ps1 — Script de vérification unique EDG Connect
# Usage : ./run_tests.ps1
# Retour : résumé passés/échoués + codes de sortie
# Dernière mise à jour : 2026-06-18

param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$Verbose
)

$ErrorActionPreference = "Continue"
$ROOT = $PSScriptRoot
$BACKEND = Join-Path $ROOT "backend"
$FRONTEND = Join-Path $ROOT "frontend"
$VENV_PYTHON = Join-Path $BACKEND "venv\Scripts\python.exe"
$VENV_PYTEST = Join-Path $BACKEND "venv\Scripts\pytest.exe"

$passedSections = @()
$failedSections = @()

function Write-Header($msg) {
    Write-Host ""
    Write-Host "══════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "══════════════════════════════════════════════" -ForegroundColor Cyan
}

function Write-OK($msg)   { Write-Host "  ✅ $msg" -ForegroundColor Green }
function Write-FAIL($msg) { Write-Host "  ❌ $msg" -ForegroundColor Red }
function Write-INFO($msg) { Write-Host "  ℹ️  $msg" -ForegroundColor Yellow }

# ── 1. VÉRIFICATION SYNTAXE BACKEND ──────────────────────────────────────────
if (-not $FrontendOnly) {
    Write-Header "1. Syntaxe Python (backend)"
    $files = Get-ChildItem "$BACKEND\api" -Recurse -Filter "*.py" | Select-Object -ExpandProperty FullName
    $syntaxOk = $true
    foreach ($f in $files) {
        $rel = $f.Replace($BACKEND, "")
        $result = & $VENV_PYTHON -c "import ast; ast.parse(open('$f', encoding='utf-8').read())" 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-FAIL "Syntaxe invalide : $rel"
            $syntaxOk = $false
        }
    }
    if ($syntaxOk) {
        Write-OK "Tous les fichiers Python — syntaxe valide"
        $passedSections += "Syntaxe Python"
    } else {
        $failedSections += "Syntaxe Python"
    }
}

# ── 2. IMPORTS BACKEND ────────────────────────────────────────────────────────
if (-not $FrontendOnly) {
    Write-Header "2. Imports modules critiques (backend)"
    Push-Location $BACKEND
    $importResult = & $VENV_PYTHON -c @"
import sys
sys.path.insert(0, '.')
import api.dependencies
import api.routes.RouteRequest
import api.routes.RouteRequestAppreciation
import api.routes.RouteAuth
import api.routes.RouteUsers
print('OK')
"@ 2>&1
    Pop-Location
    if ($importResult -match "OK") {
        Write-OK "Imports modules critiques"
        $passedSections += "Imports backend"
    } else {
        Write-FAIL "Erreur d'import : $importResult"
        $failedSections += "Imports backend"
    }
}

# ── 3. SUITE DE TESTS BACKEND ─────────────────────────────────────────────────
if (-not $FrontendOnly) {
    Write-Header "3. Suite de tests backend (pytest)"
    Push-Location $BACKEND
    $pytestArgs = @("tests/", "-v", "--tb=short", "--no-header", "-q")
    if (-not $Verbose) { $pytestArgs += "--tb=line" }
    $pytestOutput = & $VENV_PYTEST @pytestArgs 2>&1
    $pytestExit = $LASTEXITCODE
    Pop-Location

    $pytestOutput | ForEach-Object { Write-Host "    $_" }

    if ($pytestExit -eq 0) {
        Write-OK "Suite de tests backend — tout vert"
        $passedSections += "Tests backend"
    } elseif ($pytestExit -eq 1) {
        Write-FAIL "Des tests backend ont échoué (voir détails ci-dessus)"
        $failedSections += "Tests backend"
    } else {
        Write-FAIL "Erreur d'exécution pytest (exit $pytestExit)"
        $failedSections += "Tests backend"
    }
}

# ── 4. BUILD FRONTEND ─────────────────────────────────────────────────────────
if (-not $BackendOnly) {
    Write-Header "4. Build frontend (TypeScript + Vite)"
    Push-Location $FRONTEND
    $buildOutput = & npm run build 2>&1
    $buildExit = $LASTEXITCODE
    Pop-Location

    if ($buildExit -eq 0) {
        Write-OK "Build frontend — vert"
        $passedSections += "Build frontend"
    } else {
        Write-FAIL "Build frontend échoué (exit $buildExit)"
        if ($Verbose) { $buildOutput | ForEach-Object { Write-Host "    $_" } }
        $failedSections += "Build frontend"
    }
}

# ── RÉSUMÉ FINAL ──────────────────────────────────────────────────────────────
Write-Header "RÉSUMÉ"
Write-Host ""
foreach ($s in $passedSections) { Write-OK $s }
foreach ($s in $failedSections)  { Write-FAIL $s }
Write-Host ""

if ($failedSections.Count -eq 0) {
    Write-Host "  🟢 BASELINE VERTE — Toutes les vérifications passent" -ForegroundColor Green
    exit 0
} else {
    Write-Host "  🔴 $($failedSections.Count) section(s) en échec — NE PAS AVANCER à la phase suivante" -ForegroundColor Red
    exit 1
}
