# Registro de decisões do dono

### QA-SA-AUTOAJUSTE-ADOCAO-20261003 — interpretação e aprovação humana

| ID | Data do registro | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| QA-SA-AUTOAJUSTE-ADOCAO-20261003 | 2026-10-03 | global QA SA | QA pode refazer geometria, campos, tags e interpretação completa do item; nova camada é resultado agêntico mais atual, mas só substitui SA após validação humana. L1 avalia SA, L2 avalia L1 com viewer populado, L3 segue cadeia; aprovar sem melhoria necessária dispensa novo viewer. | Dono neste chat: “só substitui caso eu valide humanamente a camada tal” e “pode como deve” refazer interpretação; docs/QA-SA-AUTOAJUSTE-E-ADOCAO-HUMANA.md | requisito vigente; implementação e cobertura por classe exigem verificação |
| QA-SA-APONTAMENTO-ADOCAO-L1-20261003 | 2026-10-03 | portal/QA SA | Aprovação humana L1 cria apontamento preservando SA anterior e camada aprovada, para investigar erros descobertos/corrigidos e melhorar motor posteriormente. | Último pedido de execução do dono, transcrito em docs/HANDOFF-QA-SA-13PAV-20261003.md §1 | aprovado; implementação pendente, não alegar função entregue |
| NUMEROS-CONFIRMACAO-BASE-20261003 | 2026-10-03 | global | Manter regra atual da Base: omitir ,0 em medidas e exatamente duas casas para níveis absolutos em metros; substitui pedido anterior deste chat de uma casa fixa em tudo. | Dono respondeu à pergunta de harmonização: “Manter regra atual da Base: omitir ,0; níveis em metros com duas casas” | vigente; APRESENTACAO-NUMERICA.md preservado |


### NIVEIS-DUAS-CASAS-20261003 — exceção global em metros

Níveis absolutos em metros usam exatamente duas casas decimais, com vírgula,
incluindo ,00, em todas as classes, campos, etiquetas, SA, N3/N5 e evidências
dos agentes. Prevalece sobre NUMEROS-UMA-CASA-20261003. Outras medidas mantêm
no máximo uma casa e omitem ,0. Não converter unidades por magnitude nem alterar
geometria ou precisão persistida. Fonte: `APRESENTACAO-NUMERICA.md`.

### NUMEROS-UMA-CASA-20261003 — apresentação global

Medidas e valores decimais para humanos usam no máximo uma casa decimal e vírgula; omitir ,0 em todas
as classes, campos, SA, N3/N5 e evidências. Preservar precisão interna e valores
não editados; não modificar identificadores, contagens, datas ou fontes históricas.
Fonte: `docs/CONHECIMENTO/APRESENTACAO-NUMERICA.md`. Implementação ainda em revisão.

### LV-SUBABAS-CORTE-20261002 — Todos em SA/N3

O dono definiu: SA Todos mostra os cortes sobre o estrutural e dispensa uma segunda aba Todos no estrutural. N3 mantém ambas: Todos reúne os desenhos N3; Todos no estrutural permite consultar sua localização na planta. Fonte: `docs/SA-ANALISE/CLASSES/LV.md`, Subabas SA/N3.

### LV-CORTES-ESTRUTURAL-20261002 — desenhar seções sobre a viga

O dono esclareceu com exemplos que “Todos no estrutural” deve mostrar desenhos das seções transversais SA localizados e rotacionados sobre a viga, como os cortes identificados existentes, e remover os destaques de segmentos dessa vista. Substitui a representação visual de LV-MAPA-PARES-20261002. Fonte: `docs/SA-ANALISE/CLASSES/LV.md`, Cortes sobre o estrutural.

### LV-CONTRASTE-20261002 — reforço das etiquetas e linhas

O dono pediu maior espessura de linha/texto e cores mais claras, aproximadas ao branco, pois os destaques das laterais e do mapa estavam pouco visíveis. Mantido o tamanho reduzido das etiquetas, com reforço de peso, brilho e contornos. Fonte: `docs/SA-ANALISE/CLASSES/LV.md`, Contraste dos destaques.

### LV-MAPA-PARES-20261002 — localizar as Visões Corte no estrutural

Representação visual substituída por LV-CORTES-ESTRUTURAL-20261002; redução das etiquetas das laterais permanece vigente.

O dono pediu uma aba adicional em Visão Corte que mostre todos os segmentos A/B da viga e destaque os intervalos comuns que representam cada seção agrupada. A referência é a faixa dos pares, não as chamadas de corte identificadas no pré-processamento. Uma mesma VC pode ocupar vários trechos. Pediu também reduzir as etiquetas dos segmentos das laterais para um terço do tamanho. Fonte completa: `docs/SA-ANALISE/CLASSES/LV.md`, Mapa de pares no estrutural.

**Status:** canônico · **Criado:** 2026-09-25 · **Tier:** toda decisão aqui é **T1** (validada por humano)

Uma linha por decisão, com a fonte onde ela está escrita por extenso. **A fonte é a
autoridade**: esta linha só resume para achar. Caminhos relativos a
`Agente-cad-PYSIDE-Restored-main/`.

**Como manter:**
- Decisão nova → nova linha (ID seguinte) **e** texto completo no doc canônico do tema.
- Decisão que muda outra → a antiga ganha `revogada por D-xx` na coluna Estado; nunca apagar.
- Escopo `global` vale para toda obra; decisões de uma obra só levam `obra:<nome>`.
- Antes de perguntar ao dono, procurar aqui (e em `kb_query.py`). Pergunta repetida é custo.

## Processo, qualidade e visão

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| NIVEIS-DUAS-CASAS-20261003 | 2026-10-03 | global | Níveis absolutos em metros: exatamente duas casas decimais com vírgula, inclusive ,00, em campos, etiquetas, SA/N3/N5 e evidências de todas as classes; preservar precisão interna e verificar unidade de origem | `docs/CONHECIMENTO/APRESENTACAO-NUMERICA.md` | vigente; exceção à regra de uma casa |
| NUMEROS-UMA-CASA-20261003 | 2026-10-03 | global | Medidas apresentadas com no máximo uma casa decimal e vírgula; omitir ,0; exceto níveis em metros (duas casas); preservar precisão interna, IDs, contagens e fontes históricas | `docs/CONHECIMENTO/APRESENTACAO-NUMERICA.md` | vigente; implementação em revisão |
| D-01 | 2026-07-03 | global | G2 numérico sozinho não sela: selar exige veredito visual registrado (Nível 2) e o dono (Nível 3) | `docs/LOOPING-CANONICO.md` §1.5 | vigente |
| D-02 | 2026-07-03 | global | Nada de API de visão: veredito visual só pelo agente CLI; API exige ordem explícita + calibração | `docs/VISION-VALIDACAO-CAMINHOS.md` (Ordem do dono 03/07) | vigente |
| D-03 | 2026-09-25 | global | Evidência visual: fonte = SVG canônico da ficha; o agente lê o PNG rasterizado desse SVG, com `--zoom` vetorial em região densa | `docs/LOOPING-CANONICO.md` §1.5; `docs/QA-VISAO-EVIDENCIA-CANONICA.md` §2.4 | vigente |
| D-04 | 2026-07-13 | global | Selo laranja isolado: só acende com 100% dos campos obrigatórios de origem `qa_agente` (revogou a versão com mistura) | `docs/CONVENCAO-SELOS-VALIDACAO.md` | vigente |
| D-05 | 2026-07-03 | global | Loop canônico único; script fora da seção 1 não se usa sem ordem explícita | `docs/LOOPING-CANONICO.md` | vigente |
| D-06 | — | global | Escopo incremental rígido: 13_PAV 100% → Obra_TREINO_1 completa → outras obras, uma a uma | `CLAUDE.md` regra 6 | vigente |
| D-07 | — | global | Dúvida de interpretação vai ao dono como ficha visual, com uma pergunta respondível em uma frase; fato do desenho se mede, só convenção se pergunta | `CLAUDE.md` regra 5d | vigente |
| D-08 | 2026-09-29 | global | Jev é segunda leitura **opcional** de dúvidas SA/N1: deve somar CAD, visão, QA e revisão humana; não precisa superar cada comparador isolado para ser útil, nem escreve N1 por conta própria | `docs/SA-ANALISE/JEV-SEGUNDA-LEITURA-OPCIONAL.md` | vigente |

## Produto e entrega

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| D-88/Portal-N3 | 2026-10-01 | global | Selecionar INI, NOVA, Base 1, Base 2 ou Base 3 em radios acima do N3 de todas as classes e do comando todas as classes, antes de gerar | `docs/CONFIGURACAO-MODOS-N3.md` §Seleção antes de gerar; pedidos deste chat | vigente |
| D-89/Vigas-Pav | 2026-10-01 | global | Gradeadas/Sarrafeadas e garfos Sim/Não passam da obra ao pavimento, em radios acima do N3 granular e unificado. Padrões Sarrafeadas e Não, sem Não informado | `docs/CONFIGURACAO-MODOS-N3.md` §Seleção antes de gerar; apontamentos deste chat | vigente; geometria de garfos Sim aguarda regra do dono |
| D-10 | 2026-07-03 | global | DP-1: sem distribuição de binário | `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` | vigente |
| D-11 | 2026-07-03 | global | DP-2: servidor = workstation do dono + VPN | `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` | **revogada por D-19** |
| D-12 | 2026-07-03 | global | DP-3: equipe usa portal web com login por membro; a app PySide é do dono | `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` | vigente |
| D-13 | 2026-07-03 | global | DP-5: SCR não é entregável; AutoCAD sai do produto (entrada DWG→DXF via ODA) | `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` | vigente |
| D-14 | 2026-07-03 | global | DP-6: embeddings continuam NVIDIA NIM (dependência externa aceita). Nota 2026-09-26: o modelo `nv-embed-v1` está em fim de vida (HTTP 410); a KB usa `nemotron-3-embed-1b`, escolhido por medição (D-22) | `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` | vigente |
| D-15 | 2026-07-03 | global | DP-7: quantitativos só depois da estabilidade de qualidade | `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` | superada por D-66 (28/09) |
| D-16 | 2026-07-03 | global | DP-9: Arete é o trabalho principal; em conflito, qualidade vence prazo | `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` | vigente |
| D-17 | — | global | DP-10 a DP-14: obras chegam pelo Google Drive (1 pasta por usuário, polling); N5 = 1 DXF por classe+pavimento; liberação do N5 é self-service após validar N1+N3; fluxo de 6 etapas | `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` | vigente |
| D-18 | 2026-07-30 | global | Definição de pronto: entregável = N5; as 4 classes juntas; web é o produto, PySide vira laboratório; erro do motor → escape hatch (operador desenha no viewer web) | `docs/MASTERPLAN-CONSOLIDACAO-ENTREGA.md` §1 | vigente |
| D-19 | 2026-08-10 | global | A VPS Hetzner vira o servidor principal de tudo, com acesso público (substitui DP-2) | `docs/HANDOFF-DEVOPS-VPS-HETZNER.md` §0 | vigente |
| D-20 | — | global | Sem sincronização campo a campo web ↔ app: a app é só treino/validação interna | `docs/MASTERPLAN-OBRAS-DRIVE.md` (Fora de escopo) | vigente |
| D-21 | — | global | Generalização para as outras obras saiu da fila; volta quando o dono decidir | `docs/MASTERPLAN-CONSOLIDACAO-ENTREGA.md` (tabela final) | vigente |
| D-22 | 2026-09-26 | global | Embedder da KB = "o mais eficiente e disponível", decidido por medição (`kb_eval.py`), não por marca; hoje NIM `nemotron-3-embed-1b`, com busca só por texto como reserva | `docs/CONHECIMENTO/PLANO-HARMONIZACAO.md` §3 | vigente |

## PIL — pilar

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| D-30 | 2026-07-16 | global | Hachura de vazio no topo do painel: N3 **e** N4 devem ter; N4 já selados não são regenerados | `docs/SA-ANALISE/CLASSES/PIL.md` §5.1 | vigente |
| D-31 | 2026-08-20 | global | R1: o vão entre o fim da viga desenhada e a face do pilar é continuação da viga | `docs/INTERPRETACAO-VIGA-CHEGA-VAO-E-FACE.md` R1 | vigente |
| D-32 | 2026-08-20 | global | R2: viga mais estreita que a face → `chega`; do tamanho da face → `interior` | idem R2 | vigente |
| D-33 | 2026-08-21 | global | R3: pilar mais largo que o corredor → a viga atravessa; mesma largura + outra viga do outro lado → morre; mesma largura + a própria viga do outro lado → atravessa | idem R3 | vigente |
| D-34 | 2026-08-22 | global | R4: chegada na esquina é chegada **e** passagem (duas informações, duas faces) | idem R4 | vigente |
| D-35 | 2026-08-19 | global | Invariante de face: viga chega no meio da face → duas lajes, uma em cada canto; chega num canto → uma laje só, no canto oposto; nenhuma chegando → uma laje cobrindo a face. Checagem só expõe a incoerência, não decide quem errou | `docs/INTERPRETACAO-VIGA-CHEGA-VAO-E-FACE.md` §"Como isso se encaixa no invariante de face"; `validate_face_slab_beam_invariant` | vigente |

## LV — lateral de viga

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| D-40 | 2026-09-11 | global | Visão de corte: o N4 replica a geometria medida do recorte N2; o N3 continua proibido de ler N2 | `docs/CONTRATO-RIGIDO-MOTOR-LV-N3-N4.md` (emenda 2026-09-11) | vigente |
| D-41 | 2026-09-13 | global | Abertura de VIGA recorta painel e sarrafo; abertura de PILAR não altera o painel, só recorta o sarrafo | idem §5.2.1 | vigente |
| D-42 | 2026-09-14 | global | Abertura de viga separa segmentos — a separação vem da interpretação, para o N3 reproduzir o que o N4 copia | idem §5.2.3 | vigente |
| D-43 | 2026-09-17 | global | Cota nas pontas: esquerda ≠ direita (laje ou painel) → cota nos dois lados, laje e painel; iguais → uma só, à direita | idem §5.2.6 | vigente |
| D-44 | 2026-09-19 | global | Fator de repetição "NX": começa no 2º painel; só painéis completos (244) e iguais; 1º e último nunca entram; menos de 2 → sem fator | idem §5.2.8 | vigente |
| D-45 | — | global | G3: altura da face = seção + 4 cm (contra a altura total da lateral) | idem §6.1 | vigente |
| D-46 | — | global | G7: no encontro entre vigas decide a profundidade — menos profunda: a lateral passa por baixo até a face oposta; mais profunda: termina na primeira face | idem §6.1 | vigente |
| D-47 | 2026-09-20 | global | G9: o recuo de 11 é do `Para`; o `Passa` não recua | idem §6.1 | vigente |
| D-48 | — | global | G10: lados A e B decidem Para/Passa caso a caso; faces C e D do pilar são sempre `Passa` | idem §6.1 | vigente |
| D-49 | 2026-09-25 | global | O fundo (FV) é referência e comparação para a lateral, nunca lei | `docs/SA-ANALISE/CLASSES/LV.md`; contrato §6.1.1 | vigente |
| D-50 | 2026-09-25 | global | Questionário Q1–Q7: troca de seção abre segmento; mesma profundidade = abertura; Passa = pilar inteiro num segmento com início/fim; pilar e viga coincidentes = ambos; −11 só no N3; contagem do N4 não é referência; autonomia do SA com revisão do dono no front-end | `docs/QUESTIONARIO-LV-SA-2026-09-25.md` | vigente |

## Decisões de 2026-09-26 sobre nível de laje

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| D-36 | 2026-09-26 | global | Nível de laje não é regra fixa: nasce da **conjunção de evidências** (cota contida — que pode ser de uma parte da laje —, vizinhas, pilares, vigas, cortes), como soma de pontos | `docs/PROPOSTA-NIVEL-LAJE-POR-EVIDENCIAS.md` (desenho aguardando respostas) | vigente (princípio) |
| D-37 | 2026-09-26 | global | Inferência automática passa por **portões de coerência** (vários), nunca por uma decisão só; corrigido o bug cm×m do delta de corte | `scripts/arete/relatorios/20260926_correcao_nivel_laje/RELATORIO.md` | vigente |
| D-38 | 2026-09-26 | obra:Obra_TREINO_1 | Dados do 13_PAV com o bug corrigidos pelo agente (4 lajes, 7 pilares, 24 vigas); L318 e 16 segmentos estimados ficam para revisão | idem | vigente |

| D-51 | 2026-09-26 | global | Evidência E9: texto de rebaixo ("−30" etc.) próximo à cota vale; sem cota na laje, texto de rebaixo dentro dela provavelmente se refere a ela (ainda sem exemplos no corpus) | `docs/PROPOSTA-NIVEL-LAJE-POR-EVIDENCIAS.md` §Respostas | vigente |
| D-52 | 2026-09-26 | global | Trecho demarcado com espessura/nível diferente: se **nível − espessura** (fundo) for igual nos trechos → **1 laje só**; se os fundos diferirem → **2 lajes separadas** (marcos à parte). No 13_PAV os fundos eram iguais (1 laje) | idem | vigente |
| D-53 | 2026-09-26 | global | Validação humana é **voto muito forte**, não âncora absoluta: evidência contrária forte abre revisão (nunca muda sozinha) — serve para achar onde sistema e dono discordam | idem | vigente |
| D-54 | 2026-09-26 | obra:Obra_TREINO_1 | Pesos da soma de evidências calibrados contra as lajes validadas do 13_PAV antes de ligar | idem | vigente |
| D-55 | 2026-09-26 | global | Área sem laje costuma ser marcada por **X vermelho**; segmento de viga sem laje encostada pode ser isso (não é necessariamente erro) | idem | vigente (informativa) |
| D-56 | 2026-09-26 | LAJ | L318 **não tem** delta de −30 no corte: o −30 vinha da direção do corte calculada pelo centro da laje longa (corte da V314 lido no eixo errado, contra a L319) — corrigido em 2026-09-27: direção pela borda da laje; L318 = 852.19 | revisão das fotos pelo dono (2026-09-26) | vigente (bug resolvido) |
| D-57 | 2026-09-26 | LV/FV | Segmento de viga que **toca só em parte** uma laje usa o nível dessa laje (ex.: V308 lado B via L325) | idem | vigente |
| D-58 | 2026-09-26 | global | **Quadradinhos** hachurados = rampa (não é laje); somado ao X vermelho (D-55), lado sem laje não tem nível e não é erro | idem | nível: substituída por D-61 (resto vigente) |
| D-59 | 2026-09-26 | LAJ | **L316** é o exemplo canônico de D-52: partes com nível/espessura diferentes e mesmo fundo → uma laje só | idem | vigente (exemplo) |
| D-60 | 2026-09-26 | FV | Segmento de fundo de viga **não pode** ter linhas fora das linhas originais do estrutural (como já vale para LV). V308/V331/V332/VF203/VF301 do 13_PAV estão com segmento FV desalinhado | idem | vigente — implementada: gate `fundo_viga_linhas.py` (repara no par de paredes / largura declarada / laterais da própria viga, apara, ou anula; feedback em `fv_line_gate`) |
| D-61 | 2026-09-27 | global | Segmento de viga **sem laje encostada** recebe nível **estimado**, marcado como tal (nunca vira nível medido; não é erro): "sempre melhor estimado que não ter informação". Ordem: laje encostada (medido) → **outro segmento da mesma viga** com laje encostada → laje com nível mais próxima. Corrige D-58 no ponto do nível. Marca: `nivel_viga_estimado` na viga (origem, laje/segmento de onde veio) | chat 2026-09-27 | vigente |

## Pendente de decisão do dono

- Segmentos estimados do 13_PAV — veredito do dono (2026-09-26): V308 A fora da torre (sem nível), B = nível da L325; V327 sem laje nos dois lados (rampa/X); V328 sem laje (correto); V332 A dentro tem laje, B à direita é exterior. Aplicado em 2026-09-27: geometria FV corrigida pelo gate D-60 (V327 voltou às laterais próprias); faces sem laje encostada (V308 A, V327, V328, V332 B) recebem nível estimado e marcado por D-61 (`nivel_viga_estimado`); V308 B medido na L325.

## Decisões de 2026-09-28 sobre LV (SA)

| ID | Data | Classe | Decisão | Fonte | Estado |
|----|------|--------|---------|-------|--------|
| D-62 | 2026-09-28 | LV | Quando a continuação é **outra viga** (o nome muda), a viga para na **própria delimitação** (pilar) e o trecho seguinte é da outra, seja em L ou reto. Caso: V309 × V307 no P25 — trecho P25→canto (30,71 A / 22,53 B) é da V307; V309 = só 320 | chat 2026-09-28 | vigente — `_corner_stubs_beyond_pillar` + corte no pilar entre rótulos colineares (`lv_beam_scene.py`) |
| D-63 | 2026-09-28 | LV | Passa: pilar entre duas vigas colineares, cada uma encostando de um lado → só a **mais profunda** engloba o pilar (inteiro, inclusive pilar oco em peças, P27); a outra para na face. Mesma altura: as duas englobam | chat 2026-09-28 | vigente — `_cede_shared_end_pillars` (`cede_para`/`engloba_ini`/`engloba_fim`) |
| D-64 | 2026-09-28 | LV | Reafirma D-48/G10 ("bug gravíssimo"): lateral **Para nunca para nas faces C/D** (curtas) do pilar — só nas A/B/E/F/G/H; na face curta o pilar é tratado como Passa (englobado). **A letra é a da face do pilar por onde a lateral CORRE** (paralela à viga), não a da face onde bate de frente: pilar colinear corre pela A/B → Para para (V309 320, V329 141); passa só ao lado de face curta C/D de pilar retangular (VF301 B nos P2–P8, V302 A no P12); pilar em L: E..H → para. A 1ª leitura (face de frente) fez o Para agir como Passa e foi corrigida no mesmo dia | chat 2026-09-28 | vigente — `_side_face_is_short` (`lv_beam_scene.py`) + `segment_cell`. Auditoria no mesmo dia achou mais 2 regras abandonadas no motor de células e implementou: **D-61** (nível estimado marcado, `estimate_missing_cell_levels`) e **G9/D-47** nas pontas (Para recua 11 também no pilar de apoio da extremidade) |
| D-65 | 2026-09-28 | FV | Pilar que **nasce** no pavimento (símbolo da convenção de pilares; no 13_PAV = X) é ignorado pelo fundo: parede interrompida pelo X não é limite, o fundo **segue até topar a viga** seguinte. Corte por viga mais funda é feito nas **paredes** dela, nunca no rótulo. Caso: V301 S2 × P42 × V312 (1603,4, não 1590,1). | dono, chat 28/09 | vigente |
| D-66 | 2026-09-28 | global | Quantitativo entra no portal (aba "Materiais e Construção"): peças **medidas no N3 desenhado** + material de compra. Estoque: chapa **244 × 122**; sarrafo **2,2 × 7 × 3 m** (variantes 2,2 × 10 e 2,2 × 5); grades de viga/pilar em **meio pontalete de 3 m**. Não quantifica: Cima do pilar, Corte da LV (só perspectiva); laje = só painéis. Supera D-15 | chat 2026-09-28 | vigente — `docs/MATERIAIS-E-CONSTRUCAO.md` |
| D-67 | 2026-09-28 | PIL | **Sarrafo de pressão** (layer "Sarrafo de Pressão", linha HIDDEN, desenhado só pelo eixo) é **2,2 × 7**, cortado da barra de 3 m. Responde Q3 | chat 2026-09-28 | vigente — `plano_de_corte.material_da_bitola` |
| D-68 | 2026-09-28 | Materiais | **Por enquanto nenhuma sobra é descarte**: toda sobra de chapa e de barra entra na lista rastreável (sem tamanho mínimo). Responde Q9 | chat 2026-09-28 | vigente — `plano_de_corte.compra_de_grupos` |
| D-69 | 2026-09-28 | Materiais | **Recorte de painel é sobra**: o pedaço que sai do retângulo (entalhe/abertura/viga) entra na lista rastreável e no encaixe — peça que cabe nele (sozinho ou somado à sobra vizinha) é cortada ali | chat 2026-09-28 | vigente — `plano_de_corte._empacotar` / `_regioes_livres` |
| D-70 | 2026-09-29 | Materiais | **Reaproveitamento entre pavimentos em etapas**, cada uma para todos os itens da classe antes da próxima: 1 próprio item (medida idêntica) → 1.5 próprio item (outra medida, cortando) → lista temporária dos montados não usados → 2 outros itens (idêntica) → 2.5 outros itens (cortando) → 3 sobras de chapa/recortes (na medida) → 3.5 sobras cortadas → 4 estoque acumulado antigo → material novo só do que falta. Responde Q8 | chat 2026-09-29 | vigente — `docs/MATERIAIS-E-CONSTRUCAO.md` §12 |
| D-71 | 2026-09-29 | Materiais | **Regras de corte no reaproveitamento** (sarrafo corta junto com o painel): **LV** mesmo tipo (gradeado/sarrafeado), comprimento **igual**, match dos sarrafos/grades de extremidade (esq./dir./nenhum), só a altura varia cortando **embaixo**; **PIL** largura igual, só a altura cortando **em cima**; **FV** largura igual (espessura não se corta), só o **comprimento**, com match dos sarrafos de extremidade; **LAJ** tira de escoramento nunca, painel comum corta em qualquer direção. **Nunca entre classes** | chat 2026-09-29 | vigente — `docs/MATERIAIS-E-CONSTRUCAO.md` §12.3 |
| D-72 | 2026-09-29 | Materiais | **Estoque acumula e se gasta** ao subir a obra, rastreado pelos IDs de painel e sobra; o estoque de pavimentos mais antigos entra como etapa 4. Par "próprio item" por nome/número (V301↔V401), sem exigir mesma posição | chat 2026-09-29 | vigente — `docs/MATERIAIS-E-CONSTRUCAO.md` §12 |
| D-73 | 2026-09-29 | Portal | "Material de compra" vira **"Material necessário, preparação e reaproveitamento"** com 3 sub-abas: Preparação com Materiais Novos / Preparação com Materiais Reaproveitados e Novos / Materiais Disponíveis dos Pavimentos Anteriores (sobras juntas sem proveniência; montados por item da classe) | chat 2026-09-29 | vigente, implementado 29/09 — `docs/MATERIAIS-E-CONSTRUCAO.md` §12.6 |
| D-74 | 2026-09-29 | Materiais | **Sequência dos pavimentos = a ordem de todos os pavimentos da obra** (subsolos, térreo, 1º, tipo 2–10 como um pavimento só, 11º, 12º, cobertura, deck…): pavimento sem dados não quebra a sequência; o estoque só começa do zero no primeiro pavimento. O portal guarda anterior/próximo e a faixa do TIPO; cada repetição do TIPO alimenta a seguinte e a última alimenta o próximo pavimento | chat 2026-09-29 | vigente, implementado 29/09 — `portal_obra_pavimentos`, `GET/PUT /obras/{obra_id}/pavimentos/ordem`; consulta usa a ordem cadastrada e expande a faixa TIPO somente no cálculo, com fallback por nome em obras ainda não configuradas |
| D-75 | 2026-09-29 | Materiais | **Sobra limpa de chapa pode ir para outra classe** (só recorte puro de painel/chapa, sem sarrafo); painel montado e retalho com sarrafo continuam só na própria classe. Mantém ID e registro de proveniência e de fornecimento | chat 2026-09-29 | vigente — implementado 29/09 (`docs/MATERIAIS-E-CONSTRUCAO.md` §12.6) |
| D-77 | 2026-09-29 | Materiais | **Sobras: máximo aproveitamento, peças grandes primeiro** — não há ordem de classes; os painéis maiores de todas as classes do pavimento escolhem primeiro a sobra (a menor que serve) | chat 2026-09-29 | vigente — `docs/MATERIAIS-E-CONSTRUCAO.md` §12.6 |
| D-78 | 2026-09-29 | Materiais/Portal | **Reaproveitamento em 2 frentes: Para e Passa**, calculadas e listadas separadas (pilares e laterais de cada modo); fundo e laje entram igualmente nos dois, sem citar Para/Passa. A obra tem o campo **comportamento Para / Passa / Misto** (Misto = hoje, as 2 listas); a consulta exibe só a lista do modo da obra | chat 2026-09-29 | vigente, implementado 29/09 — `portal_obras.comportamento`, filtro de rotas internas e códigos públicos, payload público da obra/pavimento |
| D-76 | 2026-09-29 | FV | **Laterais servem de ajuda ao fundo, não de regra rígida** (espelho de o FV ser referência da LV): o fundo deve ficar tão completo quanto as laterais — trecho com as duas paredes reais e sem fundo ganha painel; painel na faixa de outra viga volta para a dona. Sempre com prova local do DXF (linha real, fora de cota, pilar sólido/hachura fora); fundo validado não muda | chat 2026-09-29 (apontamento 9cf6beac) | vigente, implementado 29/09 — `docs/SA-ANALISE/CLASSES/FV.md` §1, `src/core/beam_interpreters/fundo_viga_lateral_ref.py` |
| D-79 | 2026-09-29 | FV | **Cruzamento de fundos tem um único dono**, inclusive em chanfros e diagonais: contorno humano vence; entre automáticos decide por painel a maior profundidade, depois largura, continuidade e desempate determinístico. O perdedor é recortado pelo polígono real, sem retangularizar. Dois contornos humanos conflitantes são reportados e preservados para revisão | chat 2026-09-29 | vigente, implementado 29/09 — `docs/SA-ANALISE/CLASSES/FV.md` §1, `fundo_viga_lateral_ref.resolve_automatic_overlaps_all` |
| D-80 | 2026-09-29 | FV | **Fundo não tem comprimento mínimo**: havendo área positiva e duas faces reais, cria-se o painel mesmo isolado e mesmo com 1 cm. Comprimento nunca decide descarte. O L é preferido quando uma pequena cauda ortogonal termina na face do corpo longitudinal adjacente e o corpo é claramente dominante (no N4: V303 = 418 cm com caudas de 10/30 cm); sem dominância, cada trecho continua como painel próprio (V304×V329 = 199×141 cm). Essa relação decide apenas **unir ou separar**, nunca apagar. Trecho isolado sem ligação também não some por tamanho | chat 2026-09-29; engenharia reversa N4 do 13_PAV (V303 e contraste V304×V329) | vigente, implementado 29/09 — `docs/SA-ANALISE/CLASSES/FV.md` §1, `beam_tracer._separate_one_sided_l_extensions`, `fundo_viga_lateral_ref.py` |
| D-81 | 2026-09-30 | FV | **P13 do 13_PAV é sólido até a região apontada; ali são dois segmentos, não um fundo unido.** Um símbolo NASCE de outro pilar sobreposto e paredes contínuas não anulam seção sólida, nem exclusão de pilar com classificação incerta. Isso não reintroduz limite mínimo de fundo | dono, correção do apontamento P13 no chat 30/09 | vigente — `docs/SA-ANALISE/CLASSES/FV.md` §1, `fundo_viga_lateral_ref._bottom_scene` |
| D-82 | 2026-09-30 | FV | **L de 90 graus = dois painéis; L angulado = um painel único cortado no ângulo, sem divisão no nascimento do L.** Não decide pela dominância relativa da perna. Usar também os robôs, a lógica N4 e desenhos de referência para validar reprodução e interpretação, sem copiar geometria N4 para N1. Substitui a parte de D-80 que unia caudas ortogonais; mantém a ausência de comprimento mínimo | dono, chat 30/09 | vigente; união ortogonal removida, 59 testes focados passaram; selo N3/N4 ainda não emitido — `docs/SA-ANALISE/CLASSES/FV.md` §1 |
| D-83 | 2026-09-30 | FV | **Não criar costura artificial entre trechos contíguos da mesma faixa/seção.** No cruzamento, privilegiar continuidade física, não soma de vãos interrompidos nem orientação vertical/horizontal; incidentes terminam nas faces da viga que atravessa. Profundidade/largura e validação humana mantêm precedência. Hipótese operacional: maior painel/desenvolvimento total após D-60, com desenvolvimento como desempate. Não une pilares, mudanças de seção, chanfros ou L de 90 graus | dono, apontamento 30/09 12:29:43; fórmula de desempate é implementação testada, não regra universal ditada pelo dono | 62 testes focados; replay 13/14 sem conflitos ou lacunas medidas; gates N3/N4 não certificadas |

| D-83 | 2026-09-30 | PIL/Portal | Convenção colore também os boxes: SEGUE azul, MORRE amarelo, NASCE vermelho. NASCE no próximo pavimento permanece acessível no SA e fica excluído dos motores N3/N5; correção manual da classificação reativa ambos. Orientação, classificação, níveis e pé-direito editáveis com salvar na ficha SA | dono, apontamentos deste chat | vigente — `src/core/pillar_sa_review.py`, rotas SA, materialização N3 e montagem N5 |

| D-84 | 2026-09-30 | Portal/Pré-processamento | Convenção de Níveis em abas por classe, uma linha por item, todas as partes em colunas/detalhes, nível obtido e confiança com cores para dúvidas/conflitos. Agrupamento visual por nome/classe/torre preserva todos os registros de origem. Percentual ausente aparece como Não calculada | dono, apontamento em `documento=preproc:niveis` | vigente — `docs/PLANO-PREPROCESSAMENTO-PAVIMENTO-TORRES.md`, relatório `20260930-niveis-abas` |

| D-84 | 2026-09-30 | PIL/Portal | N5 de pilares dividido em dois arquivos e subabas: PARA (Cima, ABCD Para, Grade Para) e PASSA (Cima, ABCD Passa, Grade Passa). Cima universal compartilhada em ambos; carregar apenas conjunto ativo para reduzir peso | dono, pedido deste chat | vigente — montagem N5, pipeline, rotas e viewer web |

| LV-colunas-20260930 | 2026-09-30 | LV/Portal | Preencher aberturas de viga por segmento, com posição esquerda/direita; nova coluna Passa por pilares: Para sempre Não, Passa só faces A/B/E/F/G/H, ignorar C/D, distância esquerda + comprimento físico do pilar no segmento + distância direita | dono, chat Investigue e corrija apontamento | vigente — docs/SA-ANALISE/CLASSES/LV.md |

| D-85/FV | 2026-09-30 | FV | **Encontros angulados preferem chanfros retos completos, não recortes em degrau ou L diagonal desnecessário.** Distinguir chegada/cruzamento de vigas distintas de dobra contínua da mesma viga. L legítimo segue D-82; vigas distintas conservam donos separados. Redistribuir a área comprovada sem modificar cobertura externa, pilares, profundidades distintas ou geometria humana. Não ignorar peças pequenas | dono, `fundos` 15:12:21 e `fundos2` 15:13:38, esclarecimento no chat 30/09 | vigente — `docs/SA-ANALISE/CLASSES/FV.md` §1; relatório `20260930_fv_chanfros`; selo N3/N4 não emitido |
| D-85/FV-adendo-20261001 | 2026-10-01 | FV | **Encontro triplo: substituir a ponta com dois chanfros por uma única reta de parede a parede**, redistribuindo a ponta entre os dois fundos vizinhos, sem apagar área ou unir donos. Caso aprovado V307/V306/VF202; preservar VF202/VF203. Regra geométrica para chegadas distintas de igual profundidade, fora de sólidos e contornos humanos; não converter cruzamento passante ou dobra da mesma viga | dono, comentário "dois chanfros na V306 desnecessário" e confirmação "simmm" à proposta de redistribuição entre três | vigente — FV.md §1, `_single_cut_triple_junctions`; testes/replay em `20261001_fv_chanfro_unico`; não é selo N3/N4 |

| D-86/Pré-SA | 2026-09-30 | Pré-processamento/SA | **Pré-processar deve coletar o necessário para preencher ao máximo a Convenção de Níveis antes do SA, inclusive executando coleta canônica SA parcial/completa.** Preservar todos os níveis por segmento/parte, origem e dúvidas; o SA deve consumir a informação comprovada na interpretação. Coleta isolada não equivale a certificação QA nem atualização dos resultados SA já publicados | dono, pedido explícito neste chat | vigente — `docs/PLANO-PREPROCESSAMENTO-PAVIMENTO-TORRES.md`; evidência e consumo real em relatório `20260930-niveis-sa-evidencias` |
| D-87/LV | 2026-09-30 | LV/Visão Corte | **Agrupar pares A/B com a mesma seção**, preservando os trechos de origem. A lista deve reunir também cortes identificados no SA e no pré-processamento, com origem e associação verificáveis | dono, resposta textual neste chat: “Agrupar pares com a mesma seção” | vigente — `docs/SA-ANALISE/CLASSES/LV.md`; inventário derivado, sem mudança do N1 |
| PIL-modos-20260930 | 2026-09-30 | PIL/Portal | Nova e Ini abaixo de Para/Passa, fora do viewer e com o mesmo design. Troca exibe N5 existente; sem N3 do modo ou sem N5 apenas avisa. Motores N3/N5 perguntam estilo; N5 oferece somente modo alimentado por N3 completo correspondente | dono, apontamento deste chat | publicado; 54 testes Python e 6 cenários JS; clique real pendente por falha da conexão de automação |
| N3-modos-20260930 | 2026-09-30 | Portal/N3 | Todos os viewers N3 que possuem Nova/Ini devem exibir esses controles fora do desenho, como subabas no padrão das subabas finais N3/N5 | dono, pedido deste chat | `docs/PADRAO-SVG-WEB-PANZOOM-VIEWBOX.md` §7 |
| N3-config-modos-20261001 | 2026-10-01 | Portal/N3 | Configuração de Modos após Ver apontamentos, Ini/Nova e cinco classes com LV Para/Passa independentes. Ajustes influenciam novas gerações N3. Preservar desenho atual como padrão; legado orienta a semântica, sem restaurar algoritmos antigos | dono, pedido e esclarecimento neste chat | publicado e testado; controles efetivos e limites em docs/CONFIGURACAO-MODOS-N3.md |

## Convenção por segmento e face — decisão do dono, 2026-10-01

Vigas têm uma linha por item, com uma linha de texto por segmento FV em Nível obtido.
Nível Segmentos Laterais discrimina A/B Para/Passa e seus trechos: o vínculo com FV
é espacial, nunca por igualdade de índice. FV usa cortes; LV usa cortes/lajes e pode
completar FV sem evidência suficiente. O retorno FV→LV conserva a origem independente
e não cria confirmação circular. Pilar exibe o nível final do contato mais alto com
laje/viga e a face correspondente; base permanece na própria coluna.

Implementação v6: sementes LV independentes congeladas; cobertura única mínima de 80%
para completar FV, sem somar Para/Passa duplicadas. LV recebe intervalos geométricos
por sobreposição, podendo conter vários níveis no mesmo segmento; não há média.
Cortes com duas marcas vermelhas paralelas de interrupção não permitem converter
a altura desenhada em desnível absoluto. No 13_PAV, sete cortes foram rejeitados
por esse motivo (PNG L316 no relatório).

Confiança é suporte de evidência rastreável, não probabilidade calibrada. Origem CAD
95; referência geral 25; estimativa 30; inferência 55 ou 65 conforme método; demais
evidências 75. Pendências de origem recebem descontos explícitos. Cada transferência
usa a fonte mais fraca e fator espacial <=1. Ausência de nível tem 0; níveis por
trecho conservam seus escores individuais. Campos automáticos sem origem
independente ficam limitados a 30. Os pesos E1–E9 ainda aguardam a calibração prevista.

QA: 92 testes na rodada principal, 16 reexecutados após o ajuste final; nova coleta
na fila oficial concluída em 13_PAV, 478 geometrias preservadas frente à versão
anterior, 668 fatos com cálculo de confiança, proveniência sem ciclos. Browser:
46 pilares, 36 vigas, 31 lajes sem repetição; 86 linhas FV e 541 trechos LV.
30 dos 35 pilares existentes têm topo associado; P9/P10/P25/P34/P35 pendentes.
Persistem fontes fracas, níveis múltiplos e conflitos, expressos na ficha. Não há
validação humana de todos os fatos nem selo Arete integral. Relatório:
`scripts/arete/relatorios/20261001-niveis-segmentos/RELATORIO.md`.

## N3-config-subabas-moldura-20261001

O dono pediu agrupar configurações similares em subabas dentro de cada classe,
com uma subaba Moldura para enviar DXF e visualizar o documento. A finalidade
na geração será explicada depois: nesta etapa o arquivo é referência, sem
interferir em N3/N5. Armazenamento separado por modo/classe. Publicado na VPS
após terminar a fila existente; upload/renderização, zoom/reset, isolamento e
preservação do rascunho entre subabas foram validados. Dez testes focados passaram.
Referência: docs/CONFIGURACAO-MODOS-N3.md.


## LAJ-degraus-cortes-amarelos-20261001

O dono pediu reconhecer trechos internos com diferença de espessura mesmo sem corte de laje. Destaques amarelos notificam degraus; diferenças comprovadas de fundo (nível − espessura) em relação à laje dona ficam vermelhas no destaque de lajes. Cortes próprios de laje devem entrar em Visão de Cortes identificados pelo nome da laje e destacados em amarelo, separadamente dos cortes de viga. Preservar D-52: fundo igual significa uma laje; diferente indica separação. Ausência de cota permanece explícita, sem supor fundo igual. Ver docs/SA-ANALISE/CLASSES/LAJ.md e src/core/slab_steps.py.

## Configuração granular de modos — 01/10/2026

O dono pediu retirar Blocos, separar textos/hachuras/cotas por função real e componentes por vista, incluir Exemplos (dez DXFs por modo/classe) e Detalhes especiais com anotações. Modo Molde 1, 2 e 3 são cópias independentes de Nova; rótulos Modo iNI e Modo Nova. Preservar a qualidade do gerador atual. Moldura e Exemplos apenas armazenam referências nesta etapa. Implementação/testes locais concluídos; publicação pendente de término do job ativo na VPS. Referência: docs/CONFIGURACAO-MODOS-N3.md e scripts/arete/relatorios/20261001_config_granular/RELATORIO.md.

Atualização da entrega granular: publicado na VPS em 01/10/2026 às 19:19 UTC e confirmado no navegador de produção; os bloqueios de publicação anteriores foram resolvidos preservando alterações dos demais agentes.

## LV-abertura-nao-acrescenta-corte-20261002

Decisão do dono neste chat: **“Abertura somente nas laterais; não acrescenta Visão Corte”**.
Excluir do pareamento para seções comuns apenas a faixa física comprovada da abertura
de viga, projetada no eixo e no sentido original de leitura de cada segmento A/B.
Preservar a abertura na ficha lateral e registrar a exclusão na proveniência.
Ausência real de laje fora dessa faixa continua sendo uma seção válida.
Não reduzir por nome, tamanho do trecho ou pela contagem do N4.

## LV-corte-sarrafos-ferragens-20261001

O dono confirmou que os sarrafos da Visão Corte LV seguem fielmente os N3
respectivos de cada lado. Parafusos têm regra por medida; centrais têm mínimo
cujo valor ainda deve ser recuperado do legado. Montagem inferior sempre
presente; não recorda mínimo inferior. Regras exclusivas da seção/laterais de
viga, sem transferir Visão Cima de pilares. Fonte: conversa de 01/10/2026.
Referência: docs/CONTRATO-RIGIDO-MOTOR-LV-N3-N4.md, seção Ferragens.

Correção confirmada pelo dono após leitura do histórico: existe a exceção de
laje inferior em qualquer lado, que suprime fixações inferiores e centrais.
Sem LI, inferior não tem mínimo; centrais usam H1 > 40 / > 90 nos DOIS lados,
eixos 25 / 75 cm. A confirmação de LI substitui a afirmação anterior de inferior
sempre presente. Consulta Git autorizada apenas para leitura; nenhuma restauração.

## SA granular na edição manual — 01/10/2026

| Decisão | Regra | Fonte |
|---|---|---|
| SA-MANUAL-GRANULAR-20261001 | Reconhecer campos/níveis apenas do segmento FV/LV salvo ou item PIL/LAJ, preservando contorno e vizinhos. Sem SA completo de viga, sem aprovação automática; atualizar destaque/lista/ficha N1 dinamicamente e deixar falta de evidência pendente. | Pedido do dono em 01/10/2026; docs/PROVENIENCIA-CAMPOS-FV.md |

O dono determinou que novos/editados passem pelo reconhecimento de campos e
níveis durante o salvamento. Para vigas/laterais/fundos, somente o segmento;
para pilares/lajes, somente o item. Não executar SA completo da viga nem mudar
o contorno manual. Atualizar destaque, lista esquerda e ficha SA/N1 sem refresh,
com feedback de etapas e desempenho medido. Valores sem evidência permanecem
pendentes; reconhecimento automático não sela aprovação humana. Implementação
publicada na VPS após esvaziar a fila, com backup e preservação de alterações
concorrentes. 23 testes focados passaram. Ciclo real de criação/redesenho/exclusão
validado pelo navegador no 13_PAV com laje e segmento de fundo temporários;
ficha/lista/destaque atualizam sem refresh ao salvar. Campos sem evidência continuam
pendentes; não equivale a certificação Arete. Anotações de nomes manuais só aceitam
identidade segura pertencente a item manual existente.
Complemento de 02/10/2026: excluir também deve atualizar destaque, lista N1,
seleção e próximo segmento sem recarregar a página nem sair do estrutural.
Feedback em etapas reais: 25% requisição, 75% atualização visual, 100% concluído.
Se a exclusão já persistiu e a atualização visual falhar, repetir somente a
atualização, nunca a exclusão. Criação/edição/exclusão no estrutural não devem
abrir automaticamente a ficha de outra viga. Reteste real de S7 temporário
na V306 passou; os 91 fundos originais permaneceram integralmente iguais.
Complemento de seleção de 02/10/2026: clicar em um destaque do estrutural
preenche o editor com a classe, item e segmento exatos, incluindo o lado A/B.
Com Desenhar no SVG ativo, a seleção por clique fica desabilitada. Arrastar
para navegar não seleciona; selecionar não salva, exclui ou inicia redesenho.
Validado no navegador para FV, PIL, LAJ e LV A/B, sem alteração persistida.
OSNAP (02/10/2026): dono especificou atração apenas para pontas, encontros
literais/cruzamentos e vértices de mudança de direção; não para a extensão
da linha nem meios artificiais. Gravidade aprovada 24 px; bolinha ampliada.
Referência: docs/PROVENIENCIA-CAMPOS-FV.md e
scripts/arete/relatorios/20261001_manual_sa_granular/RELATORIO.md.


### MODE-DEFAULTS-CURRENT-20261001

O dono determinou que os valores da Configuração de Modos sejam obtidos dos geradores N3 atuais por classe e modo, sem importar predefinições do legado. Valores variáveis permanecem preservados, com as variações reais visíveis; configurações existentes não são sobrescritas. Fonte canônica: docs/CONFIGURACAO-MODOS-N3.md.


### D64 — 2026-10-01 — continuidade do fundo nas regiões do 13_PAV
O dono confirmou explicitamente a pergunta sobre L313, L320, L321, L322, L323 e L324: fundo contínuo; trechos h=10 em 852,16 m e h=13 em 852,19 m. Decisão limitada aos seis contornos e à revisão DXF examinada; não é regra universal para qualquer degrau. Persistir como revisão derivada com UID do contorno e SHA do DXF.
L317: o dono indicou que o corte atravessa uma região com cota da L316; calcular pelo contato real, não perguntar um nível que pode ser medido. Conferência geométrica: região interna L316 852,16 m, aba L317 +3 cm, portanto 852,19 m. Interrupção no fuste não invalida o delta local entre abas.


### NIV-SEM-LAJE-20261002 — nível de saída em escadas, rampas e vazios

Dono, comentários visuais de 02/10/2026: escada, rampa e X de ausência não são lajes. Vigas e pilares nesses lugares usam o nível base de saída do pavimento, obtido da convenção ou, na ausência dela, do nível mais comum das lajes. Exigir reconhecimento geométrico da ausência; não inventar laje. Preservar evidência específica de nível diferente. Substitui D-61 para ausência comprovada, mantendo-a onde falta evidência. Regra geral sem nomes/cotas fixos; motor e QA no manual `INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md` §9.

### N3-CARDS-20261002 — seleção visual dos cinco modos

O dono pediu substituir os círculos dos modos por cards compactos semelhantes aos botões QA e à lista de itens. Todos os modos não selecionados ficam com fundo azul; somente o selecionado fica verde. Preservar escolha única antes de gerar, em todas as classes e no painel de todas as classes. Complementa a decisão de pré-seleção dos modos de 01/10/2026. Fonte canônica: docs/CONFIGURACAO-MODOS-N3.md.

Complemento: aplicar também a Gradeadas/Sarrafeadas e Garfos Sim/Não. Os cinco modos devem dividir a largura disponível em uma única linha horizontal, com quebra do texto dentro dos cards e crescimento vertical apenas quando necessário. Economia de altura é prioritária para o dono.

Complemento de espaço vertical: remover a legenda permanente “Opções deste pavimento”. Preservar somente mensagens temporárias de salvamento e erros.

### Consolidação de níveis — 2026-10-01

As linhas abaixo registram instruções desta conversa, sem criar cotas universais. O identificador local D64-20261001-user-confirmation não renumera nem revoga D-64 do catálogo LV.

| Decisão | Escopo e regra | Fonte |
|---|---|---|
| NIV-REGIOES-20261001 | LAJ: medir nível e h por região; fundo = nível − h/100. Fundo igual mantém uma laje; diferente comprovado destaca vermelho. Degraus/cortes de laje amarelos na Visão de Cortes. | Dono, comentários e instruções desta conversa de 01/10; D-52 preservada |
| NIV-SEGMENTOS-20261001 | FV/LV: níveis e confiança por segmento; match espacial de fundos/laterais com faixas quando necessário; suporte independente nos dois sentidos sem ciclo. | Dono, pedido de níveis segmentados nesta conversa |
| NIV-PIL-FINAL-20261001 | PIL: nível final da face em contato com a laje/região/viga mais alta; base separada. | Dono, instrução sobre nível final dos pilares nesta conversa |
| NIV-PREPROCESS-20261001 | Coletar análise SA necessária para preencher a convenção com qualidade antes do consumo; confiança realmente calculada e QA por unidade. | Dono, instruções de pré-processamento e QA nesta conversa |
| NIV-FUNDO-CONTINUO-13PAV-20261001 | Somente L313/BD3, L320/BD6, L321/BD7, L322/BD8, L323/BD9, L324/BDA da revisão examinada: h10 = 852,16 e h13 = 852,19, fundo contínuo. | Dono confirmou explicitamente em 01/10; arquivo derivado com SHA e UID |
| NIV-CORTE-CONTATO-20261001 | Antes de perguntar cota, medir corte em contato real; L317 resolvida por L316/BD4 +3 cm. O exemplo não é hardcode. | Dono indicou o corte; prova geométrica em RESOLUCAO-L317-D64.md |


### NIV-LV-CONTINUIDADE-20261002 — passagem sobre pilar não muda nível

Dono confirmou em 02/10: a parte da lateral que passa pelo pilar não afeta o nível do segmento; conserva a definição de lajes, fundo e Visão de Corte já estabelecida para ele. Ausência local de fundo desenhado não implica mudança de cota. Mudança real deve ser tratada na segmentação/evidência, sem unificar fontes divergentes. Manual integrado §10.

### FV-REFERENCIA-MANUAL-20261002 — repartição do encontro angulado

O dono desenhou V307/V306/VF202/VF203 no 13_PAV e pediu ao motor chegar dinamicamente à mesma interpretação. A referência corrige a repartição anterior por metades: no caso de duas continuações colineares com larguras distintas e terceiro braço angulado, a continuação estreita termina na parede do braço; a larga e o braço têm uma interface única entre suas paredes reais. Geometria humana protegida, sem nomes/coordenadas especiais nem consumo de N2/N4 pelo N1. Hipótese geométrica implementada e validada por testes/replay, com tolerâncias residuais medidas; não constitui aprovação humana automática de todo o pavimento. Ver FV.md §1 e relatório `20261002_fv_stepped_junction`.

Achado técnico da validação sem cache: contatos arredondados entre vértices e
arestas impediam o preenchimento inicial de um triângulo do encontro. A correção
fica limitada à célula comprovada e à tolerância numérica de 0,05 cm, preservando
material existente. Não é limite mínimo de fundo nem autorização para unir
separações reais; ver FV.md §1. Não é uma nova convenção atribuída ao dono.


### NIV-LV-DEGRAUS-20261002 — laterais Para/Passa nos degraus das lajes

O dono confirmou que os degraus reconhecidos pelo SA das lajes devem seccionar as laterais de viga Para e Passa que os tocam. No N3, os segmentos seguem encostados em sequência, com as aberturas. A passagem sobre pilar não muda nível. V329 possui fundo e usa L318/852,19 à esquerda e vazio à direita; a maior profundidade da V329 (19/60) lhe dá passagem no P27 frente à V328 (19/55). V309A B exemplifica a divisão por regiões da L309. Motor aplica geometria e regiões dinamicamente, sem exceção por nome. Regra integrada: manual de níveis §11; QA e limitações no relatório 20261002-lv-degraus-continuidade.

### NIV-VIGA-LAJE-PAINEL-20261003 — degrau da laje não muda a viga

O dono esclareceu: mudança de nível da viga exige Visão de Corte ou mudança do hatch/preenchimento da própria viga. Degrau da laje, sozinho, não determina mudança da viga. Na ausência dessa evidência, manter a referência da viga, desenhar a laje na cota regional e um painel acima para fechar a diferença (3 cm no exemplo). A divisão das laterais Para/Passa permanece, sem confundir segmentação executiva com mudança da cota da viga. O motor deve publicar essa distinção na ficha para o N3; não consultar N2/N4 como fonte N1. Ver manual de níveis §13. O reconhecimento completo de mudanças de hatch/preenchimento ainda requer QA geométrico próprio; esta decisão não certifica automaticamente fontes estimadas.

### FV-PILAR-SOLIDO-20261002 — proteção de fundos herdados e reconstruídos

O dono apontou invasões de P19 por V303 e de P18 por V330 no 13_PAV e pediu correção preventiva. Achado técnico: os pilares já eram reconhecidos como sólidos, mas a exclusão alcançava a recuperação de trechos novos, não todos os contornos herdados/reconstruídos. A proteção deve reaplicar a diferença geométrica com os sólidos antes da recuperação e depois da resolução de encontros/prolongamentos. NASCE e pilares explicitamente ignorados não bloqueiam; nenhum limite mínimo de comprimento é introduzido. Fragmentos positivos e cortes internos são preservados sem preencher o sólido. Geometrias manuais/validadas não são alteradas silenciosamente; conflitos são registrados para revisão. Regra geral sem nomes/coordenadas especiais; FV.md §1 e relatório técnico 20261002_fv_stepped_junction. Não implica certificação Arete global.


### N3-NOVA-PIL-ESPECIAL-CIMA-20261003 — padrão aprovado do L

O dono aprovou a prévia L v26 do CIMA especial Nova e pediu sua generalização dinâmica a partir do SA para U/T, com faces A–H. A aprovação cobre o L; U/T são propostas para avaliação própria. Regras consolidadas de painéis vermelhos, encontros internos/externos, grades sem sobreposição, parafusos, hachuras, letras e cotas: [PADRAO-NOVA-PILARES-ESPECIAIS-CIMA.md](../PADRAO-NOVA-PILARES-ESPECIAIS-CIMA.md). Preservar ABCD; desenho de grades aprovado separadamente. Não confundir aprovação visual do experimento com integração no motor de produção.

### N3-NOVA-CIMA-T-FACES-PERFIS-20261003

Na proposta CIMA do T, o dono pediu trocar A com H e C com E; perfil metálico
somente nas laterais, sem fechar as três pontas livres. Correção aplicada na
prévia T_v2; não constitui aprovação geral do T nem integração em produção.
Correspondência física documentada em PADRAO-NOVA-PILARES-ESPECIAIS-CIMA.md.

### FV-MODULACAO-244-20261003 — chapa limitada sem cortar a dobra angular

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| FV-MODULACAO-244-20261003 | 2026-10-03 | global | Limite normal de chapa de 244 cm independente da dobra angular; emendar na parte reta, nunca no nascimento do L. Preservar a dobra inteira e todos os pedaços positivos; L a 90° mantém regra própria | `docs/SA-ANALISE/CLASSES/FV.md` §1 | vigente |

O dono esclareceu que o limite normal de 244 cm também vale no fundo angular.
Não é uma divisão causada pela dobra: a emenda deve ocorrer na parte reta,
mantendo a dobra inteira no painel terminal. O L a 90° continua sujeito à sua
regra própria de dois painéis. Não generalizar uma regra como substituta da outra.
Detalhar cotas da dobra e do chanfro pelos vértices; N2/N4 são comparação QA,
nunca fonte de geometria do SA. Preservar todos os pedaços positivos, inclusive
1 cm. Aplicação dinâmica sem exceção por viga ou pavimento em FV.md §1; evidência
e limites em `scripts/arete/relatorios/20261003_v307_modulacao/`.


### NIV-CORTE-CONTINUIDADE-20261003 — operacionalização geométrica

A regra do dono sobre corte/hatch e continuidade de viga é operacionalizada com haste do corte medida, aba da laje conferida e mesma seção espacial. Dimensão próxima de pilar não vale como altura FV quando a largura diverge. Degrau de laje continua separado da referência de viga. Não promover inferência a medição: preservar conflitos, fontes e score limitado. Critérios, tolerâncias e limitações estão no manual de níveis §14; exemplos VF203/VF301 são evidência de QA, nunca exceções por nome.

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| NIV-CORTE-CONTINUIDADE-20261003 | 2026-10-03 | global | Corte medido compatível com largura FV, profundidade e aba da laje pode ancorar mesma seção espacial; preservar score, fontes e conflitos. Rejeitar B/H de pilar incompatível; altura FV pode vir de seção lateral coincidente e única. Bloquear preenchimento não revisado e DXF ausente. | docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md §14 | vigente |
| NIV-VIGA-LAJE-PAINEL-20261003 | 2026-10-03 | global | Mudança de nível da viga exige corte ou transição de hatch/preenchimento; degrau de laje secciona lateral mas conserva referência da viga quando não há mudança comprovada, com painel superior para diferença. | docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md §13 | vigente |


| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| NIV-PADRAO-EXCECAO-20261003 | 2026-10-03 | global | Topo da viga no nível principal da laje ou base de saída do pavimento na ausência de laje; aplicar padrão quando não houver indicação diferente. Exceções por hatch/corte prevalecem. Lajes/vigas definem seus níveis; pilares acompanham contatos. Interpretação de vigas em níveis diferentes por hatch/corte pendente de treino com futuros exemplos reais. | Dono, resposta explícita nesta conversa; manual de níveis, seção Referência padrão e exceções explícitas | vigente; integração dinâmica e QA do motor precisam ser verificados |

### CORTE-CAUDA-LOCALIZACAO-20261003 — cortes interpretados no estrutural

O dono pediu centralizar os cortes nos respectivos segmentos de viga, evitando pilares e sobreposição. Autorizou comprimir visualmente somente a cauda reta maior que 80 cm, mantendo a região com lajes sem compressão, a cota física correta e um símbolo de interrupção dentro do corte. Não autoriza inventar lajes, níveis ou dimensões ausentes. Implementação e limites de QA: `scripts/arete/relatorios/20261003_cut_slab_contact_placement/RELATORIO.md`.

### FV-DECIMAL-CHANFRO-20261003 — comprimentos e continuidade SA→N3

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| FV-DECIMAL-CHANFRO-20261003 | 2026-10-03 | global FV | Comprimentos em campos e cotas N3 com uma casa decimal e vírgula; preservar precisão geométrica e reproduzir chanfros do contorno SA efetivo, sem confundir ponta convexa e dobra em L. | Dono nesta conversa; docs/SA-ANALISE/CLASSES/FV.md, Apresentação decimal e ponta chanfrada | vigente; validado V306 e testes rotacionados |

O dono exige comprimentos com uma casa decimal nos campos e no desenho N3
(417,98 → 418,0; 417,88 → 417,9), além do reconhecimento e reprodução dos
chanfros do SA. A precisão geométrica/persistida permanece intacta: arredondar
somente a apresentação. Implementação dinâmica sem nomes de vigas fixos;
quadrilátero chanfrado é distinto de dobra em L. Fonte canônica:
`docs/SA-ANALISE/CLASSES/FV.md`, Apresentação decimal e ponta chanfrada.


### Harmonia e transparência da confiança — NIV-HARMONIA-GATES-20261003

| ID | Data | Escopo | Decisão | Fonte | Estado |
|---|---|---|---|---|---|
| NIV-HARMONIA-GATES-20261003 | 2026-10-03 | global LAJ/FV/LV/PIL | Cruzar fontes e cortes LV por região/segmento/face, com gates de origem, associação, interpretação, exceções e concordância; evitar confirmação circular e porcentagens exageradas. | Dono, pedido de planejamento e aprovação do plano nesta conversa; manual integrado de níveis | plano aprovado; implementação nova delegada, não certificada por este registro |
| NIV-CONFIANCA-EXPLICADA-20261003 | 2026-10-03 | portal/QA | Mostrar percentual com explicação na ficha: fontes, cálculo, confirmações independentes, limitações e gates por unidade. | Dono, escolha explícita “% com explicação” na pergunta desta conversa | requisito aprovado; conferir implementação e consumo |

O plano aprovado começa com regras determinísticas e suporte reproduzível, sem bônus arbitrário nem aprendizado por reforço nesta etapa. Corte CAD e seção reconstruída são origens distintas. A mesma fonte atravessando classes não gera votos novos. Calibração probabilística futura precisa de validação independente. Regras anteriores do dono sobre padrão/exceções, degraus, ausência de laje e pilares continuam vigentes; detalhes canônicos no manual integrado.
| 2026-10-03 | PIL / NOVA / N5 | Conferir todas as faces existentes A–H por pilar e variante; C/D só têm grade com largura >40 cm, e H do T também. Agrupar peças idênticas preservando todos os nomes e a quantidade de ocorrências; bloquear N5 se faltar grade obrigatória. Continuações do índice imediatamente após o índice, deslocando e renumerando todas as demais folhas. | Dono, portal 13_PAV | Ativa |


### NIV-INVERTIDA-LOCAL-20261003 — referência padrão das invertidas

O dono confirmou: a viga invertida sobe altura da viga menos espessura da laje acima do nível da laje respectiva do trecho. Pediu aplicar como padrão das invertidas. Topo = nível da laje + (altura − espessura)/100; base = nível da laje − espessura/100. Referência local, sem impor base contínua entre trechos. Exceção explícita do corte prevalece; inversão precisa de evidência própria. Fonte: confirmação nesta conversa, trecho V330 71/L308. Regra canônica: docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md §4. Implementação inicial local na conversão; integração SA/N3 completa e portal ainda não certificados.

### TAMPA-INVERTIDA-ENCONTROS-20261004 — montagem entre faces

O dono confirmou na ficha V330_duvida_tampa_encontros.html: a tampa para nas faces das vigas incidentes, mesmo estando acima delas. Caso medido V330: P18→V301 = 311 cm e V301→VF301 = 183 cm, total 494 cm; excluir os 19 cm da V301 e os 14 cm da VF301 do comprimento de montagem. É regra de divisão das tampas, independente do contato vertical das laterais. Não alterar o concreto ou os níveis para forçar essa divisão. Fonte: resposta explícita nesta conversa em 2026-10-04. Conversão deve conservar o inventário dos encontros excluídos; não eliminar trechos sem evidência geométrica identificada.

### NIV-LAJE-CAMADAS-20261003 — nível de laje sem cota por camadas de confiança

O dono decidiu, para laje sem cota escrita:

1. As vizinhas através de viga que concordam provam o nível, se nenhuma contradiz.
2. Havendo contradição, verificam-se as visões de corte (as desenhadas e as interpretadas).
3. Persistindo a dúvida, vence o nível mais frequente entre vizinhas e segmentos que tocam a laje.

Muitas contradições baixam o percentual; muitas fontes concordantes sobem. A votação tem teto de 75%. A concordância só sobe entre origens independentes, e um segmento derivado da própria laje não vota ("para evitar confirmação por ciclicidade").

Sobre a asa: asa de corte ≠ h é erro de desenho humano, e o h declarado vence.

O consenso de vizinhas através de viga não é associação por proximidade. Não há hachura de laje neste desenho.

Complemento aprovado (v21): uma viga através da qual lajes com nível próprio já diferem é linha de degrau provada; ali o voto de continuidade não atravessa. Fonte: conversa de 03/10/2026. Regra canônica: docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md, seção NIV-LAJE-CAMADAS-20261003.

### N3-NOVA-ABCD-COTAS-FURACAO-20261004

O dono pediu trocar a altura da cadeia horizontal dos parafusos com a cota total da largura do painel no ABCD: cadeia acima, total abaixo. Medidas e furações permanecem iguais. Regra canônica: `docs/SEMANTICA-PILAR-NOVA.md`, seção 9.

### FV-T-MESMA-ALTURA-20261004 (D-90/FV)

| D-90/FV | 2026-10-04 | FV | **T de vigas de mesma altura: a viga que chega atravessa a outra e a outra é dividida nela.** Caso V303 × viga vertical 19/55 do P23 (13_PAV): a V303 não toca o P23 e segue reta; como o toco entre a V303 e o P23 é pequeno (10 cm), o fundo da viga que chega passa pela faixa da V303 (fica 29 cm) e a V303 para nas paredes dela (seg 5 fim / seg 6 início). Critério do dono: evitar segmento minúsculo. T com alturas diferentes segue "viga mais funda cruza" (FV.md §4) | dono, chat 04/10 com print do P23 | vigente — trava QA de chegada lateral implementada 04/10 (`qa_cad_gate.measure_beams`, não publicada) |
| D-91/LV | 2026-10-10 | LV | **Para e Passa têm laje igualmente, inclusive no trecho que passa pelo pilar.** Passar pelo pilar não impede laje encostando na face: o segmento Passa sobre o pilar deve declarar a laje que encosta, como qualquer outro. Casos 13_PAV: V309A B Passa seg 1 (L319) e V330 A Passa seg 4-A (L318), onde o SA declara nenhuma | dono, chat 10/10 (“mesmo no caso de passaram pelo pilar essa parte que passou tem laje também”) | vigente — o gate CAD LV (`measure_lateral_beams`, laje da face) já diverge nesses casos; correção do SA pendente |
| D-92/QA | 2026-10-10 | QA/Visão Corte | **O gate CAD pós-SA deve revisar também as Visões Corte, originais e interpretadas,** como um gate de níveis e dimensões das lajes e de cada segmento de viga, incluindo degraus de laje e de viga. Divergência na Visão Corte indica erro de nível, que é grave | dono, chat 10/10 (“o gate-pós-sa poderia revisar também os visão corte? é fundamental”; “visão cortes originais e visão cortes interpretados, incluindo degraus de lajes ou de vigas”) | registrado, não implementado — escopo em QA-GATE-MECANISMOS-E-EVOLUCAO.md §5 |

### FV-NORMAL-CRUZA-INVERTIDA-FACE-B-20261004

O dono determinou que V301 SEG 16, normal para baixo, atravesse a faixa da V330 invertida e chegue à parede direita B, como no DXF, em vez de parar em A. Ambas as paredes estruturais chegam a B; o fundo está abaixo da base da invertida. Aplicar por níveis absolutos e cobertura confirmada, conservando geometrias humanas, IDs e quantidade. A chegada a B vale para este encontro com P49, cujo contorno em planta termina na mesma face. Fonte: comentário do dono em SA/fundo, 04/10/2026. Regra canônica: docs/SA-ANALISE/CLASSES/FV.md, seção 1.
