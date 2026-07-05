# HANDOFF ARCHITECT — Backend do Portal Soberano (Gates P1–P3)

**Autor:** Aria (Architect / Visionary)
**Data:** 2026-07-05
**Para:** @dev (implementação — uma story por vez, strangler fig)
**Precede:** `MASTERPLAN-PRODUCAO-SOBERANIA.md` (decisões DP-1…DP-14, gates P0–P6, riscos R1–R9). **Este doc concretiza o que o masterplan §3 descreve em alto nível.** Não relitiga nenhuma DP-* nem gate P-*.

---

## 0. Princípios herdados (não rediscutir)

- **Portal NUNCA importa PySide6.** Ele **shella** (`subprocess`) o pipeline headless já existente. A app PySide6 continua sendo a cabine de governança do dono (DP-3, §5.4 do masterplan).
- **Portal só grava** 3 coisas: obras enviadas (baixadas do Drive), jobs, comentários `equipe:*`. **Nunca** escreve em fichas / golden / curadoria / DB de conhecimento (§3, fronteira).
- **1 job por vez** na máquina — reusa `scripts/arete/single_instance.py` (lock anti-OOM, liberado pelo SO mesmo em crash). Nunca 2 headless em paralelo.
- **Nenhuma porta pública.** Serviço só escuta em `127.0.0.1` / interface Tailscale (P3). Sem HTTPS externo, sem CORS aberto.
- **Degradar, não derrubar** (R5/R8): Drive fora, NIM fora, job com erro → serviço continua de pé; item fica em estado `aguardando_ingestao` / `erro`, nunca crash do processo web.

### Suposições registradas (ambiguidades resolvidas pela interpretação mais simples)

- **[AUTO-DECISION]** Framework web → **FastAPI + Uvicorn** (o masterplan já sugere "FastAPI ou equivalente"; é o mais simples com async para o poller e serve estáticos direto). Reason: menor superfície, um único processo.
- **[AUTO-DECISION]** Persistência de jobs/sessões/comentários → **SQLite dedicado `portal.db`**, arquivo SEPARADO do `project_data.vision` do Arete. Reason: respeita a fronteira "portal não escreve no DB de curadoria"; um DB só do portal nunca colide com o funil do dono.
- **[AUTO-DECISION]** Poller e web server → **mesmo processo Uvicorn**, poller roda como `asyncio` background task (`lifespan`). Reason: MVP, zero infra extra (DP-11); se crescer, extrai para processo próprio depois (nota em §9).
- **[AUTO-DECISION]** Execução do headless → **subprocess do CLI existente** (`python -m scripts.arete.headless_sa_analise --obra … --wait`), NÃO import in-process. Reason: isola o Qt/offscreen e a RAM do web server; um job que trava/estoura RAM não derruba o portal (R2/R4).
- **[AUTO-DECISION]** Worker de jobs → **1 thread única** dentro do mesmo processo, consumindo fila FIFO do SQLite. Reason: a exclusão mútua real já vem do `single_instance` lock; a thread só serializa e observa. Mais simples que Celery/RQ.

---

## 1. Estrutura de serviço (FastAPI)

### 1.1 Layout de módulos (novo, fora do monólito — strangler fig)

```
portal/                              # NOVO pacote, zero dependência da app PySide6
├── __init__.py
├── main.py                          # cria app FastAPI, monta routers, lifespan (sobe poller+worker)
├── config.py                        # paths, credenciais Drive, intervalos, dataclass Settings (de env/.env)
├── db.py                            # conexão SQLite portal.db, migrations idempotentes (CREATE IF NOT EXISTS)
├── models.py                        # dataclasses: Obra, Job, Comentario, Usuario, Sessao (sem ORM pesado)
├── auth.py                          # login por membro, cookie de sessão assinado (itsdangerous)
├── drive_poller.py                  # DP-10/DP-11: service account, varre pastas, baixa obra nova
├── job_queue.py                     # fila FIFO + worker thread + integração single_instance lock
├── pipeline_runner.py               # subprocess do headless + assemble_n5; traduz etapa→comando
├── routers/
│   ├── auth_routes.py               # POST /login, POST /logout, GET /me
│   ├── obras_routes.py              # GET /obras, GET /obras/{id}
│   ├── jobs_routes.py               # POST etapas (triagem/recortes/sa/validacao/n5), GET /jobs/{id}
│   ├── fichas_routes.py             # GET /obras/{id}/fichas (serve HTML existente), viewer básico
│   └── comentarios_routes.py        # POST/GET comentários T0 (equipe:*)
├── static/                          # CSS/JS mínimos do portal (listas de aprovação, viewer)
└── templates/                       # Jinja2: login, dashboard de obras, página de resultado
```

**Fronteira de import:** `portal/` importa APENAS `scripts.arete.single_instance` e `src.core.n5_assembler` como bibliotecas. Todo o resto do pipeline (SA, motores, geradores STOG) é acionado **por subprocess**, nunca importado. Isso mantém o web server livre de Qt e do peso de RAM do pipeline.

### 1.2 As 6 etapas → endpoints REST

O fluxo enxuto DP-14 tem 6 etapas. Cada uma é uma **transição de estado da obra**, disparada por um POST que enfileira (ou executa localmente) e retorna imediatamente com o job criado. A UI faz polling em `GET /jobs/{id}`.

| # | Etapa | Endpoint | O que aciona | Onde roda |
|---|-------|----------|--------------|-----------|
| 1 | **Upload** | *(nenhum — é o poller)* `GET /obras` lista o que caiu | Poller do Drive detecta+baixa (§2). Estado inicial da obra: `detectada`. | Poller |
| 2 | **Triagem** | `POST /obras/{id}/triagem` | Conversão de entrada (ODA DWG→DXF se preciso, WS-C) + validação de sanidade ezdxf (R6). Cria job `tipo=triagem`. | Worker → subprocess conversor |
| 3 | **Recortes** | `POST /obras/{id}/recortes` | Segmentação/crop dos itens da obra (fase de recorte do pipeline). Job `tipo=recortes`. | Worker → subprocess pipeline |
| 4 | **SA completo** | `POST /obras/{id}/sa` (body: `{secao?: ["pilares"…]}`) | `headless_sa_analise.py --obra … [--secao …] --wait`. Gera N3 + fichas HTML. Job `tipo=sa`. | Worker → subprocess headless (lock) |
| 5 | **Validação** | `POST /obras/{id}/validacao` (body: `{n1_ok, n3_ok, item_id}`) | Registra a validação **do usuário** (N1 interpretação + N3 desenho) no `portal.db`. NÃO recomputa; só marca. Libera pré-condição do N5 (DP-13). | Web (sem subprocess) |
| 6 | **N5** | `POST /obras/{id}/n5` (body: `{classe, pavimento}`) → depois `GET /obras/{id}/n5/{classe}/download` | Chama `assemble_n5(obra_dir, classe, pavimento=…)` (import direto — é leve, só ezdxf). Job `tipo=n5`. Download self-service. | Worker → import n5_assembler |

**Regra de gating no endpoint N5 (DP-13 + R9):** `POST /n5` só aceita se a etapa 5 (validação do usuário para aquela classe/item) estiver registrada. A resposta e a tela de download SEMPRE carregam o rótulo `certificado`/`beta` da classe (lido de um mapa em `config.py`/`portal.db`, alimentado pelo funil do dono — o portal não decide certificação, só exibe). Usuário nunca confunde "validei minha parte" com "motor certificado".

### 1.3 Contrato de resposta de job (uniforme)

```json
{
  "job_id": "uuid",
  "obra_id": "Obra_TREINO_1",
  "tipo": "sa",
  "estado": "queued|running|done|error|degraded",
  "criado_em": "2026-07-05T12:00:00",
  "iniciado_em": null,
  "finalizado_em": null,
  "engine_version": "git-<commit-curto>",
  "log_tail": "…últimas linhas do stdout/stderr…",
  "artefatos": { "html_dir": "…", "n3_dir": "…", "n5_path": "…" }
}
```

`engine_version` é gravado em toda run (P5, reprodutibilidade) via `git rev-parse --short HEAD` capturado no início do job.

---

## 2. Poller do Google Drive (DP-10 / DP-11 / R8)

### 2.1 Autenticação

- **Service account** (JSON key), escopo `drive.readonly`. Chave em `portal/.secrets/drive-sa.json` (fora do git — mas repo é privado; ainda assim, `.secrets/` no `.gitignore` local do subprojeto).
- Cada membro **compartilha sua pasta pessoal** do Drive com o e-mail da service account (leitor). Zero OAuth interativo, zero token de usuário a renovar.
- Biblioteca: `google-api-python-client` + `google-auth`.

### 2.2 Estrutura de pastas (1 por usuário — DP-10)

```
Drive (compartilhado com a service account):
  /PortalArete/
    /joao/        ← folderId mapeado ao usuário "joao" em portal.db
    /maria/
    /pedro/
```

O mapeamento `usuario → folderId` fica na tabela `usuarios` (`drive_folder_id`). O poller NÃO descobre pastas sozinho; só varre folderIds cadastrados (superfície mínima, previsível).

### 2.3 Loop do poller (asyncio background task)

```
a cada POLL_INTERVAL (default 120s):
  para cada usuario com drive_folder_id:
    files = drive.list(q="'{folderId}' in parents and trashed=false", fields="files(id,name,md5Checksum,modifiedTime)")
    para cada file com extensão .dwg/.dxf:
      chave = (file.id, file.md5Checksum)     # dedup: id+hash de conteúdo
      se chave já em tabela `obras_vistas`:  continua   # já visto → NÃO reprocessa
      senão:
        baixa para  DADOS-OBRAS/<usuario>/<obra_slug>/entrada/<nome>
        cria linha em `obras` (estado=detectada, dono=usuario)
        registra chave em `obras_vistas`
```

### 2.4 arquivo → obra → job

- **arquivo → obra:** nome do arquivo (sem extensão), normalizado por `_safe_name`, vira `obra_slug`. Uma obra = uma pasta de trabalho `DADOS-OBRAS/<usuario>/<slug>/` (compatível com o layout `Obra_*` que o headless espera — o `--obra` aponta para essa pasta).
- **obra → job:** detecção NÃO dispara processamento automático. A obra nasce `detectada`; o **usuário** dispara as etapas 2–6 pela UI (DP-14, controle explícito, evita fila entupir com lixo — R6). Exceção configurável: `AUTO_TRIAGEM=true` roda só a triagem (etapa 2) ao detectar, para dar feedback rápido de "arquivo válido?".

### 2.5 Evitar reprocessar (idempotência)

Tabela `obras_vistas(file_id, md5, visto_em)`. A chave de dedup é **`file_id + md5Checksum`** — se o membro re-subir o mesmo arquivo, md5 igual → ignora; se editar e re-subir, md5 muda → nova obra/versão (estado `detectada` de novo, sem sobrescrever a anterior). Simples e à prova de "vi de novo o que já processei".

### 2.6 Tratamento de falha (R8 — degradar sem derrubar)

```
try:
    poll()
except (HttpError, TransportError, RefreshError, TimeoutError) as e:
    log.warning("poller degradado: %s", e)
    portal_state.drive = "degradado"          # exibido no dashboard
    # NÃO propaga; a task dorme o intervalo e tenta de novo
```

- Cota estourada (429) / credencial revogada / Drive fora → o loop **loga e reagenda**, marca `drive=degradado` no estado global (visível no portal), e obras já baixadas seguem processáveis. Nenhuma exceção sobe ao Uvicorn.
- Backoff exponencial com teto (2min → 4 → 8 → máx 30min) em falha persistente.

---

## 3. Modelo de fila de jobs (P2 — 1 job por vez)

### 3.1 Exclusão mútua — reuso do `single_instance`

Dois níveis, complementares:

1. **Nível processo (já existe):** o próprio `headless_sa_analise.py` pega `acquire_lock('headless_sa')`. Se o portal (ou o dono na app) já estiver rodando um headless, o subprocess do job aborta com exit code 2 — ou, com `--wait`, aguarda. **O portal sempre invoca com `--wait`** (recomendado para automação, conforme o próprio help do script). Assim o job serializa contra QUALQUER headless da máquina, inclusive os disparados pela app PySide6 do dono.
2. **Nível fila (novo):** o worker do portal é **uma thread única**. Ele processa 1 job de cada vez, então nunca dispara 2 subprocess concorrentes por conta própria. O `single_instance` é a rede de segurança contra o dono + portal ao mesmo tempo; a thread única é a serialização interna.

> Racional: a thread única sozinha garante 1-por-vez *dentro* do portal; o lock garante 1-por-vez *na máquina inteira* (portal + app do dono). Os dois juntos = invariante do masterplan cumprida sem paralelismo de accoreconsole/headless.

### 3.2 Fila FIFO com prioridade leve

- Tabela `jobs(id, obra_id, tipo, estado, prioridade, criado_em, …)`.
- Worker: `SELECT * FROM jobs WHERE estado='queued' ORDER BY prioridade DESC, criado_em ASC LIMIT 1`.
- **Prioridade padrão = 0 (FIFO puro).** Etapas curtas que NÃO tomam o lock (validação, N5-leve) podem ter prioridade 10 para não ficarem atrás de um SA de 5min — mas isso é refinamento; MVP pode ser FIFO puro.

### 3.3 Ciclo de vida do worker

```
loop:
  job = próximo queued (FIFO)
  se nenhum: dorme 2s, continua
  marca job.estado=running, job.iniciado_em=agora, job.engine_version=git-short
  try:
      resultado = pipeline_runner.executar(job)   # subprocess com --wait, ou import n5
      job.estado = done; job.artefatos = resultado
  except Timeoutdo subprocess:
      job.estado = error; job.log_tail = "timeout"
  except QualquerErro:
      job.estado = error; job.log_tail = tail(stderr)   # quarentena, R6
  finally:
      job.finalizado_em = agora
```

### 3.4 Reinício do servidor no meio de um job (crash recovery)

Ponto crítico: o subprocess do headless é filho do processo Uvicorn. Se o servidor reiniciar, o filho pode morrer junto (ou virar órfão).

**Estratégia (simples e correta):**
- No `lifespan` startup, o worker roda uma **rotina de reconciliação**: todo job em estado `running` (que só pode ter ficado assim se o servidor caiu no meio) é **re-enfileirado** → `estado=queued` (idempotente: o headless regenera as saídas; N5 é determinístico; triagem/recortes reexecutáveis).
- O `single_instance` lock é **liberado automaticamente pelo SO** quando o processo antigo morre — então, ao reiniciar, o novo worker consegue readquirir o lock sem lock órfão (é exatamente a propriedade que motivou o `single_instance`).
- Idempotência das saídas: cada etapa escreve em diretório determinístico (`Fase-6_Execucao_CAD/…`, `n5/…`) — reexecutar sobrescreve com resultado idêntico (mesma `engine_version`). Nada de estado parcial corrompido sobrevive.

> Nota: jobs são **at-least-once**. Como todas as etapas são idempotentes por design (regeneram artefatos determinísticos), re-execução após crash é segura — sem exactly-once complexo.

---

## 4. Autenticação / sessão (uso interno, 3–5 pessoas)

**Não usar OAuth completo** — é rede interna na VPN, 3–5 membros cadastrados à mão pelo dono.

- **Cadastro:** o dono cria usuários (CLI de admin ou seed em `portal.db`): `usuarios(login, senha_hash, drive_folder_id, papel)`. Papel = `equipe` (o dono não usa o portal — usa a app PySide6).
- **Senha:** hash `bcrypt` (via `passlib`). Nunca texto plano. Repo é privado, mas hash mesmo assim.
- **Login:** `POST /login {login, senha}` → valida → emite **cookie de sessão assinado** (`itsdangerous.URLSafeTimedSerializer`, `HttpOnly`, `SameSite=Lax`, `Secure` só quando houver TLS na VPN). Payload do cookie: `{login, exp}`. TTL 12h.
- **Sessões server-side:** tabela `sessoes(token, login, criado_em, expira_em)` para permitir logout/revogação. O cookie carrega o token; o middleware valida contra a tabela.
- **Middleware:** dependência FastAPI `usuario_atual = Depends(exige_login)` em todos os routers exceto `/login` e estáticos. Sem sessão válida → 401 → redireciona para `/login`.
- **Assinatura T0 (DP-3):** todo comentário e toda validação gravam `marcado_por="equipe:<login>"` (proveniência real, evidência T0). O login é a identidade; o portal nunca dá botão de curadoria a `papel=equipe`.

> Anti-escopo respeitado (§7): "portal com login NÃO é múltiplos agentes concorrentes" — login simples ≠ gatilho de RAG produtivo.

---

## 5. Diagrama de fluxo de dados (ASCII)

```
┌─────────────┐    (1) sobe DWG/DXF        ┌──────────────────────────────────┐
│  MEMBRO     │ ─────────────────────────► │  Google Drive  /PortalArete/joao/ │
│ (fora VPN)  │                            └──────────────┬───────────────────┘
└─────────────┘                                           │ compartilhada c/ service account
                                                          │ (drive.readonly)
                                   ┌──────────────────────▼───────────────────────────────┐
                                   │           WORKSTATION DO DONO = SERVIDOR               │
                                   │                                                        │
                                   │  ┌────────────────┐  (2) poll 120s, dedup file_id+md5 │
                                   │  │  drive_poller  │◄─────────────────────────────────┐│
                                   │  │  (asyncio task)│  baixa se novo                   ││
                                   │  └───────┬────────┘                                  ││
                                   │          │ grava em DADOS-OBRAS/joao/<slug>/entrada  ││
                                   │          ▼            estado obra = "detectada"       ││
                                   │  ┌────────────────────────────────────────────────┐  ││
                                   │  │              portal.db (SQLite)                 │  ││
                                   │  │  usuarios · obras · obras_vistas · jobs ·       │  ││
                                   │  │  sessoes · comentarios(equipe:*)                │  ││
                                   │  └───────▲──────────────────────▲─────────────────┘  ││
                                   │          │ REST                 │ enfileira/lê        ││
                                   │  ┌───────┴────────┐   ┌─────────┴──────────┐          ││
   ┌────────────┐  (VPN Tailscale) │  │  FastAPI/Uvicorn│──►│  job_queue (worker  │          ││
   │  MEMBRO    │ ◄───────────────►│  │  routers + auth │   │  thread única, FIFO)│          ││
   │ (navegador)│  (3) login,      │  │  serve fichas   │   └─────────┬──────────┘          ││
   └────────────┘   dispara etapas │  └─────────────────┘             │ (4) subprocess       ││
        │           2..6           │                                  │  --wait              ││
        │                          │                    ┌─────────────▼───────────────┐      ││
        │  (5) navega fichas HTML  │                    │ single_instance lock         │      ││
        │      comenta T0          │                    │ (anti-OOM, 1 headless/máquina)│     ││
        │                          │                    └─────────────┬───────────────┘      ││
        │                          │        ODA (DWG→DXF) │  headless_sa_analise.py          ││
        │                          │        conversor     │  (Qt offscreen) → N3 + fichas    ││
        │                          │                      │  assemble_n5() → N5 por classe   ││
        │                          │                    ┌─▼──────────────────────────────┐   ││
        │  (6) libera N5           │                    │  Fase-6_Execucao_CAD/           │   ││
        └── self-service (DP-13)──►│  GET .../n5/download│    ...preview N3 · html · n5/   │───┘│
           rótulo certificado/beta │◄───────────────────┤  (portal SÓ LÊ estes artefatos) │────┘
                                   │                    └─────────────────────────────────┘
                                   │  [DONO — app PySide6, FORA do portal: curadoria/golden] │
                                   └────────────────────────────────────────────────────────┘
```

---

## 6. Encaixe no plano de 30 dias (WS-B, semanas 1–4)

| Sem. | Gate | MVP MÍNIMO de arquitetura (obrigatório no gate) | Pode vir depois |
|------|------|------------------------------------------------|-----------------|
| 1 | **P1** | Nada do portal ainda. Só garantir que `pipeline_runner` consegue invocar o headless por subprocess com `--secao` e capturar stdout/artefatos. Valida o contrato §1.3 no seco (CLI). | — |
| 2 | **P2** | `portal/` esqueleto: FastAPI + `portal.db` + `drive_poller` + `job_queue` (thread única + lock) + routers das 6 etapas + serve fichas HTML + N5 download. Auth mínima (login/cookie). Comentários server-side. | Prioridade de fila (§3.2); AUTO_TRIAGEM; viewer rico; backoff sofisticado |
| 3 | **P3** | Bind só em `127.0.0.1`/Tailscale; `Secure` cookie; seed dos 3–5 usuários + `drive_folder_id`; reconciliação de job no startup (§3.4); smoke test reinício. | Revogação fina de sessão; rate-limit de login |
| 4 | **P4** | (Portal já pronto) — piloto usa o que P2/P3 entregaram. Só rótulo `certificado/beta` bem visível (R3/R9). | Métricas de uso, retro |

**Linha de corte MVP vs depois (arquitetura):**

- **MVP (entra na v1, DP-14 — nada cortado do fluxo):** poller Drive, dedup file_id+md5, 6 endpoints de etapa, worker thread única + `single_instance --wait`, reconciliação de crash, login por cookie assinado, comentários T0 server-side, N5 self-service com rótulo, degradação R5/R8.
- **Pode vir depois (não bloqueia P4):** fila com prioridade (FIFO puro basta), poller em processo separado (asyncio task basta), backoff exponencial elaborado (retry simples basta), viewer avançado, WebSocket de progresso (polling `GET /jobs/{id}` basta), backup automático (é P5), quantitativos (é P6).

**Trade-offs assumidos:**
- *Thread única vs fila distribuída (Celery):* escolhi thread única. Ganho: zero infra, crash recovery trivial. Custo: throughput serial — aceitável, o masterplan JÁ exige serialização (1 headless/máquina). Se algum dia rodar em VPS multi-core (WS-C futuro), reavaliar.
- *Poller in-process vs daemon separado:* in-process (asyncio). Ganho: um processo só, um deploy. Custo: se o poller travar, some com o web (mitigado por try/except total do R8). Extração para processo próprio é o primeiro upgrade pós-P5.
- *SQLite vs Postgres:* SQLite. Ganho: zero servidor de DB, backup = copiar 1 arquivo (P5). Custo: 1 writer por vez — irrelevante com worker de thread única e 3–5 usuários.

**Flag de segurança (R6):** parsing de qualquer DWG/DXF recebido é **exclusivamente via ezdxf**, nunca executando conteúdo; limite de tamanho de arquivo no poller (config `MAX_OBRA_MB`); job com erro → estado `error` (quarentena), nunca derruba a fila.

---

## Resumo (≤150 palavras)

Projetei o backend concreto do portal soberano para os gates P1–P3. Entreguei: (1) **estrutura FastAPI** — pacote `portal/` isolado que NUNCA importa PySide6 e aciona o pipeline por `subprocess` do `headless_sa_analise.py` existente; mapeei as 6 etapas DP-14 a endpoints REST com contrato de job uniforme e gating de N5 por validação+rótulo (DP-13/R9). (2) **Poller do Drive** — service account read-only, 1 pasta/usuário, dedup por `file_id+md5`, degradação R8 sem derrubar o serviço. (3) **Fila** — worker de thread única + reuso do `single_instance --wait` (exclusão mútua contra portal E app do dono), FIFO, e reconciliação idempotente de jobs no reinício. (4) **Auth** simples: bcrypt + cookie de sessão assinado server-side, assinatura T0 `equipe:<login>`. (5) **Diagrama ASCII** ponta a ponta. (6) **Encaixe de 30 dias** com linha MVP vs depois e trade-offs. Respeitei todas as DP-* e a fronteira do §3.

— Aria, arquitetando o futuro 🏗️
