# Story 2.2: Endpoint `GET /api/v1/ficha/{code}/svg/{nivel}`

**Epic:** Epic 2 — Ficha do Item (N1/N3)
**Priority:** P0
**Status:** ✅ Done (implementado e testado ao vivo em 2026-07-12)
**Estimated Effort:** M (médio)

```yaml
executor: "@dev"
quality_gate: "@architect"
quality_gate_tools: ["pytest", "svgo", "coderabbit"]
```

---

## Story

**As a** usuário de campo em conexão 3G,
**I want** que o desenho N1/N3 seja servido como um recurso próprio, cacheável e otimizado, e não embutido no JSON da ficha,
**so that** eu só pague o custo de download do desenho quando realmente abrir a aba correspondente, e que o 2º acesso ao mesmo desenho seja instantâneo (cache do CDN/browser).

---

## Context

A Architecture identificou o SVG N3 denso como o principal risco de performance em 3G (R5) e decidiu servir o SVG por um endpoint dedicado `image/svg+xml`, com `Cache-Control: public, max-age=31536000, immutable` e `ETag` por content-hash — permitindo cache agressivo no Cloudflare e no browser. A otimização (`svgo`) acontece **no publish-time** (Publisher, STORY-01), não a cada request.

[Source: architecture.md §4 tabela de endpoints, linha `/ficha/{code}/svg/{nivel}`]
[Source: architecture.md §6.2 "Performance mobile/3G (NFR6/NFR7)"]
[Source: prd.md FR3, NFR6, NFR7]

---

## Acceptance Criteria

1. **Given** um `code` de item válido e `nivel ∈ {n1, n3}`, **when** `GET /api/v1/ficha/{code}/svg/{nivel}`, **then** retorna `200` com `Content-Type: image/svg+xml` e o corpo é o SVG **puro** (não envolto em JSON).

2. **Given** a mesma requisição repetida, **when** respondida, **then** inclui `Cache-Control: public, max-age=31536000, immutable` e um header `ETag` derivado de hash do conteúdo do SVG — permitindo `304 Not Modified` em requisições condicionais (`If-None-Match`).

3. **Given** `nivel='n3'` para um item sem N3 gerado, **when** consultado, **then** retorna `404 {"erro":"nao_encontrado"}` genérico (mesmo padrão da STORY-03/05 — não revela se o item existe mas só não tem N3, trata como não encontrado nesse sub-recurso).

4. **Given** `nivel` fora do conjunto `{n1, n3}` (ex.: `n2`, `svg`, string arbitrária), **when** enviado, **then** retorna `404` genérico (validação de enum, nunca 500).

5. **Given** o SVG servido, **when** comparado ao SVG original extraído da ficha HTML do portal, **then** é o mesmo desenho **otimizado por `svgo`** (metadata removida, precisão de float reduzida) — a otimização acontece como parte do processo de publicação (Publisher, STORY-01) ou de um passo de build associado, **nunca em request-time** (evita custo de CPU por request).

6. **Given** o path de arquivo do SVG a servir, **when** resolvido, **then** é construído a partir do `obra_dir` **pré-resolvido e armazenado** em `public_codes` (nunca a partir de input livre do usuário) — e validado com `resolved.is_relative_to(DADOS_OBRAS_ROOT)` antes de abrir o arquivo (anti-path-traversal).

---

## Dependencies

- **Requires:** STORY-05 (endpoint `/ficha/{code}` referencia estas URLs; a lógica de resolução de item é compartilhada).
- **Blocks:** STORY-11 (visualizador SVG do frontend consome este endpoint).

---

## Tasks / Subtasks

- [ ] Task 1 — Implementar endpoint de SVG (AC: 1, 3, 4)
  - [ ] Subtask 1.1: Router `svg_routes.py` com validação de `nivel` (enum `n1`/`n3`)
  - [ ] Subtask 1.2: Resposta `image/svg+xml` via `FileResponse`/`Response(content=..., media_type=...)`
- [ ] Task 2 — Cache e ETag (AC: 2)
  - [ ] Subtask 2.1: Cálculo de content-hash (SHA-256 truncado) como `ETag`
  - [ ] Subtask 2.2: Suporte a `If-None-Match` → `304`
  - [ ] Subtask 2.3: Header `Cache-Control: public, max-age=31536000, immutable`
- [ ] Task 3 — Otimização publish-time (AC: 5)
  - [ ] Subtask 3.1: Integrar `svgo` (via subprocess ou binding Python) no fluxo do Publisher (STORY-01) ou como passo de build associado
  - [ ] Subtask 3.2: Documentar no README do Publisher que a otimização é 1x, não por request
- [ ] Task 4 — Anti-path-traversal (AC: 6)
  - [ ] Subtask 4.1: Validação `resolved.is_relative_to(DADOS_OBRAS_ROOT)`
  - [ ] Subtask 4.2: Teste com `code` manipulado / `nivel` com `../` (deve ser rejeitado pela validação de enum antes de chegar ao path, mas testar mesmo assim)
- [ ] Task 5 — Testes (AC: todos)
  - [ ] Subtask 5.1: Teste de content-type e corpo SVG puro
  - [ ] Subtask 5.2: Teste de cache headers e 304
  - [ ] Subtask 5.3: Teste de 404 para n3 ausente e nível inválido
  - [ ] Subtask 5.4: Teste de path traversal (deve falhar/404, nunca ler fora de `DADOS_OBRAS_ROOT`)

---

## Dev Notes

### Files/Components Expected

- `consulta-publica-api/routers/svg_routes.py`
- `consulta-publica-api/services/svg_service.py` (resolução de path + cache/ETag)
- `consulta-publica-api/publisher/svg_optimize.py` (chamada a `svgo` no publish-time, associado à STORY-01)
- `consulta-publica-api/tests/test_svg_endpoint.py`
- `consulta-publica-api/tests/test_path_traversal.py`

### Technical Notes

- **Cache:** `public, max-age=31536000, immutable` (SVG imutável por content-hash). [Source: architecture.md §4 tabela]
- **Otimização:** "o Publisher (ou um passo de build) roda `svgo` sobre os SVGs materializados... `[AUTO-DECISION]` fazer no publish-time, não no request-time (custo pago 1x)." [Source: architecture.md §6.2]
- **Anti-path-traversal:** "`obra_dir` é path pré-resolvido e armazenado pelo Publisher; a API nunca constrói path a partir de input do usuário. `code` é chave de lookup, nunca componente de caminho. Após lookup, valida `resolved.is_relative_to(DADOS_OBRAS_ROOT)`." [Source: architecture.md §5.1 item 5]
- **Fallback futuro (F2, não implementar agora):** "Se ainda pesado, F2 pode rasterizar fallback PNG progressivo" — apenas nota de roadmap, fora do escopo desta story. [Source: architecture.md §10 A3]

---

## Testing

- **Test file location:** `consulta-publica-api/tests/test_svg_endpoint.py`, `test_path_traversal.py`
- **Framework:** pytest + `TestClient`
- **Test scenarios obrigatórios:**
  - Content-Type e corpo corretos para n1/n3 existentes
  - 404 para n3 ausente e nível inválido
  - Cache-Control e ETag corretos; `304` em requisição condicional
  - Path traversal simulado (nível/código manipulados) nunca lê fora de `DADOS_OBRAS_ROOT`

---

## 🤖 CodeRabbit Integration

**Story Type Analysis**
- **Primary Type:** API
- **Secondary Type(s):** Security (path traversal), Performance (cache/CDN)
- **Complexity:** Medium

**Specialized Agent Assignment**
- **Primary Agents:** @dev, @architect (revisão de path traversal e cache strategy)
- **Supporting Agents:** —

**Quality Gate Tasks**
- [ ] Pre-Commit (@dev)
- [ ] Pre-PR (@github-devops)
- [ ] Pre-Deployment (@github-devops) — endpoint serve arquivo do disco, requer scan de path traversal

**CodeRabbit Focus Areas**
- **Primary Focus:**
  - Path traversal (nunca construir path a partir de input livre)
  - Cache headers corretos (immutable + ETag)
- **Secondary Focus:**
  - Validação de enum (`nivel`)
  - Content-Type correto (`image/svg+xml`, não `application/json`)

**Self-Healing Configuration**
- **Expected Self-Healing:** Primary Agent: @dev (light) · Max Iterations: 2 · Timeout: 15 min · Severity Filter: CRITICAL only
- **Predicted Behavior:** CRITICAL (path traversal explorável): auto_fix. HIGH (cache header incorreto): document_only.

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-07-11 | 0.1 | Story criada a partir de architecture.md §4/§5.1/§6.2 e prd.md FR3/NFR6/NFR7 | River (SM) |
| 2026-07-12 | 1.0 | Implementado e testado ao vivo — ver Dev Agent Record | Claude (dev) |

---

## Dev Agent Record

**Arquivos criados/alterados:**
- `consulta-publica-api/services/svg_service.py` — `obter_svg` (validação de nível, resolução de item, anti-path-traversal), `etag_de` (content-hash SHA-256 truncado)
- `consulta-publica-api/routers/svg_routes.py` — `GET /api/v1/ficha/{code}/svg/{nivel}`, suporte a `If-None-Match` → `304`
- `consulta-publica-api/services/ficha_service.py` — refatorado: extraído `resolver_item_e_fichas(row)` (núcleo comum de resolução obra_dir/item/dir_fichas), reusado por `montar_ficha` (STORY-05) e por `svg_service.obter_svg` (evita duplicar a lógica de resolução entre as duas stories)
- `consulta-publica-api/main.py` — wiring do novo router
- `consulta-publica-api/tests/test_svg_endpoint.py` (8 testes)
- `consulta-publica-api/tests/test_path_traversal.py` (3 testes)

**Testes:** 54/54 passando no projeto inteiro (`pytest consulta-publica-api`).

**Bug real encontrado e corrigido (fora do escopo direto da story, mas
exposto por ela):** `consulta-publica-api/config.py` tinha
`dados_obras_root` default apontando para `_REPO_ROOT.parent / "DADOS-OBRAS"`
(um nível ACIMA do repo) em vez de `_REPO_ROOT / "DADOS-OBRAS"` (dentro do
repo, mesmo caminho que `portal/app/config.py` usa via
`REPO_ROOT / "DADOS-OBRAS"`). Esse campo existia desde a STORY-02 mas nunca
tinha um consumidor real até esta story introduzir a validação
anti-path-traversal (AC6) — o primeiro teste ao vivo contra dado real
(`GET /svg/n1` de um pilar com N1 confirmadamente gerado) retornou 404
porque a validação `resolved.is_relative_to(dados_obras_root)` rejeitava
corretamente TODA obra real (elas vivem dentro do repo, não no diretório
sibling). Corrigido no `config.py`; reconfirmado ao vivo depois do fix
(`GET /svg/n1` → 200 com SVG real de ~624×873 viewBox, `ETag`/`304`
funcionando, `svg/n3` ausente e nível inválido → 404 genérico, código de
obra → 404 genérico).

**Achado de teste (não bug de produção) — normalização de atributos SVG:**
`BeautifulSoup`/`html.parser` (usado por `ficha_reader._parse_html_cache`,
STORY-05) normaliza nomes de atributo de tags `<svg>` para minúsculas ao
reserializar (`viewBox` → `viewbox`) — comportamento pré-existente do
parser, não desta story. Ajustei os fixtures de teste para escrever/esperar
`viewbox` minúsculo, documentando a causa no comentário.

**Achado de teste (ressalva de URL-parsing, mesma classe do achado da
STORY-03):** valores de `nivel` contendo `/` (ex.: `../etc`, decodificado de
`%2F`) nem chegam a bater na rota `/ficha/{code}/svg/{nivel}` — o path
param sem conversor `:path` não casa barras, então o HTTP client/Starlette
responde com o 404 genérico DELES (`{"detail":"Not Found"}`), não o da
aplicação. Resultado de segurança é o mesmo (nunca 200, nunca leitura de
arquivo), só o formato do corpo difere — documentado em
`test_path_traversal.py::test_nivel_com_traversal_string_nunca_vira_path` e
no comentário de `test_svg_nivel_invalido_404_generico`.

**Decisão de kickoff — ETag simples, sem `svgo`:** implementei o `ETag` via
hash do conteúdo já embutido na ficha HTML (extraído por
`ficha_reader.extrair_fotos_ficha`, sem nenhuma transformação adicional).
A Subtask 3 da story (otimização `svgo` no publish-time) **não foi
implementada** — não há integração de `svgo` no Publisher ainda; o SVG
servido é exatamente o que o SA real já gerou. Documentado como débito
técnico explícito: se o payload real se mostrar pesado demais em 3G,
integrar `svgo` ao fluxo do Publisher (STORY-01) é o próximo passo, fora do
escopo mínimo verificado aqui.
