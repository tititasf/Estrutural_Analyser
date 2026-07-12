# Masterplan — App de Consulta Pública CAD-ANALYZER

> **Orquestrado por:** Athena (CEO-Planejamento) — ciclo completo greenfield (Comprehensive)
> **Data:** 2026-07-11
> **Status:** ✅ Planejamento completo, validado, pronto para handoff de execução

---

## O que é

Uma aplicação NOVA, pública, separada do portal interno de Triagem/SA — permite a qualquer
pessoa com o código de um item (obra/pavimento/item) consultar a ficha técnica completa
daquele elemento de fôrma: visões N1 (interpretação humana/SA) e N3 (desenho gerado por
robô), lista de painéis (vigas laterais), tudo otimizado para uso em campo (canteiro de
obra, sol forte, luvas, conectividade instável).

**Fora do MVP (Fase 2):** viewer 3D real, lista de materiais genérica para todas as classes,
QR-code físico na peça.

---

## Artefatos do Ciclo de Planejamento

| Fase | Agente | Artefato | Status |
|------|--------|----------|--------|
| Discovery | Atlas (Analyst) | [project-brief.md](project-brief.md) | ✅ |
| Strategy | Morgan (PM) | [prd.md](prd.md) | ✅ |
| Architecture | Aria (Architect) | [architecture.md](architecture.md) | ✅ |
| Design | Uma (UX) | [front-end-spec.md](front-end-spec.md) | ✅ |
| Validation | Pax (PO) | [backlog-validation.md](backlog-validation.md) — **8.5/10 GO** | ✅ |
| Stories | River (SM) | [`docs/stories/active/app-consulta-publica/`](../../stories/active/app-consulta-publica/README.md) — 15 stories | ✅ |

---

## Decisões-Chave (resumo executivo)

1. **Stack:** Next.js 14 (App Router) PWA na Vercel (frontend) + nova API FastAPI dedicada,
   read-only, porta 21390, processo isolado no mesmo servidor do portal interno (backend).
2. **Segurança como fundação, não feature:** padrão **Publisher/Reader** — um processo
   interno projeta dados mínimos para um `public_consulta.db` próprio (`mode=ro` na API
   pública); a API pública **nunca** toca `project_data.vision` nem os dados internos do
   portal. Vazamento cross-cliente é fisicamente impossível, não apenas mitigado por regra.
3. **ID opaco:** código base62 ~10 caracteres (CSPRNG), não-sequencial, revogável — nunca
   expõe `obra_id`/`pavimento`/`item_id` reais.
4. **Reuso confirmado, zero re-trabalho de motor:** SVGs de N1/N3 já saem prontos dos
   endpoints existentes; painéis LV já existem como JSON persistido em
   `Fase-4_Sincronizacao/JSON_Vigas_Laterais/` — a API pública só LÊ, nunca executa o motor
   PySide6/SA.
5. **Renderização client-side + `noindex`:** correção deliberada à ideia inicial de SEO —
   dado é privado por código, não pode ser cacheado por CDN/crawler.
6. **Gate de release único e inegociável:** STORY-15 (suíte de testes de segurança) — sem
   isso, sem deploy, independente de qualquer pressão de prazo.

---

## Quality Scorecard (Arete Framework)

| Dimensão | Peso | Score | Observação |
|----------|------|-------|------------|
| Security | 10 | 9 | Publisher/Reader + IDs opacos + rate limit + gate de release — tratado como fundação, não add-on |
| UX Excellence | 10 | 9 | 3 personas mapeadas, fluxo completo com estados de erro/offline, teste de campo com 5 operadores como gate |
| Performance | 9 | 8 | SVG cacheável por content-hash, PWA offline, mobile/3G considerado desde o design |
| Scalability | 9 | 7 | API stateless, read-only; sharding não avaliado (não necessário no MVP) |
| UI Polish | 8 | 8 | Design system com tokens de alto contraste testados contra luz solar, 3 paletas |
| Accessibility | 8 | 8 | WCAG AA real e específico (não genérico) — contraste, alvos de toque, teclado, aria-live |
| Maintainability | 7 | 7 | Zero acoplamento com motor desktop; ficha_reader compartilhado com escape hatch documentado |
| Testability | 7 | 8 | STORY-15 dedicada, acceptance criteria testáveis em todas as 15 stories |
| Time to Market | 7 | 7 | MVP claro, LV marcado como Should (pode deslizar sem descaracterizar) |
| Cost Efficiency | 6 | 7 | Vercel só frontend; backend reusa infraestrutura existente |

**Média ponderada: 8.05/10 — acima do mínimo (7.0). Handoff aprovado.**

---

## Riscos Residuais (carregados da Architecture §10 e Discovery)

1. Decisão de negócio/jurídica sobre "o que pode ser público" ainda depende de validação
   humana contínua por obra (o Publisher exige uma ação explícita de "publicar" — nunca
   publica por padrão).
2. Formato de nomenclatura de item real (`P1`, `L101`, segmentos longos) precisa de mapeamento
   cuidadoso no Publisher para não vazar via mensagens de erro ou logs.
3. `source-tree.md` do repo não existe formalmente — caminhos de arquivo das stories são
   inferidos e precisam confirmação no kickoff de cada uma (documentado em cada story).

---

## Próximo Passo — Handoff para Execução

Conforme o protocolo CEO-Planejamento ↔ CEO-Desenvolvimento: com quality score ≥ 7.0,
o masterplan está pronto para @dev começar pela **STORY-01** (schema + Publisher —
fundação de tudo, sem dependências). Ordem de execução completa no
[README de stories](../../stories/active/app-consulta-publica/README.md).
