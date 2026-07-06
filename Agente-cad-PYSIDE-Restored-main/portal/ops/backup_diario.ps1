<#
.SYNOPSIS
    Snapshot diario verificavel do portal: backup consistente do SQLite +
    GOLDEN/ + logs de triagem, com PRAGMA integrity_check como prova de
    restaurabilidade. Destino configuravel (parametro, nao hardcode).

.DESCRIPTION
    Implementa HANDOFF-DEVOPS-PORTAL.md secao 4 (backup diario com prova de restauracao).

    Por que .backup e nao 'copy':
      SQLite em WAL tem dados em portal_data.db-wal ainda nao mesclados. Um 'copy'
      do arquivo bruto pode capturar um estado inconsistente. A API de backup do
      SQLite (sqlite3 .backup no CLI, ou Connection.backup() no Python) gera uma
      copia CONSISTENTE mesmo com o servico lendo/escrevendo.

    Por que integrity_check:
      Backup que nunca foi aberto nao e' backup. O script ABRE a copia e roda
      PRAGMA integrity_check; se != 'ok', FALHA ALTO (o dono descobre no dia).

    sqlite3 CLI x Python:
      Esta maquina NAO tem sqlite3.exe no PATH (verificado 2026-07-05). O script
      prefere o CLI se existir, mas cai para o Python (sqlite3.Connection.backup +
      integrity_check) - que sempre existe, pois o portal roda em Python. Ambos os
      caminhos produzem backup consistente e verificado.

.PARAMETER Dest
    Raiz do destino do backup (OBRIGATORIO conceitualmente; tem default mas o dono
    deve apontar para o segundo disco / nuvem). Um subdiretorio com timestamp e'
    criado dentro dele.

.PARAMETER DbPath
    Caminho do portal_data.db. Default = raiz do repo (bate com portal/db/connection.py).

.PARAMETER RepoDir
    Raiz do repo (para GOLDEN/, logs de triagem e git rev-parse).

.PARAMETER PythonExe
    python.exe usado no fallback (backup + integrity_check). Default: venv ou PATH.

.PARAMETER RetencaoDias
    Quantos snapshots manter (por data). Default 14.

.PARAMETER PularArtefatos
    Se presente, faz APENAS o backup do DB (util para teste rapido do script).

.EXAMPLE
    .\backup_diario.ps1 -Dest "E:\backups\arete"

.EXAMPLE
    # Teste de logica (so o DB, destino temporario):
    .\backup_diario.ps1 -Dest "$env:TEMP\bkp-teste" -DbPath "C:\tmp\portal_data.db" -PularArtefatos
#>
[CmdletBinding()]
param(
    [string]$Dest         = "E:\backups\arete",
    [string]$DbPath       = "D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal_data.db",
    [string]$RepoDir      = "D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main",
    [string]$PythonExe    = "",
    [int]$RetencaoDias    = 14,
    [switch]$PularArtefatos
)

$ErrorActionPreference = "Stop"

# --- Resolucao do python.exe para o fallback ---
function Resolve-Python {
    param([string]$Explicit, [string]$Repo)
    if ($Explicit -and (Test-Path $Explicit)) { return $Explicit }
    $venvPy = Join-Path $Repo ".venv\Scripts\python.exe"
    if (Test-Path $venvPy) { return $venvPy }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

# --- Backup consistente do SQLite (CLI se houver, senao Python) ---
function Invoke-SqliteBackup {
    param([string]$Src, [string]$Out, [string]$Py)
    $cli = Get-Command sqlite3 -ErrorAction SilentlyContinue
    if ($cli) {
        # Caminho CLI: aspas escapadas para o .backup do sqlite3.
        & $cli.Source $Src ".backup '$Out'"
        if ($LASTEXITCODE -ne 0) { throw "sqlite3 .backup falhou (exit $LASTEXITCODE)" }
        return
    }
    if (-not $Py) { throw "Nem sqlite3 CLI nem python encontrados: impossivel fazer backup consistente." }
    # Caminho Python: Connection.backup() faz backup online consistente (WAL-safe).
    # Snippet em uma linha (evita here-string; robusto na chamada via -c).
    $pyCode = "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); " +
              "d.execute('PRAGMA busy_timeout=5000'); " +
              "s.backup(d); d.commit(); d.close(); s.close(); print('backup-ok')"
    $null = & $Py -c $pyCode $Src $Out
    if ($LASTEXITCODE -ne 0) { throw "python backup falhou (exit $LASTEXITCODE)" }
}

# --- PRAGMA integrity_check na COPIA (prova de restaurabilidade) ---
function Test-SqliteIntegrity {
    param([string]$DbFile, [string]$Py)
    $cli = Get-Command sqlite3 -ErrorAction SilentlyContinue
    if ($cli) {
        $out = & $cli.Source $DbFile "PRAGMA integrity_check;"
        return ($out | Select-Object -First 1)
    }
    $pyCode = "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); " +
              "r=c.execute('PRAGMA integrity_check;').fetchone(); c.close(); " +
              "print(r[0] if r else 'sem-resultado')"
    return (& $Py -c $pyCode $DbFile)
}

function Get-SqliteObjectCount {
    param([string]$DbFile, [string]$Py)
    $cli = Get-Command sqlite3 -ErrorAction SilentlyContinue
    if ($cli) { return (& $cli.Source $DbFile "SELECT count(*) FROM sqlite_master;") }
    $pyCode = "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); " +
              "n=c.execute('SELECT count(*) FROM sqlite_master;').fetchone()[0]; c.close(); print(n)"
    return (& $Py -c $pyCode $DbFile)
}

# --- Execucao ---
$Py = Resolve-Python -Explicit $PythonExe -Repo $RepoDir
if (-not (Test-Path $DbPath)) { throw "DbPath nao existe: $DbPath" }

$TS       = Get-Date -Format "yyyyMMdd-HHmmss"
$DestSnap = Join-Path $Dest $TS
New-Item -ItemType Directory -Force -Path $DestSnap | Out-Null

$DbName   = Split-Path $DbPath -Leaf
$DbOut    = Join-Path $DestSnap $DbName

Write-Host "[backup] $TS -> $DestSnap"
Write-Host "[backup] DB origem : $DbPath"
if (Get-Command sqlite3 -ErrorAction SilentlyContinue) {
    Write-Host "[backup] engine   : sqlite3 CLI"
} else {
    Write-Host "[backup] engine   : python ($Py)  [sqlite3 CLI ausente]"
}

# 1) Backup consistente do DB.
Invoke-SqliteBackup -Src $DbPath -Out $DbOut -Py $Py

# 2) Artefatos (GOLDEN + logs de triagem) - salvo se -PularArtefatos.
if (-not $PularArtefatos) {
    $golden  = Join-Path $RepoDir "GOLDEN"
    $triagem = Join-Path $RepoDir "scripts\arete\relatorios\triagem_erros"
    if (Test-Path $golden) {
        robocopy $golden (Join-Path $DestSnap "GOLDEN") /MIR /NFL /NDL /NJH /NJS /R:2 /W:5 | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy GOLDEN falhou (exit $LASTEXITCODE)" }
    } else { Write-Warning "[backup] GOLDEN nao encontrado em $golden (pulando)" }
    if (Test-Path $triagem) {
        robocopy $triagem (Join-Path $DestSnap "triagem_erros") /MIR /NFL /NDL /NJH /NJS /R:2 /W:5 | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy triagem falhou (exit $LASTEXITCODE)" }
    } else { Write-Warning "[backup] triagem_erros nao encontrado em $triagem (pulando)" }
}

# 3) Amarrar o backup ao commit do engine (reprodutibilidade P5).
try {
    Push-Location $RepoDir
    (git rev-parse HEAD).Trim() | Out-File -Encoding utf8 (Join-Path $DestSnap "engine_version.txt")
    Pop-Location
} catch { Write-Warning "[backup] git rev-parse falhou (engine_version.txt nao gravado): $_" }

# 4) PROVA DE RESTAURACAO - integrity_check na copia.
$check = (Test-SqliteIntegrity -DbFile $DbOut -Py $Py).Trim()
if ($check -ne "ok") { throw "BACKUP CORROMPIDO: integrity_check='$check'" }
$rows = (Get-SqliteObjectCount -DbFile $DbOut -Py $Py).Trim()
Write-Host "[backup] $TS OK - DB integro (integrity_check=ok), $rows objetos em sqlite_master."

# 5) Retencao: manter apenas os ultimos N snapshots (por nome/data).
if (Test-Path $Dest) {
    Get-ChildItem $Dest -Directory |
        Sort-Object Name -Descending |
        Select-Object -Skip $RetencaoDias |
        ForEach-Object { Remove-Item $_.FullName -Recurse -Force }
}

Write-Host "[backup] concluido. Snapshot: $DestSnap"
