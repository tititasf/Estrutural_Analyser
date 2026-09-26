# Questionario ao dono — interpretacao SA das Laterais de Viga (2026-09-25)

> **RESPONDIDO pelo dono em 2026-09-25 e aplicado no motor (`guia_lv_cells_v2`):**
> Q1 = abre segmento (cada segmento tem uma altura; encostados) · Q2 = (b) ·
> Q3 = pilar inteiro num segmento, com inicio/fim do pilar registrados ·
> Q4 = (a) ambos, comportamento conforme altura da viga que chega · Q5 = (a),
> -11 so' no N3 · Q6 = contagem do N4 nao e' referencia; vale a leitura
> autonoma do SA · Q7 = autonomia; o dono revisa no front-end depois.
>
> **Revisao do Q2 (2026-09-26, cruzamento V301 x V312 no portal):** "abertura de
> altura inteira" e' comportamento de DESENHO (N3) — no desenho ela e' um ESPACO
> entre um segmento e o outro. No SA isso significa PARAR: a lateral termina na
> primeira face da viga de mesma altura e recomeca na face oposta; vigas de mesma
> altura nao se atravessam. Nao confundir comportamento N3 com leitura SA.

Contexto: motor SA das laterais refeito pelas regras do guia
(`CONTRATO-RIGIDO-MOTOR-LV-N3-N4.md` §6.1.1). Estas sao as decisoes que o guia
nao fecha sozinho. Para cada uma: o que o motor faz HOJE (padrao provisorio) e
a evidencia. Responder com a letra basta.

## Q1 — Troca de secao no meio de um trecho abre segmento?

V301: a planta escreve `19/55 · 19/120 · 19/120 · 19/55` entre os pilares.

- (a) **HOJE:** NAO abre. O segmento carrega as secoes que cobre (degrau) e a
  dimensao governante e' a mais funda. Evidencia: as unidades do N2 validado
  da V301 atravessam a troca 55->120 (`[111, 63, 244]` = 418, corpo 109/44).
- (b) Abre sempre (leitura literal de G1: "cada mudanca abre segmento").

## Q2 — Viga incidente com a MESMA profundidade

V312 (19/120) cruza a V301 exatamente na zona 19/120, dentro do P42; V311 e
V319 (19/55) chegam na V303 (19/55). O guia so' fala em "menos" e "mais" profunda.

- (a) **HOJE:** trata como mais profunda — a lateral termina na primeira face e
  recomeca na face oposta (sinalizado `G7_profundidade_igual`).
- (b) Trata como abertura de altura inteira que pertence ao segmento anterior
  (§5.2.3: "abertura corta o painel inteiro -> segmento seguinte afastado").
  Indicio no N2 da V301: a primeira unidade soma `244+50.5+111` = 405,5 ate' a
  face da V312 e ainda leva `19 + 21.2` depois dela.

## Q3 — Pilar partido por uma viga que termina a lateral (Passa)

P42 (50 cm) e' atravessado pela V312 no meio. Em Passa a lateral chega a V312
pelos dois lados.

- (a) **HOJE:** cada segmento registra a sua metade do pilar (15,5 cm), com +11
  so' do lado interno ao segmento (abertura 26,5), sinalizado `G8_pilar_partido`.
- (b) Outra convencao (dizer qual).

## Q4 — Parede de pilar especial coincidente com viga (V304 x P26/V323)

A parede de 19 cm do P26 ("VER DET.") coincide com a V323 (19/50) que chega na V304.

- (a) **HOJE:** registra as duas coisas no mesmo lugar — abertura de pilar
  (Passa: 19+22) e abertura de viga (19+8, sobra 5), e fecha o segmento na
  borda final da V323.
- (b) So' pilar. (c) So' viga.

## Q5 — Recuo de 11 cm no Para

- (a) **HOJE:** a geometria do segmento termina NA face do pilar e o recuo -11
  vai como ajuste de ponta (`adjustment_start/end`), para o N3 aplicar.
- (b) A propria geometria N1 ja' deve terminar 11 cm antes da face.

## Q6 — Contagem da V301 no N4 validado

O motor novo da' 8 segmentos por lado nas quatro celulas da V301, e as somas
da A_PASSA batem com as unidades do N2 (405,5 / 418 / 418 ...). O registro da
sessao anterior diz "N4 V301 A:16 / B:16".

- (a) O 16 conta cada segmento em duas partes/linhas de desenho (8 segmentos reais).
- (b) Sao mesmo 16 segmentos — entao ha' uma fronteira que o guia ainda nao
  descreve (dizer qual: troca de secao? viga de mesma profundidade?).

## Q7 — Campos por indice `viga_{a|b}_seg_N_*`

Esses campos sao por lado+indice e compartilhados entre Para e Passa, mas Para
e Passa agora tem segmentacoes diferentes. Os detalhes de cada segmento
(secao, apoios, lajes, nivel, aberturas) passaram a viver no proprio vinculo
(`lv_cell`), sem campo novo (schema N1 imutavel).

- (a) **HOJE:** assim; a pre-ficha/portal leem do vinculo.
- (b) Outra forma (dizer qual).
