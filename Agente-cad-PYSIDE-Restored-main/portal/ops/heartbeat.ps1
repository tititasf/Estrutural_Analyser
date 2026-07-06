<#
.SYNOPSIS
    Heartbeat do portal: bate em /health e, apos N falhas seguidas, dispara um
    alerta via webhook configuravel (ntfy/Telegram/etc). SEM loop infinito -
    projetado para rodar 1x por invocacao via Task Scheduler.

.DESCRIPTION
    Implementa HANDOFF-DEVOPS-PORTAL.md secao 6 (monitoramento minimo).

    Camadas de defesa (o alerta e' a ultima linha):
      1. NSSM ja reinicia o servico em crash (auto-cura a maioria das quedas).
      2. Este heartbeat cobre "vivo mas travado": processo de pe mas /health nao
         responde 200 (deadlock, DB lockado, disco cheio).
      3. Alerta so dispara apos -MaxFalhas seguidas (~15 min com Task */5min),
         para nao incomodar a cada restart legitimo de atualizacao.

    O contador de falhas persiste em -StateFile entre execucoes (Task Scheduler
    roda o script do zero a cada vez). /health OK zera o contador.

.PARAMETER HealthUrl
    URL do /health. Em producao use o IP Tailscale (100.x.y.z).

.PARAMETER WebhookUrl
    URL do webhook de alerta (ntfy topico secreto, webhook Telegram, etc).
    NAO ha URL hardcode: se vazio, o script apenas LOGA a falha e NAO alerta
    (util para instalar antes de ter canal). Configure via parametro/env.

.PARAMETER MaxFalhas
    Falhas seguidas antes de alertar. Default 3.

.PARAMETER StateFile
    Arquivo que guarda o contador de falhas entre execucoes.

.PARAMETER TimeoutSec
    Timeout da requisicao /health.

.EXAMPLE
    # Sem alerta (so log), para validar o agendamento:
    .\heartbeat.ps1 -HealthUrl "http://127.0.0.1:21380/health"

.EXAMPLE
    # Com ntfy (topico secreto = "senha"):
    .\heartbeat.ps1 -HealthUrl "http://100.101.102.103:21380/health" `
        -WebhookUrl "https://ntfy.sh/arete-portal-SEU_TOKEN_UNICO"

.NOTES
    Agendar (roda a cada 5 min, sem loop no script):
      schtasks /create /tn "AreteHeartbeat" ^
        /tr "powershell -NoProfile -WindowStyle Hidden -File D:\...\portal\ops\heartbeat.ps1 -HealthUrl http://100.x.y.z:21380/health -WebhookUrl https://ntfy.sh/arete-portal-SEU_TOKEN" ^
        /sc minute /mo 5
#>
[CmdletBinding()]
param(
    [string]$HealthUrl  = "http://127.0.0.1:21380/health",
    [string]$WebhookUrl = "",
    [int]$MaxFalhas     = 3,
    [string]$StateFile  = "D:\Agente-cad-PYSIDE\logs\heartbeat_fails.txt",
    [int]$TimeoutSec    = 15
)

$ErrorActionPreference = "Stop"

function Get-FailCount {
    param([string]$Path)
    if (Test-Path $Path) {
        $v = (Get-Content $Path -Raw).Trim()
        [int]$n = 0
        if ([int]::TryParse($v, [ref]$n)) { return $n }
    }
    return 0
}

function Set-FailCount {
    param([string]$Path, [int]$Value)
    $dir = Split-Path $Path -Parent
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    Set-Content -Path $Path -Value "$Value"
}

function Send-Alerta {
    param([string]$Url, [string]$Mensagem)
    if (-not $Url) {
        Write-Warning "[heartbeat] ALERTA (sem WebhookUrl configurado): $Mensagem"
        return
    }
    try {
        # ntfy aceita POST com corpo texto puro; Telegram/genericos tambem funcionam.
        Invoke-RestMethod -Uri $Url -Method Post -Body $Mensagem -TimeoutSec $TimeoutSec | Out-Null
        Write-Host "[heartbeat] alerta enviado para o webhook."
    } catch {
        Write-Warning "[heartbeat] falha ao enviar alerta: $($_.Exception.Message)"
    }
}

$ok = $false
$detalhe = ""
try {
    $r = Invoke-WebRequest -Uri $HealthUrl -TimeoutSec $TimeoutSec -UseBasicParsing
    if ($r.StatusCode -eq 200) { $ok = $true } else { $detalhe = "status $($r.StatusCode)" }
} catch {
    $detalhe = $_.Exception.Message
}

if ($ok) {
    Set-FailCount -Path $StateFile -Value 0
    Write-Host "[heartbeat] OK - $HealthUrl respondeu 200."
    exit 0
}

# Falhou: incrementa e, no limiar, alerta.
$fails = (Get-FailCount -Path $StateFile) + 1
Set-FailCount -Path $StateFile -Value $fails
Write-Warning "[heartbeat] FALHA $fails/$MaxFalhas em $HealthUrl - $detalhe"

if ($fails -ge $MaxFalhas) {
    $msg = "PORTAL CAIU: $HealthUrl falhou $fails vezes seguidas. Detalhe: $detalhe"
    Send-Alerta -Url $WebhookUrl -Mensagem $msg
    exit 2
}

exit 1
