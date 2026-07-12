# Story 2.3: Endpoint `GET /api/v1/obra/{code}`

**Epic:** Epic 2 — Ficha do Item (N1/N3)
**Priority:** P1
**Status:** ✅ Done (implementado e testado ao vivo em 2026-07-12)
**Estimated Effort:** P (pequeno)

```yaml
executor: "@dev"
quality_gate: "@architect"
quality_gate_tools: ["pytest", "coderabbit"]
```

---

## Story

**As a** usuário que recebeu/digitou um código de **obra** (não de item específico),
**I want** ver a lista de pavimentos e, dentro deles, os itens consultáveis,
**so that** eu consiga navegar até a ficha do item certo mesmo sem saber o código exato daquele item.

---

## Context

Implementa FR5 do PRD ("quando um ID resolver para uma obra, o sistema deve listar os pavimentos e itens"). A resposta nunca expõe `item_id`/`pavimento` crus — apenas o `code` opaco de cada item, seu título e tipo, conforme a Architecture determina.

[Source: prd.md FR5]
[Source: architecture.md §4.1 "Índice de obra: derivado de `descobrir_pavimentos` + `listar_itens_n1`... mapeando cada item ao seu código opaco... a resposta nunca contém `item_id`/`pavimento` crus"]

---

## Acceptance Criteria

1. **Given** um `code` válido de `kind='obra'`, **when** `GET /api/v1/obra/{code}`, **then** retorna `200` com uma estrutura agrupada por pavimento:
   ```jsonc
   {
     "obra_rotulo": "Obra ·· A3F",
     "pavimentos": [
       {
         "pavimento_label": "Térreo",
         "itens": [
           { "code": "xY7...", "titulo": "Pilar P1", "tipo": "pilar" },
           { "code": "aB2...", "titulo": "Viga V301", "tipo": "viga_lateral" }
         ]
       }
     ]
   }
   ```
   — nenhum `item_id`/`pavimento` cru presente, apenas `code`, `titulo`, `tipo` por item, e `pavimento_label` amigável (não a string interna `"13_PAV"`).

2. **Given** um `code` de `kind='item'` (não obra), **when** enviado a `/obra/{code}`, **then** retorna `404` genérico (mesmo padrão de "fora de escopo" das outras stories).

3. **Given** uma obra publicada mas sem itens publicados em um pavimento, **when** consultada, **then** o pavimento aparece com `itens: []` (não é omitido — o frontend, STORY-10, decide como tratar visualmente o vazio).

4. **Given** a lista de itens retornada, **when** comparada aos `public_codes` do mesmo `obra_id`, **then** contém **apenas** códigos com `kind='item'` **e** `revoked=0` pertencentes ao mesmo `obra_id` do código de obra consultado — nunca itens de outra obra (teste de isolamento cross-obra, crítico para NFR5).

5. **Given** este endpoint, **when** medido, **então** usa cache `private, max-age=60` (arquitetura §4 tabela) — dado que pode mudar com republish, mas não precisa ser realtime estrito.

---

## Dependencies

- **Requires:** STORY-01 (schema), STORY-03 (padrão de resolução de `kind`).
- **Blocks:** STORY-10 (Índice de Obra no frontend consome este endpoint).

---

## Tasks / Subtasks

- [ ] Task 1 — Implementar endpoint (AC: 1, 2, 3, 5)
  - [ ] Subtask 1.1: Resolver `code` de obra → `obra_id`
  - [ ] Subtask 1.2: Query `SELECT * FROM public_codes WHERE obra_id=? AND kind='item' AND revoked=0`, agrupar por `pavimento_label`
  - [ ] Subtask 1.3: Cache-Control `private, max-age=60`
- [ ] Task 2 — Isolamento cross-obra (AC: 4)
  - [ ] Subtask 2.1: Teste com 2 obras publicadas, garantir que `/obra/{code_obra_A}` nunca retorna itens de `obra_id` B
- [ ] Task 3 — Testes (AC: todos)
  - [ ] Subtask 3.1: Teste de estrutura de resposta completa
  - [ ] Subtask 3.2: Teste de 404 para código de item
  - [ ] Subtask 3.3: Teste de pavimento vazio
  - [ ] Subtask 3.4: Teste de isolamento cross-obra (2 obras, códigos não vazam entre si)

---

## Dev Notes

### Files/Components Expected

- `consulta-publica-api/routers/obra_routes.py`
- `consulta-publica-api/services/obra_service.py`
- `consulta-publica-api/tests/test_obra_endpoint.py`
- `consulta-publica-api/tests/test_obra_cross_isolation.py`

### Technical Notes

- **Cache:** `private, max-age=60` [Source: architecture.md §4 tabela, linha `/api/v1/obra/{code}`]
- **Nunca expor cru:** "a resposta nunca contém `item_id`/`pavimento` crus, só `code` + `titulo` + `tipo`." [Source: architecture.md §4.1]
- Este é o teste de isolamento cross-obra mais direto do MVP — deve ser reaproveitado explicitamente na suíte de segurança da STORY-15 ("Código de obra A nunca resolve item de obra B").

---

## Testing

- **Test file location:** `consulta-publica-api/tests/test_obra_endpoint.py`, `test_obra_cross_isolation.py`
- **Framework:** pytest + `TestClient`, fixtures com 2+ obras publicadas via Publisher de teste
- **Test scenarios obrigatórios:**
  - Estrutura de resposta e agrupamento por pavimento
  - 404 para código de item
  - Pavimento sem itens retorna lista vazia, não erro
  - Isolamento cross-obra comprovado

---

## 🤖 CodeRabbit Integration

**Story Type Analysis**
- **Primary Type:** API
- **Secondary Type(s):** Security (isolamento cross-obra)
- **Complexity:** Low-Medium

**Specialized Agent Assignment**
- **Primary Agents:** @dev
- **Supporting Agents:** @architect (revisão do teste de isolamento cross-obra)

**Quality Gate Tasks**
- [ ] Pre-Commit (@dev)
- [ ] Pre-PR (@github-devops)
- [ ] Pre-Deployment (@github-devops) — endpoint lista dados agregados de obra, requer verificação de isolamento

**CodeRabbit Focus Areas**
- **Primary Focus:**
  - Isolamento cross-obra (query sempre filtrada por `obra_id` do código resolvido)
  - Nenhum campo cru (`item_id`, `pavimento`) na resposta
- **Secondary Focus:**
  - Cache-Control correto

**Self-Healing Configuration**
- **Expected Self-Healing:** Primary Agent: @dev (light) · Max Iterations: 2 · Timeout: 15 min · Severity Filter: CRITICAL only
- **Predicted Behavior:** CRITICAL (vazamento cross-obra): auto_fix. HIGH: document_only.

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-07-11 | 0.1 | Story criada a partir de architecture.md §4/§4.1 e prd.md FR5 | River (SM) |
| 2026-07-12 | 1.0 | Implementado e testado ao vivo — ver Dev Agent Record | Claude (dev) |

---

## Dev Agent Record

**Arquivos criados:**
- `consulta-publica-api/services/obra_service.py` — `montar_indice_obra(conn, row)`
- `consulta-publica-api/routers/obra_routes.py` — `GET /api/v1/obra/{code}`
- `consulta-publica-api/tests/test_obra_endpoint.py` (4 testes)
- `consulta-publica-api/tests/test_obra_cross_isolation.py` (2 testes)
- `consulta-publica-api/main.py` — wiring do novo router

**Testes:** 60/60 passando no projeto inteiro (`pytest consulta-publica-api`).

**Decisão de kickoff — pavimentos vêm do disco, não só de `public_codes`:**
para satisfazer AC3 (pavimento sem itens publicados ainda deve aparecer com
`itens: []`, não ser omitido), a lista de pavimentos é derivada de
`ficha_reader.descobrir_pavimentos(obra_dir)` (mesma fonte real que o
Publisher usa) — não dos valores distintos de `pavimento` já presentes em
`public_codes`, que só refletiria pavimentos com pelo menos 1 item
publicado. Para cada pavimento real, os itens vêm 100% de `public_codes`
(já denormalizado — `code`/`titulo_publico`/`tipo_elemento`), filtrados por
`obra_id` do código resolvido + `kind='item'` + `revoked=0`.

**Isolamento cross-obra (AC4, o teste de segurança mais crítico desta
story):** `test_obra_cross_isolation.py` publica 2 obras distintas
(`obra-a`/`obra-b`) na mesma tabela e confirma que `/obra/{code de A}` nunca
retorna nenhum `code`/`titulo` de itens de B (e vice-versa) — a query já é
sempre filtrada por `obra_id = ?` (nunca por LIKE/prefix ou lógica que possa
vazar). Também testado que itens `revoked=1` nunca aparecem no índice
mesmo pertencendo à obra certa. Marcado para reuso explícito na suíte da
STORY-15, conforme já previsto no Dev Notes original da story.

**Verificado ao vivo** contra `:21390` com a obra real republicada
(`mAOblv8E22`): retornou 2 pavimentos reais (`13º Pavimento` com 64 itens,
`Térreo` com 368 itens — números batem com a obra de teste usada em todas
as stories anteriores), `Cache-Control: private, max-age=60` presente, e
`GET /obra/{code de item}` retornou o 404 genérico esperado (AC2). Os
acentos (`º`, `é`) só aparecem corrompidos no print do terminal
Windows/cp1252 — já confirmado em stories anteriores que o JSON real está
em UTF-8 correto. Processo encerrado ao final via `taskkill /F /PID`.
