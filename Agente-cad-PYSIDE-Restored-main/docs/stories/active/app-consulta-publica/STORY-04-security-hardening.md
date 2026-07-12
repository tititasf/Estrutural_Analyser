# Story 1.4: Rate Limiting + CORS + Detecção de Enumeração

**Epic:** Epic 1 — Fundação & Consulta Segura por ID
**Priority:** P0 (não-negociável)
**Status:** ✅ Done (implementado e testado ao vivo em 2026-07-11)
**Estimated Effort:** M (médio)

```yaml
executor: "@dev"
quality_gate: "@architect"
quality_gate_tools: ["pytest", "slowapi", "coderabbit", "load-test script"]
```

---

## Story

**As a** responsável por segurança do produto,
**I want** rate limiting por IP em todos os endpoints de consulta por código, CORS travado no domínio do frontend, e detecção/bloqueio de rajadas de enumeração,
**so that** mesmo que um atacante tente forçar bruta os códigos opacos, ele seja detectado e bloqueado antes de ter chance estatística relevante de sucesso.

---

## Context

Camada 2 de defesa em profundidade (a camada 1 é o próprio código opaco + 404 genérico, STORY-01/03). Rate limiting e CORS **não substituem** a autorização por construção — são complementares. A Architecture é explícita: Cloudflare é a primeira linha, mas o app **também** deve limitar, pois Cloudflare pode ser contornado por origin leak.

[Source: architecture.md §5.2 "Rate limiting e detecção de enumeração (NFR3)"]
[Source: prd.md NFR3 "todo endpoint de consulta por ID deve ter rate limiting... logging de padrões de enumeração"]

---

## Acceptance Criteria

1. **Given** os endpoints `/api/v1/resolve/{code}`, `/api/v1/ficha/{code}`, `/api/v1/obra/{code}`, `/api/v1/ficha/{code}/paineis-lv`, **when** um mesmo IP excede **60 requisições/minuto**, **then** requisições subsequentes retornam `429 {"erro": "muitas_tentativas", "retry_after_seconds": N}` até a janela resetar (`slowapi` ou middleware equivalente).

2. **Given** um IP que gera uma rajada de `404`s (ex.: > 20 respostas 404 em uma janela de 60s), **when** detectado, **then** o sistema registra um evento de "possível enumeração" no log de auditoria (ver AC 5) e aplica um bloqueio temporário adicional (ex.: 30s de `429` mesmo para requisições que resolveriam com sucesso, ou flag que endurece o rate limit desse IP) — comportamento exato de bloqueio a documentar no Dev Agent Record.

3. **Given** a resposta HTTP de qualquer endpoint público, **when** inspecionado o header `Access-Control-Allow-Origin`, **then** ele é **exatamente** o domínio configurado do frontend (ex.: `https://consulta.suaempresa.app`, via env var `ALLOWED_ORIGIN` da STORY-02) — **nunca** `*`.

4. **Given** uma requisição `OPTIONS` (preflight CORS) de uma origem **diferente** da configurada, **when** recebida, **then** o servidor **não** inclui o header `Access-Control-Allow-Origin` correspondente (bloqueio efetivo de consumo por frontend hostil).

5. **Given** o sistema de logging de acesso, **when** qualquer requisição chega a um endpoint de consulta por código, **then** é registrado (IP, timestamp, código consultado — hash ou truncado se necessário para não virar oráculo de enumeração no próprio log, status da resposta) em um arquivo/DB **fisicamente distinto** de `public_consulta.db` (ex.: `public_audit.db` RW ou `public_access.log` JSONL append-only) — **nunca** no mesmo arquivo read-only.

6. **Given** o endpoint `/api/v1/health`, **when** chamado, **then** **não** está sujeito ao mesmo rate limit agressivo dos endpoints de consulta (health checks de infraestrutura não devem ser bloqueados) — limite separado e mais permissivo, ou isento.

7. **Given** o middleware de rate limit, **when** testado sob carga simulada (script de load-test simples), **then** o comportamento é consistente: primeiras 60 reqs/min passam, requisições além disso recebem `429` de forma determinística.

---

## Dependencies

- **Requires:** STORY-03 (`/resolve` precisa existir para ser instrumentado; aplica-se retroativamente a STORY-05/06/07/12 quando implementadas).
- **Blocks:** STORY-08 (frontend só pode consumir a API cross-origin depois do CORS estar configurado corretamente), STORY-15 (suíte de segurança valida rate limit e detecção de enumeração).

---

## Tasks / Subtasks

- [ ] Task 1 — Middleware de rate limiting (AC: 1, 6, 7)
  - [ ] Subtask 1.1: Integrar `slowapi` (ou equivalente) com limite 60 req/min/IP nos endpoints de consulta
  - [ ] Subtask 1.2: Excluir/relaxar `/health` do limite agressivo
  - [ ] Subtask 1.3: Resposta `429` padronizada com `retry_after_seconds`
- [ ] Task 2 — Detecção de enumeração (AC: 2)
  - [ ] Subtask 2.1: Contador de 404s por IP em janela deslizante
  - [ ] Subtask 2.2: Ação de bloqueio temporário ao ultrapassar threshold
  - [ ] Subtask 2.3: Instrumentar métrica "enumeração detectada/bloqueada" (KPI do PRD §8.2)
- [ ] Task 3 — CORS travado (AC: 3, 4)
  - [ ] Subtask 3.1: Configurar `CORSMiddleware` do FastAPI com `allow_origins=[ALLOWED_ORIGIN]` (não `["*"]`)
  - [ ] Subtask 3.2: Teste de preflight de origem não autorizada
- [ ] Task 4 — Log de auditoria separado (AC: 5)
  - [ ] Subtask 4.1: Escolher formato (JSONL append-only vs `public_audit.db` RW) — decisão de @dev, documentar escolha
  - [ ] Subtask 4.2: Implementar escrita append-only, sem nunca escrever em `public_consulta.db`
  - [ ] Subtask 4.3: Garantir que o código consultado no log não vira, ele mesmo, uma superfície de enumeração (ex.: não expor o log publicamente)
- [ ] Task 5 — Testes (AC: todos)
  - [ ] Subtask 5.1: Teste de rate limit determinístico (60 reqs OK, 61ª = 429)
  - [ ] Subtask 5.2: Teste de CORS (origem correta vs incorreta)
  - [ ] Subtask 5.3: Teste de detecção de rajada de 404s

---

## Dev Notes

### Files/Components Expected

- `consulta-publica-api/middleware/rate_limit.py`
- `consulta-publica-api/middleware/cors.py` (ou configuração inline em `main.py`)
- `consulta-publica-api/audit/logger.py` — escrita em `public_audit.db`/`public_access.log`
- `consulta-publica-api/tests/test_rate_limit.py`
- `consulta-publica-api/tests/test_cors.py`
- `consulta-publica-api/tests/test_enumeration_detection.py`

### Technical Notes

- **A única escrita permitida na zona pública é o log de auditoria** — arquivo/DB fisicamente distinto de `public_consulta.db`, que permanece `mode=ro`. Alternativa preferida se disponível: mandar telemetria para Cloudflare/observabilidade e manter a zona pública 100% sem escrita local; no MVP, arquivo JSONL append-only é suficiente. [Source: architecture.md §5.3 "A única escrita permitida na zona pública (controlada)"]
- **Defesa em profundidade explícita:** "Rate limit por IP na borda Cloudflare (primeira linha) + no app (2ª linha, `slowapi`/middleware)... Cloudflare pode ser contornado por origin leak, então o app também limita." [Source: architecture.md §5.2]
- **CORS:** "`Access-Control-Allow-Origin` = exatamente o domínio Vercel... não `*`. Bloqueia consumo por front hostil." [Source: architecture.md §5.2]
- **KPI a instrumentar:** "Enumeração detectada/bloqueada — Rajadas de varredura detectadas e barradas — Alvo: 100% das rajadas de teste barradas." [Source: prd.md §8.2 tabela de KPIs]
- Esta story cobre a área **"Backend: segurança"** explicitamente requisitada pelo escopo do masterplan (rate limiting, 404 genérico constante-time [já coberto na STORY-03], CORS, anti-enumeração).

---

## Testing

- **Test file location:** `consulta-publica-api/tests/test_rate_limit.py`, `test_cors.py`, `test_enumeration_detection.py`
- **Framework:** pytest + `TestClient`; considerar `locust`/script simples de load-test para AC7
- **Test scenarios obrigatórios:**
  - Rate limit determinístico por IP
  - CORS aceita apenas origem configurada
  - Detecção de rajada de 404 dispara bloqueio/log
  - `/health` não é afetado pelo rate limit agressivo
- **Special consideration:** estes testes formam a base da suíte de segurança formal da STORY-15 ("Enumeração sequencial simulada (1000 códigos aleatórios) → 100% 404, rate-limit dispara").

---

## 🤖 CodeRabbit Integration

**Story Type Analysis**
- **Primary Type:** Security
- **Secondary Type(s):** API (middleware), Architecture (defesa em profundidade)
- **Complexity:** High — lógica de segurança sensível, não-negociável, testada sob simulação de ataque

**Specialized Agent Assignment**
- **Primary Agents:** @dev, @architect
- **Supporting Agents:** @qa (validação da suíte de detecção de enumeração)

**Quality Gate Tasks**
- [ ] Pre-Commit (@dev): Run antes de marcar completa
- [ ] Pre-PR (@github-devops): Run antes de PR
- [ ] Pre-Deployment (@github-devops): Run SAST scan — story de segurança crítica antes de produção

**CodeRabbit Focus Areas**
- **Primary Focus:**
  - OWASP Top 10: rate limiting / broken access control (A01, API4 unrestricted resource consumption)
  - Timing attacks: nenhuma diferença observável entre bloqueado e não-bloqueado além do `429` esperado
- **Secondary Focus:**
  - CORS misconfiguration (wildcard, reflexão de origem)
  - Log de auditoria não deve criar novo vetor de leitura pública

**Self-Healing Configuration**
- **Expected Self-Healing:** Primary Agent: @dev (light) · Max Iterations: 2 · Timeout: 15 min · Severity Filter: CRITICAL only — **porém, dado que é story de Security, recomenda-se @qa em modo full (3 iterações, 30 min, CRITICAL+HIGH) na revisão final antes do gate da STORY-15.**
- **Predicted Behavior:** CRITICAL (CORS wildcard, rate limit ausente): auto_fix. HIGH (threshold de detecção mal calibrado): auto_fix por @qa na revisão full.

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-07-11 | 0.1 | Story criada a partir de architecture.md §5.2/§5.3 e prd.md NFR3/KPI enumeração | River (SM) |
| 2026-07-11 | 1.0 | Implementado e testado ao vivo — ver Dev Agent Record | Claude (dev) |

---

## Dev Agent Record

**Arquivos criados:**
- `consulta-publica-api/middleware/rate_limit.py` — `RateLimitMiddleware` (60 req/min/IP, detecção de rajada de 404, bloqueio temporário, `/health` isento)
- `consulta-publica-api/audit/logger.py` — `AuditLogger` (JSONL append-only, `public_audit.log`, código sempre hasheado — path também redigido, ver achado abaixo)
- `consulta-publica-api/main.py` — `CORSMiddleware` (`allow_origins=[settings.allowed_origin]`, `allow_methods=["GET"]`, nunca `*`) + wiring do rate limiter
- `consulta-publica-api/config.py` — novo campo `audit_log_path`
- `consulta-publica-api/tests/test_rate_limit.py` (3 testes)
- `consulta-publica-api/tests/test_cors.py` (2 testes)
- `consulta-publica-api/tests/test_enumeration_detection.py` (2 testes)

**Testes:** 34/34 passando no projeto inteiro (`pytest consulta-publica-api`).
Ajustei 1 teste pré-existente da STORY-03
(`test_enumeracao_simulada_1000_codigos_aleatorios`) que assumia 100% 404 —
agora, corretamente, uma rajada de 1000 reqs passa a receber 429 depois do
limite (reforço esperado, não regressão); a asserção virou "nunca 200",
mantendo a garantia de segurança real.

**Decisão de kickoff — sem `slowapi`:** implementei rate limiting com
middleware próprio em memória em vez de instalar a lib `slowapi` (não
estava no ambiente compartilhado com o portal; a story permite
"slowapi ou middleware equivalente"). Trade-off documentado: estado em
memória de processo único, não sobrevive a restart nem escala entre
múltiplos workers — se o deploy real usar múltiplos processos, migrar para
Redis é o próximo passo natural (não implementado, fora do escopo do MVP
de 1 processo).

**Bug real encontrado e corrigido no teste ao vivo:** o log de auditoria
hasheava o `code` corretamente (`code_hash`), mas gravava `path` **cru**
(`/api/v1/resolve/naoexiste00`) — o código reaparecia em texto puro dentro
do próprio campo `path`, derrotando o hash. Corrigido com
`_redact_code_from_path()`, que substitui o segmento do código por
`{code}` antes de logar qualquer coisa. Achado pelo teste
`test_rajada_de_404_registra_evento_de_auditoria` (falhou antes do fix,
passou depois) — exatamente o tipo de bug que a AC5/subtask 4.3 previa
como risco.

**Verificado ao vivo** contra o processo real (`:21390`): `/health` com
`Origin: http://localhost:3000` retornou o header CORS exato; origem hostil
não recebeu seu próprio header ecoado; rajada de 30 requisições a códigos
inexistentes resultou em 21×404 + 9×429 (bloqueio de rajada disparado
exatamente após o threshold de 20); `public_audit.log` real conferido
linha a linha — `path` redigido (`/api/v1/resolve/{code}`), `code_hash` de
12 hex chars, evento `enumeracao_detectada` presente com `contagem_404: 21`.
Log de teste removido ao final (345 linhas, só ruído de teste).

**Escolha de formato do log (subtask 4.1):** JSONL append-only
(`public_audit.log`), não `public_audit.db` — mais simples pro MVP, sem
custo de manter outro schema SQLite; reavaliar se volume justificar rotação
de log formal.
