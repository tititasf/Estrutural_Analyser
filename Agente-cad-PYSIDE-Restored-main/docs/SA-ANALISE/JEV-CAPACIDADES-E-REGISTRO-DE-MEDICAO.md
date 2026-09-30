# Jev — capacidades e registro de medição

Documento durável. Não chama a API Jev. Não altera N1. N2/N3/N4 não provam N1.

**Estado observado (2026-09-30, v6 wall-level set, dry-run):** catálogo `v6-2026-09-30-lv-wall-level-set`, fábrica `0.8.0-lv-wall-level-set`. Relatório: [`scripts/arete/relatorios/20260930_jev_lv_wall_level_calibration_v6/RELATORIO.md`](../../scripts/arete/relatorios/20260930_jev_lv_wall_level_calibration_v6/RELATORIO.md). Comparação válida = conjuntos no nível da parede `(pavimento, rótulo único, handle, face)`. 876 paredes fonte; comparáveis **9** (SET_EQUAL 5 / SET_DIVERGE 4); o resto abstém (ownership/source/cobertura N1). Fila Jev **4** pacotes fonte-only, API **0 / 8**. V420 `2F8` A = SET_EQUAL `{PARA, PASSA}`. 14_PAV `parity_claimed=false`. Benefício **não** reivindicado. Métricas N1 por extremo do v5 permanecem retiradas. v1–v5 intocados.

**Estado anterior (2026-09-30, v5 blinded single-outcome):** catálogo `v5-2026-09-30-lv-blinded-single-outcome`, fábrica `0.7.0-lv-blinded-single-outcome`. Relatório: [`scripts/arete/relatorios/20260930_jev_lv_blinded_single_outcome_v5/RELATORIO.md`](../../scripts/arete/relatorios/20260930_jev_lv_blinded_single_outcome_v5/RELATORIO.md). API Jev **8 / 8** (`jev-1.13.0`). Amostra n=4 (13_PAV + 14_PAV, PARA e PASSA, controlo V420 `2F8` sul/norte). Jev=CAD **3 / 4**; abstenção **1 / 4**; controlo INSUFFICIENT **4 / 4**; set-equality N1 **0 / 3**. Visão PNG **UNVERIFIED**. Benefício **não** reivindicado. v1–v4 intocados. v3 packed-0 (Choice no mesmo encontro) inalterado.

**Estado anterior (2026-09-29, Stage 1 LV source-first + colisão de parede):** catálogo `v3-2026-09-29-lv-source-encounter`, fábrica `0.6.0-lv-source-encounter`. Relatório v3: [`scripts/arete/relatorios/20260929_jev_catalog_v3_lv_source_encounter/RELATORIO.md`](../../scripts/arete/relatorios/20260929_jev_catalog_v3_lv_source_encounter/RELATORIO.md). Follow-up de colisão: [`scripts/arete/relatorios/20260929_jev_lv_source_wall_ownership/RELATORIO.md`](../../scripts/arete/relatorios/20260929_jev_lv_source_wall_ownership/RELATORIO.md). Catálogo v2 13 pacotes **WITHDRAWN**. **Pacotes Jev v3 (mesmo encontro PARA×PASSA): 0.** **Choice de dois nomes fonte no mesmo handle: 0 elegíveis após CAD; API Jev 0 nesse follow-up.** O zero v3 aplica-se só a esse pack-gate de conflito no mesmo encontro.

Governa o uso: [JEV-SEGUNDA-LEITURA-OPCIONAL.md](JEV-SEGUNDA-LEITURA-OPCIONAL.md). Hipóteses de produto: [MASTERPLAN-JEV-SA-EXPLORACAO.md](../MASTERPLAN-JEV-SA-EXPLORACAO.md). Calibração: [PLANO-CALIBRACAO-JEV-SA-QA.md](PLANO-CALIBRACAO-JEV-SA-QA.md).

## 1. O que se extrai (fonte e sidecars)

Camadas obrigatórias: **FACT** (geometria/topologia da fonte), **HYPOTHESIS** (PARA/PASSA/face a partir de factos), **N1 COMPARISON** (sidecar isolado). Evidência enviável a Jev só pode conter FACT + a pergunta; nunca N1/QA/gabarito.

| Canal | PIL | LV | FV | LAJ | Notas |
|---|---|---|---|---|---|
| **DXF Fase-1** | handle, etype, layer, xy, polígono fechado que contém o rótulo, textos `dim`, faces | rótulo único `V…`, paredes abertas (handle + extremos), parceiro paralelo, vão retangular da faixa, marcador `P…`, continuação colinear no **mesmo** extremo, rótulos de viga cruzada | contorno/aresta por segmento, textos de abertura, handles locais | polígono da laje, textos de nível, `h=`, marcadores concorrentes no mesmo anel | Parser local (`DxfParserCadSource`). Proibido recorte Fase-2 / reverse_eng. DXF inteiro não entra em prompt. |
| **SVG** | apoio experimental da **mesma** fonte | idem | idem | idem | Só se reconstruído do DXF Fase-1 com handles auditáveis. Veredito visual = PNG. Pan/zoom web = `viewBox`. |
| **PNG** | full-layer + recorte local | full-layer + recorte do encontro | full-layer por segmento | full-layer da região | Agente lê pixels. Um único sessão Grok **não** conta como dois revisores G1. |
| **N1** | `dim`, faces, snapshot hash | matriz A/B × PARA/PASSA, pontos dos localizadores, `generation_ready` | `abertura_especial` por segmento, claim repetido | `laje_nivel`, `h=` | Sidecar **depois** de congelar candidatos fonte. Localizador N1 **não** sementeia parede nem define PASSA. |
| **QA** | score/veredito da rodada, `qa_snapshot_sha256` | células remotas (audit geométrico) | scope audit por segmento | convenção de desnível | Fora de `evidence`. Bridge `jev_qa_bridge.py` é opt-in. |
| **Saída Jev** | Choice (+ Noul/Score companheiros no helper) | idem, unidade = **encontro** (parede + extremo) | presença local / NONE | nível / INSUFFICIENT | `confidence` = concentração entre opções. Não é prova física. Controlo de retirada obrigatório. |

**LV Stage 1 (observado):** o extrator `adapters_lv_v3.py` enumera encontros a partir de rótulos DXF, extremos, topologia, pilares/vãos, cruzamentos e conexão ao rótulo. ID estável: pavimento, viga, face, handle da parede, coordenada do encontro, handles fonte. 13_PAV: 31 rótulos únicos, 392 paredes, 784 encontros. 14_PAV congelado: 27 rótulos, 484 paredes, 968 encontros.

## 2. O que se mede (unidades e denominadores)

Toda métrica precisa de denominador, proveniência (ficheiro + SHA) e camada (FACT / HYPOTHESIS / N1 COMPARISON). Número solto é inválido.

| Medida | Unidade | Denominador | Onde |
|---|---|---|---|
| Cobertura de rótulos LV | rótulo único `V…` no DXF | textos `TEXT/MTEXT` que casam `BEAM_NAME_RE` e não `VF*` | `source_inventory.denominators.unique_lv_labels` |
| Cobertura de faixa | vigas com ≥1 parede ligada ao rótulo | rótulos varridos | `beams_with_strip` |
| Atribuições de parede / encontros | par viga+handle; par viga+handle+extremo | atribuições do inventário; 2 extremos/atribuição | `source_walls`, `encounters` v3; **não** equivalem a handles físicos únicos |
| Suficiência fonte | encontro com PARA xor PASSA xor nenhum xor ambos | encontros | `encounters_para_only` / `_passa_only` / `_neither` / `_para_and_passa` |
| Fidelidade de candidato | handle do inventário ∈ DXF | handles do pacote | `leakage.validate_factory_request` |
| Abstenção / fail-closed | `SOURCE_INSUFFICIENT`, `CONVENTION_INDETERMINATE`, `NOT_N1_DECISION`, `CAD_REDUNDANT` | encontros auditados | `n1_relevance_counts` |
| Contradição no mesmo encontro | PARA e PASSA no mesmo extremo | encontros | pack_gate → `para_and_passa_not_exclusive_at_one_encounter` |
| Deteção de erro (sidecar) | `n1_field_would_change` | encontros comparados | **Exploratório apenas**: localizador de parede não resolve o extremo; não usar como erro N1 confirmado |
| Cover N1 (viés) | localizador mais curto que a parede fonte | linhas sidecar | `locator_cover_rows`; **proibido** como PASSA |
| Omissão N1 | parede fonte sem localizador N1 correspondente | paredes / células | sidecar `n1_locator_miss_cells_on_beam` |
| Drift de versão | SHA DXF / estado / módulos SA | manifesto G0 | `run_manifest.json`; 14_PAV DXF/estado MATCH cópia 25/09; módulos SA locais MISMATCH |
| Custo Jev | chamadas, tokens, latência | casos elegíveis | Stage 1: 0 chamadas. v5 30/09: **8 chamadas**, 8013 tokens de entrada, latência mediana 0.268 s, USD não devolvido |
| Risco | pacote `N1_DECISION_RELEVANT` sem PNG / sem exclusividade | packed | Stage 1 packed = 0 |
| Acordo visual | consenso G1 de dois revisores independentes | casos com PNG | **não reivindicado** nesta sessão |
| Campo por classe | ver manuais `CLASSES/{PIL,LV,FV,LAJ}.md` | itens da classe no snapshot | N1 sidecar |
| Colisão de parede fonte | handle com 2+ nomes únicos distintos | handles únicos no inventário v3 | `collision_audit_*.json` |
| Par de nomes | conjunto ordenado de `V…` | pares com ≥1 parede partilhada | `denominators.pair_wall_counts` |
| Encontros em colisão | encontro cujo `wall_handle` colide | encontros do inventário | `collision_encounters` |
| Categoria geométrica | over-expanded / joint / unresolved / duplicate-name | paredes em colisão | `category_walls`; incerteza explícita por caso |
| N1 em colisão (sidecar) | `n1_field_would_change`, `lv_cell:*` | encontros das paredes em colisão | `n1_collision_sidecar_*.json` (fora de Jev) |

**Observado Stage 1**

| Pavimento | Rótulos | Paredes | Encontros | PARA only | PASSA only | ambos | packed | N1_DECISION_RELEVANT |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 13_PAV (dev DXF + `project_data.vision` RO) | 31 | 392 | 784 | 83 | 325 | 0 | **0** | **0** |
| 14_PAV (DXF/estado congelados VPS 25/09) | 27 | 484 | 968 | 203 | 356 | 0 | **0** | **0** |

14_PAV sidecar: `locator_cover_rows=262`, `n1_field_would_change=99`, `n1_decision_relevant=0`. 13_PAV sidecar: `locator_cover_rows=0`, `n1_field_would_change=21`. Os contadores `n1_field_would_change` são **sinais brutos não confirmados por extremo**, retirados como medida de erro N1 após a [correção v5](../../scripts/arete/relatorios/20260930_jev_lv_blinded_single_outcome_v5/CORRECAO-N1.md).

**Observado follow-up colisão (inventário v3, sem reescrever v3)**

Os `392/484` de `source_walls` v3 são **atribuições viga→parede**, enquanto os handles físicos únicos são `238/256`; os `784/968` encontros também se repetem por atribuição. A classificação `LIKELY_OVER_EXPANDED_STRIP` é heurística geométrica auditável, não verdade visual selada.

| Pavimento | Handles únicos | Paredes em colisão | Pares | Encontros | Over-expanded | Joint | Unresolved interior | Jev-elegível após CAD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 13_PAV | 238 | 130 | 24 | 568 | 102 | 28 | 0 | **0** |
| 14_PAV congelado | 256 | 132 | 20 | 720 | 102 | 30 | 0 | **0** |

Sidecar N1 isolado nas colisões: 13_PAV `n1_field_would_change=13` / 14_PAV `60`. TEXT duplicado do mesmo nome (CAD, fora do inventário único): 13_PAV 14 nomes, 14_PAV 0. Handles `312`/`313`: colisão V423×V424, só V424 na faixa, V419 não lista — over-expansion + atribuição surpreendente, não colisão V419.

## 3. O que se avalia com Jev (e o que não)

Jev escolhe entre candidatos **já extraídos**. CAD mede; PNG confirma geometria visível; SA produz N1; QA pontua o fluxo. Jev soma uma leitura semântica fechada com `INSUFFICIENT`.

| Comparação | Quando faz sentido | Controlo negativo | Limite |
|---|---|---|---|
| Jev × CAD | dois candidatos fonte no **mesmo** encontro, mutuamente exclusivos, ambos com handle | retirada de topologia → `INSUFFICIENT` | PARA num extremo e PASSA no outro = dois encontros (v2 WITHDRAWN) |
| Jev × dois nomes fonte no mesmo handle | exactamente dois rótulos únicos **interiores** à mesma faixa | segundo rótulo retirado → `INSUFFICIENT` | 0 casos após CAD neste follow-up; API não chamada |
| Jev cego × um outcome fonte | encontro `CAD_REDUNDANT` (PARA xor PASSA); pergunta PARA/PASSA/INSUFFICIENT | retirar gap/pilar ou continuação; perturbar xy | **executado 30/09 n=4, 8 chamadas**; Jev=CAD 3/4; controlo INSUFFICIENT 4/4; V420 `2F8` norte abstém (continuação `770` começa Δy=5); N1 set-equality 0/3; PNG UNVERIFIED; benefício não reivindicado |
| Jev × visão PNG | pacote `N1_DECISION_RELEVANT` com PNG full-layer + local | evidência visual insuficiente → retirar | uma sessão ≠ dois G1 |
| Jev × SA/N1 | a escolha mudaria um campo N1 concreto | baseline fora de `evidence` | desacordo N1 + um só outcome fonte = `NOT_N1_DECISION` no pack-gate v3; o protocolo cego compara N1 à parte |
| Jev × QA | sidecar opt-in B1/B2/B3 | Noul contraditório com Choice → `CONTRADICTORY_SIGNALS` | Score Jev não altera score QA |

**Controlos LV congelados (14_PAV, Stage 1, sem API)**

| Item / handle | Facto fonte | Hipótese | N1 / v2 |
|---|---|---|---|
| V420 `2F8` | extremos (4708.59, 3103.025) e (4708.59, 3188.025); face A | PARA no sul, PASSA no norte | v2 misturou num Choice; v3 = dois `CAD_REDUNDANT` |
| V420 `2F5` / `2F9` | face B; mesmo padrão extremos opostos | PARA xor PASSA por extremo | packed 0 |
| V411 `315` | parede y=2583–2754 | nenhum gap/continuação no extremo | v2 `CAD_REDUNDANT A_PASSA` por cover do localizador; v3 **não** infere PASSA |
| V419 | 31 paredes / 62 encontros no inventário fonte | — | v2 `no_dxf_line_matches_n1_cell`; `312`/`313` **não** estão em V419 |
| V423/V424 `312`/`313` | par aberto layer 3, x=5307.59/5321.59, y=2075–2335 | V424 no extremo sul; V423 fora da faixa (faixa ortogonal a NW) | colisão de inventário V423×V424 = `LIKELY_OVER_EXPANDED_STRIP`; não Choice |

## 4. Observado vs hipótese futura

**Observado (30/09 v5):** protocolo cego de um outcome **executado** (n=4, 8 chamadas, `jev-1.13.0`). Jev=CAD 3/4; abstenção 1/4; controlo INSUFFICIENT 4/4; tokens de entrada 8013; latência mediana 0.268 s; PNG UNVERIFIED; G1/G4 não selados; N1 não escrito. Inventário v3 e packed-0 preservados.

**Correção da comparação N1:** o sidecar v3 associa uma célula ao extremo por correspondência de handle, embora o localizador N1 possa cobrir a parede inteira e codificar PARA e PASSA nos extremos opostos. Nos quatro casos v5, a concordância por extremo com N1 é **NOT_MEASURABLE (0/4 comparáveis)**. Os números originais `CAD×N1 0/3` e `Jev×N1 2/3` foram retirados, não são evidência de erro nem de ganho. Também não usar `n1_field_would_change` do sidecar v3 como prova por extremo até haver mapeamento semântico independente. [Correção auditável](../../scripts/arete/relatorios/20260930_jev_lv_blinded_single_outcome_v5/CORRECAO-N1.md).

**Observado (29/09):** inventário fonte LV 13/14_PAV; sidecar N1 isolado; packed v3 **0**; colisões de parede 130/132; unresolved interior **0**; API Jev **0** no follow-up de dois nomes; G4 `NOT_RUN`; v2 13 packs withdrawn. v3 não foi alterado para forçar pacotes.

**Escopo do zero v3:** o pack-gate exige dois outcomes fonte mutuamente exclusivos no **mesmo** encontro. Esse critério é incompatível com um único outcome fonte (`CAD_REDUNDANT`). O zero de pacotes **não** é evidência de que Jev não tenha valor como segunda leitura cega de um outcome fonte único, comparada ao N1 depois.

**Hipótese ainda não medida:** (a) conflito no mesmo encontro, se algum dia existir; (b) valor aditivo no fluxo QA com PNG G1; (c) se declarar a tolerância de extremo como FACT muda a abstenção V420 `2F8` norte. Benefício não reivindicado. O protocolo cego (b) de 29/09 foi **executado** em 30/09 (n=4).

## 5. Gates para chamadas Jev futuras

1. Inventário fonte congelado (SHA DXF + `inventory_sha256`) **antes** de qualquer comparação N1.
2. Unidade = um encontro (viga, face, handle, coordenada).
3. Para o **modo conflito v3**, duas opções mutuamente exclusivas, ambas com handle fonte listado, no **mesmo** encontro. O modo **validação cega v5** aceita um único outcome fonte e pergunta PARA/PASSA/INSUFFICIENT sem expor a hipótese CAD.
4. Mudança de campo N1 só pode ser afirmada com alinhamento independente entre a unidade N1 e o encontro físico; o sidecar v3 não basta. No modo v3 sem conflito, usar `CAD_REDUNDANT` / `SOURCE_INSUFFICIENT` / `CONVENTION_INDETERMINATE` / `NOT_N1_DECISION`.
5. Pacote ≤ 16 KB; `INSUFFICIENT` nas criteria; controlo de retirada; anti-leakage.
6. PNG local + full-layer lido **antes** de selar `N1_DECISION_RELEVANT`. Evidência visual insuficiente → withdraw.
7. Dois revisores G1 independentes para selo visual. Uma sessão não conta dois.
8. G4 só com casos selados e significativos. Stage 1: `NOT_RUN`.
9. Codex revê Stage 1 **antes** de gastar tokens Jev.
10. Sem escrita N1, sem KB rebuild, sem VPS, sem N2/N3/N4 como prova.
11. Choice de **nomes** de rótulo no mesmo handle: só com dois rótulos únicos interiores à faixa, confirmados por CAD limitado; senão não chamar a API.
12. Protocolo cego de um só outcome (PARA/PASSA/INSUFFICIENT): desenho em [`blinded_single_outcome_protocol.json`](../../scripts/arete/relatorios/20260929_jev_lv_source_wall_ownership/blinded_single_outcome_protocol.json); **executado 30/09** em [`20260930_jev_lv_blinded_single_outcome_v5`](../../scripts/arete/relatorios/20260930_jev_lv_blinded_single_outcome_v5/RELATORIO.md) (n=4, 8 chamadas). N1 entrou só depois do freeze. Benefício não reivindicado.

## 6. Proveniência desta medição

| Artefacto | SHA / identidade |
|---|---|
| 13_PAV DXF | `d23381e30eb358cc07e8c140d92db4c06b7be97859e7f9fb3eea2c0bd33151a4` |
| 13_PAV N1 fingerprint | `728dfc1d8a39948842c1317a95a17c869d0e7672c3d3cc9d9acfa5c2d8f84ce7` (sqlite RO) |
| 14_PAV DXF congelado | `7ec8a5edd4e5aecc78d60002a7198906c83b0699a4a87084fb9fdc7ac5f36a3b` MATCH |
| 14_PAV estado | `06b1da0cff0dcadc5e75c554e30963f8e715fc70b43b1761340d50908b0df5ed` MATCH |
| 13 inventory | `c83355515d2c2f76deb6754a9f68b3ad07dca72959452cb2e7a1a254e3359827` |
| 13 sidecar | `01d007dfd057579ee2e156df34dcfa20ed1ecc4776c6edf2db5a7221912a540d` |
| 14 inventory | `9b8d80f4d38a254c37c6efba2055fd07cfb6ae2b33ebbc7b0fdac9f28dbc6cdc` |
| 14 sidecar | `7da42e5c421a4ebc63bd3b95847c486bc568f47657c8edae748854b5e01da5e4` |
| 13 collision audit | `f472d5ffdbef796c241ff2798052b3795ec6788ae591f54b5cabedaa4c4e601b` |
| 14 collision audit | `aa5eb968aa1d867c81a6aa217d662ea6f5ccdc94f60552c9400265a768a9fa5d` |
| 13 N1 collision view | `95589737ea74e54a5f5a13169397a0342162fe86543fbb4acf97ca929dadf591` |
| 14 N1 collision view | `d08da20a7735ba8906f118b439bfc6ae2606c7022fc61e926849026f9afd1a4f` |
| `parity_claimed` | sempre falso. 14_PAV é regressão congelada, não holdout. |


## Rodada LV v7 — 30/09/2026

[Conclusão, evidência visual e recomendação consultiva](../../scripts/arete/relatorios/20260930_jev_lv_hybrid_adviser_v7/ANALISE.md).
Quatro chamadas reais em duas vigas do 14_PAV: concordância com a hipótese
geométrica em 2/2 e abstenção com retirada de evidência em 2/2; 4792 tokens
de entrada, mediana de latência por chamada 0,282 s. Não demonstra erro do SA
ou melhoria do fluxo. A agregação v6 por parede perde identidade do encontro;
as divergências são candidatas de investigação, nunca correções automáticas.
Manter segunda leitura opcional no QA/Eixo B e medir a ablação por encontro
antes de promover score ou integração no motor. Sem alteração N1, robôs ou VPS.


## Rodada LV v8 — correspondência por encontro

[Auditoria, revisão e próxima execução](../../scripts/arete/relatorios/20260930_jev_lv_encounter_v8/REVISAO.md). Adaptador e auditor
read-only implementados; 47 testes passaram. A amostra contém 96 encontros
fonte e um registro de ausência de encontro. Zero pacotes elegíveis: 80
encontros retidos por identidade de projeto, 17 registros por identidade
de fonte. Zero novas chamadas Jev. Estes são impedimentos de comparação,
não erros do SA. O gate recomputa o hash do inventário e verifica a fonte
do baseline local; project_id igual não basta. A etapa seguinte exige
fonte e execução SA verificadas juntas, com apoios/face curta/miolo por
encontro. Paridade VPS atual e ganho do fluxo híbrido continuam não medidos.


## Rodada v9 — identidade VPS e baseline isolado

[Registro e artefatos](../../scripts/arete/relatorios/jev_vps_identity_v9_20260930T140535Z/RELATORIO.md).
Fonte 14_PAV da VPS coincide com o freeze; codigo local difere. Snapshot remoto isolado, sem sobrescrita da aplicacao. 80 encontros receberam geometria fonte; 120 fragmentos conservam toda evidencia. Baseline canonical via Grok, estado em BASELINE-STATUS.json. Face curta/miolo/cessao ainda requerem evidencia por encontro. Zero novas chamadas Jev nesta preparacao; ganho hibrido nao demonstrado. VPS e banco de producao sem alteracoes.

Atualização v9 executada: baseline N1 fresco com código capturado da VPS (33 vigas/35 pilares/23 lajes, 52,431 s), sem cache e sem vazamento para código local. 12 chamadas Jev reais: contato/separação original 4/4; controles originais 4/4 abstenção; mesma geometria transladada 1/2 correto +2/2 controles abstiveram. Um erro TOUCH com confiança 0,76 em linha separada por 5 unidades. Não substituir validação geométrica determinística por confiança Jev. Registrar variantes equivalentes e divergências, sem votar até obter resposta desejada. 57 testes de regressão passaram. Ganho ponta a ponta ainda não demonstrado; baseline concluído tecnicamente não certifica interpretação.


## v9 — rastreabilidade e trava do conselheiro (30/09/2026)

Auditoria orquestrada com Grok, conferida e executada pelo Codex. A sessão de
proveniência do Grok atingiu o limite de turnos; seu código corrigido foi executado
depois pelo orquestrador. Artefatos em
`scripts/arete/relatorios/jev_vps_identity_v9_20260930T140535Z/`.

Nos alvos V409/V420 do 14_PAV, 14 segmentos de origem correspondem a 14 publicados
por chave, slot, índice, contrato e coordenadas, sem duplicatas ou contradições.
A auditoria explicita campos derivados da nomenclatura dos links; não certifica
identidade física a partir deles. Os 14 `lv_cell` disponíveis na origem são
omitidos pela publicação e não chegam ao adaptador experimental v8. Preservá-los
como N1_ORIGIN é útil para diagnosticar o SA; não são gabarito independente e não
devem entrar como verdade na pergunta ao Jev. As cenas medidas foram exportadas
usando o snapshot capturado da VPS, sem importação dos motores locais.

O arredondamento transversal do SA explica uma diferença de 0,01 nas duas vigas.
Há 50 alinhamentos transversais candidatos entre 80 eventos, mas nenhum vínculo
exato de extremo no diagnóstico. Alinhamento e grupos de paredes no mesmo eixo
não provam posse, apoio, face curta, miolo ou PARA/PASSA. O adaptador v8 permanece
inalterado: a auditoria não relaxou tolerâncias para forçar elegibilidade.

As 12 consultas reais de contato já realizadas foram reutilizadas offline.
`scripts/arete/jev_contact_advisor_v9.py` vincula resposta ao hash da pergunta,
identidade, modelo e hash da evidência, verifica retirada da geometria, confronta
distância calculada e exige consistência da representação traduzida. No replay
dos quatro casos originais: três sugestões retidas e uma ADVISORY_ONLY. Duas
foram retidas por ausência de consulta equivalente; a terceira por instabilidade
e contradição na equivalente. A sugestão restante nunca escreve N1, aprova QA ou
infere PARA/PASSA. Nenhuma chamada adicional; 65 testes passaram.

Esta trava é restrita ao experimento de contato por segmentos retos. Não é gate
de produção, validador de toda geometria CAD ou calibração estatística do Jev.
Uma resposta mudou de correta para errada apenas com translação, apesar de
aumentar sua confiança. Confiança isolada e controle de retirada aprovado não
bastam. Não repetir consultas até obter a resposta desejada.

Recomendação: matemática de contato fica no verificador determinístico; Jev fica
como opção para dúvidas semânticas com evidência rastreável, retirada de evidência
e verificações equivalentes. Próximo ensaio: montar automaticamente evidência
independente dos apoios/face curta/miolo nos encontros, preservando hipóteses do
SA fora do estado Jev; então comparar SA e SA+conselheiro nos mesmos casos
congelados. Medir correções, regressões, abstenções, custo e latência. Ainda não
há ganho de qualidade ponta a ponta demonstrado nem conclusão para todas as
classes. Sem alterações em motores, robôs, banco real ou VPS.
