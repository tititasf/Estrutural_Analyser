# Compreensao Global e Auditoria de Implementacao

Data da auditoria: 2026-06-28  
Escopo: SA, N1/N3, N2/N4, N5; classes PIL, FV, LV e LAJ; visual, interpretacao, UI/design, robos e persistencia.  
Metodo: arquitetura (Aria), pipeline CAD E2E (Conductor) e rastreabilidade requisito -> codigo -> teste (Quinn).

## 1. Fontes e criterio de precedencia

1. Solicitacoes mais recentes do dono da aplicacao.
2. Regras travadas nos masterplans de fichas, loop e Arete por classe.
3. Implementacao atual do workspace, incluindo alteracoes nao commitadas.
4. Testes e artefatos gerados.
5. Historicos em `minhas_mensagens_agy`, `minhas_mensagens_codex` e `minhas_mensagens_claude`.

`analise_classificada.txt` nao e fonte suficiente isoladamente: o script atual limita cada classe a 20 mensagens aleatorias, permite duplicacao entre classes, usa termos genericos por substring e contem palavra-chave de robo com encoding corrompido.

Legenda dos gates:

- PASS: implementado e com evidencia executavel.
- PARCIAL: existe, mas falta parte do contrato ou cobertura.
- AUSENTE: regra nao encontrada no codigo atual.
- REGREDIDO: existe evidencia de versao anterior ou teste atual que demonstra perda.

## 2. Arquitetura funcional consolidada

### SA - Structural Analyzer

O SA interpreta o DXF estrutural limpo sem copiar o gabarito N2. O fluxo humano continua obrigatorio enquanto a classe nao atingir os gates. A ordem semantica e: lajes e pre-validacao contextual -> fundos de viga -> laterais de viga -> pilares. Informacoes produzidas cedo, como pilares NASCE, niveis de laje e visoes de corte, alimentam as classes seguintes.

Os tres comandos do SA possuem papeis distintos:

- Analise Geral: motor puro, sem `teacher_coords`, gera F7/N1.
- Analise com Engenharia Reversa: consulta F5/N2 como professor; nao gera DXF.
- Analise com Contexto: etapa futura baseada em F1/F2/F3; hoje pode consultar contexto read-only, mas nao deve fingir autonomia ainda inexistente.

### N1 e N3

- N1/F7 e a ficha produzida pelo SA.
- N3/F8 e o desenho produzido pelos robos exclusivamente a partir do N1.
- N2 e N4 podem julgar, pontuar e ensinar o motor, mas nunca preencher diretamente o N3.
- O gate e N3 aproximadamente igual a N4 sem vazamento de gabarito.

### N2 e N4

- N2/F5 e o gabarito humano extraido dos recortes STOG.
- N4/F9 e gerado pela ficha N2 usando o mesmo motor/robo aplicavel a classe.
- O N4 precisa reproduzir geometria, campos, cotas, textos, hachuras, layers relevantes e comportamento do desenho humano.
- A comparacao N4 x N2 e por conteudo canonico e tambem visual; score sintetico nao equivale a aprovacao humana.

### N5

- N5 e a montagem final por classe, sempre regenerada a partir do estado atual.
- Selecionar a aba N5 deve gerar/exibir o N5 da classe corrente.
- Trocar de classe deve regenerar N5 somente se o usuario ja estiver em N5; nao deve arrancar o usuario de N3/N4.
- Cada classe precisa de ordenacao e montagem isoladas.
- N5 tem regras proprias de despoluicao: quebra de trechos longos conforme contrato da classe, nomes sem repeticao desnecessaria e cotas verticais finais apenas onde aplicavel.
- N4 preserva precisao detalhada; N5 preserva legibilidade do conjunto.

## 3. Estado atual por fase

| Bloco | Gate | Evidencia atual | Estado |
|---|---|---|---|
| F1-F9 | IDs deterministas em todas as fichas | `ficha_utils.py` implementa o envelope; aplicacao concreta encontrada principalmente em F5 e F7 | PARCIAL |
| F5/N2 | Ficha validada nao pode ser sobrescrita | testes de integridade e UI F5 passaram | PASS |
| F7/N1 | Mesmo envelope de schema de F5 | `DatabaseManager.save_fase3_fichas()` carimba F7; testes relacionados passaram | PASS/PARCIAL por classe |
| F8/N3 e F9/N4 | Fichas persistidas e rastreaveis | existem fichas visuais e artefatos, mas F8/F9 ainda nao possuem persistencia canonica equivalente a F5/F7 | PARCIAL |
| Semantica | `semantic_ref` real por campo | banco tem 109 registros em `semantic_rag_kb`, mas `_semantic_refs` ainda usa `pending_domain_knowledge_link` | PARCIAL |
| RAG F5 | F5 indexada para consulta | 906/906 fichas estao com `rag_indexed=0` | AUSENTE |
| Treino | eventos e regras versionadas | 1280 `training_events`; 23 regras, 9 em producao | PASS estrutural, qualidade nao certificada |
| Atencao | nota, alerta e validacao humana persistentes em SA/N3/N4 | 71 registros em `item_attention_notes`; testes passaram | PASS |
| Galeria de artefatos | historico visual N3/N4 no Project Manager | tabela possui 7 registros, backend/testes existem, mas UI atual nao consome `rag_artifact_validations` | REGREDIDO |

## 4. Estado atual por classe e ciclo

### PIL - Pilares

| Ciclo | Estado | Evidencia/gap |
|---|---|---|
| SA -> N1 | PARCIAL | inventario dirigido por nomes P# e pre-validacao existem; teste de inventario passou. Falta gate E2E de populacao em obra real. |
| N2 -> N4 | REGREDIDO/PARCIAL | geracao CIMA/ABCD/GRADES existe e um relatorio anterior marcou 35/35; teste atual universal falha em P3 e P15 porque a cota central nao representa `comprimento * 2`. |
| N1 -> N3 | PARCIAL | robo e zonas existem; ainda falta prova completa anti-vazamento e N3 x N4 por lote atual. |
| Semantica | PARCIAL | riscos de inversao A/B/C/D, lajes/interferencias, alturas e offsets continuam abertos no masterplan. |

### FV - Fundos de viga

| Ciclo | Estado | Evidencia/gap |
|---|---|---|
| Extracao N2 | PASS estrutural/PARCIAL visual | `extraction_summary.json` registra 26/26 como OK; o motor atual preserva `segments_rich`, recortes, chanfros, apoios e metadados. |
| N2 -> N4 | PARCIAL | testes focados de segmentos ricos, geometrias especiais, aliases e preservacao no N5 passaram. As alteracoes mais recentes do gerador ainda nao possuem nova certificacao visual 26/26. |
| N1 -> N3 | PARCIAL | sincronizacao SA/robo e gerador existem; nao ha prova atual de N3 equivalente ao N4 em todas as 26 vigas sem N2 como entrada. |
| Regras vitais | PASS no motor, gate pendente | b_fv, comprimento, aberturas, chanfros, recortes e apoios sao derivados; pilares NASCE e visoes de corte devem ser informacionais, nao interrupcoes fisicas. |

### LV - Laterais de viga

| Ciclo | Estado | Evidencia/gap |
|---|---|---|
| Extracao N2 | PARCIAL | runners headless, ficha canonica e roundtrip existem; ainda ha divergencias de contagem de VCs, segmentos A/B e detalhes. |
| N2 -> N4 | REGREDIDO/PARCIAL | Comparison separa visualmente Visao Corte e Lateral A-B, mas o split fisico unitario alvo ainda nao esta concluido. |
| Gate visual | FAIL | artefatos recentes apresentam `coarse_visual_score` majoritariamente entre cerca de 15% e 56%, abaixo do gate minimo de 95%. |
| Generalizacao | FAIL | relatorio 13_PAV antigo marcou 32/32, mas o relatorio mais recente de 14_PAV marcou 10/27 PASS, 17 FAIL (37%). |
| UI | PASS/PARCIAL | subabas Vigas Para/Vigas Passam existem no SA e Comparison; `lv_para_passa` ainda tem 0 registros no banco real. |

### LAJ - Lajes

| Ciclo | Estado | Evidencia/gap |
|---|---|---|
| SA -> N1 | PARCIAL | conversor N1 -> ficha de robo e trava anti-teacher possuem testes; o motor completo ainda nao esta certificado em toda obra. |
| N2 -> N4 | REGREDIDO | teste visual oficial atual falha em L304 e L313 por HLAZ extra. Artefatos anteriores tambem registram L308/L312 com divergencias de HLAZ/outline. |
| N1 -> N3 | PARCIAL | contrato anti-vazamento tem teste; falta fechar o lote atual apos corrigir N4. |
| Escopo visual | PARCIAL | contorno, linhas internas, cotas e HLAZ existem; o gate 100% ainda nao foi recuperado. |

## 5. Visual e comportamento do Comparison Engine

| Regra | Estado | Evidencia |
|---|---|---|
| Botoes individuais N1-N5 e Gerar Todos obsoletos | PASS | permanecem apenas por compatibilidade e estao ocultos. |
| Selecionar item estrutural abre/gera N3; item reverso abre/gera N4 | PASS | `_on_item_selected()` troca para N3/N4 e inicia a sequencia protegida por `seq_id`. |
| N4 compara com N2 acima, sem ficha duplicada | PASS | `show_n2_above()` insere somente viewer e titulo acima do N4. |
| N3 compara com N1 ou N4 | PASS | dois toggles exclusivos estao no header N3. |
| Viewer principal e comparativo 25% menores em Y | PASS | teste de proporcao passou. |
| Ficha abaixo de N1, N2, N3, N4 e N5 | PASS | teste estrutural dos cinco niveis passou. |
| Score claro N3 x N4 e N4 x N2 | PASS/PARCIAL | labels existem; o scorer e simplificado e possui codigo morto apos `return`, portanto nao substitui gate visual completo. |
| Aba N5 reativa | FAIL | nao ha handler de `currentChanged` da aba de niveis. Trocar classe chama `_on_classe_changed()` e força `setCurrentIndex(4)` mesmo fora do N5. |

## 6. N5 - regressao de contrato

O `n5_assembler.py` atual faz duas operacoes:

- LAJ: sobrepoe/importa os previews N3 em suas coordenadas.
- PIL/LV/FV: empacota cada preview como folha, em linhas de largura maxima fixa.

Nao foram encontradas as regras N5 de quebra em aproximadamente 20 m, controle de repeticao de nomes, cota vertical somente no ultimo segmento, nem transformacao especifica antipoluicao. Os testes de N5 cobrem importacao, aliases, DIMENSION e MLINE, mas nao cobrem essas regras de negocio. Estado: AUSENTE.

## 7. Regressoes visuais e de interpretacao fora dos motores

1. `src/ui/style.qss`: arquivo atual tem 165 linhas/3652 bytes; a versao encontrada no stash possui redesign de aproximadamente 308 linhas. Estado: REGREDIDO.
2. `src/ui/widgets/project_manager.py`: galeria visual baseada em `rag_artifact_validations` nao esta no codigo atual; teste de metricas falha com `KeyError`. Estado: REGREDIDO.
3. `src/ui/widgets/detail_card.py`: botoes voltaram a `Remover Este Segmento` em largura completa; a versao compacta e a melhor preservacao de textos nao estao presentes. Estado: REGREDIDO.
4. `src/core/beam_tracer.py`: remove qualquer sufixo entre parenteses e reduz o nome ao prefixo+numero; perde `(A)`, `(B)` e nomes hifenizados. A versao do stash preservava letras, mas tratava numeros em parenteses de forma incorreta; precisa implementacao seletiva, nao restauracao bruta. Estado: REGREDIDO.
5. `scripts/gerar_lj_dxf_stog.py`: a versao do stash possui DIMENSION real, layers semanticas e hachura, mas tambem duplica funcao e conflita contratos de layer. Recuperacao deve ser seletiva. Estado: PARCIAL/REGREDIDO.

## 8. Evidencia de testes executados nesta auditoria

### Passaram

Treze blocos focados foram executados em conjunto, cobrindo layout/fichas, atencao, N5, integridade F5, conversao LAJ N1/N3, inventario PIL no SA, FV rico/especial, modos visuais e sincronizacao de fundos. O processo saiu com codigo 0.

RAG segmentado: 17 testes passaram.

### Falharam

1. `test_curadoria_rag_metrics.py`: `rag_artifact_validations` ausente das metricas/UI do Project Manager.
2. `test_arete_lj_13pav_n4_visual.py`: L304 e L313 possuem HLAZ indevido no N4.
3. `test_ce_n4_pil_cima_universal.py`: P3 e P15 nao possuem a cota central esperada.
4. Suite completa: algum modulo fecha `sys.stderr`/stream de captura e derruba o pytest no teardown. Os testes precisam continuar segmentados ate isolar esse import.

## 9. Gate global atual

Veredito: CONCERNS / NAO PRONTO PARA SELAR COMO ESTADO MAIS ATUAL GLOBAL.

O esqueleto arquitetural esta presente e melhor que o descrito nos masterplans antigos: F7 cresceu para 746 registros, `semantic_rag_kb` tem 109 regras, ha 1280 eventos de treino, os cinco niveis possuem fichas, as comparacoes visuais e a persistencia de atencao existem. Entretanto, ha regressao comprovada em N4 PIL e LAJ, LV nao generaliza, N5 nao cumpre seu contrato reativo/visual, e partes de UI validadas ficaram no stash.

## 10. Ordem segura para atualizacao

1. Corrigir a navegacao reativa N5 sem alterar motores: gerar ao entrar em N5; trocar classe somente regenera se N5 estiver ativo.
2. Fechar N4 por classe antes de N5: PIL P3/P15; LAJ L304/L313; FV lote visual 26/26; LV unidade por unidade ate 95%+.
3. Restaurar seletivamente regressao visual: stylesheet, Project Manager, Detail Card e parser de nomes de viga, cada um com teste proprio.
4. Implementar e testar regras N5 antipoluicao por classe.
5. Completar rastreabilidade F1-F9 e substituir `pending_domain_knowledge_link` por referencias reais.
6. Indexar F5 apenas sob politica humana/RAG vigente; hoje 906 fichas estao pendentes.
7. Rodar regressao por duas obras antes de promover qualquer regra global.

Nenhum codigo funcional foi alterado por esta auditoria.
