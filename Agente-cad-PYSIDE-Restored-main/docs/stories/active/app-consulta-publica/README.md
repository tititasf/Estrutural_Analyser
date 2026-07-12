# Roadmap de Stories — App de Consulta Pública CAD-ANALYZER

> **Preparado por:** River (AIOS Scrum Master) para CEO-Planejamento (Athena)
> **Fontes:** `project-brief.md` (Atlas), `prd.md` (Morgan), `architecture.md` (Aria), `front-end-spec.md` (Uma) — todos em `docs/planning/app-consulta-publica/`
> **Data:** 2026-07-11
> **Status:** ✅ MVP completo — 15/15 stories implementadas, testadas (193 testes automatizados: 94 backend + 99 frontend) e verificadas ao vivo em 2026-07-12. Gate de segurança (STORY-15): **GO** (AC1-10). AC11 (usabilidade de campo) pendente — gate manual, ver `docs/qa/app-consulta-publica-security-gate-report.md`.
>
> **[2026-07-12] Mudança de arquitetura pós-MVP — Auto-Publicação:** o modelo original de "publicação deliberada" (STORY-01: um curador chama `POST /admin/publicar/{obra_id}` manualmente) foi **substituído por sincronização automática**, a pedido explícito do dono — ver `portal/app/auto_publish_poller.py`. Toda obra com `estado='pronta'` no portal é publicada/republicada automaticamente a cada `auto_publish_interval_s` (default 60s, `PORTAL_AUTO_PUBLISH_INTERVAL_S`), sem ação manual. O endpoint manual continua existindo (publicação/revogação sob demanda), mas deixou de ser o único caminho. Os `codes` opacos seguem sendo mintados e preservados pelo mesmo `publisher.publish.publicar()` — a superfície de segurança (STORY-15) não mudou, só o gatilho.
>
> **[2026-07-12] Incremento pós-MVP — Código público por pavimento + visibilidade no Portal + QR:** `public_codes.kind` ganhou um 3º valor, `'pavimento'` (antes só `'obra'`/`'item'`), representando a "ficha do pavimento" (recorte limpo da torre) — mintado junto com os códigos de item em `publisher/publish.py::publicar()`, resolvido em `GET /api/v1/pavimento/{code}` (`consulta-publica-api`) e renderizado em `/pavimento/[code]` (`consulta-publica-web`). Cada obra, cada pavimento e cada item agora tem seu próprio código público opaco e não-derivável. O **Portal** (fonte da verdade dos IDs internos `obra_id`/`pavimento`/`item_id`) passou a **mostrar esses códigos publicados** direto nas suas próprias telas via `portal/app/public_codes_lookup.py` (módulo read-only, único autorizado a abrir `public_consulta.db` a partir do portal): badge do código da obra no cabeçalho de `obra_detalhe.html`, código do pavimento no painel de recorte, e `code_publico` na resposta de `GET /obras/{id}/n1/{classe}/{item_id}`. Na `consulta-publica-web`, as fichas de item (`/ficha/[code]`) e de pavimento (`/pavimento/[code]`) ganharam geração de **QR code** client-side (pacote `qrcode`) com botão de impressão, para facilitar o acesso de outros usuários em campo.

---

## Como ler este roadmap

15 stories, organizadas nos 4 Epics definidos pelo PRD (§11) e pela Architecture (§9), mais uma story transversal de **gate de segurança** que fecha o MVP. A ordem abaixo é a ordem de execução recomendada (DAG topológico) — cada story lista suas dependências explícitas.

**Convenção de prioridade:** P0 = bloqueante para qualquer entrega; P1 = necessário para o MVP completo; P2 = complementar (ainda MVP, mas pode deslizar sem descaracterizar o MVP, ex. LV conforme PRD §5.1).

**Convenção de esforço relativo:** P (pequeno, ~0.5-1 dia-dev) / M (médio, ~1-3 dias-dev) / G (grande, ~3-5 dias-dev).

**Nota de source tree:** os 4 documentos de planejamento não incluem um `source-tree.md`/`unified-project-structure.md` formal para este projeto (repo `Agente-cad-PYSIDE-Restored-main`). Os caminhos de arquivo propostos em cada story são **inferidos** a partir dos módulos citados como reais na Architecture (`portal/app/*`, `src/core/lv_generation_contract.py`, `DADOS-OBRAS/{obra}/...`) e seguem a decisão arquitetural de **processo/serviço novo e isolado** (`consulta-publica-api` no backend, `consulta-publica-web` no frontend). **@architect (Aria) e @dev (Dex) devem confirmar/ajustar os caminhos exatos no kickoff de cada story** — isto está marcado explicitamente em cada Dev Notes como ponto de confirmação, não como invenção de padrão definitivo.

---

## Ordem de Execução (DAG)

### Epic 1 — Fundação & Consulta Segura por ID

| # | Story | Prioridade | Esforço | Depende de |
|---|-------|-----------|---------|------------|
| 1 | [STORY-01](STORY-01-schema-publisher.md) — Schema `public_consulta.db` + Publisher | P0 | G | — (fundação) |
| 2 | [STORY-02](STORY-02-api-skeleton.md) — API pública FastAPI (skeleton, porta 21390, conexão RO) | P0 | M | STORY-01 |
| 3 | [STORY-03](STORY-03-resolve-endpoint.md) — Endpoint `/api/v1/resolve/{code}` | P0 | M | STORY-02 |
| 4 | [STORY-04](STORY-04-security-hardening.md) — Rate limiting + CORS + anti-enumeração | P0 | M | STORY-03 |

### Epic 2 — Ficha do Item (N1/N3)

| # | Story | Prioridade | Esforço | Depende de |
|---|-------|-----------|---------|------------|
| 5 | [STORY-05](STORY-05-ficha-reader-endpoint.md) — `ficha_reader` compartilhado + endpoint `/ficha/{code}` | P0 | M | STORY-01, STORY-03 |
| 6 | [STORY-06](STORY-06-svg-endpoint.md) — Endpoint `/ficha/{code}/svg/{nivel}` (SVG otimizado + cache) | P0 | M | STORY-05 |
| 7 | [STORY-07](STORY-07-obra-index-endpoint.md) — Endpoint `/obra/{code}` (índice de pavimentos/itens) | P1 | P | STORY-03, STORY-01 |
| 8 | [STORY-08](STORY-08-frontend-pwa-scaffold-busca.md) — Frontend: scaffold PWA + Tela de Busca | P0 | M | STORY-03, STORY-04 |
| 9 | [STORY-09](STORY-09-design-tokens.md) — Frontend: Design System / Tokens (Tailwind, WCAG AA) | P0 | M | STORY-08 |
| 10 | [STORY-10](STORY-10-frontend-ficha-obra-index.md) — Frontend: Tela Ficha do Item + Índice de Obra | P0 | G | STORY-05, STORY-07, STORY-09 |
| 11 | [STORY-11](STORY-11-svg-viewer-fullscreen.md) — Frontend: Visualizador SVG tela cheia (zoom/pan) | P0 | M | STORY-06, STORY-10 |

### Epic 3 — Lista de Painéis LV

| # | Story | Prioridade | Esforço | Depende de |
|---|-------|-----------|---------|------------|
| 12 | [STORY-12](STORY-12-paineis-lv-endpoint.md) — Endpoint `/ficha/{code}/paineis-lv` | P2 (Should) | P | STORY-05 |
| 13 | [STORY-13](STORY-13-frontend-paineis-lv.md) — Frontend: Aba Painéis LV | P2 (Should) | P | STORY-12, STORY-10 |

### Epic 4 — UX de Campo & PWA Offline

| # | Story | Prioridade | Esforço | Depende de |
|---|-------|-----------|---------|------------|
| 14 | [STORY-14](STORY-14-pwa-offline-service-worker.md) — PWA installability + Service Worker + cache offline + status | P1 (Should) | M | STORY-08, STORY-10, STORY-11, STORY-13 |

### Gate de Release (transversal a todos os epics)

| # | Story | Prioridade | Esforço | Depende de |
|---|-------|-----------|---------|------------|
| 15 | [STORY-15](STORY-15-security-test-suite-gate.md) — Suíte de Testes de Segurança (gate obrigatório) | P0 (NN) | G | STORY-01–STORY-07, STORY-12 |

---

## Mapa Epic → Stories

- **Epic 1 — Fundação & Consulta Segura por ID:** STORY-01, 02, 03, 04 (+ 08 entrega a consulta ponta-a-ponta com frontend mínimo)
- **Epic 2 — Ficha do Item (N1/N3):** STORY-05, 06, 07, 09, 10, 11
- **Epic 3 — Lista de Painéis LV:** STORY-12, 13
- **Epic 4 — UX de Campo & PWA Offline:** STORY-14 (tokens de design entram cedo em STORY-09 por serem pré-requisito de toda UI)
- **Gate transversal:** STORY-15 — não é opcional; é o único gate inegociável de release (architecture §5.4, PRD §10)

## Observações Importantes para @dev e @po

1. **Segurança não é feature isolada.** STORY-04 (rate limit/CORS/anti-enumeração) e STORY-15 (suíte de testes) não podem ser adiadas ou tratadas como "hardening posterior" — são requisitos não-negociáveis (NFR1-NFR5) confirmados por Architecture e PRD.
2. **LV (Epic 3) é Should, não Must** (PRD §5.1, `[AUTO-DECISION]` do PM) — se o cronograma apertar, STORY-12/13 são as primeiras a deslizar sem descaracterizar o MVP.
3. **Zero acoplamento com PySide6/motor SA.** Nenhuma story deve importar `src/core/lv_generation_contract.py` nem executar o motor desktop — STORY-12 lê apenas os JSON já materializados em `DADOS-OBRAS/{obra}/Fase-4_Sincronizacao/JSON_Vigas_Laterais/`.
4. **`ficha_reader.py` compartilhado (STORY-05) tem escape hatch.** Se a extração para módulo compartilhado for custosa no MVP, é aceitável copiar a lógica com teste de paridade — mas isso deve ser documentado como débito técnico explícito na story.
5. Todas as stories seguem a convenção de identificador opaco definida em STORY-01/architecture §3 — nenhuma story deve expor `obra_id`, `pavimento` ou `item_id` crus em qualquer resposta pública.
