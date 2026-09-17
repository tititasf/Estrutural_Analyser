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

