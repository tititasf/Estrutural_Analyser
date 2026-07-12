# Story 1.2: API pública FastAPI — skeleton, porta 21390, conexão read-only

**Epic:** Epic 1 — Fundação & Consulta Segura por ID
**Priority:** P0
**Status:** ✅ Done (implementado e testado ao vivo em 2026-07-11)
**Estimated Effort:** M (médio)

```yaml
executor: "@dev"
quality_gate: "@architect"
quality_gate_tools: ["pytest", "curl smoke test", "coderabbit"]
```

---

## Story

**As a** arquiteto de segurança do produto,
**I want** um novo processo FastAPI, fisicamente separado do portal interno, rodando na porta 21390, sem nenhuma credencial ou dependência de `auth`/`access`/`repository` do portal,
**so that** a superfície pública nunca tenha caminho de código para os controllers autenticados nem para os bancos internos, mesmo em caso de comprometimento total do processo público.

---

## Context

Achado central da Architecture: reusar `n1_routes.py` (que exige `Depends(auth.exige_login)`) seria acoplar a superfície pública ao controlador autenticado — **rejeitado explicitamente**. A API pública deve ser um processo/serviço novo, com seu próprio `config.py`, seu próprio bind `127.0.0.1:21390`, e **nenhum** import de módulos de autenticação/autorização do portal interno.

[Source: architecture.md §1 item 5 "Autorização interna é por membro/dono... Rejeitado explicitamente"]
[Source: architecture.md §7 "Deploy — topologia real"]
[Source: architecture.md §11 checklist "API pública é processo separado, read-only, porta 21390, sem credencial do portal"]

Esta story entrega o **esqueleto**: app FastAPI instanciável, config por env, conexão `mode=ro` ao `public_consulta.db` (criado na STORY-01), e o endpoint `/health`. Os endpoints de negócio (`/resolve`, `/ficha`, `/svg`, `/obra`, `/paineis-lv`) são stories separadas (03, 05, 06, 07, 12) para manter cada PR revisável e testável isoladamente.

---

## Acceptance Criteria

1. **Given** o repositório, **when** o processo `consulta-publica-api` é iniciado (`uvicorn main:app`), **then** ele faz bind em `127.0.0.1:21390` (nunca `0.0.0.0` — exposição só via Cloudflare Tunnel/reverse-proxy) e loga a versão/config carregada.

2. **Given** o processo rodando, **when** `GET /api/v1/health` é chamado, **then** retorna `200 {"status":"ok"}` **sem** nenhum dado sensível, com header `Cache-Control: no-store`.

3. **Given** o módulo de conexão a `public_consulta.db`, **when** inspecionado, **then** ele abre a conexão **exclusivamente** com `sqlite3.connect("file:{path}?mode=ro", uri=True)` (ou equivalente async) — uma tentativa programática de `INSERT`/`UPDATE`/`DELETE` através deste módulo **deve falhar** com `OperationalError` (comprovado em teste).

4. **Given** o código-fonte da API pública, **when** auditado (grep/import scan), **then** **não existe nenhum import** de `portal/app/auth.py`, `portal/app/access.py`, `portal/app/repository.py`, `portal/db/connection.py` (o módulo que abre `portal_data.db`/`project_data.vision`) — comprovável por teste estático (ex.: script que falha o build se esses imports aparecerem em `consulta-publica-api/**`).

5. **Given** o router da API pública, **when** inspecionado, **then** **nenhuma rota aceita `POST`, `PUT`, `DELETE` ou `PATCH`** — só `GET`. Uma tentativa de `POST /api/v1/health` retorna `405 Method Not Allowed` (FastAPI default, mas deve ser testado explicitamente pois é garantia estrutural de segurança, não um acidente).

6. **Given** a config da API (`consulta-publica-api/config.py`), **when** carregada, **then** lê `PUBLIC_CONSULTA_DB_PATH`, `DADOS_OBRAS_ROOT`, `PORT` (default 21390), `ALLOWED_ORIGIN` (para CORS, usado na STORY-04) via variáveis de ambiente — sem hardcode de paths absolutos de máquina de desenvolvedor.

7. **Given** o serviço, **when** implantado, **then** roda como processo/serviço systemd/PM2 **próprio**, distinto do processo do portal (`:21380`) — documentado no README de deploy da story (não precisa implementar o systemd unit nesta story, mas o `Procfile`/comando de start deve existir e ser diferente do comando do portal).

---

## Dependencies

- **Requires:** STORY-01 (schema `public_consulta.db` precisa existir para o módulo de conexão ser testável).
- **Blocks:** STORY-03, STORY-05, STORY-06, STORY-07, STORY-12 (todos os endpoints de negócio dependem deste skeleton existir).

---

## Tasks / Subtasks

- [ ] Task 1 — Inicializar novo app FastAPI isolado (AC: 1, 6, 7)
  - [ ] Subtask 1.1: `consulta-publica-api/main.py` com `FastAPI()` app, bind `127.0.0.1:21390`
  - [ ] Subtask 1.2: `consulta-publica-api/config.py` — env vars (`PUBLIC_CONSULTA_DB_PATH`, `DADOS_OBRAS_ROOT`, `PORT`, `ALLOWED_ORIGIN`)
  - [ ] Subtask 1.3: Comando de start distinto do portal (`Procfile`/`package.json`/script `run_consulta_publica.sh`)
- [ ] Task 2 — Módulo de conexão read-only (AC: 3)
  - [ ] Subtask 2.1: `consulta-publica-api/db/connection.py` — `get_ro_connection()` com `mode=ro`
  - [ ] Subtask 2.2: Teste que comprova `OperationalError` em tentativa de escrita
- [ ] Task 3 — Endpoint `/api/v1/health` (AC: 2)
  - [ ] Subtask 3.1: Router `health_routes.py`
  - [ ] Subtask 3.2: Teste de header `Cache-Control: no-store`
- [ ] Task 4 — Garantir isolamento estrutural (AC: 4, 5)
  - [ ] Subtask 4.1: Script/teste estático de import scan (falha se `portal.app.auth`/`access`/`repository` aparecerem)
  - [ ] Subtask 4.2: Teste que todas as rotas registradas só aceitam `GET` (iterar `app.routes`)

---

## Dev Notes

### Files/Components Expected (path a confirmar com @architect/@dev no kickoff)

- `consulta-publica-api/main.py`
- `consulta-publica-api/config.py`
- `consulta-publica-api/db/connection.py`
- `consulta-publica-api/routers/health_routes.py`
- `consulta-publica-api/tests/test_isolation.py` (import scan + method scan)
- `consulta-publica-api/tests/test_connection.py`

### Technical Notes

- **Porta 21390** é decisão explícita da Architecture (contígua ao portal `:21380`). [Source: architecture.md §7 `[AUTO-DECISION]` "porta 21390 para a API pública"]
- **Bind `127.0.0.1`**, exposto só via Cloudflare Tunnel — mesma disciplina do portal (`config.py` do portal já faz bind local). [Source: architecture.md §7]
- **Padrão a clonar:** "Portal roda FastAPI puro, uvicorn, bind `127.0.0.1:21380`, config por env em `portal/app/config.py`. Boa base para clonar o padrão numa segunda app isolada." [Source: architecture.md §1 item 6]
- **Nenhuma dependência de auth/access/repository** — isto é uma garantia estrutural testável, não apenas uma diretriz de code review. [Source: architecture.md §5.1 item 3 "Read-only físico"]

---

## Testing

- **Test file location:** `consulta-publica-api/tests/`
- **Framework:** pytest + `TestClient` do FastAPI
- **Test scenarios obrigatórios:**
  - `test_health_returns_200_no_store`
  - `test_no_write_verbs_registered` (itera `app.routes`, falha se achar POST/PUT/DELETE/PATCH)
  - `test_ro_connection_rejects_write`
  - `test_no_forbidden_imports` (scan estático de `consulta-publica-api/**` por `portal.app.auth`, `portal.app.access`, `portal.app.repository`, `portal.db.connection`)
- **Special consideration:** estes testes alimentam diretamente a suíte de segurança da STORY-15 — devem ser escritos de forma reutilizável (não descartar após esta story).

---

## 🤖 CodeRabbit Integration

**Story Type Analysis**
- **Primary Type:** Architecture (novo processo/serviço, padrão de isolamento)
- **Secondary Type(s):** Deployment (novo processo systemd/PM2), Security (isolamento físico)
- **Complexity:** Medium — skeleton simples, mas com garantias estruturais críticas

**Specialized Agent Assignment**
- **Primary Agents:** @dev, @architect (novo padrão de isolamento de serviço)
- **Supporting Agents:** @github-devops (coordenação de deploy/processo separado)

**Quality Gate Tasks**
- [ ] Pre-Commit (@dev): Run antes de marcar story completa
- [ ] Pre-PR (@github-devops): Run antes de criar PR
- [ ] Pre-Deployment (@github-devops): Run scan de config/secrets antes de deploy — novo processo em produção

**CodeRabbit Focus Areas**
- **Primary Focus:**
  - Isolamento de processo/credencial (nenhum import proibido)
  - Bind `127.0.0.1`, nunca `0.0.0.0`
- **Secondary Focus:**
  - Environment config: variáveis obrigatórias validadas na inicialização
  - Padrões consistentes com `portal/app/config.py`

**Self-Healing Configuration**
- **Expected Self-Healing:** Primary Agent: @dev (light mode) · Max Iterations: 2 · Timeout: 15 min · Severity Filter: CRITICAL only
- **Predicted Behavior:** CRITICAL (import proibido, bind `0.0.0.0`, verbo de escrita registrado): auto_fix. HIGH: document_only.

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-07-11 | 0.1 | Story criada a partir de architecture.md §1/§7/§11 | River (SM) |
| 2026-07-11 | 1.0 | Implementado e testado ao vivo — ver Dev Agent Record | Claude (dev) |

---

## Dev Agent Record

**Arquivos criados:**
- `consulta-publica-api/config.py` — `Settings`/`load_settings`, env vars
- `consulta-publica-api/db/connection.py` — `get_ro_connection` (mode=ro)
- `consulta-publica-api/routers/health_routes.py` — `GET /api/v1/health`
- `consulta-publica-api/main.py` — `create_app()`, bind 127.0.0.1:21390
- `consulta-publica-api/run_consulta_publica.bat` — start script distinto do portal
- `consulta-publica-api/tests/test_connection.py` (3 testes)
- `consulta-publica-api/tests/test_isolation.py` (3 testes — import scan + method scan + 405 e2e)
- `consulta-publica-api/tests/test_health.py` (1 teste)

**Testes:** 16/16 passando (9 STORY-01 + 7 STORY-02 —
`pytest consulta-publica-api`), incluindo os 4 cenários obrigatórios da
story (`test_health_returns_200_no_store`, `test_no_write_verbs_registered`,
`test_ro_connection_rejects_write`, `test_no_forbidden_imports`).

**Verificado ao vivo:** processo real iniciado via
`uvicorn main:app --host 127.0.0.1 --port 21390` (mesmo comando do
`run_consulta_publica.bat`) — `GET /api/v1/health` → `200 {"status":"ok"}`
com `Cache-Control: no-store`; `POST /api/v1/health` → `405`. Processo
parado ao final do teste.

**Incompatibilidade de ambiente encontrada e contornada:**
`starlette.testclient.TestClient` é incompatível com `httpx==0.28.1`
instalado neste ambiente (`Client.__init__() got an unexpected keyword
argument 'app'` — breaking change do httpx 0.28 que a versão instalada do
Starlette/FastAPI, 0.27.0/0.104.1, não acompanha). Não fiz downgrade de
dependência compartilhada com o portal — troquei os 2 testes afetados para
`httpx.AsyncClient(transport=httpx.ASGITransport(app=app))`, API moderna
equivalente, sem tocar em requirements globais. Documentado para as
próximas stories (05-14) não reintroduzirem `TestClient` sem essa mesma
ressalva.

**Decisão de kickoff:** `/docs` do Swagger mantido ativo (não removido) —
não expõe dado sensível (endpoint único é `/health`); reavaliar quando
endpoints de negócio existirem (STORY-03+).
