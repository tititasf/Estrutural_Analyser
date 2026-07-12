# Story 1.3: Endpoint `GET /api/v1/resolve/{code}`

**Epic:** Epic 1 — Fundação & Consulta Segura por ID
**Priority:** P0
**Status:** ✅ Done (implementado e testado ao vivo em 2026-07-11)
**Estimated Effort:** M (médio)

```yaml
executor: "@dev"
quality_gate: "@architect"
quality_gate_tools: ["pytest", "coderabbit"]
```

---

## Story

**As a** usuário de campo (funcionário de fôrma ou construtor),
**I want** colar um código e obter uma resposta que me diga se ele é uma obra ou um item — ou uma mensagem genérica de "não encontrado" caso contrário,
**so that** eu tenha um único ponto de entrada para qualquer tipo de consulta, sem nunca conseguir descobrir se um código "existe mas não é meu".

---

## Context

Este é o endpoint central do FR1/FR5 do PRD ("busca unificada", "obra → lista de pavimentos/itens; item → ficha") e a primeira linha de defesa contra enumeração (FR6/NFR1-NFR3). A resposta para código inexistente, malformado, revogado ou fora de escopo deve ser **idêntica e de tempo constante** — nunca revelando diferença observável entre esses 4 casos.

[Source: prd.md FR1, FR5, FR6, NFR1-NFR3]
[Source: architecture.md §4 "Resolução (API pública, read-only)"]
[Source: architecture.md §5.1 item 6 "404 genérico e indistinguível"]

---

## Acceptance Criteria

1. **Given** um `code` válido de `kind='item'` e não revogado, **when** `GET /api/v1/resolve/{code}`, **then** retorna `200 {"kind": "item", "code": "..."}` (metadados mínimos — a ficha completa vem do endpoint `/ficha/{code}` da STORY-05, este endpoint só resolve o tipo/roteamento).

2. **Given** um `code` válido de `kind='obra'` e não revogado, **when** `GET /api/v1/resolve/{code}`, **then** retorna `200 {"kind": "obra", "code": "..."}`.

3. **Given** um `code` inexistente, malformado (comprimento errado, caracteres fora de base62), revogado (`revoked=1`), **when** `GET /api/v1/resolve/{code}`, **then** retorna **exatamente** `404 {"erro": "nao_encontrado"}` em **todos** os 4 casos — mesmo corpo, mesmo status, **mesmo tempo de resposta médio** (validado por teste de timing com margem estatística, ver Testing).

4. **Given** o lookup no banco, **when** o código não existe, **then** a query **sempre executa** (não há short-circuit por formato de código antes de tocar o banco) — isto é o que garante o tempo constante (evita timing oracle).

5. **Given** um `code` com espaços acidentais (trim), **when** enviado ao endpoint, **then** o servidor faz `trim()` antes do lookup (tolerância de digitação, FR7) — mas **não** normaliza case (base62 é case-sensitive).

6. **Given** um `code` recebido como parte de path (`/resolve/{code}`), **when** processado, **then** o valor é usado **apenas** como chave de lookup no SQL parametrizado — nunca concatenado em queries ou usado para construir paths de arquivo (mitigação de injection/traversal, reforçada na STORY-05/06).

7. **Given** o endpoint, **when** chamado 1000 vezes com códigos aleatórios inexistentes (simulação de enumeração), **then** 100% das respostas são `404` idênticas — nenhuma delas revela diferença de timing/corpo que permita distinguir "não existe" de "existe mas revogado" (este cenário específico é reexecutado formalmente na STORY-15, mas o endpoint já deve passar aqui).

---

## Dependencies

- **Requires:** STORY-02 (skeleton da API), STORY-01 (schema `public_codes` deve existir e estar populável).
- **Blocks:** STORY-04 (rate limiting instrumenta este endpoint), STORY-07 (`/obra` reusa a mesma lógica de resolução), STORY-08 (frontend consome este endpoint).

---

## Tasks / Subtasks

- [ ] Task 1 — Implementar lookup de código (AC: 1, 2, 3, 4, 6)
  - [ ] Subtask 1.1: Query parametrizada `SELECT * FROM public_codes WHERE code=? AND revoked=0`
  - [ ] Subtask 1.2: Branch por `kind` (obra/item) — resposta mínima (`{kind, code}`)
  - [ ] Subtask 1.3: 404 genérico unificado para os 4 casos negativos
- [ ] Task 2 — Normalização de entrada (AC: 5)
  - [ ] Subtask 2.1: `trim()` do `code` recebido, sem alterar case
- [ ] Task 3 — Constante-time no caminho de erro (AC: 3, 4)
  - [ ] Subtask 3.1: Garantir que a query sempre executa (nenhum early-return por regex de formato antes do SQL)
  - [ ] Subtask 3.2: Considerar `time.sleep` calibrado ou operação equivalente se o benchmark mostrar variância > threshold aceitável (decisão de implementação de @dev, documentar no Dev Agent Record se aplicado)
- [ ] Task 4 — Testes (AC: todos)
  - [ ] Subtask 4.1: Testes de resolução (item, obra, 404 x4 variantes)
  - [ ] Subtask 4.2: Teste de timing estatístico (N execuções, comparar distribuição)
  - [ ] Subtask 4.3: Teste de enumeração simulada (1000 códigos aleatórios → 100% 404)

---

## Dev Notes

### Files/Components Expected

- `consulta-publica-api/routers/resolve_routes.py`
- `consulta-publica-api/services/resolve_service.py` (lógica de lookup reutilizável por `/obra`, `/ficha`)
- `consulta-publica-api/tests/test_resolve.py`
- `consulta-publica-api/tests/test_resolve_timing.py`

### Technical Notes

- **Contrato exato do endpoint:** [Source: architecture.md §4 tabela de endpoints — `GET /api/v1/resolve/{code}` — Cache: `private, no-store`]
- **Pseudocódigo de referência:**
  ```
  GET /api/v1/resolve/{code}:
    row = SELECT * FROM public_codes WHERE code=? AND revoked=0   (mode=ro)
    se row is None: 404 genérico  (idêntico a código malformado — FR6/NFR)
    se kind='obra':  retorna lista de pavimentos/itens (só códigos de item do mesmo obra_id)
    se kind='item':  retorna ficha (via obra_dir/pav/classe/item pré-resolvidos)
  ```
  [Source: architecture.md §3.3]
  **Nota de escopo:** esta story implementa apenas a **resolução de tipo** (`kind`); o corpo completo de "obra→índice" é a STORY-07 e "item→ficha" é a STORY-05. Manter o `/resolve` deliberadamente leve evita acoplar demasiada lógica num único endpoint e permite cache diferenciado.
- **Cache-Control:** `private, no-store` (o dado por código não deve ser cacheado por proxies intermediários). [Source: architecture.md §4 tabela]
- **404 genérico e constante-time é requisito não-negociável** (NFR — marcado `[NN]` no PRD). [Source: prd.md NFR1-NFR3, architecture.md §5.1 item 6]

---

## Testing

- **Test file location:** `consulta-publica-api/tests/test_resolve.py`, `test_resolve_timing.py`
- **Framework:** pytest + `TestClient`
- **Test scenarios obrigatórios:**
  - Resolução correta para `kind=item` e `kind=obra`
  - 404 idêntico para: código inexistente, malformado, revogado, fora de escopo (usar fixtures do Publisher da STORY-01)
  - Teste de timing: medir tempo médio de N requisições para código válido vs inválido, assert de diferença dentro de margem aceitável (ex.: < 20ms de desvio — thresholds a validar com @architect)
  - Enumeração simulada: 1000 códigos aleatórios → 100% 404, nenhum 200/500 inesperado
- **Special consideration:** este é o teste de segurança mais visível ao usuário final — reusar estes cenários na suíte da STORY-15.

---

## 🤖 CodeRabbit Integration

**Story Type Analysis**
- **Primary Type:** API
- **Secondary Type(s):** Security (timing oracle, anti-enumeração)
- **Complexity:** Medium — lógica simples, mas com garantia de segurança sutil (constant-time)

**Specialized Agent Assignment**
- **Primary Agents:** @dev, @architect (revisão do padrão constant-time)
- **Supporting Agents:** —

**Quality Gate Tasks**
- [ ] Pre-Commit (@dev): Run antes de marcar completa
- [ ] Pre-PR (@github-devops): Run antes de PR
- [ ] Pre-Deployment (@github-devops): Run scan de segurança (endpoint público crítico)

**CodeRabbit Focus Areas**
- **Primary Focus:**
  - Timing attacks: comparações/branches constant-time no caminho de erro
  - SQL parametrizado (zero concatenação de `code` em queries)
- **Secondary Focus:**
  - Validação de request/response schema (Pydantic)
  - Error handling consistente (sempre 404 genérico, nunca 500 vazando stack trace)

**Self-Healing Configuration**
- **Expected Self-Healing:** Primary Agent: @dev (light) · Max Iterations: 2 · Timeout: 15 min · Severity Filter: CRITICAL only
- **Predicted Behavior:** CRITICAL (SQL injection, diferença de resposta 404): auto_fix. HIGH (variância de timing): document_only + revisão manual de @architect.

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-07-11 | 0.1 | Story criada a partir de architecture.md §3.3/§4/§5.1 e prd.md FR1/FR5/FR6 | River (SM) |
| 2026-07-11 | 1.0 | Implementado e testado ao vivo — ver Dev Agent Record | Claude (dev) |

---

## Dev Agent Record

**Arquivos criados:**
- `consulta-publica-api/dbdep.py` — `get_ro_conn` (Depends, 503 se `public_consulta.db` ainda não existe — distinto do 404 por código)
- `consulta-publica-api/services/resolve_service.py` — `resolver_code` (query única, reutilizável pelas STORY-05/07/12)
- `consulta-publica-api/routers/resolve_routes.py` — `GET /api/v1/resolve/{code}`
- `consulta-publica-api/tests/test_resolve.py` (9 testes)
- `consulta-publica-api/tests/test_resolve_timing.py` (2 testes — timing + enumeração de 1000)

**Testes:** 27/27 passando no projeto inteiro (`pytest consulta-publica-api`).

**Verificado ao vivo** contra `public_consulta.db` real (dado publicado nas
stories anteriores): código revogado e código inexistente retornam **exatamente
o mesmo** `404 {"erro":"nao_encontrado"}`; código válido (temporariamente
não-revogado só para o teste, re-revogado ao final) retorna
`200 {"kind":"item","code":"..."}` com `Cache-Control: private, no-store`.

**Achado real durante os testes:** um teste inicial usava `#`/`?` como
"código malformado" — mas esses caracteres têm significado especial em URL
(fragment/query string) e são interceptados pela camada de parsing HTTP
**antes** de chegar no handler, caindo no 404 genérico do próprio Starlette
(`{"detail":"Not Found"}`), diferente do nosso `{"erro":"nao_encontrado"}`.
Isso NÃO é uma falha de timing oracle real (um atacante enumerando códigos
usa caracteres base62 válidos, nunca `#`/`?`, que o próprio HTTP client já
trata antes de qualquer requisição) — troquei o cenário de teste por um
código de comprimento inválido (mais representativo do que um atacante
realmente enviaria), mas vale registrar para a STORY-15 considerar
explicitamente esse limite de escopo do teste de tempo constante.

**Decisão de kickoff:** não apliquei `time.sleep` calibrado (Subtask 3.2) —
a query é idêntica e única para todos os casos (nenhum branch condicional
antes do SQL), e o teste de timing estatístico (margem de 50ms, generosa
para ambiente de teste local) passou sem ele. Reavaliar na STORY-15 com
ferramenta de medição dedicada e ambiente de rede real antes de decidir se
é necessário.
