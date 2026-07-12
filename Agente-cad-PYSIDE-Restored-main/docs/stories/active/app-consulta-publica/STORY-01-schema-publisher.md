# Story 1.1: Schema `public_consulta.db` + Publisher (mint/upsert/revoke de códigos opacos)

**Epic:** Epic 1 — Fundação & Consulta Segura por ID
**Priority:** P0 (bloqueante — fundação de tudo)
**Status:** ✅ Done (implementado e testado ao vivo em 2026-07-11)
**Estimated Effort:** G (grande)

```yaml
executor: "@data-engineer"
quality_gate: "@dev"
quality_gate_tools: ["pytest", "sqlite3 schema assertion tests", "coderabbit"]
```

---

## Story

**As a** curador/dono do portal interno do CAD-ANALYZER,
**I want** um processo interno (Publisher) autenticado que projete uma cópia mínima e denormalizada de uma obra publicada para um novo banco `public_consulta.db`, mintando um código opaco por item,
**so that** a app pública só consiga enxergar exatamente o que foi deliberadamente publicado, nunca mais, nunca dado comercial/pessoal, e de forma revogável.

---

## Context

Esta é a **story fundação** de todo o projeto. A defesa primária contra o risco #1 (vazamento cross-cliente / IDOR-BOLA, PRD §10 R1, architecture §2) é tornar o vazamento **fisicamente impossível**: a API pública nunca vai abrir `portal_data.db` nem `project_data.vision` — ela só enxerga `public_consulta.db`, um banco novo, escrito exclusivamente por este Publisher.

[Source: architecture.md §2 "Princípio arquitetural central: Isolamento por Projeção (Publisher/Reader)"]
[Source: architecture.md §3 "Esquema de ID opaco de consulta"]

Achados de código verificados pela Architecture nesta sessão (não são suposições):
- `obra_id` já é UUID (`repository._new_id()` = `uuid.uuid4()`) — não-sequencial.
- `pavimento` (`"TERREO"`, `"13_PAV"`) e `item_id` (`"P1"`, `"V301"`) são strings **adivinháveis** — não podem ser expostas cruas.
- `portal/db/connection.py` já proíbe fisicamente abrir `project_data.vision` — este projeto **estende** essa disciplina.

[Source: architecture.md §1 "Contexto verificado"]

---

## Acceptance Criteria

1. **Given** um `obra_id` existente no portal interno, **when** o dono/curador executa `publicar(obra_id)`, **then** o Publisher cria um `publish_batch` (UUID) e insere em `public_consulta.db`:
   - 1 registro `kind='obra'` para a obra;
   - 1 registro `kind='item'` para cada item elegível, obtido via `listar_itens_n1(estado, classe)` para cada pavimento/classe da obra.
   - Cada registro recebe um `code` **base62(10 caracteres)**, gerado via `secrets.token_bytes(8)` (CSPRNG), **único** (retry em caso de colisão, protegido por `UNIQUE` na PK).

2. **Given** a tabela `public_codes` criada, **when** inspecionado seu schema, **then** ela contém **exatamente** as colunas: `code, kind, obra_id, obra_dir, pavimento, classe, item_id, tipo_elemento, titulo_publico, obra_rotulo, revoked, created_at, publish_batch` — e um teste automatizado de schema comprova que **nenhuma** das colunas de `portal_obras`/`portal_membros` da blacklist (`cliente, criterios_cliente, data_solicitacao, data_entrega, observacoes, membro_id, login, nome, email, senha_hash, descricao`) existe nesta tabela.

3. **Given** uma obra já publicada anteriormente (existe `publish_batch` ativo), **when** o dono executa `publicar(obra_id)` novamente, **then** o Publisher faz **upsert** por `(obra_id, pavimento, classe, item_id)`, **preservando o `code` já existente** para cada item já publicado, e **revoga** (`revoked=1`) o `publish_batch` anterior — nunca gera um novo código para um item já publicado (durabilidade de QR físico F2, architecture A2).

4. **Given** uma obra ou item publicado, **when** o dono executa `revogar(obra_id)` (obra inteira, por `publish_batch`) ou `revogar(code)` (item específico), **then** o(s) registro(s) correspondente(s) recebem `revoked=1` — e a partir desse momento não devem mais resolver (testável junto com STORY-03).

5. **Given** o `obra_rotulo` de uma obra recém-publicada, **when** o dono **não** marca explicitamente um rótulo seguro, **then** o Publisher usa um default anônimo (ex.: `"Obra ·· {4 chars aleatórios base62}"`), **nunca** o campo `nome` cru da obra em `portal_obras` (que pode conter nome do cliente).

6. **Given** o Publisher, **when** invocado, **then** só é acessível **na zona interna e autenticada** — via endpoint novo `POST /admin/publicar/{obra_id}` no portal existente (`:21380`, sob `Depends(auth.exige_login)`) **ou** via CLI (`scripts/publicar_obra.py`) operado localmente pelo dono. **Nunca** exposto na zona pública.

7. **Given** uma tentativa de gerar 2 códigos idênticos (colisão simulada em teste), **when** o Publisher tenta o `INSERT`, **then** a constraint `UNIQUE` da PK rejeita e o Publisher faz retry com novo token — comportamento coberto por teste unitário.

8. **Given** `public_consulta.db`, **when** aberto pela própria API pública (fora do escopo desta story, mas o arquivo deve suportar), **then** o arquivo é abrível em `mode=ro` sem erro — ou seja, o Publisher **não** deixa locks pendentes ou transações abertas após a publicação.

---

## Dependencies

- **Requires:** Nenhuma — story fundação, primeira a ser implementada.
- **Blocks:** STORY-02 (API pública precisa do schema definido aqui), STORY-05 (endpoint `/ficha` resolve via `public_codes`), STORY-07 (`/obra` idem), STORY-12 (`/paineis-lv` idem), STORY-15 (suíte de segurança testa o Publisher/schema).

---

## Tasks / Subtasks

- [ ] Task 1 — Criar schema SQL de `public_consulta.db` (AC: 2)
  - [ ] Subtask 1.1: DDL de `public_codes` conforme architecture §3.2 (incluir `CREATE INDEX idx_public_codes_batch`, `idx_public_codes_obra`)
  - [ ] Subtask 1.2: Script de migração/inicialização (`init_public_consulta_db.py` ou equivalente) idempotente
  - [ ] Subtask 1.3: Teste de schema que falha se qualquer coluna da blacklist aparecer na tabela
- [ ] Task 2 — Implementar geração de código opaco (AC: 1, 7)
  - [ ] Subtask 2.1: Função `gerar_code() -> str` usando `secrets.token_bytes(8)` + encode base62(10)
  - [ ] Subtask 2.2: Retry-on-collision com `UNIQUE` constraint (teste simulando colisão)
- [ ] Task 3 — Implementar `publicar(obra_id)` (AC: 1, 3, 5)
  - [ ] Subtask 3.1: Descobrir pavimentos/itens via `descobrir_pavimentos` + `listar_itens_n1` (reuso de `ficha_reader.py` — mesma fonte da STORY-05)
  - [ ] Subtask 3.2: Lógica de upsert por `(obra_id, pavimento, classe, item_id)` preservando `code`
  - [ ] Subtask 3.3: Geração/preenchimento de `obra_rotulo` default anônimo
  - [ ] Subtask 3.4: Mapear `classe` → `tipo_elemento` (`pilar|laje|viga_lateral|viga_fundo`)
- [ ] Task 4 — Implementar `revogar(obra_id | code)` (AC: 4)
  - [ ] Subtask 4.1: Revogação por `publish_batch` (obra inteira)
  - [ ] Subtask 4.2: Revogação por `code` individual
- [ ] Task 5 — Expor Publisher na zona interna autenticada (AC: 6)
  - [ ] Subtask 5.1: Endpoint `POST /admin/publicar/{obra_id}` no portal (`portal/app/routers/admin_publish_routes.py`), protegido por `auth.exige_login`
  - [ ] Subtask 5.2: OU CLI `scripts/publicar_obra.py` (aceitável como alternativa/MVP se o endpoint HTTP não for prioritário — decisão de @dev no kickoff)
- [ ] Task 6 — Testes unitários e de integração (AC: todos)
  - [ ] Subtask 6.1: `test_schema_no_blacklisted_columns`
  - [ ] Subtask 6.2: `test_publicar_gera_codigos_unicos`
  - [ ] Subtask 6.3: `test_republish_preserva_code`
  - [ ] Subtask 6.4: `test_revogar_obra_inteira` / `test_revogar_item`
  - [ ] Subtask 6.5: `test_db_fecha_sem_lock_pendente`

---

## Dev Notes

### Files/Components Expected (path a confirmar com @architect/@dev no kickoff)

> **Nota de source tree:** não há `source-tree.md` para este projeto nos 4 documentos de planejamento lidos. Proposta abaixo segue a decisão de "processo/serviço novo e isolado" da Architecture (§2, §7).

- `consulta-publica-api/publisher/schema.sql` — DDL de `public_codes` (ou embutido em `db.py`)
- `consulta-publica-api/publisher/publish.py` — `publicar()`, `revogar()`, `gerar_code()`
- `consulta-publica-api/publisher/tests/test_publisher.py`
- `portal/app/routers/admin_publish_routes.py` — endpoint autenticado novo (aditivo, não modifica rotas existentes)
- **OU** `scripts/publicar_obra.py` — CLI alternativa

### Technical Notes

- **Schema exato** (não inventar colunas): [Source: architecture.md §3.2]
  ```sql
  CREATE TABLE public_codes (
      code TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK (kind IN ('obra','item')),
      obra_id TEXT NOT NULL, obra_dir TEXT NOT NULL,
      pavimento TEXT, classe TEXT, item_id TEXT,
      tipo_elemento TEXT, titulo_publico TEXT, obra_rotulo TEXT,
      revoked INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
      publish_batch TEXT
  );
  CREATE INDEX idx_public_codes_batch ON public_codes(publish_batch);
  CREATE INDEX idx_public_codes_obra ON public_codes(obra_id);
  ```
- **Token:** base62 `[0-9A-Za-z]`, 10 chars, CSPRNG (`secrets.token_bytes`), **não** derivado/hash de `obra_id`+item (rejeitado explicitamente — vazaria estrutura offline). [Source: architecture.md §3.1 `[AUTO-DECISION]` "Token table-backed em vez de HMAC stateless"]
- **`obra_dir`** deve ser path absoluto **pré-resolvido** pelo Publisher (nunca construído a partir de input do usuário na API pública — mitigação de path traversal usada pela STORY-05/06). [Source: architecture.md §5.1 item 5]
- **Reuso:** o Publisher deve reaproveitar `descobrir_pavimentos`/`listar_itens_n1` do módulo `ficha_reader.py` existente no portal — mesma fonte de dados que a STORY-05 vai extrair para módulo compartilhado. Coordenar com @dev para não duplicar lógica de leitura de estado.
- **Zero acoplamento desktop:** este Publisher não deve importar `src/core/lv_generation_contract.py` nem nada do PySide6.

---

## Testing

- **Test file location:** `consulta-publica-api/publisher/tests/test_publisher.py`
- **Framework:** pytest (alinhado ao restante do backend Python do portal)
- **Test scenarios obrigatórios:**
  - Schema não contém colunas da blacklist (assert de introspecção `PRAGMA table_info`)
  - Geração de código é única sob colisão simulada (mock de `secrets.token_bytes` retornando o mesmo valor 2x)
  - Republish preserva `code` de itens já publicados e revoga o batch anterior
  - Revogação por obra inteira e por item individual
  - DB fecha sem lock pendente (`sqlite3.connect(..., mode=ro)` funciona logo após publish)
- **Special consideration:** este é o teste mais crítico do MVP em termos de segurança — a suíte completa de segurança (STORY-15) vai depender deste schema estar correto.

---

## 🤖 CodeRabbit Integration

**Story Type Analysis**
- **Primary Type:** Database (schema, migrations)
- **Secondary Type(s):** Security (projeção mínima é requisito de segurança)
- **Complexity:** High — schema novo + lógica de revogação/upsert + é a fundação de segurança de todo o produto

**Specialized Agent Assignment**
- **Primary Agents:**
  - @dev (pre-commit reviews)
  - @data-engineer (schema e SQL review)
- **Supporting Agents:**
  - @architect (validação do isolamento Publisher/Reader)

**Quality Gate Tasks**
- [ ] Pre-Commit (@dev): Run `coderabbit --prompt-only -t uncommitted` antes de marcar a story completa
- [ ] Pre-PR (@github-devops): Run `coderabbit --prompt-only --base main` antes de abrir PR
- [ ] Pre-Deployment (@github-devops): Run scan de segurança antes de deploy — schema afeta produção

**CodeRabbit Focus Areas**
- **Primary Focus:**
  - Schema compliance: colunas exatas, constraints (`UNIQUE`, `CHECK`, `NOT NULL`)
  - Projeção mínima: nenhuma coluna comercial/pessoal cruza a fronteira
- **Secondary Focus:**
  - CSPRNG correto (`secrets`, não `random`)
  - Idempotência do upsert no republish

**Self-Healing Configuration**
- **Expected Self-Healing:**
  - Primary Agent: @dev (light mode)
  - Max Iterations: 2
  - Timeout: 15 minutes
  - Severity Filter: CRITICAL only
- **Predicted Behavior:**
  - CRITICAL issues (ex.: uso de `random` em vez de `secrets`, coluna proibida exposta): auto_fix (até 2 iterações)
  - HIGH issues: document_only (anotado em Dev Notes)

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-07-11 | 0.1 | Story criada a partir de architecture.md §2/§3 e prd.md NFR1-NFR5 | River (SM) |
| 2026-07-11 | 1.0 | Implementado e testado ao vivo — ver Dev Agent Record | Claude (dev) |

---

## Dev Agent Record

**Arquivos criados:**
- `consulta-publica-api/publisher/schema.sql` — DDL `public_codes` (schema exato, sem colunas da blacklist)
- `consulta-publica-api/publisher/db.py` — `get_connection`, `assert_no_blacklisted_columns`
- `consulta-publica-api/publisher/publish.py` — `gerar_code`, `publicar`, `revogar`
- `consulta-publica-api/publisher/tests/test_publisher.py` — 9 testes, todos AC cobertos
- `portal/app/routers/admin_publish_routes.py` — `POST /admin/publicar/{obra_id}`, `POST /admin/revogar/{obra_id}` (autenticados, `Depends(auth.exige_login)`)
- `portal/app/main.py` — registro aditivo do novo router (2 linhas)

**Testes:** 9/9 passando (`pytest consulta-publica-api/publisher/tests/test_publisher.py`).

**Verificado ao vivo** contra o portal real (obra `156f05b4-2df3-45bf-9be9-6b3817aff686`,
432 itens): publicar, republicar (upsert preservando codes), e revogar (433 linhas
afetadas, incluindo o registro da obra) — todos via `fetch()` real no navegador,
autenticado.

**Bug real encontrado e corrigido durante o teste ao vivo:** `gerar_code()` usava
`secrets.token_bytes(8)` hardcoded em vez de `secrets.token_bytes(_CODE_LEN)` —
gerava códigos de 8 caracteres em vez dos 10 especificados (architecture §3.1).
Só apareceu testando contra dado real porque o teste unitário original não
verificava o comprimento do código — adicionado `test_gerar_code_tem_10_caracteres`
como regressão.

**Estado deixado no ambiente de teste:** os 433 registros da obra de teste foram
revogados (`revoked=1`) ao final da verificação — nada fica publicamente ativo
por acidente. `D:\Agente-cad-PYSIDE\public_consulta.db` existe como artefato real
do teste, pronto para uso.

**Decisão de kickoff:** endpoint HTTP implementado (não só CLI) — reuso direto do
padrão de autenticação já existente no portal (`auth.exige_login`), sem risco
adicional.
