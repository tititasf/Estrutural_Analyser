# portal/ops — Scripts de operacao do Portal (Windows)

Scripts PowerShell que operacionalizam o deploy do portal FastAPI na workstation
Windows, conforme `docs/HANDOFF-DEVOPS-PORTAL.md` (secoes 2, 3, 4, 6).

> **Autoria / seguranca:** estes scripts foram **escritos e validados sintaticamente**
> pelo DevOps, e o `backup_diario.ps1` foi **testado de verdade** contra um
> `portal_data.db` de teste. Os scripts que alteram o sistema (instalar servico,
> Firewall, Tailscale) **NAO foram executados** — voce roda manualmente, como
> Administrador, apos revisar os parametros. Nada aqui mexe no seu sistema sozinho.

---

## Pre-requisitos (instalar/configurar UMA vez, manualmente)

| Pre-requisito | Como | Usado por |
|---|---|---|
| **Python do portal** | venv do repo (`.venv\Scripts\python.exe`) OU python do PATH | todos |
| **NSSM** | `winget install nssm` ou baixar de <https://nssm.cc/download> e por no PATH | `instalar_servico.ps1`, `atualizar_portal.ps1` |
| **Tailscale** | instalado e `tailscale up` feito; anotar o IP `100.x.y.z` (`tailscale ip -4`) | bind de rede de todos (via `-BindHost`/`-HealthUrl`) |
| **Regra de Firewall** | criada manualmente (HANDOFF 1.4) — permite `100.64.0.0/10`, bloqueia o resto na porta do portal | seguranca de rede (nao ha script aqui p/ isso; comandos no handoff) |
| **Segundo disco / nuvem** | destino de backup fora da maquina (`E:\backups\...` ou rclone) | `backup_diario.ps1` (`-Dest`) |
| **Canal de alerta** | ntfy (topico secreto) ou webhook Telegram | `heartbeat.ps1` (`-WebhookUrl`) |

> **sqlite3 CLI:** NAO e' pre-requisito. Esta maquina nao tem `sqlite3.exe` no PATH
> (verificado 2026-07-05) e o `backup_diario.ps1` cai automaticamente para o Python
> (`sqlite3.Connection.backup()` + `integrity_check`), que sempre existe. Se um dia
> instalar o CLI, o script passa a preferi-lo — sem mudar nada.

---

## Ordem de execucao

### 1. Deploy inicial (uma vez)
```powershell
# como Administrador, apos NSSM + Tailscale prontos:
.\instalar_servico.ps1 -BindHost 100.x.y.z `
    -PythonExe "D:\...\.venv\Scripts\python.exe" -ComPoller
```
Registra `portal-web` (e `portal-poller` se `-ComPoller`) como servicos que sobem
no boot sem login e reiniciam em crash. Verifique:
```powershell
sc query portal-web
curl http://100.x.y.z:21380/health   # deve responder 200
```

### 2. Backup diario (agendar via Task Scheduler)
```powershell
# testar manualmente primeiro (DB apenas, destino temporario):
.\backup_diario.ps1 -Dest "$env:TEMP\bkp-teste" -PularArtefatos

# producao — agendar 03:00 diario:
schtasks /create /tn "AreteBackupDiario" `
  /tr "powershell -NoProfile -File D:\...\portal\ops\backup_diario.ps1 -Dest E:\backups\arete" `
  /sc daily /st 03:00 /rl highest
```

### 3. Heartbeat (agendar via Task Scheduler)
```powershell
schtasks /create /tn "AreteHeartbeat" `
  /tr "powershell -NoProfile -WindowStyle Hidden -File D:\...\portal\ops\heartbeat.ps1 -HealthUrl http://100.x.y.z:21380/health -WebhookUrl https://ntfy.sh/arete-portal-SEU_TOKEN" `
  /sc minute /mo 5
```

### 4. Atualizacao (sob demanda, quando houver codigo novo)
```powershell
.\atualizar_portal.ps1 -HealthUrl "http://100.x.y.z:21380/health" `
    -PythonExe "D:\...\.venv\Scripts\python.exe"
```
Faz fetch+merge, reinicia, smoke em `/health`; se falhar, **rollback automatico**
via `git checkout` (nunca `reset --hard`).

---

## O que CADA script assume que ja existe

### `instalar_servico.ps1`
- **Assume:** NSSM no PATH; `python.exe` valido (venv ou PATH); repo em `-RepoDir`;
  `portal.app.main:app` importavel (o app existe e sobe). `-BindHost` = IP Tailscale
  em producao (recusa `0.0.0.0`).
- **Nao faz:** Firewall, Tailscale, criar venv, instalar dependencias.
- **Poller:** `-ComPoller` registra `portal-poller` como 2a instancia do mesmo app
  com `PORTAL_POLL_ENABLED=true` em porta separada (o poller vive no lifespan do app,
  ver `portal/app/main.py`; nao ha binario de poller separado hoje). Se virar script
  proprio, ajustar a linha marcada `[POLLER-ENTRYPOINT]`.

### `atualizar_portal.ps1`
- **Assume:** repo git valido com remote `origin`; servico `portal-web` ja registrado
  (passo 1); `/health` acessivel na `-HealthUrl`.
- **Garante:** fetch+merge (nunca rebase); rollback via `git checkout <commit>`
  (nunca `reset --hard`/`clean -fd` — regra do repo, incidente 10/03/2026).
- **Codigos de saida:** 0 = ok; 1 = smoke falhou e rollback OK; 2 = rollback tambem
  falhou (parar e diagnosticar a mao).

### `backup_diario.ps1`
- **Assume:** `-DbPath` existe (default = `portal_data.db` na raiz do repo, bate com
  `portal/db/connection.py`); Python disponivel para o fallback; `-Dest` gravavel.
- **Prova de restaurabilidade:** roda `PRAGMA integrity_check` **na copia** e falha
  alto se != `ok`. Backup do DB via `.backup()` (WAL-safe), nao copia bruta.
- **Artefatos:** GOLDEN/ e `scripts\arete\relatorios\triagem_erros` via robocopy
  (pulados com `-PularArtefatos`). Ausencia de artefato = warning, nao erro.
- **Retencao:** mantem os ultimos `-RetencaoDias` snapshots (default 14).
- **Off-site (nuvem):** NAO incluso — adicionar `rclone sync` apos o snapshot
  (comentado no HANDOFF 4.3) se quiser a 2a camada.
- **A adicionar quando existir (HANDOFF 4.1):** LanceDB e comentarios T0 server-side
  do portal, se ficarem fora do git.

### `heartbeat.ps1`
- **Assume:** roda 1x por invocacao via Task Scheduler (SEM loop infinito). Contador
  de falhas persiste em `-StateFile` entre execucoes; `/health` OK zera.
- **Alerta:** so apos `-MaxFalhas` (default 3) falhas seguidas. **Sem `-WebhookUrl`,
  apenas LOGA** (nao alerta) — seguro instalar antes de ter canal. Zero URL hardcode.
- **Codigos de saida:** 0 = ok; 1 = falha abaixo do limiar; 2 = limiar atingido (alertou).

---

## Pendencias do dono (fora do escopo destes scripts)

1. **Rota `/status` no portal** (HANDOFF 5.2): ainda NAO existe em `portal/app/routers/`
   (verificado 2026-07-05). E' `[ENTRYPOINT] 3/3` do handoff — a implementar no app,
   nao aqui. Ate la, `docs/STATUS.md` so e' visto abrindo o arquivo.
2. **Regra de Firewall + Tailscale ACL** (HANDOFF 1.4): comandos no handoff, rodar
   manualmente como Admin. Nao ha script aqui para isso de proposito (muda o sistema).
3. **Camada off-site do backup** (rclone): opcional mas recomendada (HANDOFF 4.2).
4. **Teste de restauracao mensal** (HANDOFF 4.4): apontar `gerar_status.py --db <backup>`
   para um snapshot e conferir que gera um STATUS.md coerente.
