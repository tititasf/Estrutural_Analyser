# LV - Compreensao De Interpretacao N2/N4

Data: 2026-06-23  
Escopo: laterais de vigas (`LV`) em engenharia reversa, ficha N2 e reproducao N4.  
Fonte empirica atual: `Obra_TREINO_1`, pavimento `13 PAV`, 30 vigas LV.

> **Limite arquitetural (2026-07-21):** este documento descreve a leitura N2
> e seus aprendizados empiricos. Ele nao define heuristicas para o gerador.
> O contrato autoritativo do motor esta em
> `docs/CONTRATO-RIGIDO-MOTOR-LV-N3-N4.md`. A ficha e a unica entrada do N4;
> ausencia de elemento e falha de interpretacao, enquanto desenho incorreto de
> campo presente e falha do motor.

Este documento registra os aprendizados do loop N2 -> ficha -> N4 -> validacao visual.
Ele deve servir como base viva para uma futura harmonizacao/RAG por classe estrutural.

## 1. Modelo Mental Da Classe LV

Uma lateral de viga nao deve ser tratada como um unico desenho plano. Ela tem duas familias
de informacao:

- `section_views`: visoes de corte, usadas para entender a secao transversal da viga.
- `face_units`: unidades laterais A/B, usadas para reproduzir as elevacoes laterais.

A ficha canonica deve preservar as duas familias. A geracao N4 pode reorganizar as
unidades A/B em ficha limpa, desde que os dados estejam corretos. A posicao original no
recorte N2 e uma pista de extracao, nao uma obrigacao de layout do N4.

## 2. Status Atual De Confianca

Pontuacao humana/tecnica atual:

- Visao-corte geral: 88%.
- Laterais A/B geral: 68%.

Metricas do ultimo loop A/B completo:

- Itens avaliados: 30 vigas.
- Unidades A/B renderizadas: 114.
- `missing_A`: vazio.
- `missing_B`: vazio.
- Media visual automatica conservadora: 34.8%.
- Minimo visual automatico conservador: 18.2%.

Observacao importante: a metrica automatica de imagem ainda penaliza crop, escala e texto
externo. Ela serve para triagem de regressao, nao como veredito final. A aprovacao visual
humana/vision do chat esta acima da metrica numerica bruta.

## 3. Padroes Confirmados

### 3.1 Visao-corte

Padroes observados:

- A visao-corte pode ser extraida com alta confianca a partir de `section_views`.
- O caminho N2 -> N4 -> reextracao esta estavel para o pavimento validado.
- O roundtrip atual fechou 33/33 pares de visao-corte.
- O N4 precisa manter a coluna A/B afastada da coluna de corte para o viewer isolar a
  visao-corte sem contaminar o crop com laterais.
- Primitivas visuais podem permanecer como evidencia do interpretador e do QA,
  mas nao substituem os campos executivos do contrato rigido.

Padrao de geracao:

- Desenhar o corte a partir dos campos executivos validados da ficha.
- Nao reler nem copiar primitivas do recorte durante a geracao estrita.
- Render/crop deve isolar a zona de corte e evitar puxar lateral A/B para dentro do quadro.

#### Correspondencia obrigatoria Corte <-> A/B

- Corte e contexto comum da mesma viga; nao autoriza espelhar, mesclar ou copiar
  dados entre os contratos A e B.
- Cada sarrafo horizontal declarado em A/B precisa ter a altura correspondente
  no Corte de sua propria face. Os pequenos retangulos verticais/horizontais
  do Corte sao sarrafos, nao simbolos de cota, e recebem hachura diagonal.
- As cotas internas B/H usam linhas e ticks convencionais; os quadrados do
  dimstyle nao sao geometria de forma. O titulo usa `VIGA (H x B)`, por
  exemplo `V327 (50x14)`.
- N3 usa esta anatomia com B/H/h_A/h_B do contrato N1; N4 usa os campos N2.
  Sem transportar primitivas N2/N4 para N3.

### 3.2 Lados A/B

Padroes observados:

- Cada recorte LV representa uma unica viga, mas pode conter varias unidades/continuacoes.
- Labels como `V301.A`, `V301.B`, `CONT. V301.A` ajudam a classificar, mas nao sao fonte
  absoluta.
- Quando todos os labels aparecem com o mesmo sufixo, mas existem fileiras distintas, a
  inferencia visual deve prevalecer:
  - fileira superior = lado A;
  - fileira inferior = lado B.
- Exemplo confirmado: V331 vinha com dois textos `V331.B`, mas a ficha correta e `V331.A`
  e `V331.B`.
- Unidades A/B devem ser geradas no N4 de forma organizada, em colunas A/B, e nao presas
  a coordenadas originais do recorte.

### 3.3 Reaproveitamento / hachuras

Padroes observados:

- Hachuras de reaproveitamento existem no N2 na layer `REAPROVEITAMENTO`.
- O motor ja conseguia detectar `reuse_regions`, mas a canonicalizacao descartava esses
  campos.
- A ficha canonica precisa preservar:
  - `reuse`;
  - `reuse_regions`;
  - `holes`;
  - `is_first`;
  - `is_last`;
  - `codigos_forma`.
- Apos preservar `reuse_regions`, o lote atual passou a carregar 106 regioes de
  reaproveitamento em 312 segmentos.

### 3.4 Lajes e cotas

Padroes observados:

- Lajes globais por unidade ajudam, mas nao bastam.
- Alguns recortes tem laje local por segmento. O N4 deve desenhar laje por painel quando
  `laje_sup_local` ou `laje_inf_local` estiverem presentes.
- Diferencas grandes entre `h_total` e `h_body` nao devem ser automaticamente tratadas
  como laje. Exemplo de erro corrigido: lajes absurdas como 59 ou 115 cm.
- Sem cota local plausivel, a diferenca grande deve ser tratada como outra cota vertical
  do desenho, nao como espessura de laje.
- Cota proxima tambem nao basta para declarar laje. V310 mostrou que cotas `16`, `13` e `5`
  podem estar proximas da face sem existir faixa/hachura de laje na elevacao. A promocao
  de laje deve exigir geometria compativel, como hachura/faixa na regiao de topo/base.

Regra operacional atual:

- Aceitar laje local plausivel ate 35 cm.
- Acima disso, nao promover como laje sem confirmacao visual/geometrica.
- Quando nao houver hachura/faixa de laje sobreposta ao topo/base da face, manter laje como
  zero mesmo que exista cota numerica proxima.
- Se nenhum segmento tiver laje local positiva, mas a unidade tiver laje global confirmada,
  o gerador deve aplicar a laje global a todos os paineis.

### 3.5 IDs e textos internos

Padroes observados:

- O gerador antigo inventava IDs internos `1`, `2`, `3` quando nao havia `codigos_forma`.
- Para ficha reversa N2, isso e visualmente errado quando o N2 nao contem esses textos.
- O fallback de IDs deve ficar ligado apenas para fichas manuais/legadas que dependam disso.
- Para face_units extraidos do N2, usar apenas codigos reais. Se nao houver codigos, nao
  sintetizar texto.

## 4. Campos Minimos Da Ficha LV Para N4 Fiel

### 4.1 `section_views`

Campos relevantes:

- `idx`
- `label`
- `b_cm` / `b`
- `h_section`
- `h_A`
- `h_B`
- `laje_sup_A`
- `laje_inf_A`
- `laje_sup_B`
- `laje_inf_B`
- `topology`
- `visual_primitives`
- `bbox`

### 4.2 `face_units`

Campos relevantes:

- `idx`
- `label`
- `side`
- `bbox`
- `h_body`
- `h_total`
- `laje_sup`
- `laje_inf`
- `pontaletes_face`
- `grade_layer_style`
- `segments`

### 4.3 Segmentos de face

Campos relevantes por segmento:

- `largura_cm`
- `height1`
- `height2`
- `panel_type`
- `grade_h1`
- `grade_h2`
- `laje_sup_local`
- `laje_inf_local`
- `slab_top`
- `slab_bottom`
- `slab_center`
- `reuse`
- `reuse_regions`
- `holes`
- `is_first`
- `is_last`
- `codigos_forma`

## 5. Decisoes De Geracao N4

Decisoes atuais:

1. Visao-corte deve ser isolada da coluna A/B.
2. A/B deve ser organizado em ficha limpa, separado por colunas A e B.
3. A/B nao precisa preservar coordenada original do recorte N2.
4. Reaproveitamento deve ser desenhado somente nas regioes detectadas, nao como painel inteiro
   quando existe `reuse_regions`.
5. IDs internos nao devem ser inventados em fichas reversas.
6. Laje deve preferir valor local por segmento quando existir.
7. Campos ausentes nao devem ser preenchidos por hardcode de viga; usar regra geometrica ou
   deixar pendente.
8. O render de validacao precisa respeitar o bbox exato. O backend `MatplotlibBackend` pode
   alterar o tamanho da figura durante o draw; o runner deve resetar `fig.set_size_inches`
   depois de `draw_layout` para evitar que o crop puxe outras unidades.
9. Em ficha reversa A/B, a nomenclatura do N4 deve ser menor que o default de ficha manual.
   Titulo grande domina a comparacao visual e nao reflete o padrao pequeno do N2.
10. Textos de pontalete em ficha reversa devem usar posicao extraida do N2 quando possivel.
    No lote atual, V330.B extraiu tres textos posicionais: `5 1/2pont`, `8 1/2pont`,
    `8 1/2pont`.
    Quando o texto existe no N2, preservar tambem `layer`, `color` e `height`.
11. Grade reversa deve respeitar as layers reais da unidade N2. Se a unidade nao tiver
    SARR real no bbox, desenhar a Grade como `Painéis` e suprimir spans globais de sarrafo.
    Se tiver SARR real, manter estilo nativo. V330.A usa `paineis`; V330.B usa `native`.
12. Cota de altura pode estar no lado esquerdo da unidade, mas so deve confirmar par quando
    o label estiver encostado na borda esquerda e fora do span superior. Isso corrige V316.B
    sem promover cotas externas em V301.
13. Laje global tambem precisa de hachura/faixa compativel. O Passo 2 de cotas pequenas nao
    pode promover `laje_sup`/`laje_inf` apenas por numero proximo; V321.A mostrou falso
    positivo de laje superior sem HATCH.
14. Validacao visual de unidade estreita com label real deve incluir o label no crop N2.
    Isso nao muda a ficha nem o N4; apenas evita falso negativo quando o N4 desenha um
    texto que existe no N2 mas estava fora do bbox estrito. V331.A confirmou a regra.
15. Texto numerico em `Painéis` pode ser cota total, nao apenas largura. Para promover
    `h_total` acima de `h_body`, exigir detalhe local e `h_body >= 80`. V312.A/V325.A
    confirmaram `h_body=103` e `h_total=124`; V321.A mostrou o falso positivo em segmento
    baixo.
16. `slab_center` e campo de ficha. Ele so deve virar faixa/hachura no N4 quando o segmento
    tem altura alta (`height1 >= 80`); em segmentos baixos, manter como evidencia sem desenhar.

## 6. Modelo de Segmentos/Painéis Confirmado (2026-06-28, via vision V301)

### 6.1 Estrutura visual N2 LV (segmentos vs painéis)

Descoberto por leitura vision iterativa com o dono sobre V301:

- Cada `face_unit` no DB representa o TEMPLATE de 2 segmentos visuais exibidos
  lado a lado (par espelho) no recorte N2. O motor detecta 1 face_unit, o DXF
  mostra 2 instâncias espelho.
- Cada segmento visual tem 2 PAINÉIS (não 4 sub-widths como o motor extrai):
  - Painel 1 (esq): `largura_cm` = grande (ex. 244), `height1` = REDUZIDO (ex. 44cm)
    — painel baixo sobre o pilar/cruzamento.
  - Painel 2 (dir): `largura_cm` = restante (ex. 161.5), `height1` = h_body (ex. 109cm)
    — painel completo do vão.
- O motor extrai 4 sub-widths [244, 28.7, 21.8, 111] por LIMITAÇÃO: as
  V-lines internas de sarrafo/abertura criam sub-segmentos extras. Os sub-widths
  28.7+21.8 = 50.5 = largura real da abertura em P2.

### 6.2 Abertura (recorte de canto)

- Uma abertura é um recorte retangular no canto de um painel (não um buraco
  interno), identificado por LWPOLYLINE DASHED na layer Painéis.
- Campos capturados: `corner` (TL/TR/BL/BR), `width`, `height`, `position`.
- A partir de 2026-06-28 o motor também exporta `raw_holes` por face_unit:
  lista de todas LWPOLYLINE DASHED que intersectam o bbox da face, em
  coordenadas brutas. O gerador N4 pode usar isso para perfis em L/degrau.

### 6.3 Height1 por segmento (degrau de painel)

- Antes: `height1 = h_body` para todos os painéis de uma face_unit.
- Agora (2026-06-28): o motor detecta H-lines INTERNAS da layer Painéis dentro
  do y_range da face. Se uma H-line interna abrange ≥55% do X de um segmento e
  está pelo menos 5cm acima de y_bot, `height1 = y_top - y_inner` (altura real
  do painel, menor que h_body).
- Exemplo V301.A: P1 [0,244] → height1=44; P2 e sub-segs → height1=109 (=h_body).

### 6.4 Laje (campo ainda problemático em V301)

- Laje correta de V301.A na imagem: 15cm (COTA "15" visível no topo).
- Motor extrai laje_sup=7cm. Causa provável: o motor encontra um H-line pair
  com h_body=125 confirmado pela COTA "124" (h_total correto de P2), porque
  124 ≈ 125 dentro da tolerância de 1.5cm. Com h_body=125 e h_total=124 o
  motor computa laje=124-125=-1 → 0, e cai no passo 2 que pega algum "7".
- Fix futuro: tornar a confirmação por COTA mais restrita ao lado DIREITO do
  par específico, não ao range geral do label.

### 6.5 Regras RAG adicionais (LV/AB/)

17. `LV/AB/h1_per_panel`: painéis em degrau têm `height1` diferente do
    `h_body` da face. Detectar via H-line interna que abrange o painel mas
    não a face inteira.
18. `LV/AB/raw_holes_face`: `raw_holes` no face_unit contém LWPOLYLINE DASHED
    em coords brutas; usar no N4 para recortes de canto (perfil em L/degrau).
19. `LV/AB/panel_count_vs_subwidths`: o motor extrai N sub-widths por V-lines;
    os visuais "painéis" do engenheiro são agrupamentos desses sub-widths
    separados por aberturas/sarrafos. Para V301.A: 4 sub-widths = 2 painéis
    visuais (P1=244, P2=161.5 com abertura 50.5×65).
20. `LV/AB/mirror_pair`: cada face_unit do DB = 2 segmentos espelho exibidos
    lado a lado no recorte N2. O N4 deve replicar o template 2× (normal +
    espelho) ao gerar por face_unit.

## 7. Gaps Restantes

Principais itens que ainda seguram A/B abaixo de arete:

- Cotas externas e textos fora do crop N2 ainda confundem a comparacao visual automatica.
- Alguns casos tem laje local dificil de separar de cota estrutural.
- Algumas unidades ainda apresentam fragmentacao alta, especialmente em vigas com muitas
  continuacoes.
- `Grade` ainda precisa validacao focada. V330 mostra que `grade_h1` e altura do corpo
  podem representar conceitos diferentes: a faixa A pode ter corpo baixo e pernas de grade
  altas. O N4 nao deve transformar isso automaticamente em altura total de face.
- Textos de pontalete (`N 1/2pont`) existem visualmente em algumas Grades, mas a formula
  generica por painel polui a ficha. Esse campo deve ser extraido do N2 quando existir,
  nao inferido sem evidencias.
- `holes` ainda esta zerado no lote atual; pode ser real para este pavimento ou gap de extracao
  a confirmar em outros pavimentos.
- Pilares/aberturas de pilar ainda nao estao validados como gate forte em A/B.

Piores casos atuais por score automatico:

- V310 A/B.
- V316 B.
- V330 B.
- V321 A.
- V301 B.
- V330 A.
- V322 B.
- V312 B.
- V310 A.

## 7. Insights Para RAG/Harmonizacao Por Classe

Para futura memoria/RAG por classe, cada aprendizado deve ser armazenado como regra com:

- classe: `LV`;
- divisao: `VC` ou `A/B`;
- sintoma visual;
- regra de interpretacao;
- campos afetados;
- exemplos positivos;
- exemplos negativos;
- nivel de confianca;
- ultima validacao de lote.

Exemplos de entradas RAG candidatas:

1. `LV/AB/side_inference`: se todos os labels tem mesmo sufixo, mas existem duas fileiras
   visuais, inferir A/B pela ordem vertical.
2. `LV/AB/reuse_regions`: hachura `REAPROVEITAMENTO` deve ser preservada como regioes por
   segmento.
3. `LV/AB/no_synthetic_ids`: nao inventar IDs de painel em ficha reversa sem `codigos_forma`.
4. `LV/AB/organized_n4_layout`: gerar A/B em colunas limpas, nao em coordenadas originais.
5. `LV/VC/visual_primitives_first`: quando houver primitivas visuais da secao, preferir
   reproducao por primitivas ao template generico.
6. `LV/AB/plausible_slab`: laje acima de 35 cm precisa confirmacao; caso contrario tratar
   como cota nao-laje.
7. `LV/AB/slab_requires_geometry`: cota de laje so vira campo de ficha quando existe faixa
   ou hachura de laje compativel na regiao visual da face/segmento.
8. `LV/visual/exact_bbox`: validar A/B com bbox estrito; falso negativo visual aparece quando
   o renderer expande o eixo e inclui corte ou outra face no N2.
9. `LV/N4/reverse_label_scale`: labels de unidades vindas do reverso devem ser discretos, nao
    titulos grandes de ficha manual.
10. `LV/AB/pontalete_explicit`: textos `N 1/2pont` em Grade devem ser extraidos como campo
    explicito por unidade ou por painel; a formula do gerador manual nao e confiavel para
    ficha reversa organizada.
11. `LV/AB/grade_layer_style`: Grade de ficha reversa deve escolher estilo por unidade:
    `paineis` quando o N2 nao tem SARR no bbox; `native` quando o N2 contem SARR real.
12. `LV/AB/left_height_cota_guarded`: aceitar cota vertical de altura no lado esquerdo apenas
    quando o label esta colado na borda esquerda e fora do span superior; evita confundir
    cotas externas com nova altura de face.
13. `LV/AB/global_slab_requires_geometry`: laje global extraida por cota tambem exige hachura
    ou faixa de laje compativel; cota pequena isolada nao deve virar laje.
14. `LV/visual/labeled_narrow_bbox`: para validacao visual, unidades estreitas com label real
    podem expandir o bbox ate o texto; nao aplicar em unidades largas para nao poluir a media.
15. `LV/AB/panel_numeric_total_height`: numeros na layer `Painéis` podem preencher
    `h_total` quando passam filtros de largura, faixa local e altura minima.
16. `LV/AB/slab_center_draw_guard`: `slab_center` extraido de cota local so vira desenho no
    N4 para segmentos altos; em segmentos baixos, e apenas campo de auditoria.
17. `LV/AB/horizontal_dimension_levels`: a cadeia individual ocupa o nivel interno;
    painel principal largo (>=150 cm) e o complemento dos demais paineis ocupam o
    nivel externo. Vale para degrau inicial e espelhado (`244 | 63+111=174` e
    `52.5+22.5=75 | 244`).
18. `LV/AB/raised_panel_witness`: as patas de uma cota horizontal devem terminar no
    fundo real do intervalo cotado. Se o intervalo pertence ao painel elevado, as
    duas patas terminam no ombro; uma borda exata nao pode cair no vazio por engano.
19. `LV/AB/coplanar_step_divider`: a divisao entre paineis elevados coplanares existe
    somente entre ombro e topo. Nunca prolongar esse divisor pelo vazio ate a base.
20. `LV/AB/top_panel_after_slab`: retangulo fechado de `Paineis`, com 4--12 cm de
    altura, imediatamente acima da laje, e campo separado da ficha
    (`painel_sup_alt/width/x_offset`). O N4 desenha retangulo e cota proprios; a
    altura total soma corpo + laje + painel superior.
21. `LV/AB/dimension_side_by_wall`: em degrau espelhado, altura de corpo/total fica
    na parede alta esquerda e alturas do painel curto ficam na parede direita. Cada
    cota vertical pertence a parede que materializa aquele nivel.
22. `LV/AB/material_body_over_bbox`: se o bbox vertical inclui cotas externas e os
    paineis formam uma altura material coerente entre 80 e 125 cm, `h_body` vem da
    maior altura dos paineis; laje e painel superior permanecem campos separados.
23. `LV/AB/explicit_zero_beats_global`: `laje_inf=0` explicito na unidade nao pode
    ser substituido pelo fallback global. O fallback so preenche campo ausente.
24. `LV/AB/dimension_chain_can_split`: a cadeia horizontal cotada pode revelar mais
    paineis que as V-lines brutas (`174 = 111+63`). A reconciliacao pode aumentar a
    quantidade de segmentos quando a soma recompõe exatamente a largura util.
25. `LV/AB/slab_dimension_outer_anchors`: as cotas de laje 14/15 pertencem às duas
    extremidades do contorno superior, nunca à parede interna do degrau.
26. `LV/N4/layout_order_is_drawing_order`: detalhes por ocorrencia devem repetir a
    ordenacao espacial final do desenhador; ordenar CONT/sem-rotulo de forma distinta
    desloca painel superior e cotas para a unidade vizinha.
27. `LV/AB/trailing_locator_pair`: dois paineis finais menores que 28 cm, cuja soma
    fica abaixo de 55 cm depois de um painel principal, sao marcos de localizacao e
    nao entram na cadeia util; o prefixo anterior pode formar cota externa 161,5.

## 8. Inventario Minimo Nas Fichas De Interpretacao / Validacao Visual

Desde 2026-07-17, validacao visual N2×N4 de LV **so e valida** com inventário
linha-a-linha (nao contagem, nao "parece igual").

Documento canônico: `docs/QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md`.

### 8.1 O que toda ficha / veredito deve carregar

1. **Metadados da face:** origem abs N2, h_body, `panel_widths[]`, clip.
2. **LINEs estruturais** Painéis+SARR: id, `(x1,y1)→(x2,y2)` rel, orient, L, status vs N4.
3. **Cotas:** no N2 sao `TEXT` numericos (muitas na layer `Painéis`); no N4 sao
   `DIMENSION`. Listar valor + insert/mid + status MATCH/MISSING/EXTRA.
4. **Textos:** label do item (`V301.A`) vs vizinhos do recorte (nao copiar).
5. **Resumo de status** e path do JSON/MD de rastreio.

### 8.2 Ficha HTML (review / granular)

Antes dos checkboxes de aprovacao/reprovacao, a ficha (ou o pacote G2-V anexo) deve
ter um bloco **"Inventario minimo"** ou link para
`scripts/arete/relatorios/g2v/{item}_n2_inventory/*.md`. Sem isso, o agente nao
pode emitir PASS no harness.

### 8.3 Exemplo ouro

V301 face A: `scripts/arete/relatorios/g2v/v301_n2_inventory/`  
Script: `scripts/arete/tmp/_v301_n2_inventory.py`.

SEG1 corpo (9 linhas estruturais) MATCH 9/9; cotas N2 agrupadas (50.5, 161.5) vs
N4 granular (28.7, 21.8, …) devem aparecer no rastreio, nao serem omitidas.

## 9. Proximos Ataques

Ordem recomendada:

1. V310: entender por que A/B tem score baixo apesar de ficha plausivel.
2. V328/V316/V305: separar falha real de crop/escala.
3. V302/V322: refinar laje local por segmento e evitar cota externa no crop.
4. V330: validar regra de `Grade`.
5. Rodar pavimento inteiro novamente e atualizar pontuacao humana:
   - alvo A/B 80%;
   - depois 90%;
   - depois 95% arete.

## 10. Regra De Seguranca

Nenhuma regra deve ser hardcoded por viga. Todo ajuste precisa ser:

- geometricamente justificavel;
- valido para lote de regressao;
- documentado aqui ou em documento sucessor;
- testado em pelo menos um item alvo e um lote de controle.
