# HANDOFF-DEVOPS — Deploy & Operação do Portal na Workstation

**Autor:** Gage (DevOps / Operator)
**Data:** 2026-07-05
**Escopo:** Plano executável de deploy e operação do portal web (FastAPI) na
workstation Windows do dono, atendendo aos gates **P3** (acesso remoto seguro) e
**P5** (operação estável) do `MASTERPLAN-PRODUCAO-SOBERANIA.md`.
**Público:** operação de **1 pessoa** (o dono), sem equipe de infra dedicada.

> **Fonte de verdade:** `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` (DP-1 a DP-14,
> gates P0–P6, riscos R1–R9). Este documento **não redecide nada** — apenas
> operacionaliza o que já foi fechado. Se algo aqui conflitar com o masterplan, o
> masterplan vence.

## Invariantes herdados do masterplan (não violar)

| Invariante | Origem | Consequência operacional |
|---|---|---|
| Nenhuma porta exposta à internet pública | §3, DP-11, P3 | Portal escuta **só** na interface Tailscale. Zero port-forward no roteador. |
| Uma máquina = ponto único de falha | R2 | Backup externo diário obrigatório (§4 deste doc). |
| Fila serial — nunca 2 jobs pesados juntos | P2, `single_instance.py` | Worker reusa o lock de arquivo; enquanto `accoreconsole` existir, 1 job por vez. |
| Serviços externos degradam, não derrubam | R5 (NIM), R8 (Drive) | Poller e RAG capturam exceção, logam, reagendam. Serviço web segue de pé. |
| Portal só **lê** artefatos; grava só obras/jobs/comentários | §3 | Backup do portal ≠ backup dos dados de curadoria (que são do dono). |

**Estado atual (verificado 2026-07-05):** o serviço FastAPI do portal **ainda não
existe** (é o gate P2, a construir). Este handoff descreve o alvo de deploy para
quando o serviço existir. Onde precisar de um ponto de entrada concreto, assumo o
módulo `portal/app.py` expondo o objeto ASGI `app` (`uvicorn portal.app:app`) —
se o P2 escolher outro caminho, **atualizar apenas os 3 lugares marcados
`[ENTRYPOINT]` abaixo**, nada mais.

---

## 1. Tailscale + restrição do serviço à VPN

### 1.1 Por que Tailscale
Escolha do masterplan (DP-2: "Tailscale ou equivalente"). Tailscale entrega o que
o P3 pede com custo/esforço mínimo para 1 pessoa: rede WireGuard privada, sem abrir
porta no roteador, com identidade por membro (login Google/Microsoft) — o que
sustenta o requisito "logins dos 3–5 membros".

### 1.2 Instalação na workstation (servidor)
1. Baixar em <https://tailscale.com/download/windows> e instalar.
2. `tailscale up` → autenticar com a conta do dono. Anotar o IP `100.x.y.z` da
   máquina (é o endereço fixo dentro da VPN): `tailscale ip -4`.
3. Recomendado: no admin console, **desabilitar key expiry** da máquina-servidor
   (Machines → servidor → Disable key expiry) para o nó não cair sozinho a cada 180
   dias — evita "serviço inacessível" sem causa aparente.
4. Recomendado: dar um nome MagicDNS estável ao servidor (ex.: `portal`), para a
   equipe acessar `http://portal:<porta>` em vez de decorar o IP.

### 1.3 Logins da equipe (3–5 membros) — requisito literal do P3
- Convidar cada membro pelo admin console (**Users → Invite external users**) com o
  e-mail dele. Cada um instala o Tailscale no próprio dispositivo e entra.
- Opcional e recomendado para 1 operador: usar **ACLs** para restringir o que a
  equipe enxerga a apenas a porta do portal no servidor. Exemplo de ACL:

```jsonc
// Admin console → Access Controls
{
  "groups": { "group:equipe": ["ana@ex.com", "bruno@ex.com"] },
  "acls": [
    // dono acessa tudo
    { "action": "accept", "src": ["autogroup:owner"], "dst": ["*:*"] },
    // equipe só alcança a porta do portal na máquina-servidor
    { "action": "accept", "src": ["group:equipe"], "dst": ["portal:8787"] }
  ]
}
```

> Nota P3 ≠ transporte de obra. A equipe **envia obras pelo Google Drive** (DP-10),
> não por upload no portal. A VPN serve para **acessar o portal** (ver fichas,
> comentar, baixar N5). São dois canais distintos — não confundir.

### 1.4 Restringir o portal para responder SÓ dentro da VPN
Duas camadas, ambas obrigatórias (defesa em profundidade):

**Camada A — bind na interface Tailscale (não em `0.0.0.0`).** O uvicorn escuta
apenas no IP `100.x.y.z`. Assim, mesmo que o Firewall do Windows falhe, a porta não
existe em `localhost` público nem na LAN doméstica.

```bash
# [ENTRYPOINT] 1/3 — troque portal.app:app se o P2 usar outro módulo
uvicorn portal.app:app --host 100.x.y.z --port 8787 --workers 1
```

> `--workers 1` é intencional: o worker de jobs é serial (invariante da fila). A
> concorrência HTTP de leitura é suficiente com 1 worker para 3–5 pessoas.

**Camada B — regra de Firewall do Windows** que só aceita a sub-rede Tailscale
(`100.64.0.0/10`, CGNAT range oficial do Tailscale) na porta do portal:

```powershell
# PowerShell como Administrador (rodar uma vez)
New-NetFirewallRule -DisplayName "Portal Arete (Tailscale only)" `
  -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8787 `
  -RemoteAddress 100.64.0.0/10
# E bloquear explicitamente qualquer outra origem na mesma porta:
New-NetFirewallRule -DisplayName "Portal Arete BLOCK non-VPN" `
  -Direction Inbound -Action Block -Protocol TCP -LocalPort 8787 `
  -RemoteAddress LocalSubnet,Internet
```

**Verificação (fazer após configurar):**
- De um dispositivo da equipe **na VPN**: `http://portal:8787/health` responde.
- Do celular **fora da VPN** (4G, VPN desligada): a conexão **falha/timeout**. Se
  responder, a Camada A ou B está errada — parar e corrigir antes do P3 fechar.

---

## 2. Portal como serviço persistente no Windows (sobrevive a reboot)

Requisito literal do P3: *"máquina reinicia → serviço volta → processa 1 item →
serve a ficha"*, **sem intervenção manual**. Task Scheduler "at logon" não serve
(exige login interativo). A solução robusta para 1 operador é **NSSM** (Non-Sucking
Service Manager): registra o uvicorn como serviço nativo do Windows, com
**restart automático em crash** e start no boot sem login.

### 2.1 Instalar NSSM e registrar o serviço
```bash
# 1) Instalar NSSM (via winget, ou baixar de nssm.cc e pôr em C:\nssm\)
winget install nssm

# 2) Registrar o serviço (PowerShell/cmd como Admin)
#    [ENTRYPOINT] 2/3 — ajuste o caminho do python do venv e o módulo ASGI
nssm install AreteePortal ^
  "D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\.venv\Scripts\python.exe" ^
  "-m" "uvicorn" "portal.app:app" "--host" "100.x.y.z" "--port" "8787" "--workers" "1"

nssm set AreteePortal AppDirectory "D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main"
nssm set AreteePortal Start SERVICE_AUTO_START
# Restart automático: se cair, NSSM reinicia (throttle 5s, sem limite)
nssm set AreteePortal AppThrottle 5000
nssm set AreteePortal AppExit Default Restart
# Logs rotativos do stdout/stderr do serviço
nssm set AreteePortal AppStdout "D:\Agente-cad-PYSIDE\logs\portal-out.log"
nssm set AreteePortal AppStderr "D:\Agente-cad-PYSIDE\logs\portal-err.log"
nssm set AreteePortal AppRotateFiles 1
nssm set AreteePortal AppRotateBytes 10485760

nssm start AreteePortal
```

### 2.2 Poller do Google Drive (DP-10/DP-11) — segundo serviço
O poller que varre o Drive é **outro processo persistente** e deve ser registrado
como um segundo serviço NSSM idêntico (`AreteePoller`), apontando para o script do
poller (a criar no P2). Motivo de separar do web: se o poller travar/reiniciar por
falha da API do Drive (R8), o portal web segue servindo fichas normalmente.

### 2.3 Endpoint `/health` (contrato mínimo do serviço)
O portal **deve** expor `GET /health` retornando `200` + JSON com: versão do engine
(commit), status do worker de fila, e último poll do Drive. É o alvo do smoke test
(§3) e do heartbeat (§6). Sem `/health`, não há como automatizar P3/P5 — tratar
como parte obrigatória do P2.

### 2.4 Verificação de persistência (smoke do P3)
```bash
shutdown /r /t 0            # reinicia a máquina
# após o boot, SEM abrir sessão de app nenhuma:
sc query AreteePortal       # deve estar RUNNING
curl http://100.x.y.z:8787/health   # deve responder 200
```

---

## 3. Rotina de atualização (git pull + restart + smoke, com rollback)

Requisito P5: *"rotina de atualização documentada (git pull + restart do serviço)
com smoke test"*. Toda run precisa gravar `engine_version` (commit) — por isso a
rotina **fixa o commit antigo antes de atualizar**, o que dá o rollback de graça.

Guardar como `scripts/arete/atualizar_portal.ps1`:

```powershell
# atualizar_portal.ps1 — atualização segura do portal com rollback automático
$ErrorActionPreference = "Stop"
cd "D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main"

$OLD = git rev-parse HEAD          # commit atual = ponto de rollback
Write-Host "[update] commit atual (rollback point): $OLD"

git fetch origin
git merge origin/main --no-edit    # regra do projeto: fetch+merge, NUNCA rebase/reset
# se houver dependências novas:
.\.venv\Scripts\pip.exe install -r requirements.txt

nssm restart AreteePortal
Start-Sleep -Seconds 8             # dar tempo do uvicorn subir

# --- SMOKE TEST: só considera sucesso se o /health responder 200 ---
try {
    $r = Invoke-WebRequest -Uri "http://100.x.y.z:8787/health" -TimeoutSec 20
    if ($r.StatusCode -ne 200) { throw "health status $($r.StatusCode)" }
    Write-Host "[update] SMOKE OK — atualizacao aplicada. novo commit: $(git rev-parse HEAD)"
}
catch {
    Write-Warning "[update] SMOKE FALHOU: $_ — REVERTENDO para $OLD"
    git merge --abort 2>$null
    git checkout $OLD -- .          # volta o worktree ao commit bom (sem reset --hard)
    git checkout $OLD               # detach no commit bom
    nssm restart AreteePortal
    Start-Sleep -Seconds 8
    Invoke-WebRequest -Uri "http://100.x.y.z:8787/health" -TimeoutSec 20 | Out-Null
    Write-Host "[update] ROLLBACK concluido — servico de volta no commit $OLD"
    exit 1
}
```

**Regras herdadas de git (não negociáveis neste repo):**
- `fetch + merge`, **nunca** `pull --rebase` nem `reset --hard`.
- Rollback usa `git checkout <commit>` — **jamais** `reset --hard` / `clean -fd`
  (perde dados). O incidente 10/03/2026 (perda de 3 squads por `reset --hard`) é a
  razão desta regra.
- Se o smoke falhar **e** o rollback também falhar em subir: parar tudo, deixar o
  serviço no último estado bom conhecido e diagnosticar à mão. Nunca deixar em
  estado ambíguo com a equipe usando.

**Quando o smoke falha:** o script já reverte sozinho. O dono só precisa olhar o
motivo em `logs/portal-err.log` e corrigir antes de tentar de novo. A equipe nunca
vê uma versão quebrada — o portal volta ao commit anterior automaticamente.

---

## 4. Backup diário (com prova de restauração)

Requisito P5: backup de `project_data.vision`, `GOLDEN/`, logs de triagem e LanceDB,
**para fora da máquina**. R2 é o risco que isto mitiga (máquina única). Backup que
nunca foi restaurado não é backup — por isso a rotina inclui **verificação de
restaurabilidade**, não só "o arquivo existe".

### 4.1 O que entra no backup (fontes reais verificadas)
| Fonte | Caminho real (2026-07-05) | Observação |
|---|---|---|
| DB canônico | `D:\Agente-cad-PYSIDE\project_data.vision` | **É o `_DB_DEFAULT` de `gerar_status.py`** — a cópia na raiz do repo (`...Restored-main\project_data.vision`) é stale; **backupar o de cima**. |
| GOLDEN | `...Restored-main\GOLDEN\` (~79 MB) | Itens selados; versionado em git, mas backup externo dá redundância independente do GitHub. |
| Logs de triagem | `...Restored-main\scripts\arete\relatorios\triagem_erros\*.jsonl` | Evidência T0. |
| Comentários T0 do portal | (a definir no P2 — provável SQLite server-side) | **Adicionar quando o P2 criar.** Único dado que NÃO está no git. |
| LanceDB | (ainda não existe — WS-C consolida) | **Adicionar quando existir.** Até lá, N/A (RAG é opcional, R5). |

### 4.2 Destino "fora da máquina"
Ordem de preferência para 1 operador, do mais simples ao mais robusto:
1. **Segundo disco físico** na mesma máquina (`E:\backups\`) — mínimo aceitável do
   masterplan, protege contra falha do disco primário, **não** contra incêndio/roubo.
2. **Nuvem** (recomendado como camada 2): `rclone` para Google Drive/Backblaze B2.
   Fecha o R2 de verdade (off-site).

Fazer **os dois** é barato e recomendado: local para restauração rápida, nuvem para
desastre. O masterplan pede "segundo disco OU nuvem"; um operador sério faz ambos.

### 4.3 Script de backup — `scripts/arete/backup_diario.ps1`
```powershell
# backup_diario.ps1 — snapshot diário verificável
$ErrorActionPreference = "Stop"
$TS   = Get-Date -Format "yyyyMMdd-HHmmss"
$DEST = "E:\backups\arete\$TS"          # destino local (segundo disco)
New-Item -ItemType Directory -Force -Path $DEST | Out-Null

# 1) DB canônico via API de backup do SQLite (consistente mesmo com o serviço lendo)
$SRC_DB = "D:\Agente-cad-PYSIDE\project_data.vision"
sqlite3 "$SRC_DB" ".backup '$DEST\project_data.vision'"

# 2) GOLDEN + logs de triagem (robocopy /MIR incremental)
robocopy "D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\GOLDEN" "$DEST\GOLDEN" /MIR /NFL /NDL /R:2 /W:5
robocopy "D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\relatorios\triagem_erros" "$DEST\triagem_erros" /MIR /NFL /NDL /R:2 /W:5

# 3) Registrar o commit do engine junto ao backup (reprodutibilidade P5)
cd "D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main"
git rev-parse HEAD | Out-File "$DEST\engine_version.txt"

# 4) PROVA DE RESTAURAÇÃO — não basta o arquivo existir:
#    abrir a cópia do DB e rodar integrity_check + uma contagem real.
$check = sqlite3 "$DEST\project_data.vision" "PRAGMA integrity_check;"
if ($check -ne "ok") { throw "BACKUP CORROMPIDO: integrity_check='$check'" }
$rows = sqlite3 "$DEST\project_data.vision" "SELECT count(*) FROM sqlite_master;"
Write-Host "[backup] $TS OK — DB integro, $rows objetos, commit $(git rev-parse --short HEAD)"

# 5) Camada off-site (nuvem) — opcional mas recomendado
# rclone sync "$DEST" "gdrive:backups/arete/$TS" --transfers 4

# 6) Retenção: manter últimos 14 dias
Get-ChildItem "E:\backups\arete" | Sort-Object Name -Descending | Select-Object -Skip 14 | Remove-Item -Recurse -Force
```

Agendar via Task Scheduler (backup pode ser "at logon"/diário, diferente do serviço):
```powershell
schtasks /create /tn "AreteBackupDiario" /tr "powershell -File D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\backup_diario.ps1" /sc daily /st 03:00 /rl highest
```

### 4.4 Por que isto é "restaurável", não só "existe"
- `.backup` do SQLite gera cópia **consistente** (não um `copy` de arquivo aberto).
- `PRAGMA integrity_check` **abre e valida** o arquivo copiado — se corrompeu, o
  script **falha alto** (o dono descobre no dia, não no desastre).
- `engine_version.txt` amarra o backup ao commit que o gerou (P5).
- **Teste de restauração mensal (manual, 5 min):** copiar um backup para uma pasta
  temporária, apontar `gerar_status.py --db <backup>` para ele e conferir que gera
  um STATUS.md coerente. Só assim se sabe que o backup é utilizável de ponta a ponta.

---

## 5. Publicar o `docs/STATUS.md` dentro do próprio portal

Requisito P5 (WS-D): STATUS gerado por `scripts/arete/gerar_status.py` →
`docs/STATUS.md`, publicado no portal para o dono ver o estado real **sem abrir o
arquivo à mão**. O script já existe e escreve `docs/STATUS.md` a partir de fontes
read-only. Falta (a) regenerar periodicamente e (b) servir por HTTP.

### 5.1 Regeneração periódica
`gerar_status.py` é read-only e barato — pode rodar sozinho. **Não** rodar em
paralelo com um job pesado sem coordenação: reusar o mesmo `single_instance` para
não competir por RAM/DB durante uma rodada headless. Task diária:
```powershell
schtasks /create /tn "AreteStatusRefresh" /tr "D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\.venv\Scripts\python.exe D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\gerar_status.py" /sc hourly /mo 6
```
Melhor ainda: chamar `gerar_status.py` **ao fim de cada job** do worker (o STATUS
reflete o resultado imediatamente após processar uma obra).

### 5.2 Servir no portal — rota `/status`
Adicionar ao portal uma rota que renderiza `docs/STATUS.md` como HTML. Contrato:

```python
# [ENTRYPOINT] 3/3 — rota a incluir no portal (portal/app.py)
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
import markdown  # pip install markdown

router = APIRouter()
_STATUS = Path(__file__).resolve().parents[1] / "docs" / "STATUS.md"

@router.get("/status", response_class=HTMLResponse)
def status_page():
    if not _STATUS.is_file():
        return HTMLResponse("<h1>STATUS ainda não gerado</h1>"
                            "<p>rode scripts/arete/gerar_status.py</p>", status_code=200)
    html = markdown.markdown(_STATUS.read_text(encoding="utf-8"),
                             extensions=["tables", "fenced_code"])
    mtime = _STATUS.stat().st_mtime
    from datetime import datetime
    gerado = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
    return HTMLResponse(f"<article style='max-width:900px;margin:2rem auto;"
                        f"font-family:system-ui'><p><em>Gerado: {gerado}</em></p>{html}</article>")
```

Assim o dono abre `http://portal:8787/status` na VPN e vê o estado real, sempre
fresco, sem tocar em arquivo. Como o portal só **lê** o `.md` (invariante §3), isso
não fere nenhuma fronteira. Ligar um item de menu "Status" visível só para o login
do dono (não para a equipe).

---

## 6. Monitoramento mínimo (como o dono descobre que o serviço caiu)

Sem dashboard sofisticado. Para 1 operador, o mínimo eficaz é um **heartbeat** que
bate no `/health` e **avisa por push no celular** quando falha N vezes seguidas.

### 6.1 Heartbeat — `scripts/arete/heartbeat.ps1`
```powershell
# heartbeat.ps1 — roda a cada 5 min via Task Scheduler; alerta se cair
$URL   = "http://100.x.y.z:8787/health"
$STATE = "D:\Agente-cad-PYSIDE\logs\heartbeat_fails.txt"
$MAX   = 3   # só alerta após 3 falhas seguidas (evita alarme por restart normal)

try {
    $r = Invoke-WebRequest -Uri $URL -TimeoutSec 15
    if ($r.StatusCode -eq 200) {
        Set-Content $STATE "0"           # zera contador
        # NSSM já reinicia o serviço; heartbeat só observa e alerta.
        return
    }
    throw "status $($r.StatusCode)"
}
catch {
    $fails = 0
    if (Test-Path $STATE) { $fails = [int](Get-Content $STATE) }
    $fails++
    Set-Content $STATE "$fails"
    if ($fails -ge $MAX) {
        # ALERTA — escolher UM canal (ntfy é o mais simples, zero setup de servidor):
        Invoke-RestMethod -Uri "https://ntfy.sh/arete-portal-SEU_TOKEN_UNICO" `
          -Method Post -Body "PORTAL CAIU: $URL falhou $fails vezes. $_"
        # (instalar o app ntfy no celular e assinar o tópico 'arete-portal-SEU_TOKEN_UNICO')
    }
}
```
```powershell
schtasks /create /tn "AreteHeartbeat" /tr "powershell -WindowStyle Hidden -File D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\heartbeat.ps1" /sc minute /mo 5
```

### 6.2 Camadas de defesa (o alerta é a última linha)
1. **NSSM** já reinicia o serviço em crash — a maioria das quedas se auto-cura.
2. **Heartbeat** cobre o que o NSSM não vê: processo "vivo mas travado" (deadlock,
   DB lockado, disco cheio) — `/health` não responde 200 mesmo com o processo de pé.
3. **Alerta push (ntfy)** só dispara após 3 falhas seguidas (~15 min), para não
   incomodar o dono a cada restart legítimo de atualização.

`ntfy.sh` é a opção de menor atrito (tópico secreto = "senha", app grátis no
celular, sem servidor). Alternativa igualmente válida: um webhook do Telegram. O que
**não** fazer: e-mail (o dono não vê a tempo) ou dashboard que exige alguém olhando.

---

## 7. Gatilho para migrar à VPS Linux (não prescrever data)

O masterplan trata a VPS como **degrau futuro** (DP-2, R2), **bloqueado por WS-C**.
O gatilho é **técnico, não de calendário**:

> **Migrar para VPS Linux somente quando `accoreconsole` sair do pipeline** — isto
> é, quando **WS-C estiver fechado**: entrada DWG→DXF migrada de `accoreconsole`
> (que exige AutoCAD, só roda em Windows) para **ODA File Converter** (gratuito,
> multiplataforma), com regressão golden verde comprovando saída idêntica.

Enquanto `accoreconsole` for a porta de entrada, o servidor **tem** que ser Windows
com AutoCAD — VPS Linux é tecnicamente impossível, não é escolha. Assim que a
dependência de AutoCAD cair, a mesma stack deste handoff (uvicorn + serviço +
backup + heartbeat) reaparece em Linux com equivalentes diretos: **systemd** no
lugar do NSSM, **cron** no lugar do Task Scheduler, **Tailscale** e **rclone**
idênticos. Nenhuma peça deste plano é jogada fora na migração — só troca o
gerenciador de serviço.

**Checklist de prontidão para VPS (só olhar quando WS-C fechar):**
- [ ] WS-C fechado: ODA substituiu `accoreconsole`, zero AutoCAD no pipeline do servidor.
- [ ] Backup externo já operando e restaurado com sucesso ≥1 vez (não migrar dado sem rede).
- [ ] LanceDB consolidado (WS-C também aposenta ChromaDB/FAISS) — vector store portável.
- [ ] NIM segue como dependência externa consciente (DP-6) — funciona igual da VPS.

Até lá: **não migrar**. A workstation + backup externo diário é a operação
sancionada pelo masterplan para v1.

---

## Resumo de entrega

Entreguei `docs/HANDOFF-DEVOPS-PORTAL.md`, o plano executável de deploy e operação
do portal na workstation do dono, cobrindo os 7 pontos pedidos e ancorado no que
existe no repo (verifiquei que o serviço FastAPI ainda não existe — é o P2 — e
marquei 3 pontos `[ENTRYPOINT]` para ajuste quando ele nascer). Concreto: Tailscale
com ACL + bind na interface VPN + regra de Firewall (dupla camada, zero porta
pública); NSSM registrando portal e poller como serviços que voltam no boot sem
login e reiniciam em crash; rotina `atualizar_portal.ps1` com fetch+merge, smoke em
`/health` e rollback automático via `git checkout` (nunca `reset --hard`);
`backup_diario.ps1` com `.backup` consistente do SQLite, `integrity_check` como
prova de restaurabilidade e camada off-site opcional; rota `/status` servindo o
`STATUS.md` já gerado; heartbeat com alerta push via ntfy após 3 falhas. O gatilho
de VPS é técnico — fechar WS-C (fim do `accoreconsole`) — sem data. Todos os
invariantes do masterplan (VPN-only, fila serial via `single_instance.py`, degradar
sem derrubar) foram respeitados.
