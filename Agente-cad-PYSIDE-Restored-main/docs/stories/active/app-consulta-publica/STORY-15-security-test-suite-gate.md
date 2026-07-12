# Story (Gate): Suíte de Testes de Segurança — Gate Obrigatório de Release

**Epic:** Transversal a todos os Epics (fundação de segurança do Epic 1, executada como gate final)
**Priority:** P0 — **NÃO-NEGOCIÁVEL** (único gate inegociável de release, conforme architecture.md §5.4 e prd.md §10)
**Status:** ✅ Done — **GATE AUTOMATIZADO: GO** (AC1-10, 2026-07-12) — AC11 pendente (gate manual, não bloqueante para merge)
**Estimated Effort:** G (grande)

```yaml
executor: "@dev"
quality_gate: "@qa"
quality_gate_tools: ["pytest", "coderabbit", "load-test script", "manual pentest checklist"]
```

---

## Story

**As a** responsável pela segurança e confiabilidade do produto,
**I want** uma suíte de testes de integração que comprove, de forma automatizada e repetível, que é impossível vazar dados cross-cliente, enumerar códigos, ou escrever através da API pública,
**so that** o MVP só seja liberado para produção com a garantia formal de "zero incidentes de vazamento cross-cliente" (KPI de tolerância zero do PRD).

---

## Context

A Architecture e o PRD são explícitos: **esta suíte é o único gate inegociável de release do MVP.** Todos os endpoints construídos nas stories 01-07 e 12 devem passar por esta bateria de testes de integração antes de qualquer deploy em produção. Esta story **não implementa funcionalidade nova** — ela consolida, formaliza e expande os testes de segurança já escritos individualmente em cada story anterior (STORY-01 AC2, STORY-02 AC3-5, STORY-03 AC3/7, STORY-04 todos, STORY-06 AC6, STORY-07 AC4, STORY-12 AC3/4) numa suíte única, executável em CI, com relatório de gate GO/NO-GO.

[Source: architecture.md §5.4 "Suíte de segurança obrigatória (gate de release — PRD §7/§10)"]
[Source: architecture.md §11 "Resumo das decisões inegociáveis (checklist de gate)"]
[Source: prd.md §7 "Testing Requirements... suíte de segurança obrigatória do gate de release"]
[Source: prd.md §10 "A recomendação de go/no-go do MVP fica condicionada à suíte de segurança verde"]
[Source: prd.md §8.2 KPI "Vazamento cross-cliente — Incidentes de acesso a obra de outro cliente — 0 (tolerância zero)"]

---

## Acceptance Criteria

1. **Given** qualquer rota da API pública (`/resolve`, `/ficha`, `/svg`, `/obra`, `/paineis-lv`, `/health`), **when** uma requisição `POST`, `PUT`, `DELETE` ou `PATCH` é enviada, **then** retorna `405 Method Not Allowed` em **100%** das rotas — nenhuma exceção.

2. **Given** uma simulação de enumeração sequencial (1000 códigos aleatórios base62 de 10 caracteres, não correspondentes a nenhum código real publicado), **when** enviados a `/resolve/{code}`, **then** **100%** retornam `404` idêntico, o rate-limit dispara conforme esperado (STORY-04), e **zero** informação é vazada (nenhuma resposta 200/500 inesperada).

3. **Given** duas obras publicadas distintas (Obra A, Obra B, com clientes/dados diferentes simulados em fixture de teste), **when** o código de obra/item de A é usado em qualquer combinação de manipulação de query string, header, ou path junto com dados de B, **then** o código de A **nunca** resolve para dado de B, e vice-versa — testado exaustivamente para `/resolve`, `/ficha`, `/obra`, `/svg`, `/paineis-lv`.

4. **Given** um `code` malformado contendo sequências de path traversal (`../`, `%2e%2e%2f`, URL-encoded, null bytes), **when** enviado a qualquer endpoint que resolva path de arquivo (`/svg/{nivel}`, `/paineis-lv`), **then** retorna `404` genérico e **nunca** lê um arquivo fora de `DADOS_OBRAS_ROOT` (comprovado por teste que tenta ler um arquivo sabidamente fora da árvore, ex. `/etc/passwd` ou equivalente Windows, e confirma falha).

5. **Given** a resposta de qualquer endpoint público, **when** seu JSON é comparado contra a blacklist de campos (`cliente`, `criterios_cliente`, `data_solicitacao`, `data_entrega`, `observacoes`, `membro_id`, `login`, `nome`, `email`, `senha_hash`, `descricao`), **then** **nenhum** desses campos aparece em nenhuma resposta, em nenhum endpoint — teste de asserção de schema exaustivo.

6. **Given** o módulo de conexão a `public_consulta.db`, **when** uma tentativa programática de `INSERT`/`UPDATE`/`DELETE` é feita através da conexão usada pela API pública, **then** falha com `OperationalError` (comprova que o DB está de fato aberto `mode=ro`, não apenas "por convenção de código").

7. **Given** o código-fonte completo de `consulta-publica-api/**`, **when** auditado por scan estático, **then** **nenhum** import de `portal.app.auth`, `portal.app.access`, `portal.app.repository`, `portal.db.connection`, `src.core.lv_generation_contract` (ou equivalente PySide6) existe em qualquer arquivo.

8. **Given** um item/obra revogado (`revoked=1`) via Publisher (STORY-01), **when** consultado em qualquer endpoint, **then** retorna `404` genérico idêntico a "nunca existiu" — nenhuma diferença de comportamento observável entre "revogado" e "nunca existiu".

9. **Given** a suíte completa, **when** executada em CI, **then** produz um relatório único de gate com veredicto **GO** (todos os testes acima verdes) ou **NO-GO** (qualquer falha) — este relatório é o critério formal de "suíte de segurança verde" exigido antes de qualquer deploy em produção (PRD §10).

10. **Given** o CORS configurado (STORY-04), **when** uma requisição de origem não autorizada tenta acessar qualquer endpoint, **then** o header `Access-Control-Allow-Origin` não corresponde à origem da requisição (bloqueio efetivo).

11. **Given** o teste de usabilidade de campo (gate manual, não automatizado — NFR10), **when** executado com ≥5 usuários reais (funcionário de fôrma + construtor) em ≥3 obras distintas, **then** ≥4 de 5 completam a consulta N1/N3 (+ painéis LV quando aplicável) na primeira tentativa, sem treinamento formal, em <5s em 4G — **este item é um gate manual separado**, coordenado por @po/@ux, não bloqueante para o merge desta story, mas bloqueante para o **lançamento** do MVP (MVP Success Criteria, PRD §4.3).

---

## Dependencies

- **Requires:** STORY-01, STORY-02, STORY-03, STORY-04, STORY-05, STORY-06, STORY-07, STORY-12 (todos os endpoints e camadas de segurança precisam existir para serem testados de ponta a ponta).
- **Blocks:** Nenhuma story de desenvolvimento — bloqueia **apenas o release/deploy em produção** do MVP. É o último passo antes do go/no-go.

---

## Tasks / Subtasks

- [ ] Task 1 — Consolidar suíte de testes existentes (AC: todos)
  - [ ] Subtask 1.1: Reunir os testes já escritos individualmente em cada story (01-07, 12) num diretório único `consulta-publica-api/tests/security_suite/`
  - [ ] Subtask 1.2: Eliminar duplicação, garantir cobertura cruzada (ex.: teste de path traversal cobre tanto `/svg` quanto `/paineis-lv`)
- [ ] Task 2 — Implementar testes novos de cross-obra exaustivos (AC: 3)
  - [ ] Subtask 2.1: Fixture com 2+ obras publicadas via Publisher de teste, dados propositalmente diferentes
  - [ ] Subtask 2.2: Matriz de combinações (code de A + tentativa de acessar recurso de B em cada endpoint)
- [ ] Task 3 — Implementar simulação de enumeração em escala (AC: 2)
  - [ ] Subtask 3.1: Gerador de 1000 códigos aleatórios não-existentes
  - [ ] Subtask 3.2: Assert de 100% 404 + verificação de disparo de rate-limit
- [ ] Task 4 — Implementar testes de path traversal exaustivos (AC: 4)
  - [ ] Subtask 4.1: Payloads de traversal conhecidos (raw, URL-encoded, null byte, unicode)
- [ ] Task 5 — Teste de blacklist de schema (AC: 5)
  - [ ] Subtask 5.1: Script genérico que varre a resposta JSON de cada endpoint contra a lista de campos proibidos
- [ ] Task 6 — Teste de read-only físico e isolamento de import (AC: 6, 7)
  - [ ] Subtask 6.1: Reuso/expansão dos testes da STORY-02
- [ ] Task 7 — Teste de revogação (AC: 8)
  - [ ] Subtask 7.1: Publicar → revogar → confirmar 404 idêntico
- [ ] Task 8 — Relatório de gate (AC: 9)
  - [ ] Subtask 8.1: Script/job de CI que agrega resultados e produz veredito GO/NO-GO
  - [ ] Subtask 8.2: Documentar o relatório em `docs/qa/` (conforme `qaLocation` do core-config do framework AIOS, ou local equivalente deste projeto)
- [ ] Task 9 — Coordenar gate manual de usabilidade (AC: 11)
  - [ ] Subtask 9.1: Notificar @po/@ux para agendar teste de campo com ≥5 usuários/≥3 obras (não implementável em código, é um checkpoint humano)

---

## Dev Notes

### Files/Components Expected

- `consulta-publica-api/tests/security_suite/test_no_write_verbs.py`
- `consulta-publica-api/tests/security_suite/test_enumeration_1000.py`
- `consulta-publica-api/tests/security_suite/test_cross_obra_isolation.py`
- `consulta-publica-api/tests/security_suite/test_path_traversal.py`
- `consulta-publica-api/tests/security_suite/test_schema_blacklist.py`
- `consulta-publica-api/tests/security_suite/test_ro_db_and_imports.py`
- `consulta-publica-api/tests/security_suite/test_revocation.py`
- `consulta-publica-api/tests/security_suite/conftest.py` (fixtures compartilhadas: 2+ obras publicadas, códigos revogados)
- `docs/qa/app-consulta-publica-security-gate-report.md` (relatório de gate, gerado/atualizado a cada execução)

### Technical Notes

- **Lista exata de testes exigidos pela Architecture** (não inventar critérios adicionais nem remover nenhum destes): [Source: architecture.md §5.4]
  > - Tentativa de `POST/PUT/DELETE` em qualquer rota → 405
  > - Enumeração sequencial simulada (1000 códigos aleatórios) → 100% 404, rate-limit dispara, zero vazamento
  > - Código de obra A nunca resolve item de obra B
  > - Path traversal via `code` (`../`, encoded) → 404, nunca lê fora de `DADOS-OBRAS`
  > - Resposta pública não contém nenhum campo da blacklist — asserção de schema
  > - DB aberto `mode=ro`: tentativa de escrita programática → `OperationalError`
- **Checklist de gate inegociável** (11 itens, todos verificáveis nesta story exceto o último que é gate manual): [Source: architecture.md §11]
- **Avaliação estratégica do PM:** "o risco dominante desta iniciativa não é de produto, é de segurança... A recomendação de go/no-go do MVP fica condicionada à suíte de segurança verde (zero vazamento cross-cliente demonstrado) — este é o único gate inegociável." [Source: prd.md §10]
- **KPI de tolerância zero:** "Vazamento cross-cliente — Incidentes de acesso a obra de outro cliente — 0 (tolerância zero)." [Source: prd.md §8.2]
- **Gate manual separado (AC11) não é testável em CI** — é responsabilidade de @po/@ux coordenar, mas está documentado aqui porque é parte do "MVP Success Criteria" formal do PRD §4.3, e a story não deve ser considerada "MVP pronto para lançar" sem ele, mesmo que o gate automatizado (AC1-10) esteja 100% verde.

---

## Testing

- **Test file location:** `consulta-publica-api/tests/security_suite/`
- **Framework:** pytest, executado em CI a cada PR que toca `consulta-publica-api/**`
- **Test scenarios obrigatórios:** todos os 10 primeiros ACs desta story (o AC11 é gate manual, não parte da suíte automatizada)
- **Special considerations:**
  - Esta suíte deve rodar **antes de qualquer merge para a branch de release/produção** — não é opcional, não é "nice to have", é o gate de segurança formal do produto.
  - Recomenda-se que @qa (não apenas @dev) faça a revisão final desta suíte antes do primeiro deploy em produção, dado o modo `full` de self-healing (3 iterações, 30 min, CRITICAL+HIGH) ser mais apropriado que o modo `light` de @dev para uma story deste nível de criticidade.

---

## 🤖 CodeRabbit Integration

**Story Type Analysis**
- **Primary Type:** Security
- **Secondary Type(s):** Integration (suíte de testes ponta-a-ponta cobrindo múltiplos endpoints), Architecture (valida decisões estruturais de isolamento)
- **Complexity:** High — é o gate mais crítico do projeto; consolida e formaliza segurança de todas as stories anteriores

**Specialized Agent Assignment**
- **Primary Agents:**
  - @dev (implementação da suíte)
  - @qa (revisão final e veredito de gate)
  - @architect (validação de que os testes cobrem corretamente as decisões estruturais do §2/§5)
- **Supporting Agents:** @github-devops (integração da suíte no pipeline de CI/CD como gate bloqueante de deploy)

**Quality Gate Tasks**
- [ ] Pre-Commit (@dev): Run `coderabbit --prompt-only -t uncommitted`
- [ ] Pre-PR (@github-devops): Run `coderabbit --prompt-only --base main`
- [ ] Pre-Deployment (@github-devops): Run scan completo de segurança (SAST) + confirmação do relatório GO/NO-GO desta suíte como condição de deploy

**CodeRabbit Focus Areas**
- **Primary Focus:**
  - OWASP Top 10: Broken Access Control (A01), IDOR/BOLA, injection, path traversal
  - Timing attacks: constant-time em todos os caminhos de erro testados
  - Data protection: nenhum campo comercial/pessoal vazado em nenhuma resposta
- **Secondary Focus:**
  - Cobertura de teste: todos os endpoints das stories 01-07/12 representados na suíte
  - Qualidade do relatório de gate (claro, acionável, versionado)

**Self-Healing Configuration**
- **Expected Self-Healing:**
  - Primary Agent: @qa (full mode)
  - Max Iterations: 3
  - Timeout: 30 minutes
  - Severity Filter: CRITICAL, HIGH
- **Predicted Behavior:**
  - CRITICAL issues (qualquer vazamento cross-cliente, path traversal explorável, verbo de escrita aceito): auto_fix (até 3 iterações) — **nenhum CRITICAL pode ser aceito como débito técnico nesta story**
  - HIGH issues (cobertura de teste incompleta, relatório de gate malformado): auto_fix

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-07-11 | 0.1 | Story criada a partir de architecture.md §5.4/§11 e prd.md §7/§8.2/§10 — gate final consolidado, cobrindo a área "Testes: suíte de segurança" do escopo do masterplan | River (SM) |
| 2026-07-12 | 1.0 | Suíte implementada e executada — veredicto GO (AC1-10) — ver Dev Agent Record e `docs/qa/app-consulta-publica-security-gate-report.md` | Claude (dev) |

---

## Dev Agent Record

**Arquivos criados:**
- `consulta-publica-api/tests/security_suite/conftest.py` — fixture `duas_obras` (2 obras sintéticas, dados propositalmente diferentes/distinguíveis: pilar com N1/N3, viga_lateral com contrato LV materializado, 1 item revogado) + helper `requisitar()` compartilhado (httpx.ASGITransport)
- `test_no_write_verbs.py` (AC1, 2 testes — 6 rotas reais × 4 verbos = 24 combinações)
- `test_enumeration_1000.py` (AC2, 1 teste — 1000 códigos, app único compartilhado para o rate-limit acumular estado de verdade)
- `test_cross_obra_isolation.py` (AC3, 6 testes — `/resolve`, `/ficha`, `/svg`, `/obra`, `/paineis-lv`)
- `test_path_traversal.py` (AC4, 4 testes — obra_dir fabricado fora da raiz para svg E paineis-lv, payloads clássicos de traversal)
- `test_schema_blacklist.py` (AC5, 6 testes — varredura recursiva de todo JSON de resposta)
- `test_ro_db_and_imports.py` (AC6/AC7/AC10, 3 testes)
- `test_revocation.py` (AC8, 5 testes)
- `docs/qa/app-consulta-publica-security-gate-report.md` (AC9 — relatório de gate)

**Testes:** 94/94 passando em `consulta-publica-api` inteiro (27 novos da
suíte de segurança + 67 pré-existentes das STORY-01–14, todos reexecutados
sem regressão).

**Decisão de kickoff — fixture sintética de 2 obras, não republicação da
obra real:** ao contrário das stories anteriores (que às vezes reusaram a
obra real republicada para smoke test ao vivo), a suíte de segurança
precisa de **2 obras com dados propositalmente diferentes e
distinguíveis** para provar isolamento cross-obra de forma determinística
— a obra real de teste (`Obra-Teste-Inicial`) é uma só, não serviria para
provar "nunca vaza de A pra B". `conftest.py::duas_obras` monta 2 obras
completas (pilar N1/N3 + viga_lateral com LV real) com títulos/rótulos
únicos ("Cliente Confidencial X"/"Y") justamente para que qualquer
vazamento apareça como uma string literal detectável no teste.

**1 ajuste de fixture necessário (não bug de produção):** a 1ª versão
tentou inserir o item "revogado" reaproveitando a mesma identidade
`(obra_id, pavimento, classe, item_id)` do pilar ativo da obra A — violou
o índice único `idx_public_codes_item_identity` do schema real
(`publisher/schema.sql`). Corrigido dando ao item revogado uma identidade
própria; achei este comportamento correto do schema, não um bug: a
revogação real (`publisher.publish.revogar`) sempre faz `UPDATE` na MESMA
linha, nunca cria uma duplicata com a mesma identidade.

**AC10 (CORS) não tinha arquivo próprio nos Dev Notes originais** — a
story já tinha AC10 no texto mas o file-list de Task/Dev Notes não previa
um arquivo dedicado; agrupei no mesmo arquivo de AC6/AC7
(`test_ro_db_and_imports.py`) por serem todos testes de "propriedade
estrutural do processo" (DB read-only, imports proibidos, CORS) — decisão
de organização, não desvio de cobertura (AC10 tem seu próprio teste,
`test_cors_bloqueia_origem_nao_autorizada_em_endpoint_real_com_dado`,
reconfirmando contra um endpoint REAL com dado, não só `/health` como a
STORY-04 original testava).

**Verificado ao vivo** contra o processo real (`:21390`): `POST /health` e
`POST /resolve/x` retornaram 405 (AC1 confirmado fora do ambiente de
teste), requisição com `Origin: http://evil.example.com` não recebeu
nenhum header `Access-Control-Allow-Origin` na resposta (AC10 confirmado
ao vivo).

**AC11 (gate manual de usabilidade de campo) permanece PENDENTE** — não é
implementável em código; documentado explicitamente no relatório de gate
como bloqueante apenas do LANÇAMENTO do MVP, não deste merge, conforme a
própria story especifica. Recomendação registrada para @po/@ux coordenar.

**Veredicto formal:** ✅ **GO** para os 10 critérios automatizáveis —
ver `docs/qa/app-consulta-publica-security-gate-report.md` para o
relatório completo por AC.
