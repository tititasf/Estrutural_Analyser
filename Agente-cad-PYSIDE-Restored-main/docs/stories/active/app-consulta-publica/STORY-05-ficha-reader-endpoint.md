# Story 2.1: `ficha_reader` compartilhado + Endpoint `GET /api/v1/ficha/{code}`

**Epic:** Epic 2 — Ficha do Item (N1/N3)
**Priority:** P0
**Status:** ✅ Done (implementado e testado ao vivo em 2026-07-12)
**Estimated Effort:** M (médio)

```yaml
executor: "@dev"
quality_gate: "@architect"
quality_gate_tools: ["pytest", "coderabbit"]
```

---

## Story

**As a** funcionário de fôrma consultando um item pelo código,
**I want** receber a ficha completa (identificação, campos N1, URLs de SVG, flag de painéis LV) numa única resposta JSON leve,
**so that** eu veja rapidamente a especificação do item sem baixar SVGs pesados antes de precisar deles.

---

## Context

O portal interno já produz `foto_n1`/`foto_n3` como string SVG embutida via `ficha_reader.py` (`ler_estado_pavimento`, `listar_itens_n1`, `obter_item_n1`, `extrair_fotos_ficha`). A Architecture decidiu **reusar essa lógica de leitura**, mas **sem** as dependências de `auth`/`access`/`repository`, e **desacoplar o SVG do JSON** (o JSON só carrega URLs, o SVG vem por endpoint próprio — STORY-06) para manter o payload leve em 3G.

[Source: architecture.md §4.1 "Reuso máximo (não recomputar o que já existe)"]
[Source: architecture.md §4.2 "Projeção mínima — exemplo de resposta `/api/v1/ficha/{code}`"]
[Source: prd.md FR2, FR3]

---

## Acceptance Criteria

1. **Given** um `code` válido de `kind='item'` (resolvido via lógica da STORY-03), **when** `GET /api/v1/ficha/{code}`, **then** retorna `200` com o JSON exato:
   ```jsonc
   {
     "code": "aF3kZ9xQ2m",
     "tipo": "pilar",
     "titulo": "Pilar P1",
     "obra_rotulo": "Obra ·· A3F",
     "pavimento_label": "Pavimento Tipo",
     "campos": { "Classificação": "...", "Nível Relativo": "...", "Lado A": "..." },
     "atencao": "",
     "svg": { "n1": "/api/v1/ficha/aF3kZ9xQ2m/svg/n1", "n3": "/api/v1/ficha/aF3kZ9xQ2m/svg/n3" },
     "tem_lv": true
   }
   ```
   — o SVG **nunca** é embutido cru no JSON, apenas as URLs (arquitetura §4.2).

2. **Given** um item sem N3 gerado (`svg.n3` ausente na fonte), **when** consultado, **then** `svg.n3` é `null` no JSON — o frontend (STORY-10) decide não renderizar a aba N3.

3. **Given** um `code` de `kind='obra'` (não item), **when** enviado a `/ficha/{code}`, **then** retorna o mesmo `404 {"erro":"nao_encontrado"}` genérico (este endpoint só serve itens — fora de escopo é tratado como não encontrado, não como erro 400 diferenciado, para não vazar informação de tipo).

4. **Given** o módulo de leitura de fichas (`ficha_reader.py` extraído/compartilhado), **when** usado pela API pública, **then** **não** importa `auth.py`, `access.py`, ou `repository.py` do portal — apenas lógica pura de leitura de `estado_<pav>.json` e parsing de fichas HTML.

5. **Given** o campo `tem_lv`, **when** calculado, **then** reflete se existe um arquivo JSON correspondente em `Fase-4_Sincronizacao/JSON_Vigas_Laterais/{LV-PARA,LV-PASSA}/{beam}_{A,B}.json` para o item — **sem** importar `lv_generation_contract.py` nem executar nenhum motor (apenas checagem de existência de arquivo, a leitura completa é a STORY-12).

6. **Given** o `obra_rotulo` e `pavimento_label`, **when** retornados, **then** vêm exclusivamente da projeção já denormalizada em `public_codes` (STORY-01) — nunca derivados on-the-fly de `portal_obras`/strings internas (`"13_PAV"` nunca aparece cru).

7. **Given** a resposta deste endpoint, **when** auditada contra a blacklist de campos comerciais/pessoais (`cliente`, `membro_id`, `senha_hash`, etc.), **then** nenhum desses campos aparece — testável por assertion de schema (mesmo princípio da STORY-01 AC2, agora aplicado à resposta HTTP).

---

## Dependencies

- **Requires:** STORY-01 (schema/projeção), STORY-02 (skeleton API), STORY-03 (padrão de resolução/404 genérico reutilizado).
- **Blocks:** STORY-06 (endpoint de SVG referenciado pelas URLs desta resposta), STORY-10 (frontend consome este endpoint), STORY-12 (`/paineis-lv` reusa o mesmo padrão de resolução de item).

---

## Tasks / Subtasks

- [ ] Task 1 — Extrair/adaptar `ficha_reader.py` para módulo compartilhado (AC: 4)
  - [ ] Subtask 1.1: Avaliar com @dev/@architect se a extração para `src/shared/ficha_reader.py` é viável no prazo do MVP
  - [ ] Subtask 1.2: **Escape hatch aceito:** se custoso, copiar a lógica de leitura para `consulta-publica-api/services/ficha_reader.py` **com teste de paridade** contra o original do portal — documentar como débito técnico explícito no Dev Agent Record
  - [ ] Subtask 1.3: Garantir zero import de `auth`/`access`/`repository`
- [ ] Task 2 — Implementar endpoint `/ficha/{code}` (AC: 1, 2, 3, 6)
  - [ ] Subtask 2.1: Resolver `code` (reuso do serviço da STORY-03) → obter `obra_dir/pav/classe/item_id` pré-resolvidos
  - [ ] Subtask 2.2: Montar resposta com `campos{}`, `atencao`, `titulo`, `obra_rotulo`, `pavimento_label`
  - [ ] Subtask 2.3: Montar `svg.n1`/`svg.n3` como URLs (não conteúdo)
- [ ] Task 3 — Calcular `tem_lv` (AC: 5)
  - [ ] Subtask 3.1: Checagem de existência de arquivo (sem leitura/parse completo — isso é STORY-12)
- [ ] Task 4 — Testes (AC: todos)
  - [ ] Subtask 4.1: Teste de resposta completa para item com N1+N3+LV
  - [ ] Subtask 4.2: Teste de `svg.n3 = null` quando ausente
  - [ ] Subtask 4.3: Teste de 404 genérico para código de obra
  - [ ] Subtask 4.4: Teste de paridade (se copiado) entre `ficha_reader` original e a cópia
  - [ ] Subtask 4.5: Teste de blacklist de schema na resposta

---

## Dev Notes

### Files/Components Expected

- `src/shared/ficha_reader.py` (alvo ideal — módulo compartilhado) **ou** `consulta-publica-api/services/ficha_reader.py` (escape hatch com teste de paridade)
- `consulta-publica-api/routers/ficha_routes.py`
- `consulta-publica-api/services/ficha_service.py`
- `consulta-publica-api/tests/test_ficha_endpoint.py`
- `consulta-publica-api/tests/test_ficha_reader_paridade.py` (se escape hatch usado)

### Technical Notes

- **Contrato de resposta exato** (não inventar campos): [Source: architecture.md §4.2, exemplo JSON completo reproduzido no AC1]
- **Decisão de extração vs cópia:** "extrair `ficha_reader.py` para um módulo compartilhado `src/shared/ficha_reader.py`... importado pelas duas apps, em vez de copiar... Se a extração for custosa no MVP, aceitável copiar com teste de paridade (escape hatch)." [Source: architecture.md §4.1 `[AUTO-DECISION]`, também architecture.md §10 A4]
- **Funções reaproveitáveis do portal:** `ler_estado_pavimento`, `listar_itens_n1`, `obter_item_n1`, `extrair_fotos_ficha` (de `portal/app/ficha_reader.py`). [Source: architecture.md §1 item 1, §4.1]
- **SVG desacoplado do JSON** é decisão de performance, não só de organização — evita payload pesado em 3G. [Source: architecture.md §4.2 nota, §6.2]

---

## Testing

- **Test file location:** `consulta-publica-api/tests/test_ficha_endpoint.py`
- **Framework:** pytest + `TestClient`, fixtures de `public_codes` populadas via Publisher de teste (reusar fixtures da STORY-01)
- **Test scenarios obrigatórios:**
  - Resposta completa contra o contrato JSON exato do AC1
  - `svg.n3 = null` quando arquivo ausente
  - 404 genérico para `kind='obra'`
  - Blacklist de campos comerciais ausente na resposta
  - (se escape hatch usado) paridade campo-a-campo com `ficha_reader.py` original em uma amostra de itens reais

---

## 🤖 CodeRabbit Integration

**Story Type Analysis**
- **Primary Type:** API
- **Secondary Type(s):** Architecture (decisão de módulo compartilhado vs cópia)
- **Complexity:** Medium — reuso de lógica existente, mas requer disciplina de isolamento

**Specialized Agent Assignment**
- **Primary Agents:** @dev, @architect (validar decisão de extração vs cópia)
- **Supporting Agents:** —

**Quality Gate Tasks**
- [ ] Pre-Commit (@dev)
- [ ] Pre-PR (@github-devops)
- [ ] Pre-Deployment (@github-devops) — endpoint público expõe dado de cliente, requer scan de projeção mínima

**CodeRabbit Focus Areas**
- **Primary Focus:**
  - Error handling e validação de request/response schema (Pydantic)
  - Ausência de campos comerciais/pessoais na resposta (blacklist)
- **Secondary Focus:**
  - Paridade de lógica se `ficha_reader` foi copiado (não divergir do original)
  - Nenhum import de `auth`/`access`/`repository`

**Self-Healing Configuration**
- **Expected Self-Healing:** Primary Agent: @dev (light) · Max Iterations: 2 · Timeout: 15 min · Severity Filter: CRITICAL only
- **Predicted Behavior:** CRITICAL (campo proibido vazando, import proibido): auto_fix. HIGH (divergência de paridade): document_only + revisão manual.

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-07-11 | 0.1 | Story criada a partir de architecture.md §4.1/§4.2 e prd.md FR2/FR3 | River (SM) |
| 2026-07-12 | 1.0 | Implementado e testado ao vivo — ver Dev Agent Record | Claude (dev) |

---

## Dev Agent Record

**Arquivos criados:**
- `consulta-publica-api/services/ficha_service.py` — `encontrar_dir_fichas` (cópia isolada, escape hatch), `pavimento_label`, `tem_lv`, `montar_ficha`
- `consulta-publica-api/routers/ficha_routes.py` — `GET /api/v1/ficha/{code}`
- `consulta-publica-api/tests/test_ficha_endpoint.py` (5 testes)
- `consulta-publica-api/tests/test_ficha_reader_paridade.py` (4 testes)
- `consulta-publica-api/main.py` — wiring do novo router

**Testes:** 43/43 passando no projeto inteiro (`pytest consulta-publica-api`).

**Decisão de kickoff — reuso direto vs escape hatch:** `portal.app.ficha_reader`
foi importado **diretamente** (`from portal.app import ficha_reader`) após
inspeção estática confirmar zero import de `auth`/`access`/`repository`/`db`
nele (só `json, logging, functools, pathlib, typing, math, bs4`) — nenhuma
cópia necessária para essa parte (AC4). Já `encontrar_dir_fichas` mora em
`portal.app.pipeline_runner`, um módulo bem mais pesado (subprocess, imports
lazy de DB) — optei por **copiar** só essa função isolada (escape hatch da
Subtask 1.2) em vez de importar o módulo inteiro ou extrair um novo módulo
compartilhado, para não puxar máquinaria não relacionada ao processo público;
`test_ficha_reader_paridade.py` garante que a cópia nunca diverge do
comportamento do original (4 cenários: múltiplos runs pega o mais recente,
obra sem runs, dir inexistente, dir sem manifest ignorado).

**Bug de teste encontrado e corrigido (não bug de produção):**
`test_ficha_completa_com_n1_n3_lv` originalmente montava um item pilar
(`"P1"`) mas escrevia o arquivo LV fixture como `V101_A.json` (nome de viga
não relacionado) — `tem_lv()` corretamente resolve pelo `beam_name` do
PRÓPRIO item (aqui `"P1"`), então retornava `False` corretamente e o TESTE
estava errado, não o código: semanticamente pilares nunca têm dado LV (é
conceito exclusivo de `viga_lateral`). Corrigido renomeando o fixture para
`P1_A.json`, com comentário explicando que o fixture testa só a mecânica de
checagem de existência de arquivo, não a semântica real pilar/viga.

**Verificado ao vivo** contra o processo real (`:21390`) usando o
`public_consulta.db` real (republicado via `publisher.publish.publicar` para
gerar códigos não-revogados, já que os 433 códigos anteriores estavam todos
`revoked=1` de testes de sessões passadas): `GET /api/v1/ficha/{code de
pilar real}` retornou 200 com `svg.n1` presente, `svg.n3=null` (N3 não
gerado para esse pilar), `tem_lv=false` (correto), `Cache-Control: private,
no-store`; `GET /api/v1/ficha/{code inexistente}` e `GET /api/v1/ficha/{code
de kind='obra'}` retornaram ambos o mesmo 404 genérico
`{"erro":"nao_encontrado"}` (AC3). `pavimento_label` retornou `"13º
Pavimento"` corretamente em UTF-8 (o `º` só aparecia corrompido no print do
terminal Windows/cp1252, não no JSON real — confirmado inspecionando os
bytes crus da resposta). Processo uvicorn encerrado ao final via
`taskkill /F /PID`.
