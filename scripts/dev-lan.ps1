# dev-lan.ps1 — Mode de développement LAN EDG Connect
# Usage : .\scripts\dev-lan.ps1 [-BackendPort 8000] [-FrontendPort 3000] [-IpAddress <ip>] [-NoQrCode]
#
# Démarre le backend (FastAPI/uvicorn) et le frontend (Vite) en écoute sur
# toutes les interfaces (0.0.0.0), détecte l'IP LAN du poste, génère
# automatiquement frontend/.env.lan.local (VITE_API_URL), et affiche les URLs
# à ouvrir depuis un téléphone/PC connecté au même réseau Wi-Fi.
#
# Ne modifie AUCUN fichier source existant : "npm run dev" et
# "backend\start-dev.ps1" (sans argument) continuent de fonctionner comme
# avant. CTRL+C arrête uniquement les processus démarrés par ce script.

param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000,
    [string]$IpAddress = "",
    [switch]$NoQrCode
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot
$BACKEND = Join-Path $ROOT "backend"
$FRONTEND = Join-Path $ROOT "frontend"

function Write-OK($msg)     { Write-Host "  [OK]   $msg" -ForegroundColor Green }
function Write-FAIL($msg)   { Write-Host "  [X]    $msg" -ForegroundColor Red }
function Write-INFO($msg)   { Write-Host "  [i]    $msg" -ForegroundColor Yellow }
function Write-Header($msg) {
    Write-Host ""
    Write-Host "══════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "══════════════════════════════════════════════" -ForegroundColor Cyan
}

# ═══════════════════════════════════════════════════════════════════════════
# 1. Détection de l'IP LAN
# ═══════════════════════════════════════════════════════════════════════════

function Get-LanCandidates {
    $excludePatterns = @("*vEthernet*", "*WSL*", "*Loopback*", "*Docker*", "*VPN*", "*Bluetooth*", "*Tailscale*", "*ZeroTier*", "*Hyper-V*")
    $preferredPatterns = @("Wi-Fi*", "WLAN*", "Ethernet*")

    $configs = Get-NetIPConfiguration -ErrorAction SilentlyContinue | Where-Object {
        $_.IPv4Address.IPAddress -and $_.NetAdapter -and $_.NetAdapter.Status -eq "Up"
    }

    $candidates = foreach ($c in $configs) {
        $ip = $c.IPv4Address.IPAddress
        if ($ip -like "127.*" -or $ip -like "169.254.*") { continue }
        $alias = $c.InterfaceAlias
        $excluded = $false
        foreach ($p in $excludePatterns) { if ($alias -like $p) { $excluded = $true } }
        $preferred = $false
        foreach ($p in $preferredPatterns) { if ($alias -like $p) { $preferred = $true } }
        [PSCustomObject]@{ IP = $ip; Alias = $alias; Excluded = $excluded; Preferred = $preferred }
    }

    return $candidates | Sort-Object -Property @{Expression = "Preferred"; Descending = $true}, @{Expression = "Excluded"; Descending = $false}
}

Write-Header "APPLICATION — LAN DEVELOPMENT"

if ($IpAddress) {
    $lanIp = $IpAddress
    Write-OK "IP LAN forcée manuellement : $lanIp"
} else {
    $candidates = @(Get-LanCandidates)
    if ($candidates.Count -eq 0) {
        Write-FAIL "Impossible de déterminer l'adresse IP LAN."
        Write-INFO "Vérifiez que le Wi-Fi/Ethernet est connecté, ou forcez l'IP : .\scripts\dev-lan.ps1 -IpAddress 192.168.1.25"
        exit 1
    }
    if ($candidates.Count -gt 1) {
        Write-INFO "Plusieurs interfaces réseau détectées :"
        foreach ($c in $candidates) {
            $tag = if ($c.Excluded) { " (ignorée, probablement pas le LAN)" } else { "" }
            Write-Host "         - $($c.IP)  [$($c.Alias)]$tag"
        }
    }
    $best = $candidates | Where-Object { -not $_.Excluded } | Select-Object -First 1
    if (-not $best) { $best = $candidates | Select-Object -First 1 }
    $lanIp = $best.IP
    Write-OK "IP LAN détectée : $lanIp  [$($best.Alias)]"
}

# ═══════════════════════════════════════════════════════════════════════════
# 1 bis. MySQL — la base reste LOCALE (jamais exposée au réseau)
#
# Seul le backend lui parle, sur 127.0.0.1 : les appareils du réseau n'accèdent
# qu'au frontend et à l'API. Exposer MySQL au LAN serait un risque inutile.
# On se contente donc de vérifier qu'elle répond, et de démarrer son service
# Windows si elle est à l'arrêt — sans quoi le backend échoue au démarrage.
# ═══════════════════════════════════════════════════════════════════════════

function Get-MySqlService {
    # Le nom varie beaucoup selon la distribution : MySQL80, MySQL57, MariaDB,
    # et surtout wampmysqld64 sous WAMP ou mysql sous XAMPP. On cherche donc
    # "mysql"/"mariadb" N'IMPORTE OU dans le nom — une expression ancree sur le
    # debut laisserait passer wampmysqld64, le cas le plus courant ici.
    # Un service deja demarre est prefere : certaines machines en declarent
    # plusieurs (une installation MySQL residuelle a cote de WAMP).
    return Get-Service -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match 'mysql|mariadb' -or $_.DisplayName -match 'mysql|mariadb' } |
        Sort-Object -Property @{Expression = { $_.Status -eq 'Running' }; Descending = $true} |
        Select-Object -First 1
}

function Test-MySqlPort {
    param([int]$Port = 3306)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        $ok = $async.AsyncWaitHandle.WaitOne(1500, $false) -and $client.Connected
        $client.Close()
        return $ok
    } catch {
        return $false
    }
}

if (Test-MySqlPort) {
    Write-OK "MySQL repond sur 127.0.0.1:3306 (base locale, non exposee au reseau)."
} else {
    $svc = Get-MySqlService
    if (-not $svc) {
        Write-FAIL "MySQL ne repond pas sur 127.0.0.1:3306 et aucun service MySQL/MariaDB n'a ete trouve."
        Write-INFO "Demarrez votre serveur MySQL (XAMPP/WAMP/Laragon : bouton Start du panneau), puis relancez."
        exit 1
    }
    Write-INFO "MySQL est a l'arret (service '$($svc.Name)') — demarrage en cours…"
    try {
        Start-Service -Name $svc.Name -ErrorAction Stop
    } catch {
        Write-FAIL "Impossible de demarrer le service '$($svc.Name)' : $($_.Exception.Message)"
        Write-INFO "Relancez ce script depuis un PowerShell EN ADMINISTRATEUR, ou demarrez MySQL a la main."
        exit 1
    }
    $mysqlUp = $false
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 1
        if (Test-MySqlPort) { $mysqlUp = $true; break }
    }
    if ($mysqlUp) {
        Write-OK "MySQL demarre (service '$($svc.Name)')."
    } else {
        Write-FAIL "Le service '$($svc.Name)' a ete demarre mais le port 3306 ne repond toujours pas."
        exit 1
    }
}

# ═══════════════════════════════════════════════════════════════════════════
# 2. Vérification des ports
# ═══════════════════════════════════════════════════════════════════════════

function Test-PortFree {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $conn) { return $true }
    $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
    $name = if ($proc) { $proc.ProcessName } else { "inconnu" }
    Write-FAIL "Le port $Port est déjà utilisé (PID $($conn.OwningProcess) - $name)."
    return $false
}

$backendPortFree = Test-PortFree -Port $BackendPort
$frontendPortFree = Test-PortFree -Port $FrontendPort
if (-not $backendPortFree -or -not $frontendPortFree) {
    Write-INFO "Fermez le processus concerné, ou relancez avec -BackendPort / -FrontendPort."
    exit 1
}
Write-OK "Ports $BackendPort (backend) et $FrontendPort (frontend) libres."

# ═══════════════════════════════════════════════════════════════════════════
# 3. Pare-feu Windows — vérification (jamais de désactivation, jamais d'élévation forcée)
# ═══════════════════════════════════════════════════════════════════════════

function Test-FirewallAllowsPort {
    param([int]$Port)
    try {
        $rules = Get-NetFirewallPortFilter -Protocol TCP -ErrorAction SilentlyContinue |
            Where-Object { $_.LocalPort -eq "$Port" -or $_.LocalPort -eq "Any" }
        foreach ($r in $rules) {
            $rule = $r | Get-NetFirewallRule -ErrorAction SilentlyContinue
            if ($rule -and $rule.Direction -eq "Inbound" -and $rule.Action -eq "Allow" -and $rule.Enabled -eq "True") {
                return $true
            }
        }
        return $false
    } catch {
        return $null  # module NetSecurity indisponible — on ne bloque pas pour autant
    }
}

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$portsNeedingRule = @()
foreach ($p in @($BackendPort, $FrontendPort)) {
    $allowed = Test-FirewallAllowsPort -Port $p
    if ($allowed -eq $false) { $portsNeedingRule += $p }
}

if ($portsNeedingRule.Count -gt 0) {
    if ($isAdmin) {
        foreach ($p in $portsNeedingRule) {
            try {
                New-NetFirewallRule -DisplayName "EDG Connect LAN Dev - Port $p" -Direction Inbound -Action Allow -Protocol TCP -LocalPort $p -ErrorAction Stop | Out-Null
                Write-OK "Règle pare-feu créée pour le port $p."
            } catch {
                Write-INFO "Échec de création de la règle pare-feu pour le port $p : $($_.Exception.Message)"
            }
        }
    } else {
        Write-INFO "Aucune règle pare-feu entrante détectée pour : $($portsNeedingRule -join ', ')"
        Write-INFO "Si le téléphone n'arrive pas à se connecter, lancez ceci dans un PowerShell EN ADMINISTRATEUR :"
        foreach ($p in $portsNeedingRule) {
            Write-Host "         New-NetFirewallRule -DisplayName `"EDG Connect LAN Dev - Port $p`" -Direction Inbound -Action Allow -Protocol TCP -LocalPort $p" -ForegroundColor DarkYellow
        }
        Write-INFO "(Windows affiche parfois une popup d'autorisation au premier démarrage — acceptez-la.)"
    }
} else {
    Write-OK "Pare-feu Windows : ports déjà autorisés (ou vérification indisponible, non bloquant)."
}

# ═══════════════════════════════════════════════════════════════════════════
# 4. Génération de frontend/.env.lan.local (jamais committé — cf. .gitignore ".env.*.local")
# ═══════════════════════════════════════════════════════════════════════════

$apiLanUrl = "http://${lanIp}:${BackendPort}/api/v1"
$envLanContent = @"
# Généré automatiquement par scripts\dev-lan.ps1 — NE PAS ÉDITER, NE PAS COMMITTER.
# Régénéré à chaque lancement du mode LAN. N'affecte que "vite dev --mode lan".
VITE_API_URL=$apiLanUrl
"@
Set-Content -Path (Join-Path $FRONTEND ".env.lan.local") -Value $envLanContent -Encoding utf8
Write-OK "Configuration frontend générée : VITE_API_URL=$apiLanUrl"

# ═══════════════════════════════════════════════════════════════════════════
# 5. Démarrage backend + frontend (fenêtres séparées)
# ═══════════════════════════════════════════════════════════════════════════

Write-Header "Démarrage des services"

# Fichiers de lancement temporaires plutôt que des chaînes -Command échappées :
# des guillemets imbriqués dans -ArgumentList sont fragiles (le chemin du repo
# contient des parenthèses/espaces) et peuvent empêcher silencieusement la
# fenêtre détachée d'exécuter quoi que ce soit. Un vrai fichier .ps1 évite
# entièrement ce problème. -ExecutionPolicy Bypass reste nécessaire (même
# pattern que start-dev.cmd) pour l'exécuter et pour l'appel imbriqué à
# start-dev.ps1.
$launcherDir = Join-Path $env:TEMP "edg-connect-lan"
New-Item -ItemType Directory -Path $launcherDir -Force -ErrorAction SilentlyContinue | Out-Null

$backendLauncher = Join-Path $launcherDir "backend-launch.ps1"
@"
`$host.UI.RawUI.WindowTitle = 'EDG Connect - Backend (LAN)'
Set-Location -LiteralPath '$BACKEND'
`$env:UVICORN_RELOAD_DIRS = 'api'
& '$BACKEND\start-dev.ps1' -BindHost 0.0.0.0 -Port $BackendPort
"@ | Set-Content -LiteralPath $backendLauncher -Encoding UTF8

$backendProc = Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-File", $backendLauncher) -PassThru -WindowStyle Normal
Write-OK "Backend lancé (PID $($backendProc.Id)) — fenêtre séparée."

Write-INFO "Attente que le backend réponde sur /health…"
$backendReady = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) { $backendReady = $true; break }
    } catch { }
}

if (-not $backendReady) {
    Write-FAIL "Le backend ne répond pas après 30s. Vérifiez la fenêtre 'EDG Connect — Backend (LAN)'."
    Write-INFO "Causes fréquentes : port déjà occupé, erreur au démarrage FastAPI, base de données injoignable."
} else {
    Write-OK "Backend prêt."
}

# Binaire vite local appelé directement (node_modules\.bin\vite.cmd) plutôt que
# "npx vite" : évite la résolution/overhead npx à chaque lancement.
$viteCmdPath = Join-Path $FRONTEND "node_modules\.bin\vite.cmd"
$frontendLauncher = Join-Path $launcherDir "frontend-launch.ps1"
# --port doit être passé explicitement : vite.config.ts fixe port 3000 en dur
# avec strictPort:true, donc sans --port ici, -FrontendPort serait ignoré par
# Vite (qui essaierait toujours 3000) tout en désynchronisant la vérification
# de santé de ce script (qui, elle, sonderait bien le port demandé).
@"
`$host.UI.RawUI.WindowTitle = 'EDG Connect - Frontend (LAN)'
Set-Location -LiteralPath '$FRONTEND'
& '$viteCmdPath' dev --host 0.0.0.0 --port $FrontendPort --mode lan
"@ | Set-Content -LiteralPath $frontendLauncher -Encoding UTF8

$frontendProc = Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-File", $frontendLauncher) -PassThru -WindowStyle Normal
Write-OK "Frontend lancé (PID $($frontendProc.Id)) — fenêtre séparée."

Write-INFO "Attente que le frontend écoute sur le port $FrontendPort…"
$frontendReady = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    $test = Test-NetConnection -ComputerName "127.0.0.1" -Port $FrontendPort -InformationLevel Quiet -WarningAction SilentlyContinue
    if ($test) { $frontendReady = $true; break }
}

if (-not $frontendReady) {
    Write-FAIL "Le frontend ne répond pas après 30s. Vérifiez la fenêtre 'EDG Connect — Frontend (LAN)'."
} else {
    Write-OK "Frontend prêt."
}

# ═══════════════════════════════════════════════════════════════════════════
# 6. Vérification de connectivité via l'IP LAN elle-même
# ═══════════════════════════════════════════════════════════════════════════

$apiLanOk = $false
if ($backendReady) {
    try {
        $resp = Invoke-WebRequest -Uri "http://${lanIp}:${BackendPort}/health" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        $apiLanOk = $resp.StatusCode -eq 200
    } catch { $apiLanOk = $false }
}

# ═══════════════════════════════════════════════════════════════════════════
# 7. QR code (best-effort — jamais bloquant, aucune dépendance ajoutée au projet)
# ═══════════════════════════════════════════════════════════════════════════

$frontendLanUrl = "http://${lanIp}:${FrontendPort}"
if (-not $NoQrCode -and $frontendReady) {
    try {
        $qrApiUrl = "https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=" + [uri]::EscapeDataString($frontendLanUrl)
        $qrPath = Join-Path $env:TEMP "edg-connect-lan-qr.png"
        Invoke-WebRequest -Uri $qrApiUrl -OutFile $qrPath -TimeoutSec 5 -ErrorAction Stop
        Start-Process $qrPath
        Write-OK "QR code généré et ouvert ($qrPath)."
    } catch {
        Write-INFO "QR code non généré (pas de connexion internet ?) — utilisez l'URL affichée ci-dessous."
    }
}

# ═══════════════════════════════════════════════════════════════════════════
# 8. Récapitulatif
# ═══════════════════════════════════════════════════════════════════════════

Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║       EDG CONNECT — LAN DEVELOPMENT           ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "IP LAN détectée : $lanIp" -ForegroundColor Green
Write-Host ""
Write-Host "Backend"
Write-Host "  Local : http://localhost:$BackendPort"
Write-Host "  LAN   : http://${lanIp}:${BackendPort}"
Write-Host "  API   : $apiLanUrl"
Write-Host ""
Write-Host "Frontend"
Write-Host "  Local : http://localhost:$FrontendPort"
Write-Host "  LAN   : $frontendLanUrl"
Write-Host ""
if ($backendReady) { Write-OK "Backend accessible" } else { Write-FAIL "Backend inaccessible" }
if ($frontendReady) { Write-OK "Frontend accessible" } else { Write-FAIL "Frontend inaccessible" }
if ($apiLanOk) { Write-OK "API joignable via l'IP LAN" } else { Write-FAIL "API non joignable via l'IP LAN (pare-feu ?)" }
Write-OK "CORS : allow_origins=['*'] déjà actif en développement (backend/api/main.py)"
Write-Host ""
Write-Host "───────────────────────────────────────────────"
Write-Host ""
Write-Host "📱 Ouvrir sur le téléphone (même Wi-Fi que ce PC) :" -ForegroundColor Cyan
Write-Host ""
Write-Host "   $frontendLanUrl" -ForegroundColor White
Write-Host ""
Write-Host "───────────────────────────────────────────────"
if (-not $apiLanOk -or -not $frontendReady) {
    Write-Host ""
    Write-Host "⚠️  Le téléphone doit être connecté au même réseau local que ce PC." -ForegroundColor Yellow
    Write-Host "⚠️  Si l'API reste injoignable, vérifiez le pare-feu Windows (voir ci-dessus)." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "CTRL+C → arrêter l'environnement LAN (backend + frontend)" -ForegroundColor DarkGray
Write-Host ""

# ═══════════════════════════════════════════════════════════════════════════
# 9. Attente + arrêt propre (CTRL+C) — ne tue QUE les processus démarrés ici
# ═══════════════════════════════════════════════════════════════════════════

function Stop-ProcessTree {
    param([int]$ProcessId)
    if (-not $ProcessId) { return }
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) { Stop-ProcessTree -ProcessId $child.ProcessId }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

try {
    while ($true) { Start-Sleep -Seconds 1 }
} finally {
    Write-Host ""
    Write-INFO "Arrêt de l'environnement LAN…"
    Stop-ProcessTree -ProcessId $backendProc.Id
    Stop-ProcessTree -ProcessId $frontendProc.Id
    Write-OK "Backend et frontend arrêtés."
}
