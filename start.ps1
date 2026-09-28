# start.ps1 — Point d'entrée unique EDG Connect (MySQL + backend + frontend)
#
# Usage :
#   .\start.ps1                          # tout démarrer, accessible sur le réseau local
#   .\start.ps1 -IpAddress 192.168.1.25  # forcer l'IP si la détection se trompe
#   .\start.ps1 -BackendPort 8001 -FrontendPort 3001
#   .\start.ps1 -NoQrCode                # ne pas générer le QR code
#
# Ce que fait ce script, dans l'ordre :
#   1. démarre MySQL s'il est à l'arrêt (la base reste locale, jamais exposée) ;
#   2. détecte l'adresse IP de cette machine sur le réseau local ;
#   3. ouvre les ports dans le pare-feu Windows si nécessaire ;
#   4. lance le backend et le frontend en écoute sur toutes les interfaces ;
#   5. affiche l'adresse à ouvrir depuis un téléphone ou un autre PC du réseau.
#
# CTRL+C arrête le backend et le frontend démarrés ici (MySQL reste actif :
# c'est un service Windows, partagé avec vos autres outils).
#
# Les lancements séparés habituels (backend\start-dev.ps1 et npm run dev)
# continuent de fonctionner exactement comme avant, en local uniquement.

param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000,
    [string]$IpAddress = "",
    [switch]$NoQrCode
)

$ErrorActionPreference = "Stop"

$devLan = Join-Path $PSScriptRoot "scripts\dev-lan.ps1"
if (-not (Test-Path $devLan)) {
    Write-Host "Introuvable : $devLan" -ForegroundColor Red
    Write-Host "Ce fichier fait partie du depot — verifiez que scripts\dev-lan.ps1 n'a pas ete supprime." -ForegroundColor Yellow
    exit 1
}

& $devLan -BackendPort $BackendPort -FrontendPort $FrontendPort -IpAddress $IpAddress -NoQrCode:$NoQrCode
exit $LASTEXITCODE
