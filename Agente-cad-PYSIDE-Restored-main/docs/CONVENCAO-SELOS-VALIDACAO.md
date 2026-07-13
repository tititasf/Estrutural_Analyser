# Convenção de Selos de Validação

**Fonte única da verdade** para as cores/selos de validação de campo e de item
no app desktop (SA). Todos os outros docs devem linkar pra este em vez de
reexplicar a convenção. Lógica de cálculo implementada em
`src/core/validation_model.py` (funções puras, testadas em
`tests/test_validation_model.py`).

## Por que 3 origens de campo?

Um mesmo campo pode ser validado por 3 fontes diferentes, cada uma com um
propósito distinto:

| Origem | Cor | Onde acontece | O que significa |
|---|---|---|---|
| `humano_app` | 🔵 Azul | App desktop, campo a campo (`detail_card.py`) | Humano confirmou esse campo específico no app |
| `humano_portal` | 🌸 Rosa | Portal de Formas, campo a campo (Fase 2) | Humano confirmou esse campo pela web |
| `qa_agente` | 🟠 Laranja | Agente QA-Global-Evidências (`qa_evidence_auditor.py`) | Agente automatizado confirmou esse campo (hoje só classe LAJ) |

Um campo pode ter **até as 3 origens ao mesmo tempo** — elas empilham, não se
substituem. Cada validação registra `{"origem": ..., "quando": iso8601}`
(exceto migração de dado legado, que grava `quando: null`). O contorno do
campo na UI reflete a origem de maior prioridade presente (azul > laranja >
rosa), e o tooltip lista todas as origens presentes.

## Por que 4 selos de item?

Um item (pilar/laje/viga) pode ter **até os 4 selos ao mesmo tempo** — são
independentes, não mutuamente exclusivos:

| Selo | Cor | Critério | Fonte de cálculo |
|---|---|---|---|
| Verde | ✅ | Validação geral do item, sem granularidade de campo (mais fraco — não olha campo nenhum) | `is_validated` (setado direto, inclusive por sync do Portal) |
| Rosa | 🌸 | 100% dos campos obrigatórios com origem `humano_portal` (ou N/A) | `calcular_selos_item(...)["rosa"]` |
| Azul | 🔵 | 100% dos campos obrigatórios com origem `humano_app` (ou N/A) | `calcular_selos_item(...)["azul"]` (era `is_fully_validated`) |
| Laranja | 🟠 | 100% dos campos obrigatórios com origem `qa_agente` (ou N/A) — **isolado**, sem mistura com outras origens | `calcular_selos_item(...)["laranja"]` |

**Isolamento do laranja (decisão do dono, 2026-07-13):** o selo laranja só
acende quando TODOS os campos obrigatórios têm a origem `qa_agente`
especificamente (ou estão em N/A). Um item com 1 campo `qa_agente` + 1 campo
`humano_app` **não** gera laranja nem azul — cada selo exige cobertura 100%
pela SUA própria origem. Essa regra existia numa versão anterior com mistura
(laranja também acendia em laranja+azul), **revogada** explicitamente pelo
dono para manter o agente isolado e mensurável.

**N/A não carrega origem:** um campo marcado N/A conta como "resolvido" pra
qualquer um dos 3 selos de cobertura (azul/rosa/laranja), sem precisar de
nenhuma origem tagueada — é tratado à parte, com motivo em `na_reasons`.

## Peso / hierarquia

Verde é o único selo "fraco" (não granular). Azul, rosa e laranja têm peso
equivalente entre si — todos exigem cobertura 100% campo-a-campo, diferindo
só na fonte. O laranja carrega peso pleno de propósito: é o agente que a
corporação está construindo pra reduzir a necessidade de human-in-the-loop,
então sua cobertura isolada é o sinal mais importante de progresso da
automação.

## Onde isso é renderizado

- **App desktop (SA) — única superfície com feedback visual rico.**
  `src/ui/widgets/detail_card.py` (borda/tooltip por campo) e `main.py`
  (`_montar_selo_icone_e_cor`, ícone combinado + cor de texto na árvore
  lateral).
- **Portal de Formas / Consulta de Fôrma** — não mostram essa granularidade.
  O Portal (Fase 2) só ganha a CAPACIDADE de gravar validação de campo
  (gera o `humano_portal`/rosa), sem UI de feedback multi-selo.

## Escopo do agente QA-Global-Evidências

Autoridade de escrita continua restrita como já era (`validation_ready` só
pra classe LAJ, `diagnostic_only` pra PIL/FV/LV) — essa convenção muda
**como** o agente grava (`origem=qa_agente` em vez de indistinguível), não
**quem** pode escrever. Ver `squads/qa-global-evidencias/agents/aegis.md`.
