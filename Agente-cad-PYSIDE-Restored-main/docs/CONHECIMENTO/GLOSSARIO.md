# Glossário — base global da empresa

**Status:** canônico · **Criado:** 2026-09-25 · **Escopo:** global

Uma linha por termo, com a fonte onde a definição completa mora (caminhos relativos a
`Agente-cad-PYSIDE-Restored-main/`). Se a fonte e esta linha divergirem, **vale a fonte**
— e esta linha deve ser corrigida. Termo novo entra aqui com fonte; sem fonte, não entra.

## Negócio e desenho

| Termo | Significado | Fonte |
|---|---|---|
| **Fôrma** | molde (chapas, sarrafos, garfos, madeira) que dá forma ao concreto de pilar, viga ou laje; o produto da empresa | `docs/interviews/*.md` |
| **Prancha / DXF de fôrma** | o desenho entregue à obra; hoje, o **N5** | `docs/MASTERPLAN-CONSOLIDACAO-ENTREGA.md` §1 |
| **STOG** | padrão de desenho das pranchas humanas da empresa; os geradores DXF reproduzem o conteúdo STOG no estilo dos robôs | `docs/HANDOFF-ARETE-EXECUTOR.md` v1.2 |
| **Robô SCR** | geradores legados em AutoCAD script (`.scr`) — definem o **estilo** de desenho que os geradores DXF portam | `docs/ROBO_SCR_PATTERNS.md`, `docs/ROBOS_GUIDE.md` |
| **Gerador STOG** | `scripts/gerar_{pl,lv,fv,lj}_dxf_stog.py`: ficha → DXF; certificados, usados via adapter | `CLAUDE.md` (fatos do ambiente) |
| **PI** | Processo Interno do projetista: por pavimento, pé-direito, cota, m², chapas, garfos, madeira | `../docs/HANDOFF-B-KNOWLEDGE-EXTRACTION.md` §1 |
| **NSC** | proposta comercial (escopo, totais de material, valor/m²) | `../docs/HANDOFF-B-KNOWLEDGE-EXTRACTION.md` §1 |
| **Chapa, sarrafo, garfo, grade, gastalho** | componentes físicos da fôrma; o vocabulário de cada classe está na semântica | `docs/SEMANTICA-{PILAR,VIGA,LAJE}-NOVA.md` |
| **Pavimento (PAV)** | andar da obra; unidade de trabalho (ex.: `13_PAV`) | `CLAUDE.md` (escopo Fase A) |
| **Obra de treino** | obra real usada para calibrar o sistema; **Obra_TREINO_1** é a principal | `CLAUDE.md` |

## Pipeline

| Termo | Significado | Fonte |
|---|---|---|
| **N1** | interpretação da planta estrutural pelo SA (campos por item) — schema imutável | `CLAUDE.md` |
| **N2** | ficha extraída do desenho STOG humano pelo motor reverso — o gabarito | `CLAUDE.md` |
| **N3** | DXF do robô gerado a partir de N1 (via conversão Fase-4) | `CLAUDE.md` |
| **N4** | DXF do robô gerado a partir de N2 — prova o gerador | `CLAUDE.md` |
| **N5** | prancha final: 1 DXF por classe + pavimento, consolidado dos previews N3 | `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` DP-12 |
| **SA — Structural Analyzer** | o interpretador da planta estrutural (produz N1) | `docs/SA-ANALISE/CLASSES/README.md` |
| **Motor reverso** | extrai a ficha N2 do recorte humano (`scripts/motor_reverso_*.py`) | `docs/MASTERPLAN-ENGENHARIA-REVERSA.md` |
| **Recorte** | trecho do DXF humano correspondente a um item; base do N2 | `docs/MASTERPLAN-ENGENHARIA-REVERSA.md` |
| **Ficha** | conjunto de campos de um item numa classe (N1 ou N2); ver F1–F9 | `docs/SCHEMA-FICHA-GRANULAR.md`, `docs/MASTERPLAN-FICHAS-F1-F9-HARMONIZACAO.md` |
| **Headless** | execução sem UI do SA + fichas; **único** ponto de entrada `scripts/arete/headless_sa_analise.py` | `CLAUDE.md`, `docs/LOOPING-CANONICO.md` |
| **CE — Comparison Engine** | módulo da app que compara N1/N2/N3/N4 lado a lado | `docs/MASTERPLAN-ENGENHARIA-REVERSA.md` |
| **Escape hatch** | quando o motor erra, o operador desenha a geometria no viewer web e o motor interpreta dali | `docs/MASTERPLAN-CONSOLIDACAO-ENTREGA.md` §1 |
| **Fase 0–8** | pastas de dados de uma obra (`Fase-2_Triagem` = recortes, `Fase-4_Sincronizacao` = JSONs N1→robô intocáveis, `Fase-6_Execucao_CAD` = N4…) | [MAPA-DO-CONHECIMENTO.md](MAPA-DO-CONHECIMENTO.md) §3 |

## Classes e partes

| Termo | Significado | Fonte |
|---|---|---|
| **PIL** | pilar; partes **CIMA** (planta do topo), **ABCD** (faces), **GRADES** | `docs/SA-ANALISE/CLASSES/PIL.md` |
| **Faces ABCD** | A/B = faces longas, C/D = curtas; especiais (L/U/T) ganham E, F… | `docs/INTERPRETACAO-PILARES-ABCD.md` |
| **NASCE / SEGUE / MORRE** | convenção do pilar no pavimento; pilar que nasce não é sólido naquele pavimento | `docs/SA-ANALISE/CLASSES/PIL.md`, `FV.md` |
| **V.chega / V.passa** | viga que termina na face do pilar / que atravessa | `docs/INTERPRETACAO-VIGA-CHEGA-VAO-E-FACE.md` |
| **LV** | lateral de viga; partes **VC** (visão de corte), **Face A**, **Face B** | `docs/SA-ANALISE/CLASSES/LV.md` |
| **Para / Passa** | comportamento da lateral no encontro; A e B decidem caso a caso, faces C/D do pilar são sempre Passa | `docs/CONTRATO-RIGIDO-MOTOR-LV-N3-N4.md` G10 |
| **FV** | fundo de viga; o ponto crítico é a **segmentação** (viga contínua = N segmentos) | `docs/SA-ANALISE/CLASSES/FV.md` |
| **LAJ** | laje; **hachura de apoio** nos apoios e **HLAZ** (faixa de união) | `docs/SA-ANALISE/CLASSES/LAJ.md` |
| **Contaminação** | elemento de outro item capturado no recorte (vizinho), não defeito do item | `scripts/arete/g2v_harness.py` (prompt) |
| **Painel montado** | chapa já cortada com os sarrafos pregados; sobe inteiro para o pavimento seguinte e é cortado junto com os sarrafos (D-71) | `docs/MATERIAIS-E-CONSTRUCAO.md` §12 |
| **Sobra (chapa/barra)** | pedaço que sobra do plano de corte ou do recorte de painel; tem ID rastreável e nunca é descarte (D-68/D-69) | `docs/MATERIAIS-E-CONSTRUCAO.md` §10–11 |
| **Tira de escoramento** | faixa hachurada da laje (união); nunca é reaproveitada | `docs/MATERIAIS-E-CONSTRUCAO.md` §5, D-66 |
| **Etapas de reaproveitamento** | 1 / 1.5 próprio item (idêntico / cortando) → 2 / 2.5 outros itens → 3 / 3.5 sobras → 4 estoque antigo → material novo (D-70) | `docs/MATERIAIS-E-CONSTRUCAO.md` §12.2 |
| **Gradeado / Sarrafeado** | tipo do painel de LV; no reaproveitamento só troca com o mesmo tipo (D-71) | `docs/CONTRATO-RIGIDO-MOTOR-LV-N3-N4.md`, `docs/MATERIAIS-E-CONSTRUCAO.md` §12.3 |

## Qualidade

| Termo | Significado | Fonte |
|---|---|---|
| **Arete** | paridade de conteúdo canônico entre o que o robô gera e o gabarito humano (estilo do robô, conteúdo do humano) | `docs/HANDOFF-ARETE-EXECUTOR.md` v1.2, `docs/MASTERPLAN-ARETE-QUALITY-GATES.md` |
| **G0** | sanidade do gabarito | `MASTERPLAN-ARETE-QUALITY-GATES.md` §4 |
| **G1** | round-trip da ficha N2 → N4 → N2′ | idem |
| **G2** | paridade canônica N4 × recorte N2, por parte — **nunca sela sozinho** | idem; `LOOPING-CANONICO.md` §1.5 |
| **G3** | UI e persistência | idem |
| **G4** | convergência da conversão N1 | idem |
| **G5** | paridade final N3 × N4 | idem |
| **G6** | golden set e regressão | idem |
| **G2-V / N1-V / G5-V** | vereditos **visuais** dos pares N2×N4 / N1×N2 / N3×N4 via `g2v_harness.py --backend cli` | `docs/LOOPING-CANONICO.md` §1.5 |
| **Golden (GOLDEN/)** | conjunto selado de itens aprovados; toda correção roda a regressão dele | `CLAUDE.md` regra 3 |
| **Selos** | azul (`humano_app`), rosa (`humano_portal`), laranja (`qa_agente`, isolado), verde (geral) | `docs/CONVENCAO-SELOS-VALIDACAO.md` |
| **Inventário mínimo** | rastreio linha/cota/texto com MATCH/MISSING/EXTRA antes de qualquer PASS visual | `docs/QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md` |
| **Microciclo** | rodada curta de um item/classe para descobrir e reverificar uma causa; nunca certifica | `docs/LOOPING-CANONICO.md` |
| **Dossiê QA** | prova primária de uma rodada de QA (grafo de fontes, hashes, adaptador, veredito) | skill `qa-global-evidencias` |
| **Aegis** | orquestrador da squad QA Global de Evidências | `squads/qa-global-evidencias/agents/aegis.md` |
| **Jev / TypeSafe** | modelo de julgamento tipado usado como **segunda leitura opcional** de dúvidas localizadas SA/N1; escolhe entre candidatos da fonte ou aponta evidência insuficiente, sem escrever N1 nem selar QA | `docs/SA-ANALISE/JEV-SEGUNDA-LEITURA-OPCIONAL.md`; `docs/CONHECIMENTO/MAPA-DO-CONHECIMENTO.md` §5; D-08 |
| **Pacote de evidência Jev** | JSON pequeno por item/campo/segmento com candidatos reais do DXF (handle, layer, coordenada, relação espacial) e pergunta fechada; hipótese SA fica fora do estado enviado ao modelo | `scripts/arete/examples/jev_sa_second_read_l410.json`; `scripts/arete/jev_sa_second_read.py` |
| **Controle de retirada** | segunda consulta que remove evidência decisiva para testar se Jev se abstém ou muda a leitura; não é gabarito da obra | `docs/SA-ANALISE/JEV-SEGUNDA-LEITURA-OPCIONAL.md` |
| **INSUFFICIENT** | opção explícita de uma pergunta `Choice` quando os candidatos/dados da fonte não sustentam a escolha; sinal para recuperar evidência ou revisar, não para preencher N1 | `scripts/arete/jev_sa_second_read.py`; `docs/SA-ANALISE/JEV-SEGUNDA-LEITURA-OPCIONAL.md` |

## Conhecimento e RAG

| Termo | Significado | Fonte |
|---|---|---|
| **T0 / T1 / T2 / TX** | quarentena / validado por humano numa obra / consolidado em ≥2 obras / revogado | `docs/POLITICA-CONFIANCA-RAG.md` |
| **Regra × instância** | regra semântica (vale para a classe) × caso de uma obra (não generaliza sozinho) | `../MASTERPLAN-CEREBRO-RAG-MULTIMODAL-v1.0.md` §3.3 |
| **KB global** | índice buscável desta base (docs + glossário + decisões + regras T1+) | [CONTRATO-KB-MULTIOBRA.md](CONTRATO-KB-MULTIOBRA.md) |
| **KB de obra** | mesmo esquema, escopo de uma obra, arquivo separado | [CONTRATO-KB-MULTIOBRA.md](CONTRATO-KB-MULTIOBRA.md) |
| **Mesma origem (same-origin)** | evidência de uma obra só vale para aquela obra | `docs/MASTERPLAN-MINIRAG-QA-N1.md` |

## Produto e infraestrutura

| Termo | Significado | Fonte |
|---|---|---|
| **Portal** | interface web da equipe (FastAPI em `portal/`), nunca importa PySide | `docs/HANDOFF-ARCHITECT-PORTAL.md` |
| **DP-n** | decisões de produto numeradas (DP-1…DP-14) | `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` |
| **P0–P6 / P0–P7** | gates de produto (P0–P6, soberania) e etapas do caminho crítico de entrega (P0–P7) | `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md`; `CLAUDE.md` item 5 |
| **VPS** | servidor Hetzner (cad-analyzer.duckdns.org) que hospeda o portal | `docs/HANDOFF-DEVOPS-VPS-HETZNER.md` |
