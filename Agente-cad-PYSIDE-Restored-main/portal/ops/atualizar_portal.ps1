<#
.SYNOPSIS
    Atualiza o portal (fetch+merge), reinicia o servico, roda smoke test em /health
    e faz ROLLBACK automatico via git checkout se o smoke falhar.

.DESCRIPTION
    Implementa HANDOFF-DEVOPS-PORTAL.md secao 3 (rotina de atualizacao com rollback).

    Regras de git deste repo (NAO NEGOCIAVEIS):
      * fetch + merge  -> NUNCA pull --rebase.
      * rollback via 'git checkout <commit>' -> JAMAIS 'git reset --hard' nem
        'git clean -fd' (incidente 10/03/2026: reset --hard destruiu dados).

.PARAMETER RepoDir
    Raiz do repositorio.

.PARAMETER ServiceName
    Nome do servico NSSM do portal-web. Default "portal-web".

.PARAMETER HealthUrl
    URL do /health para o smoke test. Em producao use o IP Tailscale.

.PARAMETER PythonExe
    python.exe para reinstalar dependencias (se requirements.txt mudou). Opcional.

.PARAMETER SmokeTimeoutSec
    Timeout de cada tentativa de /health.

.PARAMETER SmokeRetries
    Quantas vezes tentar o /health antes de considerar falha (uvicorn demora a subir).

.EXAMPLE
    .\atualizar_portal.ps1 -HealthUrl "http://100.101.102.103:21380/health" `
        -PythonExe "D:\...\.venv\Scripts\python.exe"
#>
[CmdletBinding()]
param(
    [string]$RepoDir        = "D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main",
    [string]$ServiceName    = "portal-web",
    [string]$HealthUrl      = "http://127.0.0.1:21380/health",
    [string]$PythonExe      = "",
    [int]$SmokeTimeoutSec   = 20,
    [int]$SmokeRetries      = 5,
    [string]$Nssm           = "nssm"
)

$ErrorActionPreference = "Stop"
Set-Location $RepoDir

function Test-Health {
    param([string]$Url, [int]$TimeoutSec, [int]$Retries)
    for ($i = 1; $i -le $Retries; $i++) {
        try {
            $r = Invoke-WebRequest -Uri $Url -TimeoutSec $TimeoutSec -UseBasicParsing
            if ($r.StatusCode -eq 200) { return $true }
            Write-Warning "[update] /health status $($r.StatusCode) (tentativa $i/$Retries)"
        } catch {
            Write-Warning "[update] /health falhou (tentativa $i/$Retries): $($_.Exception.Message)"
        }
        Start-Sleep -Seconds 4
    }
    return $false
}

function Restart-Portal {
    $svc = Get-Command $Nssm -ErrorAction SilentlyContinue
    if ($svc) {
        & $Nssm restart $ServiceName
    } else {
        Write-Warning "[update] NSSM nao encontrado - tentando Restart-Service $ServiceName"
        Restart-Service -Name $ServiceName -ErrorAction Stop
    }
    Start-Sleep -Seconds 8
}

# --- Ponto de rollback: commit atual ANTES de qualquer mudanca ---
$OLD = (git rev-parse HEAD).Trim()
Write-Host "[update] commit atual (ponto de rollback): $OLD"

# --- fetch + merge (NUNCA rebase/reset) ---
git fetch origin
git merge origin/main --no-edit
$NEW = (git rev-parse HEAD).Trim()
Write-Host "[update] apos merge: $NEW"

# --- dependencias novas, se houver python informado ---
if ($PythonExe -and (Test-Path $PythonExe) -and (Test-Path (Join-Path $RepoDir "requirements.txt"))) {
    Write-Host "[update] instalando/atualizando dependencias..."
    & $PythonExe -m pip install -r (Join-Path $RepoDir "requirements.txt")
}

Restart-Portal

# --- SMOKE TEST ---
if (Test-Health -Url $HealthUrl -TimeoutSec $SmokeTimeoutSec -Retries $SmokeRetries) {
    Write-Host "[update] SMOKE OK - atualizacao aplicada. Novo commit: $NEW"
    exit 0
}

# --- ROLLBACK (git checkout, NUNCA reset --hard) ---
Write-Warning "[update] SMOKE FALHOU - REVERTENDO para $OLD"

# Se houver merge em andamento (conflito), aborta o merge (seguro: nao apaga worktree).
git merge --abort 2>$null

# Volta o worktree ao commit bom e destaca nele (sem reset --hard / clean -fd).
git checkout $OLD -- .
git checkout $OLD

Restart-Portal

if (Test-Health -Url $HealthUrl -TimeoutSec $SmokeTimeoutSec -Retries $SmokeRetries) {
    Write-Host "[update] ROLLBACK concluido - servico de volta no commit $OLD"
    exit 1
} else {
    Write-Error "[update] ROLLBACK NAO subiu o servico. PARANDO em estado conhecido ($OLD). Diagnostique em logs\\$ServiceName-err.log manualmente. NAO deixar ambiguo com a equipe usando."
    exit 2
}
