<#
.SYNOPSIS
    Registra o portal (uvicorn) e, opcionalmente, o poller do Drive como
    servicos Windows via NSSM, com restart automatico e start no boot sem login.

.DESCRIPTION
    Implementa HANDOFF-DEVOPS-PORTAL.md secao 2 (portal como servico persistente).

    Dois servicos:
      - portal-web    : uvicorn portal.app.main:app  (SEMPRE)
      - portal-poller : mesmo app, mas com PORTAL_POLL_ENABLED=true, em um
                        segundo servico ISOLADO (HANDOFF 2.2), SO se -ComPoller.

    IMPORTANTE (leia antes de rodar):
      * Este script NAO foi executado pelo DevOps por seguranca (instala servico
        Windows real). Rode voce mesmo, como Administrador, apos revisar os
        parametros abaixo.
      * O poller NAO e um binario separado no codigo atual: o app FastAPI ja sobe
        o poller no lifespan quando PORTAL_POLL_ENABLED=true (ver portal/app/main.py).
        Por isso o "portal-poller" e uma segunda instancia do MESMO app com o
        poller ligado e as rotas HTTP desligadas na pratica (bind em porta separada
        so para health). Se, no futuro, o poller virar um script proprio, troque
        apenas a linha marcada [POLLER-ENTRYPOINT].

.PARAMETER PythonExe
    Caminho absoluto do python.exe que roda o portal. Default tenta o venv do repo
    e cai para o python do PATH. NAO deixe hardcode de um venv que nao existe.

.PARAMETER RepoDir
    Raiz do repositorio (AppDirectory do servico).

.PARAMETER Host
    IP em que o uvicorn escuta. Em producao: o IP Tailscale (100.x.y.z), NUNCA
    0.0.0.0 (HANDOFF 1.4, invariante VPN-only). Default 127.0.0.1 para teste local.

.PARAMETER Port
    Porta do portal-web. Default 21380 (bate com portal/app/config.py).

.PARAMETER PollerPort
    Porta do portal-poller (health isolado). Default 21381.

.PARAMETER LogsDir
    Diretorio para stdout/stderr rotativos dos servicos.

.PARAMETER Nssm
    Caminho do nssm.exe. Default "nssm" (assume no PATH; via winget/choco fica no PATH).

.PARAMETER ComPoller
    Se presente, tambem registra o servico portal-poller.

.EXAMPLE
    # Producao (rodar como Admin, apos winget install nssm):
    .\instalar_servico.ps1 -Host 100.101.102.103 -PythonExe "D:\...\.venv\Scripts\python.exe" -ComPoller

.NOTES
    PRE-REQUISITO OBRIGATORIO: NSSM instalado.
      winget install nssm
      -- OU baixar de https://nssm.cc/download e colocar nssm.exe em C:\nssm\ (e no PATH).
#>
[CmdletBinding()]
param(
    [string]$PythonExe,
    [string]$RepoDir   = "D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main",
    [string]$BindHost  = "127.0.0.1",
    [int]$Port         = 21380,
    [int]$PollerPort   = 21381,
    [string]$LogsDir   = "D:\Agente-cad-PYSIDE\logs",
    [string]$Nssm      = "nssm",
    [switch]$ComPoller
)

$ErrorActionPreference = "Stop"

$WebSvc    = "portal-web"
$PollerSvc = "portal-poller"

# --- Resolucao do python.exe (nao hardcodar um venv inexistente) ---
if (-not $PythonExe) {
    $venvPy = Join-Path $RepoDir ".venv\Scripts\python.exe"
    if (Test-Path $venvPy) {
        $PythonExe = $venvPy
    } else {
        $cmd = Get-Command python -ErrorAction SilentlyContinue
        if (-not $cmd) {
            throw "python.exe nao encontrado. Passe -PythonExe com o caminho do interpretador do portal."
        }
        $PythonExe = $cmd.Source
        Write-Warning "Venv nao encontrado em $venvPy - usando python do PATH: $PythonExe"
    }
}

# --- Validacoes de pre-requisito ---
$nssmCmd = Get-Command $Nssm -ErrorAction SilentlyContinue
if (-not $nssmCmd) {
    throw "NSSM nao encontrado ('$Nssm'). Instale com 'winget install nssm' ou baixe de https://nssm.cc/download e ponha no PATH."
}
if (-not (Test-Path $PythonExe)) { throw "PythonExe nao existe: $PythonExe" }
if (-not (Test-Path $RepoDir))   { throw "RepoDir nao existe: $RepoDir" }
New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

if ($BindHost -eq "0.0.0.0") {
    throw "Bind em 0.0.0.0 viola a invariante VPN-only (HANDOFF 1.4). Use o IP Tailscale ou 127.0.0.1."
}

Write-Host "[install] NSSM      : $($nssmCmd.Source)"
Write-Host "[install] Python    : $PythonExe"
Write-Host "[install] RepoDir   : $RepoDir"
Write-Host "[install] Web bind  : ${BindHost}:$Port"

function Register-PortalService {
    param(
        [string]$Name,
        [int]$SvcPort,
        [bool]$PollEnabled
    )

    # Se ja existe, remove antes de recriar (idempotente).
    $existing = & $Nssm status $Name 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Warning "[install] Servico '$Name' ja existe - parando e removendo para recriar."
        & $Nssm stop   $Name 2>$null | Out-Null
        & $Nssm remove $Name confirm 2>$null | Out-Null
    }

    # [POLLER-ENTRYPOINT] app ASGI. Se o poller virar script proprio, troque aqui.
    $appArgs = @(
        "-m", "uvicorn", "portal.app.main:app",
        "--host", $BindHost, "--port", "$SvcPort", "--workers", "1"
    )

    & $Nssm install $Name $PythonExe @appArgs
    & $Nssm set $Name AppDirectory $RepoDir
    & $Nssm set $Name Start SERVICE_AUTO_START
    & $Nssm set $Name DisplayName "Arete Portal ($Name)"

    # Variaveis de ambiente do servico (PORTAL_HOST/PORT batem com config.py).
    $envBlock = "PORTAL_HOST=$BindHost`nPORTAL_PORT=$SvcPort`nPORTAL_POLL_ENABLED=$($PollEnabled.ToString().ToLower())"
    & $Nssm set $Name AppEnvironmentExtra $envBlock

    # Restart automatico em crash (throttle 5s, sem limite de tentativas).
    & $Nssm set $Name AppThrottle 5000
    & $Nssm set $Name AppExit Default Restart
    & $Nssm set $Name AppRestartDelay 5000

    # Logs rotativos de stdout/stderr.
    & $Nssm set $Name AppStdout (Join-Path $LogsDir "$Name-out.log")
    & $Nssm set $Name AppStderr (Join-Path $LogsDir "$Name-err.log")
    & $Nssm set $Name AppRotateFiles 1
    & $Nssm set $Name AppRotateOnline 1
    & $Nssm set $Name AppRotateBytes 10485760

    & $Nssm start $Name
    Write-Host "[install] Servico '$Name' registrado e iniciado (porta $SvcPort, poller=$PollEnabled)."
}

Register-PortalService -Name $WebSvc -SvcPort $Port -PollEnabled $false

if ($ComPoller) {
    # Segundo servico isolado (HANDOFF 2.2): se o poller travar por falha do Drive,
    # o portal-web segue servindo fichas.
    Register-PortalService -Name $PollerSvc -SvcPort $PollerPort -PollEnabled $true
} else {
    Write-Host "[install] -ComPoller ausente - poller NAO registrado (portal-web sobe sozinho)."
}

Write-Host ""
Write-Host "[install] CONCLUIDO. Verifique com:"
Write-Host "    sc query $WebSvc"
Write-Host "    curl http://${BindHost}:$Port/health"
