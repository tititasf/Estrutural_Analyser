# Interpretação — quando a viga "chega" na face do pilar

Decisões do dono em **2026-08-20**, respondendo à dúvida levantada no caso
`V313 × P29` do 13_PAV. Este documento é a fonte da regra; o código aponta
para cá.

Evidência visual da dúvida:
`scripts/arete/relatorios/qa_pil_dinamico_causas_20260819/DUVIDA-V313-P29.html`

O formato dessa ficha virou padrão: `scripts/arete/gerar_duvida_html.py`.
Dúvida de interpretação que só se decide olhando o desenho vai ao dono nesse
formato — recorte real do DXF com pan/zoom por viewBox, elementos em disputa
realçados, leituras lado a lado com a consequência de cada uma, e **uma**
pergunta respondível em uma frase.

---

## R1 — O vão entre a viga e a face é continuação da viga

> "obviamente esse vão é continuação da viga acima"

Quando o desenho não repete o trecho da viga entre o fim do corredor traçado e
a face do pilar, esse vão **não** é ausência de viga: é a própria viga, que o
desenho deixou de repetir porque ali passa outra viga ou porque é a região de
apoio.

**Caso de referência.** `P29` termina em `y=2029`. Acima há 19 cm sem nada
desenhado, depois `V306` (2048–2067) e só então `V313` começa em `y=2067`.
`V313` está alinhada ao eixo de `P29`. Pela regra, **V313 chega em P29** — o
vão de 38 cm é continuação dela.

**Consequência para o motor.** Exigir contato geométrico exato é errado. A
chegada vale enquanto o vão for ocupado por viga (ou pela região de apoio que
o desenho omite).

**Estado da implementação.** `_bridgeable_gap` em
`src/core/pillar_face_beams.py` calcula quanto do vão é fechável (soma dos
corredores de outras vigas que o ocupam + a própria seção). A regra está
**desligada** e o motivo é uma dependência a montante: o vão só fecha se a
viga que o ocupa alcançar o pilar, e `V306` chega truncada em `P29`.

Tentativas medidas para destruncar, todas revertidas:

| tentativa | resultado |
|---|---|
| aplicar o corredor recuperado a todas as vigas | 205 células, PASS 7 |
| estender só onde o recuperado contém o traçado | 211 células, PASS 1 |
| ligar a ponte com os corredores como estão | 123 células, PASS 13 |
| **só reparar trecho sem parede desenhada** | **110 células, PASS 17** |

A conclusão que sobra: **o par de paredes não delimita a extensão da viga**.
As paredes continuam além dela porque outros elementos são colineares — e o
principal deles é o **próprio pilar**: um pilar alinhado ao eixo da viga tem
arestas exatamente sobre as mesmas retas, e a varredura não vê interrupção
nenhuma. Foi o que esticou `V313` (2029–2421) por cima de `P20` até o
território de `V314`.

**Linha de chamada não serve neste desenho.** Medido em 2026-08-21: dos 37
rótulos de viga, **33 não têm nenhuma linha com extremo a 8 cm do texto**, e
os 4 restantes encostam em traço de hachura ou linha de cota, não em leader.
O DXF não tem entidade `LEADER`/`MLEADER` alguma — só `LINE`, `TEXT`,
`LWPOLYLINE` e `CIRCLE`. O desenho amarra rótulo a viga por **posição**, não
por chamada.

**Critério que faltava, encontrado em 2026-08-21: o apoio.** A viga termina
no pilar que ela não atravessa, e o que distingue os dois casos é a largura:

| relação | leitura |
|---|---|
| pilar **estritamente mais largo** que o corredor na direção transversal | a viga fica embutida e sai do outro lado — `VF203` (14 cm) atravessa `P28` (80 cm) |
| pilar com **a mesma largura** do corredor | a viga morre nele — `V313` (19 cm) termina em `P20` (19 cm) |

É a mesma régua da R2, aplicada à extensão em vez de ao papel. E é
independente de camada: usa só a caixa do pilar e a largura do corredor.

`blocking_supports` + `_cut_at_blocks` em
`src/core/beam_corridor_recovery.py`. Efeito medido: **110 → 101 células,
PASS 17 → 18, violações 9 → 8**. `V309` passou a recuperar 2300–2620 (sua
extensão real) e `P10` e `P25` ficaram verdes.

Com o corte por apoio no lugar, as duas tentativas anteriores foram
retestadas e **continuam piorando**: estender trecho medido dá 127 células /
PASS 14, e ligar a ponte da R1 dá 107 / PASS 15. Ambas seguem desligadas.

Um bug de corte foi corrigido no caminho: o corte por rótulo comparava contra
rivais que **perderam** o par de paredes, e `V306` saía com 26 cm de um
corredor de 2400 por causa do rótulo de `VF202`. Agora só quem ganha o par
corta.

---

## R2 — Mais estreita que a face → `chega`; do tamanho da face → `interior`

> "por ser menor que a face C é considerado viga chega e não viga interior"

O que distingue **chegada** de **interior** numa face curta é a comparação
entre a **largura da viga** e o **comprimento da face**:

| Relação | Papel | Leitura |
|---|---|---|
| largura da viga **<** comprimento da face | `chega` | a viga encosta na face e sobra face dos lados |
| largura da viga **=** comprimento da face | `interior` | a face inteira fica dentro do corpo da viga |

**Casos de referência.** `V313` tem 19 cm e a face C de `P29` tem 24 cm →
`chega`. `V308` tem 19 cm e a face C de `P35` também 19 cm → `interior`
(achado anterior do dono, protegido por
`tests/test_pillar_face_beams.py::test_beam_stopping_on_short_face_materializes_corner_openings_on_long_faces`).

Consequência já implementada: uma viga que corre **paralela** às faces
vizinhas e morre naquele canto já está vinculada nelas, e ali é `interior`,
não uma chegada nova — `_bound_on_adjacent_faces`.

---

## Como isso se encaixa no invariante de face

Complementa o invariante já registrado (viga que chega parte o contato da
laje):

- viga chega no **meio** da face (`XX`) → duas lajes, uma em cada canto;
- viga chega num **canto** → uma laje só, no canto oposto;
- **nenhuma** viga chegando → uma laje cobrindo a face (`XX`).

Verificação: `validate_face_slab_beam_invariant` em
`src/core/pillar_abcd_tables.py`.

---

## O que ainda não está decidido

Nada nesta dúvida. O que falta é **capacidade**, não regra: recuperar a
extensão real dos corredores de viga (`src/core/beam_corridor_recovery.py`
faz isso hoje só como reparo, onde o trecho traçado não tem parede desenhada).
Com os corredores inteiros, R1 pode ser ligada.


---

## R3 — Pilar que a viga atravessa x pilar onde ela morre (2026-08-21)

Derivado da geometria e confirmado no corpus:

| relação | leitura | caso |
|---|---|---|
| pilar **estritamente mais largo** que o corredor | a viga fica embutida e sai do outro lado | `VF203` 14 cm por `P28` 80 cm |
| pilar com **a mesma largura**, e outra viga do outro lado | a viga morre nele | `V313` 19 cm em `P20`, com `V314` depois |
| pilar com **a mesma largura**, e a própria viga do outro lado | a viga atravessa | `V308` por `P34` |

Quem diz o que há do outro lado é o **rótulo**. `blocking_supports` +
`separating_blocks` em `src/core/beam_corridor_recovery.py`.

Seção ilegível não desqualifica um rival: `V307` sai do traçador com `192/60`
e, filtrada por largura, sumia — `V309` invadia o território dela.

## O bloqueio que continua: extensão de corredor

Duas causas grandes do 13_PAV são a mesma: o corpus trata a viga como
**atravessando** o pilar (`V316` em `C.passa`/`D.passa` de `P13`; `V319` em
`C.interior`/`D.interior` de `P23`) e o motor a trata como terminando nele. O
corredor recuperado já sabe que ela continua (`V316`: 2661–3323 cobre `P13`
inteiro), mas o trecho traçado para na face.

Quatro variantes de extensão foram medidas, todas revertidas:

| variante | células | PASS |
|---|---|---|
| corredor recuperado em todas as vigas | 205 / 188 | 7 |
| "recuperado contém o traçado" | 211 / 127 | 1 / 14 |
| extensão cirúrgica pelo apoio cruzado | 145 | 17 |
| **só reparo** | **97** | **23** |

`_extend_through_crossed_support` fica no código, testada e **desligada**,
para quando a truncagem for resolvida a montante no traçador.

Também medido e revertido: marcar `interior` nas **duas** faces curtas quando
a viga morre numa delas. Acerta `P23` (5→2 células) e `P24` (5→3), mas leva o
total de 97 para 165 e o PASS de 23 para 12. A face oposta é interior por
**passagem**, não por simetria.


---

## Diagnóstico do traçador de vigas (2026-08-21)

Em vez de tentar cobrir todos os casos, as situações foram **nomeadas e
medidas**. Das 36 vigas do 13_PAV:

| situação | vigas | tratamento |
|---|---|---|
| traçado correto | 24 | — |
| **traçado sem parede** — geometria fabricada ou deslocada | 8 | reparo pelo par de paredes (`beam_corridor_recovery`); 7 recuperadas |
| **corredor inflado** — bbox de trechos disjuntos ou de diagonal | 4 | guarda de espessura (`_run_thickness_matches_section`) |

`VF203` é o caso extremo: recebeu geometria em x 1038–1434, onde o desenho
não tem **nenhuma** linha. `V323`, `V329`, `V331` e `VF202` recebem corredor
de 49 a 76 cm para seções de 14 a 19.

### Seção que se autocorrige pela geometria

`V307` saía com seção `192/60`; o desenho traz `19/60` a 96 cm do rótulo.
A recuperação passou a tentar as cotas vizinhas quando a seção declarada não
encontra par de paredes — e adota só a que a **geometria confirma**, nunca a
mais próxima por si só. Assim `V307` entrou no reparo.

Testado o contrário: escolher a seção pela cota mais próxima do rótulo, como
regra geral, acerta **12 de 31** contra 27 da regra atual. A autocorreção é
exceção para leitura corrompida, não substituição da regra.

### Alcance por face — o que o desenho não admite

`beams_within_reach_of_faces` mede a distância do corredor de cada viga a cada
face. Errar o papel (`passa` × `chega`) é leitura; nomear numa face uma viga
cujo corredor está a centenas de centímetros dela não é. O tier
`T0_OUT_OF_REACH` tira essas do gate.

O alcance é **60 cm**, generoso de propósito: pela R1, o vão entre o fim da
viga e a face é continuação da viga, e no 13_PAV chega a 38 cm. Um alcance de
30 cm tieraria 4 células a mais e subiria o PASS de 23 para 25 — mas estaria
marcando como impossível justamente o que a R1 diz que vale. Ficam contando
como **dívida do motor**, não como erro de corpus.


---

## R1 e R2 ligadas (2026-08-21)

Depois de seis tentativas frustradas, as duas regras do dono estão no motor.

**O que faltava para a R1** não era a ponte — era a informação de **o que
ocupa o vão**. `_bridgeable_gap` perguntava isso ao trecho *traçado* das
outras vigas, e o de `V306` para em x 1603, no pilar `P28`. O corredor
**medido** dela vai a 3788 e cobre `P29`. Passar o corredor medido
(`measured_corridors`, só para essa pergunta — nunca para atribuir viga a
face) fez a ponte fechar os 38 cm: 19 de `V306` mais a própria seção.

**O que faltava para a R2** era que a montagem da tabela forçava
`interior` para qualquer chegada central em face curta. Agora compara larguras
(`_short_face_role`): viga mais estreita que a face é `chega`, do tamanho da
face é `interior`. Restrita a contorno retangular — em L a caixa envolvente
devolve o braço inteiro, e quem trata E/F é o contorno real.

**Terceira peça:** chegada central tem folga **simétrica**, o que sobra da
face dos dois lados. `V313` em `P29`: face 24, viga 19, 2,5 de cada lado — o
número exato do corpus.

Efeito conjunto: **79 → 76 células, PASS 23 → 25**, com `P31` e `P32` verdes.


---

## R4 — Chegada na esquina é chegada **e** passagem (2026-08-22)

> "ela chega na face B, na esquina BC, e por estar chegando na esquina C
> simultaneamente para o lado C é viga passa. então é ambas informações."

Uma viga que morre no pilar encostando numa **esquina** produz **duas** linhas,
não uma escolha entre duas:

| face | papel | canto |
|---|---|---|
| face longa em que ela chega | `chega` | `BC` (ou `AC`) |
| face curta do topo | `passa` | `CB` (ou `CA`) |

O dono acrescentou o porquê físico: a parede dessa viga pode ser mais profunda
que a viga interior ou a que chega do lado C, e então **passa por baixo** dela.
A profundidade é tema de lateral de viga, mas a leitura em planta já registra
a passagem.

**Consequência no motor.** `apply_c_dualidade` já criava o par; quem o
desfazia era `apply_c_interior_suppress_top_dual`, que apagava chegada e
passagem juntas sempre que a face C tivesse qualquer viga de interior — mesmo
sendo **outra** viga. A supressão passou a valer só onde a viga **não chega de
fora**: chegada é vinda de fora, o corredor tem de ultrapassar a linha da face
afastando-se do pilar (`_arrives_from_outside`).

**Consequência no gate.** O par é uma informação só: quando a linha da face
longa é rebaixada por medição (`T0_NO_PASSAGE_THROUGH_FACE`), a contrapartida
em C daquela viga fica sem julgamento junto. O corpus do `P10` registra
`B.passa@BC` onde a medição diz que a viga **chega** — a metade dela em C
nunca foi registrada, e não há prova sobre nenhuma das duas.

**Efeito medido:** `P41`, `P23` verdes; `P10` continua verde. 23 → 20 células,
32 → 34 itens.

Casos de referência: `P41`/`V301`, `P24`/`V304`, `P49`/`V301`, `P10`/`V302`.
Ficha da dúvida que o dono respondeu:
`scripts/arete/relatorios/qa_pil_dinamico_causas_20260819/DUVIDA-P10-P41-CHEGA-OU-PASSA.html`
