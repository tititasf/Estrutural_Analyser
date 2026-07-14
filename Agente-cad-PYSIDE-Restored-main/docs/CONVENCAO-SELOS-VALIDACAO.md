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

## Mapeamento de field_id Portal ↔ SA (Fase 3.1-3.4)

O Portal manda pro endpoint `POST .../campo/{field_id}/validar` o field_id
REAL do app desktop (não mais o label exibido cru) — fonte única desse
mapeamento é `portal/app/ficha_reader.py` (`_FIELD_ID_PILAR`,
`_FIELD_ID_LAJE`, `_FIELD_ID_SEGMENTO_SUFIXO`), exposto como
`campos_field_id` ao lado de `campos` em cada item N1.

| Classe | Label no Portal | field_id no SA | Observação |
|---|---|---|---|
| Pilar | Nome | `name` | 1:1 |
| Pilar | Classificação | `classification` | Fase 3.2 — virou campo validável de verdade no app (era `QComboBox` solto) |
| Pilar | Orientação, Nível Relativo | — | sem equivalente no SA, gap documentado (não implementado) |
| Pilar | Lado A-D, Lajes contíguas (agregado) | — | continuam só display — a validação real é pela versão GRANULAR abaixo |
| Pilar | Laje {lado} #{i} — Nome/Altura/Nível (granular, Fase 3.3) | `p_s{lado}_l{i}_n`/`_h`/`_v` | field_id IDÊNTICO ao app, zero tradução — mesma fonte de dado que "Lado A-D"/"Lajes contíguas", só quebrada por lado × índice |
| Laje | Nome | `name` | 1:1 |
| Laje | Nível | `laje_nivel` | nomes diferentes, mesmo conceito |
| Laje | Altura | — | sem equivalente no SA, gap documentado |
| Laje | *(demais ~18 campos: visão de corte, pilares de apoio, pontaletes...)* | — | Portal N1 não expõe UI própria — validados por CRUZAMENTO, ver seção abaixo |
| Segmento (fundo) | Nome | `name` | absoluto, compartilhado com o header do item |
| Segmento (fundo) | Comprimento, Largura | `_dim` (sufixo) | aproximação: SA não separa largura de comprimento nesse segmento |
| Segmento (lateral \*\_para) | Comprimento | `_comprimento_total` (sufixo) | classe-derivável (não depende de estado runtime) |
| Segmento (lateral \*\_passa) | Comprimento | `_comp_total_passa` (sufixo) | idem |

Sufixos (começam com `"_"`) só viram field_id real depois de resolver
`seg_uid = f"{prefix}_seg_{idx}"` no app desktop — `prefix` vem de
`main.py::_SEG_WEB_CLASSE_PREFIX` (por classe), `idx` é regex-parseado do
`titulo` ("V101 (segmento N)"), gravado em `portal_validacoes_campo.titulo`
no momento da validação (migration 009).

## Cruzamento corte/pilar → laje (Fase 3.5)

A laje tem ~18 campos que o Portal N1 nunca vai expor diretamente (visão de
corte, pilares de apoio, pontaletes...) — em vez disso, confirmações já
feitas em OUTRAS classes alimentam esses campos por cruzamento de nome,
implementado em `main.py::_sincronizar_cruzamento_laje_drive`:

1. **Cortes → `laje_visao_corte`.** Classe "Visão de Cortes" (já existe no
   Portal) ganha um botão "Confirmar corte" (sentinela `field_id="_item_"`,
   já que o corte não tem sub-campo individual no SA). Cada corte referencia
   até 2 lajes (`own_laje`/`neigh_laje`, por nome). O motor conta — usando
   só a listagem do Portal, nunca cruzando com a lista local
   `links['laje_visao_corte']['cut_view_geom']` (uids diferentes, evita
   matching frágil) — quantos cortes referenciam cada laje vs. quantos
   foram confirmados; só marca `laje_visao_corte` (`humano_portal`) quando
   **100% baterem** (campo atômico no SA).
2. **Contato pilar↔laje → `laje_pilares_apoio`.** Quando um campo granular
   `p_s{lado}_l{i}_n` (Fase 3.3) é validado no Portal, o motor lê o VALOR
   já local desse campo no pilar (nome da laje digitado ali — o Portal só
   confirma QUE foi validado, o valor mora no pilar local) e marca
   `laje_pilares_apoio` (`humano_portal`) na laje referenciada.

Ambos são **best-effort, nunca bloqueantes** (try/except, log de aviso —
mesmo padrão de `_sincronizar_selo_verde_drive`).
