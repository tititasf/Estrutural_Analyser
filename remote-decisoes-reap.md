# Registro de decisões do dono

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
| D-74 | 2026-09-29 | Materiais | **Sequência dos pavimentos = a ordem de todos os pavimentos da obra** (subsolos, térreo, 1º, tipo 2–10 como um pavimento só, 11º, 12º, cobertura, deck…): pavimento ausente no cadastro não quebra a sequência; o estoque só começa do zero no primeiro pavimento (ex.: subsolo). O portal de fôrmas guarda anterior/próximo de cada pavimento | chat 2026-09-29 | vigente, implementado 29/09 — `portal_obra_pavimentos`, `GET/PUT /obras/{obra_id}/pavimentos/ordem`; consulta usa a ordem cadastrada, com fallback provisório por nome em obras ainda não configuradas |
| D-75 | 2026-09-29 | Materiais | **Sobra limpa de chapa pode ir para outra classe** (só recorte puro de painel/chapa, sem sarrafo); painel montado e retalho com sarrafo continuam só na própria classe. Mantém ID e registro de proveniência e de fornecimento | chat 2026-09-29 | vigente — implementado 29/09 (`docs/MATERIAIS-E-CONSTRUCAO.md` §12.6) |
| D-77 | 2026-09-29 | Materiais | **Sobras: máximo aproveitamento, peças grandes primeiro** — não há ordem de classes; os painéis maiores de todas as classes do pavimento escolhem primeiro a sobra (a menor que serve) | chat 2026-09-29 | vigente — `docs/MATERIAIS-E-CONSTRUCAO.md` §12.6 |
| D-78 | 2026-09-29 | Materiais/Portal | **Reaproveitamento em 2 frentes: Para e Passa**, calculadas e listadas separadas (pilares e laterais de cada modo); fundo e laje entram igualmente nos dois, sem citar Para/Passa. A obra tem o campo **comportamento Para / Passa / Misto** (Misto = hoje, as 2 listas); a consulta exibe só a lista do modo da obra | chat 2026-09-29 | vigente, implementado 29/09 — `portal_obras.comportamento`, filtro de rotas internas e códigos públicos, payload público da obra/pavimento |
| D-76 | 2026-09-29 | FV | **Laterais servem de ajuda ao fundo, não de regra rígida** (espelho de o FV ser referência da LV): o fundo deve ficar tão completo quanto as laterais — trecho com as duas paredes reais e sem fundo ganha painel; painel na faixa de outra viga volta para a dona. Sempre com prova local do DXF (linha real, fora de cota, pilar sólido/hachura fora); fundo validado não muda | chat 2026-09-29 (apontamento 9cf6beac) | vigente, implementado 29/09 — `docs/SA-ANALISE/CLASSES/FV.md` §1, `src/core/beam_interpreters/fundo_viga_lateral_ref.py` |
