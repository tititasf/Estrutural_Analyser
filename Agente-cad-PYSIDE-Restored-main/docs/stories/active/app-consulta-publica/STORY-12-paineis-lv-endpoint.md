# Story 3.1: Endpoint `GET /api/v1/ficha/{code}/paineis-lv`

**Epic:** Epic 3 — Lista de Painéis LV
**Priority:** P2 (Should — primeira a deslizar sob pressão de prazo, conforme PRD §5.1)
**Status:** ✅ Done (implementado e testado ao vivo em 2026-07-12)
**Estimated Effort:** P (pequeno)

```yaml
executor: "@dev"
quality_gate: "@architect"
quality_gate_tools: ["pytest", "coderabbit"]
```

---

## Story

**As a** funcionário de fôrma montando uma Viga Lateral (LV),
**I want** ver a lista estruturada de painéis (largura, tipo, módulo STOG) do item que estou montando,
**so that** eu monte a fôrma certa de primeira, sem recontar/adivinhar a distribuição de painéis.

---

## Context

**Achado decisivo da Architecture:** o motor SA já materializa o contrato LV em disco durante a Fase-4 — o JSON em `DADOS-OBRAS/{obra}/Fase-4_Sincronizacao/JSON_Vigas_Laterais/{LV-PARA,LV-PASSA}/{beam}_{A,B}.json` contém exatamente o schema de saída de `build_lv_generation_contracts`. Isso **elimina** qualquer necessidade de importar `src/core/lv_generation_contract.py` ou rodar PySide6 — a API pública **só lê o JSON já em disco**.

[Source: architecture.md §1 item 2 "A lista de painéis LV JÁ ESTÁ EM DISCO"]
[Source: architecture.md §4.1 "Painéis LV: ler o JSON já materializado"]
[Source: prd.md FR4]

---

## Acceptance Criteria

1. **Given** um `code` de item com `tem_lv=true` (calculado na STORY-05), **when** `GET /api/v1/ficha/{code}/paineis-lv`, **then** retorna `200` com os campos públicos filtrados do JSON: `panels[].width`, `panels[].height1`, `panels[].height2`, `panels[].panel_type`, `total_width`, `h_section`, agrupados por lado (A/B) quando aplicável.

2. **Given** um item sem JSON de contrato LV materializado (`tem_lv=false` ou arquivo ausente), **when** consultado, **then** retorna `404 {"erro":"nao_encontrado"}` genérico — **nunca inventa** dados de painéis.

3. **Given** o serviço que implementa este endpoint, **when** auditado, **then** **não importa** `src/core/lv_generation_contract.py` nem qualquer módulo do motor PySide6 — apenas `json.load()` do arquivo já persistido.

4. **Given** o path do JSON de painéis, **when** resolvido, **então** é construído a partir do `obra_dir` pré-resolvido em `public_codes` (mesma disciplina anti-path-traversal da STORY-06) — validado contra `DADOS_OBRAS_ROOT`.

5. **Given** a resposta, **when** cacheada, **então** usa `Cache-Control: public, max-age=3600` (arquitetura §4 tabela).

6. **Given** o campo `panel_type` (`cheio`/`recorte`), **when** retornado, **então** reflete exatamente o valor do JSON de origem — sem reinterpretação ou arredondamento adicional além do que já vem persistido.

---

## Dependencies

- **Requires:** STORY-05 (padrão de resolução de item + flag `tem_lv`).
- **Blocks:** STORY-13 (frontend consome este endpoint).

---

## Tasks / Subtasks

- [ ] Task 1 — Implementar leitura do JSON persistido (AC: 1, 3, 6)
  - [ ] Subtask 1.1: Localizar arquivo em `Fase-4_Sincronizacao/JSON_Vigas_Laterais/{LV-PARA,LV-PASSA}/{beam}_{A,B}.json` a partir do `obra_dir`/`item_id` pré-resolvidos
  - [ ] Subtask 1.2: Parsear e filtrar apenas os campos públicos (blacklist de qualquer campo interno não listado no AC1)
  - [ ] Subtask 1.3: Agrupar por lado (A/B) na resposta
- [ ] Task 2 — 404 quando ausente (AC: 2)
  - [ ] Subtask 2.1: Tratamento de `FileNotFoundError` → 404 genérico (nunca 500)
- [ ] Task 3 — Anti-path-traversal (AC: 4)
  - [ ] Subtask 3.1: Reuso da validação `is_relative_to(DADOS_OBRAS_ROOT)` da STORY-06
- [ ] Task 4 — Cache (AC: 5)
  - [ ] Subtask 4.1: Header `Cache-Control: public, max-age=3600`
- [ ] Task 5 — Testes (AC: todos)
  - [ ] Subtask 5.1: Teste com JSON real de exemplo (fixture baseada em `V301_A.json` citado na Architecture)
  - [ ] Subtask 5.2: Teste de 404 para item sem contrato LV
  - [ ] Subtask 5.3: Teste estático de ausência de import de `lv_generation_contract.py`/PySide6

---

## Dev Notes

### Files/Components Expected

- `consulta-publica-api/routers/paineis_lv_routes.py`
- `consulta-publica-api/services/paineis_lv_service.py`
- `consulta-publica-api/tests/test_paineis_lv_endpoint.py`
- `consulta-publica-api/tests/fixtures/lv_sample.json` (baseado no schema real observado)

### Technical Notes

- **Achado verificado em código real** (não suposição): "Verificado: `DADOS-OBRAS/{obra}/Fase-4_Sincronizacao/JSON_Vigas_Laterais/LV-PARA/V301_A.json` contém exatamente o schema de saída de `build_lv_generation_contracts` (`panels`, `total_width`, `h_section`, `structural_segments`, ...)." [Source: architecture.md §1 item 2]
- **Zero acoplamento com PySide6/motor SA** é requisito explícito, não boa prática opcional: "Heurística 'zero coupling, max modularity' satisfeita." [Source: architecture.md §8]
- **Campos exatos citados na Architecture:** `panels[].width/height1/height2/panel_type`, `total_width`, `h_section`. [Source: architecture.md §4.1]
- **Cache:** `public, max-age=3600`. [Source: architecture.md §4 tabela]
- **Generalização futura (nota, não implementar agora):** "Arquitetura do `/paineis-lv` é generalizável para `/materiais/{classe}` quando o dado a montante existir (mesmo padrão: ler JSON persistido)" — apenas registro de intenção F2, fora do escopo desta story. [Source: architecture.md §10 A5]

---

## Testing

- **Test file location:** `consulta-publica-api/tests/test_paineis_lv_endpoint.py`
- **Framework:** pytest + `TestClient`
- **Test scenarios obrigatórios:**
  - Resposta correta com fixture real de JSON LV (campos e agrupamento por lado)
  - 404 quando arquivo ausente
  - Nenhum import de `lv_generation_contract`/PySide6 (scan estático)
  - Path traversal via manipulação de `code` (deve falhar antes de qualquer leitura de arquivo)

---

## 🤖 CodeRabbit Integration

**Story Type Analysis**
- **Primary Type:** API
- **Secondary Type(s):** Architecture (zero acoplamento com motor desktop)
- **Complexity:** Low — leitura de arquivo já existente, sem lógica de negócio nova

**Specialized Agent Assignment**
- **Primary Agents:** @dev
- **Supporting Agents:** @architect (validar zero acoplamento)

**Quality Gate Tasks**
- [ ] Pre-Commit (@dev)
- [ ] Pre-PR (@github-devops)
- [ ] Pre-Deployment: N/A (dado já público via projeção, sem novo vetor de risco além do path traversal já mitigado)

**CodeRabbit Focus Areas**
- **Primary Focus:**
  - Path traversal (mesma disciplina da STORY-06)
  - Ausência de import proibido (`lv_generation_contract.py`, PySide6)
- **Secondary Focus:**
  - Tratamento de erro (arquivo ausente → 404, nunca 500)

**Self-Healing Configuration**
- **Expected Self-Healing:** Primary Agent: @dev (light) · Max Iterations: 2 · Timeout: 15 min · Severity Filter: CRITICAL only
- **Predicted Behavior:** CRITICAL (path traversal, import proibido): auto_fix. HIGH: document_only.

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-07-11 | 0.1 | Story criada a partir de architecture.md §1/§4.1 e prd.md FR4 | River (SM) |
| 2026-07-12 | 1.0 | Implementado e testado ao vivo — ver Dev Agent Record | Claude (dev) |

---

## Dev Agent Record

**Schema real confirmado:** localizei um contrato LV real já materializado
fora de `DADOS-OBRAS` (`sandbox_lv_loop/runs/.../JSON_Vigas_Laterais/V301_A.json`)
e conferi contra `src/core/lv_generation_contract.py::build_lv_generation_contracts`
(linhas ~213-238) — confirma exatamente os campos citados na Architecture
(`total_width`, `total_height`, `h_section`, `panels[].width/height1/height2/panel_type`)
mais vários campos internos (`points`, `contract_id`, `source_key`,
`structural_segment_index`, `grade_h1/h2`) que o endpoint deliberadamente
filtra fora (blacklist implícita — só passa os 4 campos por painel citados
no AC1).

**Decisão de kickoff — agrupamento por lado, não por code do item:** cada
`code` de item `viga_lateral` representa 1 (lado, behavior) específico
(ex.: classe `lateral_a_para` = lado A, behavior Para) — mas o wireframe
§5.4 mostra "LADO A" e "LADO B" juntos na MESMA ficha de Painéis. Então
`obter_paineis_lv` deriva o `behavior` (Para/Passa) da classe do item
resolvido, e lê **ambos** os arquivos `{beam_name}_A.json`/`{beam_name}_B.json`
desse behavior — não só o lado do próprio item. `total_width`/`h_section`
do topo vêm do primeiro lado encontrado (assume-se consistente entre
lados do mesmo beam; não verificado contra um caso real divergente).

**Arquivos criados:**
- `consulta-publica-api/services/paineis_lv_service.py` — `obter_paineis_lv`
- `consulta-publica-api/routers/paineis_lv_routes.py` — `GET /api/v1/ficha/{code}/paineis-lv`
- `consulta-publica-api/tests/test_paineis_lv_endpoint.py` (6 testes, fixture baseada no schema real)
- `consulta-publica-api/tests/test_paineis_lv_isolation.py` (1 teste — scan estático de imports)
- `consulta-publica-api/main.py` — wiring do novo router

**Testes:** 67/67 passando no projeto inteiro (`pytest consulta-publica-api`).

**2 bugs de teste encontrados e corrigidos (não bugs de produção):**
1. Meu fixture de teste usava `"name"` no dict de segmento, mas
   `ficha_reader._normalizar_segmento` deriva `item_id` de `s.get("uid")`
   (não `name`) — sem `uid`, `item_id` virava `None` e nunca batia com o
   `item_id` registrado em `public_codes`, causando 404 mesmo com o
   contrato LV presente. Corrigido adicionando `"uid"` ao fixture. Achado
   comparando com o mapeamento real de `ficha_reader.py` (a mesma fonte já
   auditada nas STORY-05/06).
2. O teste de isolamento (`test_paineis_lv_isolation.py`) originalmente
   escaneava o CONTEÚDO INTEIRO do arquivo por substring
   `"lv_generation_contract"` — e falhava contra o PRÓPRIO docstring do
   módulo, que MENCIONA esse nome de propósito para explicar por que ele
   não é importado (ironia do teste "provar demais"). Corrigido para
   escanear só linhas que começam com `import`/`from`.

**Verificado ao vivo** contra `:21390` com dados reais (obra republicada):
nenhum item real (pilar nem viga_lateral) desta obra de teste tem contrato
LV materializado em `Fase-4_Sincronizacao/JSON_Vigas_Laterais/`, então o
caminho positivo (200 com painéis reais) só foi validado via fixture de
teste baseada no schema real — mas o caminho negativo foi confirmado ao
vivo: `GET /ficha/{code de viga_lateral real}/paineis-lv` e
`GET /ficha/{code de pilar real}/paineis-lv` ambos retornaram o 404
genérico esperado, e nenhum 500/exceção ocorreu (tratamento de
`FileNotFoundError`/ausência de dado funciona corretamente contra dado
real, não só mock).
