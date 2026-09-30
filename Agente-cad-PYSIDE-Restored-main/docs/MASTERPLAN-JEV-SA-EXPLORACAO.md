# Masterplan — Jev para interpretar a planta estrutural no SA/N1

> **v6 wall-level set (30/09, dry-run):** comparação válida por `(pavimento, rótulo único, handle, face)` com conjuntos de extremos. 876 paredes; comparáveis 9 (SET_EQUAL 5 / SET_DIVERGE 4); fila Jev 4 pacotes fonte-only; API **0 / 8**. V420 `2F8` A = SET_EQUAL `{PARA, PASSA}`. Relatório: [`20260930_jev_lv_wall_level_calibration_v6/RELATORIO.md`](../scripts/arete/relatorios/20260930_jev_lv_wall_level_calibration_v6/RELATORIO.md). Jev continua consultivo. Benefício false. `parity_claimed=false`.

> **Correção de interpretação v5 (30/09):** a comparação por extremo com N1 é **NOT_MEASURABLE (0/4 comparáveis)** porque o localizador N1 cobre a parede e não distingue o extremo. Ignorar os contadores brutos CAD×N1 e Jev×N1 em `audit.json`/`STATUS.json`; prevalece [CORRECAO-N1.md](../scripts/arete/relatorios/20260930_jev_lv_blinded_single_outcome_v5/CORRECAO-N1.md). Os 8 resultados Jev e os controles permanecem observações válidas, sem prova de ganho frente ao SA.

> **v5 2026-09-30 — protocolo cego de um outcome.** n=4 encontros (V420 `2F8` sul/norte + V313 `4C8` + V304 `444`). API Jev **8 / 8**, `jev-1.13.0`. Jev=CAD **3 / 4**; INSUFFICIENT **1 / 4**; controlo INSUFFICIENT **4 / 4**. PNG **UNVERIFIED**. Benefício **false**. Relatório: [`20260930_jev_lv_blinded_single_outcome_v5/RELATORIO.md`](../scripts/arete/relatorios/20260930_jev_lv_blinded_single_outcome_v5/RELATORIO.md). v1–v4 intocados. O packed 0 do v3 aplica-se só ao Choice de conflito no mesmo encontro.

> **Follow-up 2026-09-29 — colisão de parede fonte.** Inventário v3 13_PAV 130 paredes / 14_PAV 132 paredes com 2+ nomes únicos. Unresolved interior **0**. API Jev **não** chamada nesse follow-up. `312`/`313` = V423×V424 over-expanded (V424 local; V419 não lista). Protocolo cego: **executado depois** (v5 30/09). Relatório: [`20260929_jev_lv_source_wall_ownership/RELATORIO.md`](../scripts/arete/relatorios/20260929_jev_lv_source_wall_ownership/RELATORIO.md).

> **Catalog v3 LV source-first — packed 0 (Stage 1).** Inventário fonte 13_PAV 784 encontros / 14_PAV congelado 968 encontros. Sidecar N1 isolado. `N1_DECISION_RELEVANT` **0**. API Jev **não** chamada. Relatório: [`20260929_jev_catalog_v3_lv_source_encounter/RELATORIO.md`](../scripts/arete/relatorios/20260929_jev_catalog_v3_lv_source_encounter/RELATORIO.md). Registro de capacidades: [`SA-ANALISE/JEV-CAPACIDADES-E-REGISTRO-DE-MEDICAO.md`](SA-ANALISE/JEV-CAPACIDADES-E-REGISTRO-DE-MEDICAO.md). v2 13 pacotes continuam **WITHDRAWN**.

> **Catalog v2 LV 14_PAV — packed 0 (final).** Os 13 pacotes `N1_DECISION_RELEVANT` da fábrica `0.5.0` estão **WITHDRAWN**. Fábrica vigente `0.5.1-lv-cell-encounter-failclosed`. Dry-run corrigido: scanned 30 / packed **0** / `N1_DECISION_RELEVANT` **0**. Status: [`STATUS.json`](../scripts/arete/relatorios/20260929_jev_calibracao_catalog_v2_lv_cell/STATUS.json). Auditoria: [`20260929_jev_catalog_v2_lv_independent_audit/RELATORIO.md`](../scripts/arete/relatorios/20260929_jev_catalog_v2_lv_independent_audit/RELATORIO.md). G4 `NOT_RUN`. Sem afirmação de melhoria do SA.

> **Próxima etapa formalizada:** [plano de calibração Jev × SA/QA](SA-ANALISE/PLANO-CALIBRACAO-JEV-SA-QA.md) define referência independente (fonte+PNG agentico, regra determinística ou abstenção), pacotes automáticos de conflitos CAD por classe, perguntas/controles e comparação pareada do fluxo completo com e sem Jev. Adjudicação atual e futura é agentica; caso indeterminado permanece indeterminado.

> **Implementação incremental em 29/09:** `qa_evidence_auditor.py review` aceita
> pacotes Jev opt-in vinculados ao DXF Fase-1 e ao hash do snapshot N1. O
> helper executa Choice, Noul e Score independentes com controle de retirada,
> e o bridge grava sinais consultivos sem alterar score QA. O microteste local
> L410 encontrou Choice/controle coerentes e Noul contraditório; o estado
> correto do conjunto é revisão, não aprovação. Procedimento e relatório:
> `docs/SA-ANALISE/JEV-SEGUNDA-LEITURA-OPCIONAL.md` e
> `scripts/arete/relatorios/20260929_jev_qa_bridge_l410_integrated_v2/RELATORIO.md`.

Atualização: 2026-09-29. Coordenação: Astra com CEO-Planejamento/Athena. Estado: investigação das quatro classes consolidada; [manual de uso opcional](SA-ANALISE/JEV-SEGUNDA-LEITURA-OPCIONAL.md) e CLI de segunda leitura disponíveis. Registro de medição: [JEV-CAPACIDADES-E-REGISTRO-DE-MEDICAO.md](SA-ANALISE/JEV-CAPACIDADES-E-REGISTRO-DE-MEDICAO.md).

## Estado de execução — 2026-09-29 (colisão de parede LV, follow-up)

Relatório: [`scripts/arete/relatorios/20260929_jev_lv_source_wall_ownership/RELATORIO.md`](../scripts/arete/relatorios/20260929_jev_lv_source_wall_ownership/RELATORIO.md). Inventários v3 reutilizados (SHA inalterados). **Sem API Jev.** v3 **não** foi modificado para forçar pacotes. `parity_claimed=false`.

| Gate | Estado | Nota |
|---|---|---|
| **Colisão fonte** | cumprido | 13_PAV 130 paredes / 24 pares / 568 encontros. 14_PAV 132 / 20 / 720. Categorias: over-expanded 102+102, joint 28+30, unresolved interior **0**. |
| **312/313** | classificado | Colisão V423×V424; só V424 na faixa; V419 não lista. Over-expansion + atribuição surpreendente. |
| **Choice de dois nomes** | 0 elegíveis | CAD limitado confirmou a classificação. API não chamada (0/8). |
| **Protocolo cego 1 outcome** | **executado v5 30/09** | n=4, 8 chamadas. Jev=CAD 3/4; controlo INSUFFICIENT 4/4; V420 `2F8` norte abstém. PNG UNVERIFIED. Benefício false. |
| **G4** | **NOT_RUN** | Sem pacote N1 válido. Sem selo. |

**Próximo FAIL:** definir se a tolerância de extremo PASSA entra como FACT explícito (caso V420 `2F8` norte, continuação `770` Δy=5); G1 PNG continua não medido. Expansão da faixa fonte (over-expansion) permanece CAD, independente desta amostra Jev.

## Estado de execução — 2026-09-29 (catalog v3 LV source-first)

Relatório: [`scripts/arete/relatorios/20260929_jev_catalog_v3_lv_source_encounter/RELATORIO.md`](../scripts/arete/relatorios/20260929_jev_catalog_v3_lv_source_encounter/RELATORIO.md). Fábrica `0.6.0-lv-source-encounter`. **Sem API Jev.** 14_PAV congelado = regressão. `parity_claimed=false`.

| Gate | Estado | Nota |
|---|---|---|
| **G0** | manifesto | 13_PAV DXF/N1 iguais ao closeout. 14_PAV DXF/estado MATCH às cópias congeladas. |
| **Inventário fonte** | cumprido | 13_PAV: 31 rótulos / 392 paredes / 784 encontros. 14_PAV: 27 / 484 / 968. N1 só no sidecar. |
| **G2** | fail-closed | packed **0**, `N1_DECISION_RELEVANT` **0**. V420 `2F8`/`2F5`/`2F9` = dois encontros cada. Cover N1 não é PASSA. |
| **G1** | não reivindicado | Sem pacote visual. Uma sessão ≠ dois revisores. |
| **G4** | **NOT_RUN** | Sem pacote N1 válido. Stage 2 Jev não justificado. |

## Estado de execução — 2026-09-29 (catalog v2 LV face×behavior)

Relatório original (artefatos preservados): [`scripts/arete/relatorios/20260929_jev_calibracao_catalog_v2_lv_cell/RELATORIO.md`](../scripts/arete/relatorios/20260929_jev_calibracao_catalog_v2_lv_cell/RELATORIO.md). **Correção independente:** [`scripts/arete/relatorios/20260929_jev_catalog_v2_lv_independent_audit/RELATORIO.md`](../scripts/arete/relatorios/20260929_jev_catalog_v2_lv_independent_audit/RELATORIO.md). Fábrica vigente `0.5.1-lv-cell-encounter-failclosed`, catálogo `v2-2026-09-29-lv-cell-encounter-failclosed`. Os 13 pacotes 14_PAV `N1_DECISION_RELEVANT` da fábrica `0.5.0` foram **retirados** (PARA e PASSA em extremos opostos não são Choice da mesma célula). Dry-run corrigido packed **0**. Catálogo v1 permanece regressão (`--catalog v1`). **Sem API Jev.** `parity_claimed=false`. G1 independente **não** reivindicado.

| Gate | Estado | Nota |
|---|---|---|
| **G0** | cumprido | 13_PAV DXF/N1 iguais ao closeout. 14_PAV DXF/estado MATCH às cópias congeladas. |
| **G2** | fábrica v2 fail-closed | LV 14_PAV corrigido: scanned 30, packed **0**, `N1_DECISION_RELEVANT` **0**. V420 `2F8`/`2F5`/`2F9` → `para_and_passa_on_distinct_encounters`. V419 continua `no_dxf_line_matches_n1_cell`. |
| **G1** | incompleto | PNG da rodada 0.5.0 existem; não são selo. Sem consenso G1, sem revisor fresco nesta correção. |
| **G4** | **NOT_RUN** | Sem pacote N1 válido. |
| **G5** | fechado | Sidecar opt-in; sem escrita N1. |

Não há afirmação de melhoria do SA. G4 continua bloqueado.

## Estado de execução — 2026-09-29 (cobertura closeout)

Relatório: [`scripts/arete/relatorios/20260929_jev_calibracao_cobertura_closeout/RELATORIO.md`](../scripts/arete/relatorios/20260929_jev_calibracao_cobertura_closeout/RELATORIO.md). Dry-runs read-only já gravados (`dryrun_13pav_full`, `dryrun_14pav_full`); **sem API Jev** nesta rodada. 14_PAV congelado = regressão, não holdout. `parity_claimed=false`.

| Gate | Estado | Nota |
|---|---|---|
| **G0** | cumprido | Manifestos com SHA DXF/N1/módulos. 13_PAV vs registro VPS 25/09: MISMATCH (outro pavimento). 14_PAV DXF/estado/projeto MATCH às cópias congeladas; módulos SA locais MISMATCH às cópias 25/09. |
| **G1** | parcial no piloto G3/G4; **este closeout não adicionou G1** | O piloto [`20260929_jev_calibracao_g3_g4_pilot`](../scripts/arete/relatorios/20260929_jev_calibracao_g3_g4_pilot/RELATORIO.md) já tem duas revisões cegas (`g1_adjudication_after_png.v2.json` e `second_blind_review.json`). Acordo geométrico em V420 (`LINE_2F5`) e em L410 (nível N1 do item indeterminado). **Sem consenso** em V411 (`INSUFFICIENT` vs `LINE_315`) e **sem ownership N1** de célula. A pasta de closeout não rodou `g1-render` nem gerou PNG novo. |
| **G2** | cumprido na fábrica | Universo PIL+LV+FV+LAJ: 13_PAV 149/11 packed, 14_PAV 117/15 packed. 26/26 JSON validam. PIL 0, FV 0. |
| **G3** | catálogo v1 existe; execute do closeout não correu | `v1-2026-09-29-g3-lv-polygon-context`. Pacotes do closeout validam localmente. Choice L410 histórico coerente com controle; Noul contraditório não reexecutado. |
| **G4** | A/B N1 significativo **NOT_RUN** | O piloto G3/G4 tem só comparação diagnóstica do mesmo agente (`g4_paired.v2.json`, `g4_formal: NOT_RUN`). Os 26 pacotes do closeout são `CAD_REDUNDANT` ou `CONVENTION_INDETERMINATE` e não sustentam A/B de campo N1. |
| **G5** | fechado | Sidecar opt-in; SA opera sem API; sem escrita N1. |

O que destravaria A/B N1: pacote `N1_DECISION_RELEVANT` (PIL com rótulo único + loop fechado; FV claim **e** contorno por segmento; pergunta LV A/B × PARA/PASSA com linha DXF da célula — V419 hoje `no_dxf_line_matches_n1_cell`); regra determinística de desnível LAJ confirmada por consenso agentico fonte+PNG, ou o caso permanece `CONVENCAO_INDETERMINADA`; G1 com consenso em ownership N1; prompts congelados. O segundo revisor cego do piloto **não** sela V411 nem N1. Detalhe e matriz no RELATORIO do closeout.

> **Critério corrigido pelo dono em 29/09:** Jev não precisa “superar” SA, CAD ou QA isolados. Seu valor é **somar** uma leitura rápida e específica, com abstenção e controles, ao sistema combinado. O gate de superioridade isolada que aparece em registros históricos deste plano não governa o uso opcional de desenvolvimento. Produção automática continua exigindo evidência de segurança e benefício no fluxo completo.

> **Correção de baseline:** os experimentos iniciais do 14_PAV usaram uma cópia SQLite e um DXF locais que não são o projeto/fonte da execução produtiva da VPS. O [relatório de paridade com a VPS](../scripts/arete/relatorios/20260924_jev_14pav/vps_parity/RELATORIO.md) é a referência para o snapshot de 25/09: 31/31 dimensões PIL simples já corretas no SA, 20/22 níveis LAJ no estado produtivo, 33 vigas, 27 contratos LV anexados. Oportunidades de completude medidas apenas na cópia local não devem ser vendidas como lacunas da VPS.

**Decisão vigente:** não trocar o motor de interpretação por Jev nem chamar Jev em todo item. Na fonte produtiva, PIL 31/31 e LAJ 15/15 escolhas elegíveis empataram com CAD; dez negativos PIL tiveram escolhas erradas sem abstenção. O ganho implementável é um **cruzamento de evidências em QA**, primeiro em modo paralelo: valor SA versus texto DXF com handle, posição, contorno e ficha PNG para conflitos; em LV, comparar cada célula com o FV da própria viga antes de `generation_ready`. O caso L410 já foi detectado: SA `855.22`, texto direto junto ao rótulo `855.25`, Jev e regra CAD concordam com o texto direto. O DXF confirma que `855.22/h=11` ficam sobre um `SOLID` cinza e `855.25/L410 h=14` na região principal; ainda falta validar a convenção de desnível. Em LV, V419/V420 têm células remotas que chegam prontas aos contratos produtivos; Jev acrescentou uma segunda checagem coerente para dois exemplos e um controle; o CAD localiza geometricamente o problema. Em FV, V414/VF402 repetem contagens globais nas fichas por segmento sem evidência de contagem local. O código local diverge semanticamente da VPS em `beam_tracer.py`, `fundo_viga.py` e `analise_geral_headless.py`; qualquer correção deve fixar manifesto, hash dos módulos, DXF e snapshot N1 do ambiente que alimenta o portal.

**Consulta dinâmica já testada:** em L410, a pergunta Jev sem os textos locais `h=` absteve-se; com `L410 h=14` e o concorrente `h=11`, escolheu `855.25`. Ao remover o marcador `855.25` e deixar o concorrente no contorno, absteve-se. A regra de proximidade simples falha nesse controle; uma regra CAD com pareamento `h=` também passa. Portanto, a função demonstrada de Jev é segunda checagem contextual barata (~0,25 s por pergunta neste probe), acionada por conflito e sempre sujeita ao gate CAD/PNG. [Counterfactual](../scripts/arete/relatorios/20260924_jev_14pav/vps_parity/l410_jev_height_counterfactual.json).

Não impor `h=` como regra universal: em somente 7 dos 15 candidatos diretos LAJ da VPS o marcador ficou a até 60 unidades do texto `h=` correspondente. A expansão semântica entra quando há conflito ou níveis concorrentes, preservando a cobertura simples nos outros casos.

O [roteador sombra](../scripts/arete/relatorios/20260924_jev_14pav/vps_parity/dynamic_router_shadow.json) evita consultas PIL de rotina e classifica 22 pendências do 14_PAV produtivo: uma LAJ pronta para segunda pergunta Jev + visão, sete LAJ que precisam de mais fonte, nove LV em revisão geométrica por célula, três LV em revisão de flag/visual e duas FV com contagem repetida sem proveniência local. O [detector LV](../scripts/arete/relatorios/20260924_jev_14pav/vps_parity/lv_cell_geometry_audit_vps.json) sinalizou 32 células lineares `Para` A/B em nove vigas e um registro lateral inválido; esses números são triagem, com V419/V420 confirmadas nas quatro fichas do snapshot. Jev reconheceu dois casos remotos, um controle coerente e um controle sem geometria. Em FV, absteve-se em oito de oito segmentos sem evidência de abertura local. Essa contribuição já justifica **uso opcional na investigação**. Automação de produto exige evidência de segurança e benefício no fluxo combinado (G4 N1), ainda `NOT_RUN`.

**Achados congelados 25/09 (histórico, não verdade N1):** V419/V420 como regressão visual e de quatro contratos; [A/B parcial no mesmo DXF](../scripts/arete/relatorios/20260924_jev_14pav/vps_parity/beam_tracer_ab_same_dxf.json) mostra que alterar orientação local ainda captura horizontais alheios em V420; V406, V413, V415, V416, V418, V421 e V422 seguem no denominador de triagem; FV V414/VF402 repetem `abertura_especial` sem proveniência por segmento; L410 tem [auditoria CAD](../scripts/arete/relatorios/20260924_jev_14pav/vps_parity/l410_physical_audit.json) e permanece `CONVENCAO_INDETERMINADA` após as duas revisões cegas do piloto. Artefatos read-only; nada publicado na VPS.

**Experimento `catalog-v2-lv-cell-ownership-source` (29/09):** executado; os 13 `N1_DECISION_RELEVANT` foram retirados na auditoria independente do mesmo dia. G4 permanece `NOT_RUN`. L410/L309/L319: abster. Zero rebuild de KB.

## Missão e fronteira

Testar se Jev melhora a **interpretação do Structural Analyzer (SA/N1)** a partir da planta estrutural em DXF e, quando útil, de SVG derivado da mesma planta. O comparador é o N1 produzido hoje. O resultado procurado são interpretações melhores dos campos e vínculos N1 nas classes PIL, FV, LV e LAJ. O 13_PAV da Obra_TREINO_1 é o conjunto de desenvolvimento desta rodada.

O schema N1 é imutável. O Jev produz propostas rastreáveis em arquivos separados, sem escrita automática no N1. O SA atual é o baseline operacional. O plano trata da leitura da planta estrutural; geração de desenhos e engenharia reversa não são tarefas deste projeto Jev.

## Capacidades técnicas confirmadas

Jev da TypeSafe AI recebe texto ou JSON e responde perguntas fechadas por Choice, Score ou Noul. A versão usada no piloto é `jev-1.13.0`, pela API. Ela não recebe pixels/imagens e não oferece fine-tuning dos pesos com dados do cliente. A adaptação de domínio vem do estado e das perguntas; aprendizagem supervisionada persistente, se útil, será implementada pelo nosso sistema. [Introdução](https://docs.typesafe.ai/introduction), [modelos](https://docs.typesafe.ai/models).

O fornecedor documenta fraquezas em precisão numérica, contagem e contexto irrelevante. Logo, código CAD calcula coordenadas, transformações, dimensões, distâncias, contato e continuidade; Jev escolhe entre candidatos semânticos concretos. `confidence` resume a distribuição de opções e precisa de calibração com casos do SA antes de orientar ações. [Limitações](https://docs.typesafe.ai/model-jaggedness/jev-1.13), [confiança](https://docs.typesafe.ai/confidence).

“Teste local” significa que parsing, comparação, cache, relatórios e eventual modelo supervisionado rodam na workstation. A inferência Jev usa a API. A credencial fornecida pelo dono foi lida do `.env` pelo SDK e não foi copiada para código ou relatório.

## Primeiro experimento real: dimensão de pilar

O harness read-only [jev_pil_dim_pilot.py](../scripts/arete/jev_pil_dim_pilot.py) abriu um DXF estrutural pequeno, selecionou textos locais, construiu JSON CAD e um SVG **textual** novo da mesma fonte. Comparou o valor N1 com regras determinísticas e Jev. A referência de dimensão veio exclusivamente dos quatro cantos do polígono CAD para pilares retangulares simples; nenhum outro pipeline serviu de gabarito.

| Braço | Acertos em 41 pilares retangulares elegíveis |
|---|---:|
| Dimensão textual N1 atual | 31 |
| Regra: texto de dimensão mais próximo na layer pertinente | 35 |
| Regra: texto coerente com contorno calculado | 41 |
| Jev com JSON estruturado | 41 |
| Jev com SVG textual compacto | 39 |
| Jev com SVG textual convertido para JSON | 40 |

O universo SA consultado contém 46 pilares; cinco ficaram fora desse probe devido à referência geométrica restrita. O Jev JSON corrigiu dez dimensões textuais N1 incorretas, inclusive casos em que o nome `P20` ou o texto `2.5` ocupava o campo de dimensão. A regra geométrica também resolveu os dez. **Nesta tarefa ainda não há ganho incremental demonstrado do Jev**. O SVG textual errou P18 e P24, escolhendo textos de vigas próximas. Entre 41 chamadas por formato, a latência mediana foi ~0,24 s; JSON consumiu 67.339 tokens de entrada, SVG 48.149; leitura do DXF levou ~0,17 s. [Resultados por item](../scripts/arete/relatorios/20260924_jev_pil_dim_pilot/jev_41.json).

Esses números são de desenvolvimento no pavimento já trabalhado. A referência geométrica não aprova face, viga, laje ou pilar especial. O cabeçalho DXF indica `$INSUNITS=6`, enquanto os comprimentos numéricos seguem a prática da obra; antes de qualquer aplicação N1, auditar essa convenção. O piloto encontrou valores N1 incorretos mesmo quando o campo tinha marca de validação, portanto o marcador não substitui conferência da planta.

Os SVGs de ficha já existentes que foram inspecionados vêm de etapas derivadas do SA e representam textos como paths de glifos. Eles não são fonte independente para julgar o N1 e não fornecem `<text>` legível ao Jev. O braço SVG deste experimento é reconstruído do **DXF estrutural**, com textos reais, posições e IDs. Uma terceira variante faz parse desse SVG para JSON, preservando retângulo-alvo e elementos `<text>`; ela errou P24. [Resultado SVG→JSON](../scripts/arete/relatorios/20260924_jev_pil_dim_pilot/svg_json_41.json). Ainda exige auditoria completa de transformações e camadas.

Teste negativo: após remover dos candidatos todos os textos compatíveis com o contorno, Jev JSON se absteve em 2/10, SVG textual em 4/10 e SVG→JSON em 4/10; nos demais escolheu outro texto, frequentemente de viga. Isso impede usar a escolha Jev isolada como correção N1. A regra geométrica recusou os dez casos, como esperado. [Dados dos testes negativos](../scripts/arete/relatorios/20260924_jev_pil_dim_pilot/negative_10.json), [SVG→JSON](../scripts/arete/relatorios/20260924_jev_pil_dim_pilot/svg_json_negative_10.json).

## Rodada adicional: PIL, FV, LV e LAJ

O auditor QA canônico, em modo somente leitura, produziu 1.737 decisões de campo para 149 itens-classe: 46 PIL, 36 FV, 36 LV e 31 LAJ. **Fato histórico do log QA (não gabarito N1):** 79 revisões humanas e 2 pendências em PIL, 52 pendências em FV e 12 em LV; LAJ teve 248 confirmações de campo. Esses estados **não** certificam visualmente um item inteiro. [Evidência QA](../scripts/arete/relatorios/20260924_jev_allclasses_qa_baseline/decisoes.jsonl).

Vinte probes de campo do QA (cinco por classe) foram convertidos em estados JSON pequenos para o Jev **sem enviar veredito, status ou motivo**. Ele confirmou 6/9 probes PASS, reteve 3/9 PASS e não confirmou nenhum dos 11 FAIL/PENDENTE. Não houve erro técnico. Isso testa triagem dos checks já montados, não interpretação independente da planta; executar o QA determinístico é mais direto para esses mesmos checks. [Resultados](../scripts/arete/relatorios/20260924_jev_allclasses_qa_baseline/jev_probe_20.json).

No teste LAJ, os 31 rótulos de laje foram encontrados uma vez no DXF original. O Jev recebeu cada rótulo e textos `h=` próximos, sem o valor N1 no estado. JSON direto escolheu o mesmo texto do N1 em 5/31 e se absteve em 26/31. Ao converter os mesmos textos para um SVG semântico e fazer parse do SVG para JSON, concordou com o N1 em 31/31. Essa divergência radical de apresentação é um risco de robustez; concordância com N1 não é gabarito. Em L309, o contorno N1 abrange dois `h=` de áreas vizinhas, enquanto a leitura do recorte do DXF associa o `h=13` ao rótulo L309. Este caso é evidência de que contenção geométrica isolada é insuficiente, não de que Jev tenha corrigido um erro. [Casos LAJ](../scripts/arete/relatorios/20260924_jev_allclasses_qa_baseline/jev_laj_31.json), [recorte DXF](../scripts/arete/relatorios/20260924_jev_allclasses_qa_baseline/L309_source.png).

As 36 vigas são registros-fonte compartilhados pelos contratos FV e LV. O teste bruto procurou um rótulo único da viga e até oito textos de seção no raio de 240 unidades CAD: 35 vigas elegíveis, uma com dois rótulos excluída. O Jev se absteve em 35/35. A pergunta de proximidade não modela todos os segmentos e seções FV/LV; logo este resultado não reprova todas as hipóteses semânticas de viga, mas também não fornece ganho para a tarefa proposta. [Casos de viga](../scripts/arete/relatorios/20260924_jev_allclasses_qa_baseline/jev_beam_36.json).

**Decisão desta rodada:** não substituir o motor SA/N1 nem promover correções Jev para produção. PIL dimensão mostrou empate com regra CAD e falha relevante de abstenção; FV/LV não mostraram escolha útil de seção; LAJ mostrou forte sensibilidade ao formato; a triagem QA não superou o QA que já possui os fatos. Esse foi o veredito inicial da rodada ampla; a decisão de 29/09 permite Jev como ferramenta consultiva opcional em perguntas específicas, mantendo referência independente para qualquer automação. [Relatório da rodada](../scripts/arete/relatorios/20260924_jev_allclasses_qa_baseline/RELATORIO.md).

## Prova adicional em 14_PAV da mesma obra

O snapshot N1 de `d4f298ab-1658-4e60-898d-ec666d54ba8c` tem 35 nomes PIL, 37 registros de vigas e 22 LAJ, todos com `is_validated=0`. Dos 35 pilares, 33 passaram no critério estrito de retângulo simples; os 33 campos textuais `dim` estavam vazios. Jev com DXF→JSON e regra CAD escolheram o mesmo texto/handle coerente com o polígono em 33/33. SVG textual e SVG→JSON fizeram 31/33. Nas dez perturbações que retiraram o texto correto, Jev JSON **não se absteve nenhuma vez** e escolheu uma seção de outra entidade; a regra recusou dez. Portanto, existe oportunidade de **completude de dimensão**, mas o ganho veio da extração/validação geométrica, não de inteligência incremental Jev.

Em LAJ, `h=` já está preenchido em 22/22 N1. JSON direto Jev concordou com N1 em 2/21 lajes de rótulo único, abstendo-se nas demais; SVG→JSON concordou em 21/21. Em vigas, houve 31/31 abstenções elegíveis na pergunta de seção próxima. A auditoria QA encontrou 1.738 decisões de campo, muitas pendências de relação/segmento; o Jev reproduziu PASS/HOLD de 17 probes processáveis, sem resolver a ambiguidade de registros PIL repetidos. Inspecionei visualmente os SVGs exatos enviados ao Jev e recortes DXF de P18/P48: os textos de viga próximos explicam os erros do braço SVG. [Relatório e imagens](../scripts/arete/relatorios/20260924_jev_14pav/RELATORIO.md).

**Conclusão após 14_PAV:** manter o veto à substituição do SA e ao preenchimento Jev sem validador. A hipótese ainda aberta é Jev como desempate semântico em contatos/segmentos cuja topologia CAD tenha sido calculada; ela precisa de benchmark visual próprio. O 14_PAV é externo ao piloto 13_PAV, mas da mesma obra e não constitui validação prospectiva independente de padrões já conhecidos.

## Arquitetura híbrida: todas as forças cooperam

O objetivo de produto é **SA + CAD determinístico + visão + Jev + QA + aprendizagem local**, com responsabilidade diferente para cada fonte. Uma regra perfeita num campo não elimina Jev do sistema: ela libera Jev para as ambiguidades que restam. Tampouco uma resposta Jev elimina a inspeção do desenho. O modelo opera como componente consultivo que propõe, explica a trilha de handles e ajuda a priorizar revisão. O contrato de fusão conserva todas as leituras, inclusive discordâncias e abstenções, em vez de reduzir o item a um score único.

| Componente | Contribuição | Limite que o próximo componente cobre |
|---|---|---|
| SA/N1 atual | Detecta itens, persiste polígonos e relações já inferidas | Campos vazios, identidades duplicadas e vínculos com revisão pendente |
| Extrator CAD + regras | Medidas, topologia, contato e candidatos rastreáveis por handle | Ambiguidade semântica entre textos, detalhes e relações |
| SVG semântico + PNG full-layer | Mesmo desenho em estrutura consultável e pixels para inspeção visual; recortes locais e contextuais | SVG textual isolado pode omitir linework ou continuação fora do recorte |
| Jev | Escolhe entre candidatos e pode ligar referências explícitas entre documentos | Sensibilidade ao formato e tendência a escolher outro texto quando a prova falta |
| QA canônico + revisão agentica fonte+PNG | Aponta campos pendentes e resolve conflitos sobre a planta completa | Não é gabarito automático de todos os campos de um item; logs QA com revisão humana histórica são triagem |
| ML local | Aprende de decisões agenticas com prova CAD/PNG e consenso, ou de regra determinística | Requer corpus versionado e avaliação separada por obra/desenho; caso indeterminado fica fora do treino |

Primeiro protótipo de fusão: [sidecar do 14_PAV](../scripts/arete/relatorios/20260924_jev_14pav/hybrid_fusion_14pav.json), gerado por [script reproduzível](../scripts/arete/jev_sa_vision_fusion_pilot.py). Ele reúne 33 propostas de dimensão PIL, duas verificações visuais pontuais, dez controles negativos recusados, 22 estados LAJ de altura, 15 propostas de nível textual, sete lajes sem texto de nível interno, 37 estados de viga, quatro alertas de escopo FV e fila de 99 itens-classe com campos QA não resolvidos. Nenhum desses estados grava ou aprova o N1.

A [rodada LAJ de nível](../scripts/arete/relatorios/20260924_jev_14pav/hybrid_laj_level_22.json) identificou em 15/22 lajes um texto `855.xx` interno ao polígono N1, com handle do DXF original. Jev e regra CAD de texto interno mais próximo escolheram **os mesmos 15 handles**; Jev se absteve em 7/22 e em 5/5 controles sem texto interno. Assim, há candidato útil para completar N1, mas a evidência atual favorece implementar primeiro a recuperação geométrica auditável; Jev só entra se reduzir erros ou revisão quando houver ambiguidades reais. L401/L410 tiveram inspeção visual pontual. **Fato histórico:** essa inspeção pontual não sela as 15 lajes. Aprovação futura exige consenso agentico fonte+PNG ou regra determinística; sem isso o caso permanece indeterminado.

Em [L401/L410 com ordem de candidatos invertida](../scripts/arete/relatorios/20260924_jev_14pav/hybrid_laj_level_stability.json), Jev manteve os handles; sem polígono e sem indicador de contenção absteve-se em ambos. Isso apoia seu uso como checagem de evidência, mas é uma ablação de apenas dois itens e não satisfaz o gate de valor incremental.

O [auditor FV de escopo](../scripts/arete/relatorios/20260924_jev_14pav/hybrid_fv_scope_audit.json) encontrou quatro vigas multissegmentadas com a mesma contagem de `abertura_especial` repetida em todas as fichas locais, enquanto os contatos geométricos locais variam ou são muito menores. É um alerta para recuperar abertura, apoio e origem **por segmento**, não veredito de erro: contato de pilar não é automaticamente abertura. A próxima pergunta Jev deve receber o segmento local completo, a lista de entidades que de fato tocam seu polígono e uma opção de abstenção; comparar com regra CAD e SVG/PNG full-layer. Para LV, preparar os quatro estados A/B × PARA/PASSA por célula, sem transportar interpretação FV.

**Caso multiarquivo P26/P27:** os rótulos da planta apontam `VER DET.`; no DXF separado de detalhes há o título `P26=P27` e dimensões externas 165×218. Jev ligou os dois nomes ao título e escolheu a linha N1 da forma em L de cada pilar quando recebeu as dimensões; nos controles sem título ou sem dimensões, absteve-se. A geometria CAD validou as medidas e a visão do PNG full-layer confirmou a forma em L. P26 ainda possui outra linha N1 de geometria menor sob o mesmo nome; a fusão **não a descartou** nem certificou faces/vigas. [Evidência de título](../scripts/arete/relatorios/20260924_jev_14pav/hybrid_special_detail_2.json), [evidência geométrica](../scripts/arete/relatorios/20260924_jev_14pav/hybrid_special_geometry.json), [imagem](../scripts/arete/relatorios/20260924_jev_14pav/hybrid_visual/P26_P27_detail_full.png).

**Caso de rótulo repetido L409:** duas entidades `TEXT` no DXF original dizem L409, mas apenas o handle `109E` está no contorno da laje persistida. Jev escolheu essa instância com o bbox e absteve-se quando o bbox foi retirado. O CAD confirmou contenção; a visão do desenho mostrou as duas ocorrências. Isso resolve a referência de uma instância sem eliminar a outra nem aprovar a laje inteira. [Teste](../scripts/arete/relatorios/20260924_jev_14pav/hybrid_l409_duplicate.json).

Próxima etapa híbrida: para cada campo pendente da fila QA, recuperar a região completa da face/segmento/aresta **e documentos referenciados** antes de perguntar ao Jev; produzir SVG navegável e PNG full-layer para visão agentica; calcular topologia no código; registrar propostas/discordâncias por campo. Casos com consenso agentico fonte+PNG (ou regra determinística) entram no corpus; discordância e convenção irresolúvel permanecem indeterminados. Medir o sistema combinado contra o SA atual e contra a mesma fusão sem Jev, preservando cobertura e taxa de erro crítico. Essa ablação quantifica a contribuição do Jev sem impor que ele resolva tudo sozinho.

## Arquitetura experimental

```text
planta estrutural DXF + hash
  → recuperador de fonte principal + DXFs de detalhes referenciados
  → extrator CAD local → entidades, textos, blocos, contornos e topologia
  → JSON CAD + SVG textual da fonte + PNG full-layer para visão agentica
  → SA atual + regras geométricas + Jev em candidatos rastreados
  → fusão com discordâncias, ausência de prova e QA por campo
  → propostas N1 em sidecar + ficha de revisão agentica
  → decisões agenticas com prova CAD/PNG → ML local e calibração por família
```

Contrato de entidade: arquivo/hash, handle e instância de bloco, tipo, layer, texto bruto/normalizado, coordenadas originais, OCS/WCS e matriz aplicada. Contrato de hipótese: item, face física, relação candidata, pontos de contato, continuidade, tolerância, fonte e decisão. Registrar entidades não suportadas e candidatos excluídos; não descartar silenciosamente dados importantes.

O Jev recebe somente o estado necessário à pergunta. Comparar trechos locais do DXF como texto, JSON CAD e SVG textual com **mesmos candidatos e mesma vizinhança**. Um recorte pequeno demais deve declarar contexto incompleto, pois a viga pode continuar além da janela. O SVG só é válido se preservar texto CAD, handles e transformação DXF↔SVG; SVG renderizado a partir de um resultado N1 não serve de entrada independente.

Perguntas fechadas prioritárias para PIL:

| Família N1 | Pergunta | Resposta permitida |
|---|---|---|
| Identidade | Qual texto rotula este volume? | Handle / INSUFFICIENT |
| Dimensão | Qual texto descreve a seção do pilar? | Handle / INSUFFICIENT |
| Face/canto | Onde a relação toca o contorno físico? | Face/canto candidato / INSUFFICIENT |
| Viga | Qual viga rotulada corresponde ao contato? | ID candidato / NONE / INSUFFICIENT |
| Papel da viga | Ela CHEGA, PASSA ou é INTERIOR? | Opção fechada / INSUFFICIENT |
| Laje | Existe laje nomeada em contato com esta face? | ID candidato / NONE / INSUFFICIENT |
| Nível/anotação | Qual campo ou elemento recebe o texto? | Opção fechada / INSUFFICIENT |

NONE significa ausência sustentada por evidência; INSUFFICIENT indica evidência insuficiente. Timeout/API indisponível é erro técnico separado. Uma face pode ter múltiplos vínculos: perguntar por candidato/slot e combinar no código. Nenhuma pergunta pede ao modelo para inventar coordenadas, dimensões ou nomes.

Contratos de pesquisa das demais classes, cada um isolado da resposta N1 correspondente:

| Classe | Unidade da pergunta | Fatos preparados em código | Saída fechada candidata |
|---|---|---|---|
| FV | Segmento de fundo, início/fim, abertura ou apoio | Eixo, contorno, cortes, interseção, medidas, textos e handles locais | ID/posição de apoio, presença de abertura, seção textual, NONE/INSUFFICIENT |
| LV | Cada lado e segmento do contrato lateral | Orientação local, pilares/lajes vizinhos, contatos por lado e referências cruzadas | Entidade por lado, tipo de relação, NONE/INSUFFICIENT |
| LAJ | Rótulo, altura e cada aresta de apoio | Contorno, rótulos `h=`, distância, adjacência e topologia de borda | Handle de altura, entidade de apoio por aresta, NONE/INSUFFICIENT |

Não condensar uma viga inteira em uma pergunta de seção próxima: o teste inicial de 35 vigas se absteve em todas. Para FV/LV, a recuperação de candidatos deve cobrir o segmento completo antes de solicitar Jev. Para LAJ, repetir o mesmo conjunto com JSON direto e SVG→JSON e exigir estabilidade entre formatos ou abstenção rastreável; 31/31 de concordância com N1 após SVG não basta.

## Desenho de avaliação

Congelar o N1 atual por versão/hash. Usar o CAD original e verificações geométricas reproduzíveis como referência onde a resposta é exata. Ambiguidades de face e vínculo recebem leitura agentica PNG+fonte, com handles citados; sem consenso ou sem regra determinística o caso permanece indeterminado. Campos N1 validados são pistas, não verdade automática. Inventariar os 46 pilares, subtipos e itens eventualmente omitidos; reportar resultados também sobre o denominador completo, pois avaliar só os candidatos recuperados esconderia falhas de detecção.

Comparar braços pareados e **ablar componentes da fusão**: A=N1 atual; B=SA+CAD/regras; C=B+visão/revisão agentica; D=C+Jev em JSON; E=C+Jev em SVG textual/convertido; F=C+ML local; G=C+ML local+features Jev. A meta é medir quanto cada força acrescenta ao conjunto, inclusive recuperação de evidência, taxa de conflitos resolvidos e tempo de revisão agentica, mantendo cobertura e custo comparáveis. Na dimensão retangular, B e D empataram; investigar Jev nas relações de face/viga e nas referências a detalhes, onde a semântica e a busca entre documentos são mais relevantes.

Casos de teste por tarefa: positivos, negativos de ausência real, vigas próximas mas sem contato, múltiplas vigas, CHEGA versus PASSA, faces curtas/longas, cantos, pilares especiais e contextos incompletos. Congelar perguntas antes de medir o lote reservado. Verificar ordem dos candidatos, anonimização de IDs, instruções PT/EN, retirada de layer e variação da janela. O 13_PAV já influenciou o SA; ele é conjunto de desenvolvimento/regressão. Generalização só será avaliada prospectivamente em pavimento/obra ainda não usados, conforme escopo incremental do projeto.

Métricas: precisão/recall por campo e subtipo; itens omitidos; face+canto+entidade corretos; matriz CHEGA/PASSA; erro entre respostas aceitas; taxa de abstenção; tempo de revisão agentica por item; latência p50/p95 do pipeline completo; memória, tokens e custo por acerto. Comparar cobertura equivalente para não premiar um modelo que apenas se abstém mais. A confiança Jev deve ser calibrada por família; erro de relação aceito com confiança alta é falha crítica.

## Aprendizagem e gates

Registrar cada predição antes da correção, decisão agentica independente (fonte+PNG), entidade/face/canto, fonte CAD, versão de parser/SA/Jev/pergunta e motivo. Não treinar em respostas Jev tratadas como verdade. Agrupar todas as faces, recortes e transformações do mesmo item/desenho no mesmo split. Começar com regras/ranking simples e, se houver volume, regressão logística ou árvore pequena; comparar geometria versus geometria+Jev. Aprendizagem ativa prioriza desacordos SA×regra×Jev e casos raros, mas audita também amostra aleatória de respostas confiantes. [Exemplo oficial de Jev como feature de ML externo](https://docs.typesafe.ai/cookbooks/autoresearch_feature_discovery).

Gates próprios da exploração:

1. **J0 Dados:** fonte, versão, unidades, universo e baseline N1 identificados.
2. **J1 Fidelidade:** JSON/SVG preservam texto, handles, geometria e transformação necessária.
3. **J2 Qualidade:** comparação pareada por tarefa, com negativos e sem novo erro crítico aceito.
4. **J3 Complementaridade:** mostrar em quais dúvidas Jev confirma, contesta ou pede mais evidência de forma útil ao QA; registrar controles e custo. Vitória exclusiva sobre CAD não é requisito.
5. **J4 Aprendizagem:** ganho em casos não usados no ajuste, sem vazamento.
6. **J5 Integração:** propostas N1 revisáveis por campo e sem regressão ao baseline.
7. **J6 Expansão:** cada nova classe tem perguntas, evidência e benchmark próprios.

Para **uso opcional de desenvolvimento**, basta uma pergunta localizada, evidência rastreável e comportamento seguro nos controles: o agente decide se a segunda leitura ajuda aquele caso. Para **automação de produto**, medir o fluxo completo com e sem Jev em qualidade, cobertura, carga de revisão, latência e custo; não aceitar novo erro crítico. Em tarefas triviais em que Jev apenas repete uma regra, o roteador economiza a chamada. O antigo limiar exploratório de 20% não é obrigação para manter Jev como ferramenta consultiva.

## Operação, Rust e próximos passos

Executar pela CLI em Python 3.12, banco em read-only, artefatos novos por rodada, cache por hash de estado+pergunta+modelo e versão Jev fixa. Não aplicar alterações N1 durante o piloto. Em falha da API, manter o SA atual e registrar falha. Credenciais só no ambiente; chamadas remotas recebem a vizinhança mínima do CAD. Não usar comandos Git sem autorização expressa do workspace.

O DXF do piloto carregou em ~0,17 s; logo Rust não é gargalo demonstrado nessa amostra. Só considerar parser/kernel Rust após perfil em plantas maiores e prova de equivalência de blocos, textos, coordenadas e transformações. JSON estruturado pode ser gerado em Python.

Backlog executável:

1. **Congelamento e referência:** registrar hash do DXF, snapshot N1 e universo por classe; auditar unidades. Adjudicar campos ambíguos com dois agentes independentes sobre recortes do DXF bruto (PNG full-layer), inclusive negativos e itens que o SA omitiu; regra determinística quando a geometria decide; senão `INDETERMINADO`. Não derivar verdade de `validated` ou de saída QA de campo.
2. **Extrator neutro:** implementar entidades CAD→JSON com handle, texto, layer, posição e transformações; gerar SVG textual opcional e validar sua conversão de volta a JSON. Registrar o que ficou fora da janela e permitir expansão até cobrir o segmento/topologia necessária. O piloto usa Python; medir gargalo antes de Rust.
3. **Tarefas por classe:** PIL face/viga/laje e especiais; FV apoios, abertura e dimensão por segmento; LV quatro contratos laterais e referências; LAJ altura, contorno e apoio por aresta. Definir candidatos no código, Choice com NONE/INSUFFICIENT e decisões por campo em sidecar.
4. **Benchmark pareado:** rodar A–G com mesma recuperação de candidatos e negativos, congelando perguntas antes do teste reservado. Revisar falsos positivos de alta confiança e discordâncias; medir acurácia em cobertura equivalente, tempo de revisão agentica, tokens e p95 de ponta a ponta. G4 N1 só com pacotes `N1_DECISION_RELEVANT` e consenso G1.
5. **Aprendizagem:** incluir somente decisões agenticas com prova CAD/PNG e consenso, ou regra determinística, com proveniência e versionamento. Primeiro modelo local pequeno com CAD; segundo modelo com CAD+saídas Jev. Split por desenho/obra e teste prospectivo; usar ablação para decidir se Jev vale custo/risco. Casos indeterminados ficam no teste de abstenção.
6. **Gate de produto:** começar com sidecar opt-in no QA, com SA preservado. Promover automação apenas se o sistema combinado mostrar contribuição útil sem erro crítico novo e com reversibilidade; onde a consulta for redundante, desativar aquele gatilho, sem encerrar Jev para outras dúvidas.

Cada rodada produz relatório por item, denominadores, acertos, regressões, abstenções, origem da referência (fonte+PNG / regra / abstenção) e próximo experimento. Os pilotos atuais cumprem o reconhecimento técnico; **não** cumprem o gate de verdade independente para FV/LV/LAJ nem o de generalização.

A investigação de **posição e uso** está encerrada: Jev entra como segunda leitura opt-in no Eixo B, com evidência compacta, controle e sidecar; nenhuma classe recebe preenchimento automático por Jev. Futuros estudos de face/viga e CHEGA/PASSA podem calibrar gatilhos mais específicos, mas não bloqueiam o uso opcional já documentado. Treino ML e automação de produto permanecem etapas distintas, dependentes de consenso agentico fonte+PNG (ou regra determinística) e da avaliação do sistema combinado.


## Rodada LV v7 — 30/09/2026

[Conclusão, evidência visual e recomendação consultiva](../scripts/arete/relatorios/20260930_jev_lv_hybrid_adviser_v7/ANALISE.md).
Quatro chamadas reais em duas vigas do 14_PAV: concordância com a hipótese
geométrica em 2/2 e abstenção com retirada de evidência em 2/2; 4792 tokens
de entrada, mediana de latência por chamada 0,282 s. Não demonstra erro do SA
ou melhoria do fluxo. A agregação v6 por parede perde identidade do encontro;
as divergências são candidatas de investigação, nunca correções automáticas.
Manter segunda leitura opcional no QA/Eixo B e medir a ablação por encontro
antes de promover score ou integração no motor. Sem alteração N1, robôs ou VPS.


## Rodada LV v8 — correspondência por encontro

[Auditoria, revisão e próxima execução](../scripts/arete/relatorios/20260930_jev_lv_encounter_v8/REVISAO.md). Adaptador e auditor
read-only implementados; 47 testes passaram. A amostra contém 96 encontros
fonte e um registro de ausência de encontro. Zero pacotes elegíveis: 80
encontros retidos por identidade de projeto, 17 registros por identidade
de fonte. Zero novas chamadas Jev. Estes são impedimentos de comparação,
não erros do SA. O gate recomputa o hash do inventário e verifica a fonte
do baseline local; project_id igual não basta. A etapa seguinte exige
fonte e execução SA verificadas juntas, com apoios/face curta/miolo por
encontro. Paridade VPS atual e ganho do fluxo híbrido continuam não medidos.


## Rodada v9 — identidade VPS e baseline isolado

[Registro e artefatos](../scripts/arete/relatorios/jev_vps_identity_v9_20260930T140535Z/RELATORIO.md).
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
