# Contrato Rigido do Motor LV N3/N4

Data: 2026-07-21  
Status: contrato arquitetural e comportamento executavel (`lv_draw_contract/v2`)

## 1. Decisao central

O motor de Laterais de Viga e uma maquina deterministica de desenho. Ele nao
interpreta CAD, nao procura uma forma visual parecida e nao corrige uma ficha
durante a geracao.

```text
N1 --interpretador SA--> ficha executiva LV --motor compartilhado--> N3
N2 --motor reverso-----> ficha executiva LV --motor compartilhado--> N4
```

N1 e N2 sao origens independentes. Eles podem produzir fichas com o mesmo
contrato de desenho, mas nenhum deles pode consultar ou completar o outro.

Consequencia operacional:

- elemento ausente na ficha (abertura, laje, painel, pilar) e falha de leitura;
- elemento presente e correto na ficha, mas desenhado em medida/layer/posicao
  incorreta, e falha do motor;
- ficha invalida nao gera um desenho aproximado: a geracao falha com o caminho
  exato do campo ausente;
- a mesma projecao de campos de desenho produz o mesmo `drawing_fingerprint`.

## 2. Evidencia do robo de Laterais

O pacote disponivel em `_ROBOS_ABAS/Robo_Laterais_de_Vigas` e uma distribuicao
PyInstaller/obfuscada, nao o fonte aberto. O `Analysis-00.toc` identifica os
modulos originais:

- `robo_laterais_viga_pyside.py`;
- `gerador_script_viga.py`;
- `gerador_script_combinados.py`;
- `Ordenador_VIGA.py`;
- `Combinador_VIGA.py`.

O arquivo preservado `dist/dados_vigas_ultima_sessao.json` confirma a ficha do
robo: viga, lado, continuacao, largura/altura total, fundo, ate oito paineis,
`width`, `height1`, `height2`, tipo Grade/Sarrafeado, alturas de grade, lajes,
quatro vazios, sarrafos de extremidade e pilares. Portanto, o comportamento
original tambem e ficha -> script; coordenadas do desenho de origem nao fazem
parte do contrato do gerador.

O motor Python atual implementa a anatomia SCR documentada no cabecalho de
`scripts/gerar_lv_dxf_stog.py`: distribuicao por altura, Grade, sarrafos,
visao-corte, layers e cotas. A reforma preserva essas regras e remove a
re-interpretacao silenciosa do caminho N4.

## 3. Fronteiras e responsabilidades

| Componente | Pode fazer | Nao pode fazer |
|---|---|---|
| Interpretador N1 | Ler SA, classificar A/B e Para/Passa, publicar ficha N3 | Consultar N2/N4 |
| Interpretador N2 | Ler recorte aprovado, extrair secoes, unidades, paineis e vazios | Alterar o gerador para esconder erro de leitura |
| Adaptador | Renomear campos e unidades sem perda semantica | Criar lado, painel, altura ou abertura inexistente |
| Validador | Normalizar tipos, exigir invariantes, calcular fingerprint | Inferir geometria |
| Motor N3/N4 | Aplicar regras SCR fixas aos campos validados | Reler recorte, copiar A para B, autodistribuir ficha incompleta |
| QA | Comparar ficha, inventario e entidades DXF | Aprovar somente por semelhanca global |

## 4. Unidade atomica de desenho

Uma viga possui uma ou mais `face_units`. Cada unidade representa um segmento
executivo individual, com lado A ou B e uma cadeia ordenada de paineis.

Campos obrigatorios da ficha N4 estrita:

- identificacao: `viga`;
- secao: `b_cm`, `h_cm`, `h_B_cm`, `section_views[].h_section`;
- unidade: `face_units[].side`, `h_body`, `segments`;
- painel: `largura_cm`, `height1`, `panel_type`;
- os dois lados A e B precisam existir explicitamente.

Campos condicionais sao comandos de desenho, nao pistas:

- `holes[]`: vazio real do painel;
- `laje_sup_local`, `laje_inf_local`, `slab_center`: faixas de laje;
- `grade_h1`, `grade_h2`: geometria da Grade;
- `sarrafos_horizontais`, `sarrafos_verticais`: replay explicito;
- `sarrafo_vertical_esquerdo/direito`: fechamento de extremidade;
- `reuse_regions`: classificacao/regiao, sem hatch de painel no N4;
- `suppress_auto_sarrafos`: suprime expressamente a regra SCR automatica.

`bbox`, coordenadas absolutas e confianca pertencem a rastreabilidade do
interpretador. Eles nao mudam o desenho nem o fingerprint.

## 5. Regras fixas do motor

### 5.1 Paineis e sarrafos

- A ordem e a largura dos paineis sao exatamente as da ficha.
- Um painel nao nasce de linha de cota, sarrafo ou borda de abertura.
- Sem replay explicito de sarrafos, aplica-se a tabela SCR por altura do
  painel: `<15`, `15-30`, `30-80` e `>=80`.
- Painel de degrau continua recebendo sarrafos dentro da sua altura real.
- A supressao so ocorre por `suppress_auto_sarrafos=true`.

### 5.2 Degrau, abertura e cota interna

- `height1 < h_body` define o perfil de degrau e alinha o painel pelo topo.
- O ombro e geometria de `Painéis`; a cota do ombro e entidade `DIMENSION` em
  `COTA`.
- A cota interna de 65 cm e mantida quando o ombro mede 65 cm.
- A linha de extensao da cota nunca vira divisor vertical em `Painéis`.
- `holes[]` pertence ao painel que o declarou; o motor posiciona o vazio pelo
  `corner`, `width`, `height` e `position`, relativo a esse painel.

#### 5.2.1 Modos de abertura de pilar (2026-09-11)

A passagem de pilar na lateral tem **mais de uma representacao de desenho**. Nao
generalizar a partir de uma so.

1. **Retangulo tracejado** — `LWPOLYLINE` DASHED em `Painéis`. E' o modo que
   `holes[]` / `holes_lwpoly` ja' cobriam.
2. **Vazio de sarrafos (painel SARRAFEADO)** — nao ha' tracejado nenhum: a
   abertura e' a INTERRUPCAO da corrida de sarrafos, e cada sarrafo
   interrompido leva uma tampa vertical de 7cm (2.2x7) na ponta. A largura da
   abertura e' cotada da borda da face ate' a interrupcao.
   Evidencia: V13 face A, abertura de 78, tampas nos handles 53 e 54 do N2.
   A interrupcao ja' vem da ficha em `sarrafos_horizontais[].x_left`.

> **REGRA DO DONO (2026-09-13) — como separar abertura de PILAR de abertura
> de VIGA.** O que distingue as duas e' O QUE CADA UMA RECORTA:
>
> | abertura | painel | sarrafo |
> |---|---|---|
> | **de VIGA** | produz **vazio e recorte no painel** | tambem interrompe |
> | **de PILAR** | **nao altera o painel** | **so' recorta o sarrafo** |
>
> Ou seja: se o painel foi recortado, a abertura e' de viga; se so' a corrida
> de sarrafo foi interrompida e o painel esta' inteiro, e' de pilar.
>
> O marcador de origem vem do **N1**, nao do N2 — o N2 e' desenho, e o desenho
> so' mostra a consequencia. O que o motor precisa e' ter **comportamento
> separado para os dois casos**; a classificacao pode chegar do N1.
>
> **IMPLEMENTADO em 2026-09-13** — `classificar_aberturas_pilar()` em
> `gerar_lv_dxf_stog.py`. Quatro condicoes, todas necessarias, para uma
> interrupcao virar abertura de pilar:
>
> 1. nao coincide com DIVISA entre paineis (ali o sarrafo para por construcao);
> 2. nao coincide com a borda do PAINEL DE FECHAMENTO superior (a corrida
>    `0->200` da V13 acaba em 200 porque o painel tem 200, nao por corte);
> 3. o x nao cai em FAIXA de painel rebaixado — painel rebaixado E' o vazio,
>    logo e' abertura de viga. Testar so' as bordas da faixa nao basta: na
>    V301.B a interrupcao em 299.7 cai no meio do painel de 244 rebaixado
>    (37.6 contra 103);
> 4. a abertura ENCOSTA na borda da face (o pilar fica na ponta da viga).
>
> Resultado medido (verticais SARR de 5-9 cm):
>
> | viga | N2 | regra geometrica | classificador |
> |---|---|---|---|
> | V13 | 4 | 3 | **4** |
> | V301 | 0 | 40 | **16** |
>
> As 16 que sobram na V301 **ja' estavam no N4 de 11/09 que o dono validou** —
> nao sao invencao desta rodada, e sao questao separada. O classificador
> devolve a V301 exatamente ao estado aprovado.
>
> **REESCRITO em 2026-09-17 — a assinatura e' a VARIACAO POR ALTURA.** As
> quatro condicoes acima descreviam mal o que o codigo fazia, e a de numero 4
> era VAZIA: o candidato era montado a partir da borda da face
> (`(base, x_left)` e `(x_right, topo)`), entao todo candidato encostava na
> borda por construcao. Numa face com varios paineis, cada corrida que nao
> comecasse em `base` virava uma abertura ate' a borda — na V302.A isso
> produzia 171,5 / 298,5 / 117 e na CONT.V302.A um 927, todos desenhados como
> tampa e cotados.
>
> O pilar sobe do fundo, para as corridas de baixo, e a corrida de cima passa
> POR CIMA dele. Medido no N2:
>
> | unidade | alturas de baixo | altura de cima | abertura |
> |---|---|---|---|
> | V13.A | y=7,3/18,3/25,3 comecam em 78 | y=37,3 comeca em 0 | 0..78 |
> | V13.B | y=7,4/18,4/25,4 acabam em 337 | y=37,4 vai a 415 | 337..415 |
> | CONT.V302.A | cobrem [7,784] e [934,976] | y=37,3 cobre [7,976] | 784..934 |
>
> ABERTURA = cobertura na altura mais alta do corpo MENOS a uniao das de
> baixo, exigindo que a diferenca seja um ENTALHE num painel que tenha
> cobertura baixa em outro ponto (sem isso a V302.A daria o painel 3 inteiro,
> que so' tem uma corrida). A regra do dono — abertura de viga recorta o
> painel — fica como guarda semantica.
>
> Isso derruba tambem a condicao 4: a abertura da CONT.V302.A esta' em
> 784..934 de uma face de 976, **no meio**, e 150 e' valor escrito no N2.

##### Como validar (o oraculo antigo nao validava nada)

> `scripts/arete/validar_abertura_pilar_lv.py [VIGA ...]`
>
> A tampa no N2 e' um SARR vertical curto (5-9 cm) e vem em **PAR VERTICAL no
> mesmo x** — duas por PAREDE, nao duas por abertura. Parede que coincide com
> a borda da face nao leva tampa (V13.A: a abertura 0..78 so' tem tampa em
> 78). A verificacao correta e' por POSICAO DE PAREDE: cada parede com tampa
> tem de bater com uma parede prevista, e cada parede prevista longe da borda
> tem de ter tampa.
>
> O oraculo anterior contava tampas e dividia por dois. Contagem nao verifica
> nada: ele dava "25 coerentes, 7 divergentes" para um classificador que
> produzia abertura de 927 de largura, e devolvia ZERO tampas para a V13, que
> tem 4. Nao reusar aquele numero.
>
> **Estado medido em 2026-09-17** (paredes, nao vigas):
> 29 acertadas · 64 tampas sem previsao · 10 previsoes sem tampa.
>
> Perfeitas: V13, V301, V302, V305, V306, V310, V311, V315, V317, V319, V321,
> V323, V324, V326, V327, V328, V330, V331, V332, VF203, VF301.
> Falham: V312/V320/V325 (nenhuma previsao), V314/V318/V322 (1 de 12),
> V316 (1 de 8), V308 (3 de 6), e uma parede solta em V303/V304/V329.
>
> **Causa conhecida das falhas grandes, ainda sem fix:** nessas unidades a
> corrida-lintel fica ACIMA do corpo e o filtro `y > h_corpo + tol` a
> descarta. Medido na V312 (unidade x 5877,3..6126,6, corpo 103, paineis de
> 103/67/38,2/103/59/103): o vao 74,4..137,4 existe e casa com as tampas, mas
> o lintel esta' em y=120,3. Tirar o filtro quebra a V13, onde ele e' o que
> exclui a corrida do painel de fechamento (y=57,8 num corpo de 44). Nao
> mexer sem uma regra que atenda os dois — faltar continua melhor que
> inventar, e o motor NAO desenha tampa sem lista de aberturas.
>
> A cota da abertura (P6, o "78" da V13) passou a ser emitida junto, dentro do
> corpo a ~0.68 da altura — medido no N2: face A "78" em x=39.0 (abertura
> 0..78) e face B "78" em x=376.0 (abertura 337..415), as duas a 29.8 do fundo
> num corpo de 44.
>
> Testes: `tests/test_lv_abertura_pilar_vs_viga.py` (7 casos).
>
> **Historico do defeito (2026-09-13) — a tampa e' so' de abertura de PILAR.**
> Correcao do dono: abertura comum (chegada de VIGA) interrompe a corrida de
> sarrafos do mesmo jeito e **nao leva tampa**. O criterio implementado em
> `draw_sarr_lv_horizontal_from_n2` e' puramente geometrico (`a > base + 10.0`:
> "a corrida que comeca muito depois das outras foi interrompida"), entao ele
> detecta INTERRUPCAO e nao sabe quem interrompeu.
>
> Medido nos recortes que o motor de fato usa (os do DB, `reverse_eng_recortes`
> — atencao: ha' recortes homonimos de outra prancha em
> `DADOS-OBRAS/Fase-2_Triagem/`, e medir neles da' numero errado):
>
> | viga | verticais SARR no N2 | com 5-9cm (tampa) | o N4 desenha |
> |---|---|---|---|
> | V13 (abertura de pilar) | 6 | **4** | 3 |
> | V301 (abertura de viga) | 48 | **0** | **24** |
>
> Ou seja: 24 tampas inventadas na V301 e 1 faltando na V13. O desenho humano
> marca a diferenca de forma medivel (a V13 tem verticais de exatamente 7cm; a
> V301 nao tem nenhuma entre 5 e 9), entao o conserto e' achar no N2 o que
> identifica a abertura como sendo de pilar — nao calibrar o limiar geometrico.
> Mesma licao do degrau de laje (§3.4.1 do doc de interpretacao): ler o que o
> desenho declara, nao inferir por forma.

#### 5.2.3 Abertura de viga SEPARA SEGMENTOS (2026-09-14)

Regra do dono. Vale para o N4 por fidelidade, mas o motivo real e' o **N3**: o
N3 nasce do N1, onde nao ha' desenho para imitar — so' estrutura. Se o segmento
nao vier separado da interpretacao, o N3 nunca reproduz o que o N4 reproduz por
copia. E' preparar o terreno para **N1 -> N3 identico ao N4**.

1. **Um painel com abertura de viga nao e' um segmento com buraco** — sao DOIS
   segmentos distintos, mesmo encostados.
2. **A fronteira fica na borda DIREITA da abertura.** A abertura e a sobra
   pertencem ao segmento que vem ANTES ("sempre a abertura faz parte do
   segmento que vem primeiro").
3. **Distancia entre os segmentos depende do corte:**

   | corte | segmento seguinte |
   |---|---|
   | abertura corta o painel INTEIRO em Y | pode ficar **afastado** |
   | sobra uma parte embaixo | **encostado, parede com parede** |

4. **Parede compartilhada e' desenhada UMA vez** — a divisoria e' a parede
   direita do primeiro e a esquerda do segundo ao mesmo tempo.
5. **O primeiro segmento NAO emite as cotas verticais da sua parede direita**
   quando ela e' compartilhada — senao sobrepoem as do segundo.

Evidencia medida no N2 da V302.A (unidade 0..470, fundo em y=0.3):

```
vertical   x=178.5  y 5.3 -> 43.3      borda esquerda da abertura
horizontal y=5.3    x 178.5 -> 200.5   PISO da abertura = topo da sobra
vertical   x=200.5  y 0.3 ->  5.3      borda direita da sobra
```

Corte em **200.5** -> segmentos de **200.5** e **269.5**. A sobra e' de 22 x 5.

**Deteccao:** a marca confiavel e' a **horizontal INTERMEDIARIA** (nem fundo
nem topo), que e' o piso da abertura. Procurar no TOPO da unidade falha quando
os segmentos tem alturas diferentes — na V302.A o seg.1 tem 43 e o seg.2 tem
45, entao o topo do seg.1 nao e' o topo da unidade e a abertura passa batido.
Implementado em `_detectar_aberturas_viga()` (`motor_reverso_lv.py`), que emite
`aberturas_viga` = `[{x_ini, x_fim, sobra_h, abertura_h}]` e `cortes_segmento`
na face unit. Medido: **20 de 120 unidades** das 32 vigas do 13_PAV.

**Estado (2026-09-14):** implementados — a ficha emite os campos, o desenho
recorta a abertura e deixa a sobra, as alturas por segmento saem certas e a
laje segue o TOPO PLANO (`laje_local = total - altura_do_segmento -
painel_sup`, revelada pela cota de altura total do N2: 43+16 = 45+14 = 59 na
V302.A). V301 e V13 regeneradas seguem byte a byte iguais ao validado.

**PENDENTE — `h_body` errado em 4 unidades de 120.** Medido: a caixa da
unidade nem sempre cerca o corpo. Na V302 a unidade 2A tem caixa de 56 (inclui
a laje de 12 por cima) e a 3A tem 24 (CORTA 21.4 do fundo), enquanto o N2 cota
44 e 45. Tambem V303.A (116 -> 43) e CONT.VF203.B (122.1 -> 40). Isso contamina
a formula do topo plano nessas unidades: a 2A fecha em 60 e a 3A em 61, quando
o N2 diz 59 nas duas.

> **DUAS TENTATIVAS FALHARAM (2026-09-14) — nao repetir sem ideia nova.**
> 1. medir o corpo pelas HORIZONTAIS de largura cheia: na CONT.V301.B elas
>    casam com a faixa da laje e o corpo de 104.6 virava 19;
> 2. medir pelas PAREDES verticais (extensao mais repetida entre os
>    divisores): pior — unidades inteiras da V301 sumiam do desenho
>    (NOMENCLATURA 6->5 em VIEW_A e 11->10 em VIEW_B).
>
> As duas foram revertidas. O conserto certo passa por entender a deteccao da
> caixa da unidade (`pair`), nao por adicionar mais uma guarda medindo
> geometria por fora. A guarda que ja' existe (`panel_body_heights`) so' age
> entre 80 e 125 de altura com folga de 20, e por isso nao alcanca estes casos.

#### 5.2.4 Lado da unidade incoerente com a posicao (2026-09-14)

**Causa raiz do `h_body` errado, achada investigando a fundo.** Nao sao linhas
espurias: e' falta de coerencia entre o LADO atribuido e a POSICAO da unidade.

No N2 as faces ficam em COLUNAS: a face A numa faixa de x, a B noutra (V302:
A em 3883..4862, B em 5217..6144). Uma unidade sem rotulo herda o lado do
ANCHOR, e `_row_pairs_for_anchor` aceita candidatos que se alinham em **y** com
esse anchor (tolerancia 8) — sem olhar x. Anchor de uma coluna captura pares da
outra, e o resultado sai com o lado errado E a altura errada.

Evidencia na V302 (mesma posicao, mesmas larguras, lados e alturas diferentes):

```
A   -        h=56.0  x 5217.5..5619.0  y 7061.0  w=[244.0, 157.5]
B   V302.B   h=44.0  x 5217.5..5619.0  y 7061.0  w=[244.0, 157.5]
```

`select_canonical_face_units` nao desfaz isso porque agrupa por
`(lado, altura, larguras)` — alturas diferentes caem em grupos diferentes e as
duas variantes sobrevivem.

Isso explica de uma vez os apontamentos do dono na V302: o bloco de 11 pontos
com `LINE·Painéis 140.3cm` no SEGMENTO 2A e' a unidade `CONT. V302.A` de 140.3
desenhada sobre a correta de 44 ("acima dessas linhas erradas ta correto o
desenho"). E o `h_body` 56/24 das unidades 2A/3A e' a copia mal-laterada.

**Medido nas 32 vigas: 16 unidades de 120 com lado incoerente**, em 12 vigas.
V301 e V13 ficam FORA da regra — nelas as colunas A e B se sobrepoem em x,
entao o teste de territorio nao se aplica. Isso e' a trava de seguranca.

As 16 tem DUAS naturezas, e o conserto difere:

| natureza | quantas | acao |
|---|---|---|
| tem GEMEA no lado certo, mesmas larguras | **2** (as duas na V302) | descartar — e' copia corrompida |
| NAO tem gemea | **14** | reatribuir o lado; sao desenhos reais, so' rotulados na face errada |

Descartar as 14 perderia desenho. Por isso a acao tem de ser por natureza, nao
uma regra so'.

#### 5.2.2 Cotas de abertura — pendencias medidas (2026-09-13)

Apontadas pelo dono na revisao da V13 face A. Medidas, ainda sem conserto:

1. **Cota do painel de topo sai 4x, deveria sair 1x.** O N2 da face A tem UMA
   cota `3`, na borda esquerda (x=2.0). O N4 emite 4 por face (2 posicoes x 2
   alturas: y=-137.7 e y=-141.7). O bloco de `_top_panel_h` em
   `gerar_lv_dxf_stog.py` emite 2 (esquerda e direita) — ha' um SEGUNDO
   emissor ainda nao localizado, responsavel pelo par de y=-137.7. A
   duplicacao e' anterior ao degrau de laje: contagem identica nos N4 gerados
   antes e depois daquele commit.
2. **Cota `78` da abertura de pilar nao e' reproduzida.** O N2 tem
   `TEXT·COTA handle=168 texto="78"` (largura da abertura, cotada da borda da
   face ate' a interrupcao da corrida de sarrafos — §5.2.1 item 2). O N4 nao
   emite cota nenhuma para a abertura.

Resolvido nesta rodada: a cota da laje sob o painel saia `12,3` na face A e
`12,5` na face B (com medida real 12.4 — o texto nem batia com a medida). E'
**aritmetica, nao medicao**: laje cotada 15 menos painel 3 = 12 exato. A folga
de desenho (0.3/0.4) nao pode virar cota. Agora sai `12` nas duas faces.
   Discriminador: e' abertura quando a corrida comeca **muito** depois das
   outras da mesma face. O recuo normal de canto (`SARR_INSET_H`) nao e'
   abertura — trata-lo como tal gera tampa em quase toda viga.
3. **Painel GRADEADO** — comportamento proprio, ainda **sem caso observado**
   (o 13_PAV inteiro e' Sarrafeado: 360 segmentos, 29 vigas). Registrar aqui
   quando aparecer, sem extrapolar do modo 2.

#### 5.2.5 Laje superior: uma faixa, topo plano (2026-09-18)

Medido no N2 em quatro unidades de tres vigas. A hachura `AR-CONC` — que E'
a laje — e' **SEMPRE UMA por unidade**, cobrindo a largura inteira:

| unidade | largura | faixa |
|---|---|---|
| V13.A | 415 | +44..+59 |
| V302.B | 401,5 | +44..+59 |
| V302.A | 470 | fundo em DOIS niveis (43 e 45), topo plano |
| CONT.V302.A | 976 | +44..+59 |

Regras que decorrem disso:

1. **Degrau de laje so' existe quando o CORPO muda de altura.** Onde o corpo
   muda, o FUNDO da faixa acompanha o degrau e o topo continua plano — e' um
   poligono com entalhe, nao dois retangulos (`_draw_laje_escalonada`).
2. **O painel de fechamento ocupa os centimetros de CIMA da faixa**, sobreposto
   a ela, nao acima dela. V302.B: `ANSI31` de +56 a +59 sobre a `AR-CONC` de
   +44 a +59. A altura menor que o N2 escreve ali (12 contra 15) e' a laje
   VISIVEL sob o painel: **assunto de cota, nao de desenho**.
3. **A laje assenta no painel que esta' embaixo dela**, nao no topo global da
   face. Guarda medida: `height1` so' vale como altura de corpo quando esta' a
   menos de 10 cm de `h` — em degrau alto ele e' SUB-BANDA (V301: height1=44
   num corpo de 109, e sem a guarda as 10 cotas de laje da viga caiam 65 cm).
4. **`AR-CONC` vive na layer `COTA`**, nao em `Hachura`. O coletor de HATCH
   filtrava por layer e nunca a via — ver a armadilha de medicao em §5.2.7.

#### 5.2.6 Cotas: nivel, ponta e o que a abertura de viga leva (2026-09-18)

**Nivel da cota horizontal — por PAPEL, nao por largura.**
`nivel 0 (25)` = paineis; `nivel 1 (50)` = o que particiona a face.
Sem abertura de viga a face e' UM segmento: todo painel vai para o nivel 0 e o
externo guarda o TOTAL. Com abertura, o externo guarda a particao (borda +
complemento). Medido no N2 da V13.A, validada: nivel 26,5 traz `244 | 63 | 108`
e o nivel 55,0 traz o `415` da face inteira — o 244 nao sobe de nivel por ser
largo. A regra anterior era `w_sum >= 150 -> nivel externo`.

> **Excecao medida:** quando o COMPLEMENTO e' o numero que o N2 escreve naquela
> unidade, ele manda — trocar um valor do papel por um total que nao esta' la'
> seria inventar.
> `V13.A` compl 171 ausente / total 415 no N2 → total.
> `V301` (5 unid.) compl 174 NO N2 / total 418 ausente → complemento.
> `CONT.V302.A` nenhum dos dois no N2 → total, que e' o que o dono pediu.
> Sem `edge_span_candidates` informado vale o comportamento historico.

**Qual ponta recebe cota — REGRA DO DONO (2026-09-17).** Compara-se a
extremidade esquerda com a direita, em altura de laje **e** de painel.
Qualquer uma diferente ja' e' motivo para cota dos **dois** lados, e ai saem
**ambas** (laje e painel), nao so' uma. Iguais: uma so', na direita.
Em continuacao a comparacao atravessa os segmentos ENCOSTADOS; separados,
cada um se comporta sozinho.

- A comparacao usa a altura CRUA do painel, nao a travada pelos 10 cm — sao
  perguntas diferentes: onde a laje ASSENTA e se as pontas DIFEREM. Na V301 as
  pontas sao 109 e 44, e e' isso que faz o humano cotar os dois lados.
- **Nao ha' piso heuristico.** O antigo ("unidade repetida so' recebe onde ha'
  faixa de marco") matava casos reais: a V302.B#1, paineis [170, 244], saia sem
  NENHUMA cota de laje e o N2 escreve 14 na direita.
- O bloco do marco tem de abrir tambem quando ha' TRECHO de laje: a laje global
  pode ficar abaixo do limiar de 12 (V302.B: 12 sob o painel) enquanto o trecho
  da outra ponta tem 15.

**Abertura de viga leva tampa e duas cotas.** Medido no N2 da unidade
[53, 63,5] da V302 (x0=4086, y0=6708,1), tudo em layer `COTA`:

```
LINE 22 em (4117, 6767,1)->(4139, 6767,1)      tampa, no topo do SEGMENTO
LINE 22 em (4117, 6776,2)->(4139, 6776,2)      cota da largura, 9,1 acima
LINE 44 em (4105,2, 6723,1)->(4105,2, 6767,1)  cota da altura, 11,8 a` esquerda
```

**Patinhas.** O N2 deixa **3 cm de folga** entre o objeto e a linha de extensao
(`dimexo=3`), e 3 de sobra alem da linha de cota (`dimexe=3`). Medido na V302.B
com a borda em x rel 0: cotas 44/12/3 com extensao de -3,0 a -16,9 e linha em
-13,9; cota 59 com extensao de -3,0 a -42,9 e linha em -39,9.

#### 5.2.7 Armadilhas de medicao ja' pagas (nao repetir)

1. **Misturar referencia arredondada com crua.** `_top_panel_face` media a laje
   sob o painel como `caixa_do_painel - pair.y_top`. O `y_top` do pair vem
   ARREDONDADO e a caixa e' crua: na V302.B dava `7116,6 - 7105,0 = 11,6` onde
   o desenho tem `7116,6 - 7104,6 = 12,0`. A fracao nao estava no desenho — era
   o arredondamento vazando para a medida, e dali para o trecho e para a cota
   ("11,5"/"14,5" onde o N2 escreve 12 e 15). Referencia crua correta: o FUNDO
   da hachura `AR-CONC`, que por definicao assenta no topo do corpo.
2. **Filtrar hachura por layer.** `AR-CONC` esta' em `COTA`; o coletor so'
   guardava `REAPROVEITAMENTO` e `Hachura`.
3. **Dois frames de coordenada.** `lv_n4_face_unit_details` recompoe o proprio
   `y0` a partir do crop e isso diverge do frame do gerador — na V302.B o painel
   de fechamento e a cota total saiam 4 cm abaixo do topo real. Ancorar no que
   ja' esta' DESENHADO (a hachura da laje) elimina a conta e a divergencia.
4. **Ancorar so' uma ponta.** Ao ancorar o topo da cota total no desenho e
   deixar o pe' em `y0 - li`, ela passou a medir 62,6 com o texto dizendo 59.
   Os dois extremos tem de sair da mesma fonte.
5. **Detector de texto por proximidade mente.** Contar textos numericos numa
   janela ao redor da unidade pega o VIZINHO de fileira. Foi o que me fez
   concluir que "o N2 da V301 cota as duas pontas em 17/17" — falso. O desenho
   validado vale mais que o detector.
6. **`dimtad: 0` so' e' honrado na cota VERTICAL.** Na horizontal empurra o
   texto de 8 para 11 acima. E reposicionar o MTEXT dentro do bloco renderizado
   funciona chamando a funcao direto, mas nao no caminho real do gerador.

#### 5.2.8 Fator de repeticao "NX" (2026-09-19)

O desenho humano **comprime** sequencias de paineis iguais e marca o fator no
papel. Medido no N2 da V303.B: a face ocupa 798,5 no desenho — `244 | 244 |
66,5 | 244` — e um texto **`7X`** sobre o segundo painel diz que ele vale por
sete. A soma real, confirmada pelo dono, e' `244 + 7x244 + 66,5 + 244 =
2262,5`. Na V302 ha' um `8X` equivalente na `CONT.V302.A`.

**Niveis de cota passam a ter tres degraus:**

| | nivel 1 (25) | nivel 2 (50) | nivel 3 (75) |
|---|---|---|---|
| sem fator | paineis | **total** | — |
| com fator | paineis | **`NX`** | **total** |

A cota do fator cobre SO' o painel que ela multiplica. A total mantem o vao que
a face ocupa no papel, mas o TEXTO e' a soma com fator.

##### N4 (vem do N2): ler

O marcador era descartado em silencio — a coleta de `TEXT` da layer `COTA` faz
`float(txt)` e `"7X"` levanta excecao que o `except` de fora engole. Agora
`fator_txts` guarda `^\d{1,2}\s*[Xx]$` e `_fatores_por_painel` associa cada
marca ao painel cujo intervalo contem o x do texto (na V303.B o `7X` cai no
centro exato do 2o painel).

##### N3 (vem do N1): gerar

No N3 chega a lista REAL de segmentos, e o desenho tem de ser montado ja'
comprimido. **Regra do dono:**

- a sequencia comeca a partir do **segundo** painel;
- so' entram paineis **completos** (244) e todos iguais entre si;
- o **primeiro** e o **ultimo** painel nunca entram no multiplicador;
- com menos de 2 paineis na sequencia nao ha' multiplicador.

```
244 244 244          ->  sem multiplicador (sobra 1 no meio)
244 244 244 244      ->  244 | 244x2 | 244
80  244 244 122      ->  80  | 244x2 | 122
244 244 80  244      ->  sem multiplicador (a sequencia quebra)
[244]*8 + 66,5 + 244 ->  244 | 244x7 | 66,5 | 244     (a V303.B real)
```

`comprimir_paineis_repetidos()` em `gerar_lv_dxf_stog.py` implementa isso, com
`tests/test_lv_fator_repeticao.py` (9 casos, incluindo o real da V303.B e a
invariante de que comprimir nao muda a soma).

> **Por que isso importa para o N3** (dono, 2026-09-19): "nos n1 vamos ter os
> valores de cada segmento e vamos montar o n3 com base no SA/N1, que vai
> definir o numero de segmentos". O N1 nao traz o desenho comprimido — traz os
> segmentos reais. A compressao e' responsabilidade do montador do N3.

### 5.3 Hachuras N4

- painel nao recebe hatch;
- reaproveitamento nao recebe hatch;
- laje/perfil nao recebe hatch de painel;
- somente vazio/abertura explicito recebe `HATCH` na layer `Hachura`;
- a geometria de corte possui regras proprias e nao autoriza transportar
  primitivas do recorte N2 **para as laterais**.

> **Emenda 2026-09-11 (decisao do dono) — proveniencia da VISAO DE CORTE.**
> A proibicao acima vale para as LATERAIS. Para a **visao de corte**, o N4
> passa a **replicar a geometria medida do recorte N2**; o N3 continua
> proibido de ler N2.
>
> Quem decide a proveniencia e' a **propria secao** (a marca
> `n1_contract_clean`), nao a flag de CLI. A cadeia e' de 3 niveis:
> secao de contrato N1 -> anatomia limpa; secao vinda da ficha N2 -> replica
> do recorte; sem primitivas -> detalhe procedural como ultimo recurso.
>
> Motivo: o template procedural nao reproduz o que o corte real tem. No V13
> Corte 1 ele emitia `55x19` com cotas 55/50, enquanto o N2 tem
> 13/59/44/7/10/19 — inclusive um desnivel de 7cm entre a laje da face A e a
> da face B, que nenhum parametro escalar carregava.
>
> Consequencia operacional: as primitivas de corte do N2 vem em **escala 2x**
> (layer `Cota Seção (2x)`). O empilhamento das secoes precisa ser **medido**,
> nao estimado por `h_sec`, senao as secoes se sobrepoem.

### 5.4 Nomenclatura e layout

- cada `face_unit` e desenhada separadamente;
- o layout limpo pode reposicionar unidades, sem alterar sua geometria;
- a apresentacao/QA nomeia cada unidade como `SEGMENTO 1A`, `SEGMENTO 1B`,
  `SEGMENTO 2A` etc.; o identificador original permanece nos metadados;
- N2 e N4 de uma unidade devem ser comparados lado a lado; unidades sucessivas
  aparecem em linhas sucessivas.

## 6. Caminhos N3 e N4

### N3

`src/core/lv_generation_contract.py` converte os vinculos canonicos SA em
quatro fichas isoladas: A/B x Para/Passa. A conversao define paineis executivos
e publica `generation_ready`. O gerador recebe `--behavior` e nao carrega
`fichas_lv_v2.json`.

#### 6.1 Gramatica da viga no N1 (2026-09-20)

> **A AUTORIDADE E' O GUIA DO DONO**, nao esta secao:
> `scripts/arete/html_fichas/Obra_TREINO_1/TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260706_103941/laterais_viga/interpretacao_laterais.html`
> — "Guia de Interpretacao das Laterais de Viga — A/B e Para/Passa", listado
> como `protected_guide` em `squads/qa-global-evidencias/data/class_profiles/lv.json`.
>
> O arquivo estava AUSENTE do disco (a pasta `scripts/arete/html_fichas` entrou
> no `.gitignore` e a copia local se perdeu). Recuperado do commit `2b3c4f4654`
> em 2026-09-20. Se sumir de novo, esta' no historico do git.
>
> O que segue e' resumo para consulta rapida, com o estado de implementacao de
> cada regra. Divergiu do guia? o guia manda.

Regua para medir o refino: `scripts/arete/comparar_lv_n3_n4.py`.

**G0 — LV tem somente A e B.** "Laterais de viga usam somente A e B — C/D nao
fazem parte deste contrato." A face sai do vinculo `seg_side_a`/`seg_side_b`,
nunca da posicao na tela. Em viga horizontal B fica acima e A abaixo; em viga
vertical A fica a' esquerda e B a' direita. O lado A le-se da esquerda para a
direita (ou de cima para baixo); **o lado B le-se invertido**, e o ponto
inicial/final do segmento tem de respeitar esse sentido.

**G6 — `Para`/`Passa` e' relacao com PILAR, nao com viga.**

| classe | o que acontece | segmentos por lado | vinculo |
|---|---|---|---|
| `Para` | as paredes PARAM nas faces do pilar central | 2 (A1+A2, B1+B2) | `comprimento_total` |
| `Passa` | as paredes ATRAVESSAM o pilar | 1 continuo | `comp_total_passa` |

**G7 — Encontro entre VIGAS decide-se por PROFUNDIDADE.** "No encontro entre
vigas, nao classificar como Para ou Passa: comparar as profundidades."

- incidente **menos profunda** -> a lateral prolonga-se por baixo dela ate' a
  face oposta;
- incidente **mais profunda** -> a lateral termina na primeira face encontrada.

Vale igualmente nos casos `Para` e `Passa`.

**G8 — Folgas de desenho (hardcoded no guia).**

    laje                              + 2 cm
    altura da viga                    + 4 cm      <- e' o "+4" de G3
    largura da viga incidente na abertura + 8 cm  <- 4 de cada lado
    pilar: distancia a' extremidade    - 11 cm de cada lado
    abertura do pilar atravessado = comprimento_pilar + 22 cm

A abertura representa o trecho da lateral que sera' sarrafeado.

**G1 — Segmento e' trecho entre mudancas.** Ao longo da extensao, a viga muda
de tamanho e de secao varias vezes. *Cada mudanca abre um segmento novo.* Nao
existe "a secao da viga": existe a secao DE CADA SEGMENTO.

> Medido na V301 (13_PAV): entre os pilares a planta escreve
> `19/55 · 19/120 · 19/120 · 19/55` ao longo do mesmo rotulo. O N2 confirma,
> com `h_section_all = [55, 120]`. A conversao resolve UMA secao por viga e
> aplica a todos os paineis — incapaz de representar isto por construcao.

**G2 — Cruzamento com outra viga e' abertura ou interrupcao.** Onde outra viga
cruza, a lateral abre ou interrompe; depois o proximo segmento continua. E' a
mesma gramatica que o N2 ja' usa (§5.2: abertura de viga SEPARA segmentos) —
os dois lados falam a mesma lingua, so' o N1 ainda nao aplica.

**G3 — Altura da face = secao + 4 cm.** Convencao rigida, confirmada pelo
dono. Vale contra a altura TOTAL da lateral (corpo + laje), nao contra o corpo:

    V13    55+4 = 59    V301  120+4 = 124    V302  55+4 = 59 (43+16)
    V303   55+4 = 59    V304   55+4 = 59

**G4/G5 — RETIRADAS.** Eu as havia escrito a partir da fala do dono, antes de
achar o guia, e nesta forma estavam erradas:

> ~~"viga cruzando: encosta ou recua 4 | pilar: chega e nao desconta"~~
> ~~"A e B decidem por Para/Passa; faces C e D de pilar sao sempre Passa"~~

O guia coloca cada peca no lugar: `Para`/`Passa` e' com PILAR (G6), viga com
viga e' por PROFUNDIDADE (G7), e o "4" do dono e' a folga por lado da viga
incidente — o guia a escreve como **+8 cm** no total (G8). LV nao tem C/D (G0).

**G9 — O recuo de 11 e' do `Para`; o `Passa` nao recua.** Arbitrado pelo dono
em 2026-09-20: *"quando Para sim recua esses 11, se Passa nao"*.

Atencao ao ler o guia: o `-11` que aparece la' esta' no exemplo de **`Passa`**
(Interpretacao 1, "Distancia extremidade esquerda: 180-11 = 169"). Nao e'
contradicao — sao grandezas diferentes:

- no `Passa`, o `-11` descreve onde comeca a ABERTURA sarrafeada, que e' 11 mais
  larga de cada lado que o pilar (`abertura = pilar + 22`). A lateral em si
  segue inteira;
- no `Para`, o `-11` e' recuo da PROPRIA lateral, que termina antes da face do
  pilar.

Verificavel no N4 quando G6 for implementado; ate' la', leitura declarada.

**G10 — Quem decide `Para`/`Passa`.** Os lados **A e B** decidem caso a caso.
As faces **C e D do pilar** sao *sempre* `Passa`. (LV nomeia so' A e B — G0;
C e D aqui sao as faces CURTAS do pilar que a lateral encontra.)

> ATENCAO — o codigo de hoje nao implementa G6 nem G7.
> `_passa_endpoint_adjustments` aplica `-4` por causa de PILAR ("lado oposto ao
> volume do pilar recua 4 cm"), que nao e' nenhuma das duas regras, e ignora
> completamente o encontro entre vigas.

#### 6.1.1 SA/N1 das laterais: as quatro celulas pelas regras do guia (2026-09-25)

**Regra do dono (2026-09-25): o fundo (FV) serve de REFERENCIA e comparacao
para a lateral, NUNCA de lei.** Consequencias ja' aplicadas:

- `harmonize_lateral_segment_links` (`preficha_segments.py`) NAO reescreve mais
  a lateral com a borda do fundo. Ele forcava o segmento lateral N = borda do
  segmento de fundo N (LV virava copia do FV, sujeiras incluidas) e fixava A na
  borda de y maximo, invertendo A/B em toda viga horizontal (G0 manda A
  embaixo). Hoje so' mede a divergencia em `beam['_lv_fv_reference_divergence']`.
- `main.py` deixou de copiar Passa -> Para quando Para ficava vazio.

**O que estava errado, medido no 13_PAV (Obra_TREINO_1, V301-V304):**

| defeito | causa | dono |
|---|---|---|
| A/B/Para/Passa identicos | os 4 interpretadores liam UMA lista (`lv_merged_bottom_*`, segmentacao do fundo) | `beam_tracer.py:394` + `lateral_viga.py:144` |
| A = face de cima | `_edge_from_fundo` e o harmonize usavam y maximo para A | `lateral_viga.py`, `preficha_segments.py` |
| segmentos sobrepostos (V301 S5/S6, S7/S8, S15/S16) | duas ocorrencias do rotulo consolidadas sem dedup | `consolidate_occurrences` |
| V303 com 4 de 6 segmentos da V306 (442 cm ao lado) | captura lateral por proximidade | `BeamTracer` |
| V304 na faixa errada (2422-2441; o DXF so' tem bordas em 2441/2460) | contorno de fundo deslocado uma largura (o "caso V304" do §5c do CLAUDE.md) | `BeamTracer`/FV |
| P26 (U de 165 cm) cortando a V304 em pedacos de 34 | bbox do pilar no lugar do poligono | `BeamTracer` (obstaculo por bbox) |
| uma secao por viga (V301 toda 19/55; V302/V304 com 120 vazado) | `lv_dimension_text` / `dim_global` unico | `beam_tracer.py:237`, `main.py _populate_lv_segment_ui_fields` |
| `nivel = null`, `pillar_openings = []` | nunca calculados | — |

**Implementacao nova (nao altera o schema N1 — so' os vinculos laterais que ja' existem):**

- `src/core/lv_beam_scene.py` — topologia BRUTA medida no DXF: faixa pelo
  PROPRIO rotulo (rotacao -> orientacao; par de bordas paralelas encostado nele,
  largura do rotulo `b/h`), extensao seguindo as bordas, pilar pelo POLIGONO
  real, vigas que tocam cada face (T ou X) com a secao delas no ponto de
  encontro, zonas de secao pelos rotulos da propria viga (fronteira entre
  rotulos diferentes usa os divisores do fundo so' como referencia; sem ela,
  ponto medio, marcado), lajes encostadas em cada face.
- `src/core/beam_interpreters/lateral_viga_cells.py` — decide por celula:
  G0 (A=t_lo, B=t_hi, B lido invertido), G6/G9 (Para para nas faces do pilar;
  o -11 vai como ajuste de ponta e e' aplicado no N3 — o SA desenha de face a
  face), Passa: o pilar fica INTEIRO num so' segmento, com `pos_inicio`/`pos_fim`
  do pilar a partir do inicio do segmento e abertura = pilar + 22 (nenhuma
  fronteira cai dentro de pilar), G7 (incidente MENOS profunda -> abertura
  +8/+4 com fronteira na borda FINAL da abertura, §5.2.3; MESMA profundidade ou
  mais profunda -> o SA PARA na primeira face e recomeca na oposta), G1 (cada segmento tem UMA secao: a troca de secao abre
  segmento novo, encostado), Caso 9 (T parte so' a face que recebe a viga),
  Caso 11 (lajes/nivel por segmento).
  **Respostas do dono ao questionario (2026-09-25):** Q1 troca de secao abre
  segmento; Q2 revisado em 26/09: mesma altura = o SA PARA (vigas de mesma
  altura nao se atravessam); a "abertura de altura inteira" e' so' o ESPACO
  que o N3 desenha entre os dois segmentos — comportamento N3, nao leitura SA;
  Q3 Passa = pilar inteiro num
  segmento com inicio/fim registrados; Q4 pilar e viga coincidentes = ambos;
  Q5 -11 so' no N3; Q6 contagem do N4 NAO e' referencia (o humano pode ter
  errado) — vale o comportamento e a leitura autonoma do SA; Q7 livre.
  Detalhes do segmento vivem no proprio vinculo (`lv_cell`), porque os campos
  `viga_{a|b}_seg_N_*` sao por lado+indice e compartilhados entre Para e Passa.
- Passada global no headless (`apply_lv_cells_all`), depois da passada global
  do FV. Celula com segmento validado por humano fica congelada.

**Prova (DXF real da VPS, pipeline headless read-only):** V301 com 16
segmentos por lado (305,5 19/55 | 134,5 19/120 com P42 inteiro | 84,5 |
318 ...), fronteiras de secao conferidas contra a cadeia de cotas do DXF
(ex.: 106,5 | 19 | 41,5 junto ao P48) e overlays PNG lidos para V301/V303/V304. PIL (46), FV (76), LAJ (31)
com hash identico com e sem a passada. Testes: `tests/test_lv_cells_guia.py`.

**Viga diagonal (guia Caso 8, 2026-09-26, `guia_lv_cells_v6`):** V307 e VF202
tem cena propria num referencial GIRADO (`LvScene.angle`, angulo real das
bordas junto ao rotulo); os pontos voltam ao DXF. Sentido de leitura do A =
0 graus na horizontal, -90 na vertical e o proprio eixo na diagonal; A = lado
DIREITO desse sentido (reproduz G0 nas ortogonais). Cada face vai ate' onde a
propria linha vai (pontas em esquadro obliquo), sem entrar na faixa de outra
viga. Convencao CONFIRMADA pelo dono (2026-09-26): duas diagonais alinhadas
que dividem a mesma linha de face (V307 19/55 e VF202 14/55, face A) — a
primeira termina no fim do trecho comum as duas faces dela, a seguinte
comeca ali. Encontro obliquo deixa lasca triangular: lasca de ponta menor que
a largura da incidente vira ponta (V306 face A passa a comecar na VF202).
Canto em L ortogonal x diagonal (v7): na ponta em que a diagonal CONTINUA a
viga (ocupa >= metade da largura alem da ponta), a face de fora da ortogonal
vai ate' o canto de fora pela propria linha (VF203 A de 1444,65 -> 1439,08 na
VF202; V309 A de 2217,51 -> 2209,33 na V307). Se outra viga encosta POR FORA
nesse trecho (VF202 na face A da V306), a face nao estende.

Fronteira FV x LV (2026-09-27) — regras comuns, cada classe granular:
1. Autoridade unica de PAREDES da viga = cena do DXF (`lv_beam_scene`: faixa
   medida a partir do rotulo da propria viga). A LV corta celulas por ela; o
   gate D-60 do FV decide "fundo entre as laterais da propria viga" por ela
   (largura da faixa = largura aceita no reparo). Vinculo lateral salvo so' e'
   fallback quando a viga nao tem cena — ele pode ser antigo (o merge repoe) e
   anulou 22 fundos certos no job LV de 27/09 (V301/V303/V309/V314...).
2. Isolamento por classe: job que nao roda Fundos so' AUDITA o gate FV (copia
   dos dados); reparar/anular fundo e' decisao do job de FV.
3. FV e' referencia para a LV (fronteira de secao), nunca lei; e a LV nao e'
   lei do FV — os dois leem o mesmo DXF.
4. Sem fronteira do FV a LV cai no meio entre rotulos de secao: fundo anulado
   muda a secao das laterais. Conferir as duas classes depois de job de FV.
5. Publicacao granular: o portal promove do job de uma classe so' os
   segmentos DELA (`fundo` <- job de FV, `lateral_*` <- job de LV; com
   `--item`, so' as vigas pedidas); o resto fica do estado anterior
   (`pipeline_runner._preservar_segmentos_de_outras_classes`). Sem isso o job
   de LV publicava os fundos crus por cima dos auditados (27/09).
O "V330" horizontal em (4480, 1623) e' legenda solta junto ao P49, sem faixa
de viga — nao e' segundo trecho. Duvidas abertas ao dono:
`docs/QUESTIONARIO-LV-SA-2026-09-25.md`.

### N4

`scripts/motor_reverso_lv.py` extrai a ficha N2. Em seguida:

1. `validate_n4_ficha` valida e normaliza a ficha;
2. `gerar_lv_n4_fichas.py` materializa o mesmo formato consumido pelo motor;
3. `gerar_lv_dxf_stog.py --strict-contract` desenha;
4. a ficha fornecida e autoritativa.

Reextrair o recorte e uma nova operacao do interpretador. Ela so ocorre com
`--refresh-from-recorte`; nunca como fallback escondido durante a geracao.

## 7. Invariantes verificaveis

- ficha sem A ou B: erro, nunca copia do outro lado;
- largura/altura zero: erro com caminho do campo;
- mudar somente `bbox` ou confianca: mesmo fingerprint;
- mudar largura, altura, painel, vazio ou sarrafo: novo fingerprint;
- degrau 109/44: cota interna 65 em `COTA`;
- no mesmo degrau, nenhuma vertical baixa indevida em `Painéis`;
- lateral sem vazio: zero HATCH;
- lateral com um vazio: exatamente o hatch desse vazio.

## 8. Regra para evolucao

Uma correcao no motor precisa ser expressa como regra universal de ficha e ter
teste positivo e de controle. Condicao pelo nome `V301`, coordenada do recorte
ou score visual nao e regra de motor. Se a informacao necessaria nao existe na
ficha, primeiro corrige-se o interpretador/contrato; so depois o motor aplica o
campo de forma deterministica.

