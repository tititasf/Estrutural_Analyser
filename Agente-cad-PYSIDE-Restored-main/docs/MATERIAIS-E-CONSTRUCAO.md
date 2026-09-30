# Materiais e Construção — quantitativo de painéis e sarrafos

> Doc canônico do tema (2026-09-28). Consolida as regras que estavam espalhadas
> pelos geradores STOG, pela semântica das classes e pelos robôs SCR legados, e
> descreve como o portal transforma o desenho técnico (N3) em **lista de peças**
> e em **material de compra**. Decisão que abre o tema: **D-66** (supera D-15).

## 1. Princípio: medir o desenho, não recalcular

A lista de materiais é **medida no DXF N3 desenhado** — o mesmo que a equipe
recebe na aba "Desenho Técnico". Cada gerador já aplicou as regras dele (módulo
de chapa, barra de 3 m, posições por altura). Recalcular essas regras num
segundo lugar criaria outra verdade que diverge do desenho. Consequência: **se a
lista estiver errada, o erro está no desenho** — e o conserto é no gerador.

Dois níveis de saída, por item (aba "Materiais e Construção" da ficha):

| Nível | O que é | Unidade |
|---|---|---|
| **Peças** | cada painel e cada sarrafo cortado, com medida | un + cm |
| **Material de compra** | chapas e barras que cortam essas peças (plano de corte) | chapas / barras |

## 2. Estoque — convenção do dono (D-66)

| Material de compra | Seção | Comprimento | Corta |
|---|---|---|---|
| Chapa de compensado | — | **244 × 122 cm** | todos os painéis (LV, FV, LAJ, ABCD) |
| Sarrafo | **2,2 × 7 cm** | **3 m** | sarrafos padrão (layer `SARR_2.2x7`) |
| Sarrafo (variante) | 2,2 × 10 cm | 3 m | `SARR_2.2x10` (grades de pilar) |
| Sarrafo (variante) | 2,2 × 5 cm | 3 m | `SARR_5cm` (FV com viga de 10–14 cm), LV com painel < 15 cm |
| Meio pontalete | ver §8 Q1 | 3 m | grades de viga e de pilar (`SARR_3.5x7`) |

## 3. O que se quantifica, por classe

| Classe | Vista | Quantifica? | Painéis | Sarrafos |
|---|---|---|---|---|
| **PIL** | ABCD (Para ou Passa) | sim | sim (pilha por face) | sim |
| **PIL** | Grades (Para ou Passa) | sim | não existem | sim (grade = sarrafos + meio pontalete) |
| **PIL** | Cima (seção) | **não** — só perspectiva | — | — |
| **LV** | Laterais (lado A e lado B) | sim | sim | sim |
| **LV** | Corte (VC) | **não** — só perspectiva (por enquanto) | — | — |
| **FV** | Fundo | sim | sim | sim |
| **LAJ** | Painéis | sim | sim | **não** — laje é só painel |

O pilar tem **duas classes de material**: ABCD (painéis + sarrafos) e Grades
(só sarrafos/pontaletes). Cada código de pilar é de **um modo** (Para ou Passa)
e só mede o ABCD/Grades daquele modo.

## 4. Como cada gerador produz as peças

### 4.1 LV — lateral de viga (`scripts/gerar_lv_dxf_stog.py`)

- **Painéis:** ordem e largura **exatamente as da ficha** (`panels[]`,
  `CONTRATO-RIGIDO-MOTOR-LV-N3-N4.md` §5.1). O motor de células corta a lateral
  em pilares (Para/Passa, D-48/D-62/D-63/D-64) e cada trecho vira painéis de até
  244 cm.
- **Sarrafos por altura do painel** (`_get_sarrafo_positions`, tabela SCR):

  | Altura do painel h | Sarrafos horizontais | Posições (a partir do fundo) |
  |---|---|---|
  | h < 15 | 2 (largura 5 cm) | 5 e h−5 |
  | 15 ≤ h < 30 | 2 | 7 e h−7 |
  | 30 ≤ h < 80 | 4 | 7, centro ±3,5, h−7 |
  | h ≥ 80 | 8 | 7, centro ±3,5, quartos ±3,5, h−7 |

  Comprimento = largura do painel (pode passar do painel em reaproveitamento,
  `SEMANTICA-VIGA-NOVA.md` §2.3). Supressão só com `suppress_auto_sarrafos`.
- **Painel de degrau** continua recebendo sarrafos na altura real dele.

### 4.2 FV — fundo de viga (`scripts/gerar_fv_dxf_stog.py`)

- **Painéis:** módulo de 244 cm (`PAINEL_MODULO`); vão ≤ 244 = 1 painel;
  maior = n × 244 + resto; resto < 30 cm funde no último painel. A largura do
  painel é a largura do fundo (b da viga).
- **Sarrafos:** longitudinais com recuo de 7 cm das bordas; faixas internas a
  cada ≤ 21 cm (`SARR_MAX_GAP`); exemplos: b=19 → [7, 12]; b=45 → [7, 19, 26, 38].
  Barra horizontal ≤ 300 cm (`SARR_MAX_LEN`), dividida nas uniões de painel.
- **Bitola pela largura da viga:** b ≤ 14 → `SARR_5cm`; b < 10 → `SARR_CONTORNO_10cm`;
  demais → `SARR_2.2x7`.

### 4.3 LAJ — laje (`scripts/gerar_lj_dxf_stog.py`)

- **Painéis:** chapas padrão 244 / 122 / 60 + uma sobra; a sobra nunca passa de
  122 no eixo curto (a chapa é 244 × 122). Junta explícita do recorte N2 é
  respeitada mesmo fora do módulo. Laje poligonal gera painéis **recortados**.
- **Sem sarrafos** na lista (decisão do dono): as linhas pareadas de 19 cm que o
  gerador desenha são referência de apoio, não material deste quantitativo.

### 4.4 PIL — pilar (`scripts/gerar_pl_dxf_stog.py`)

- **ABCD — painéis:** cada face (A, B, C, D; E–H em pilar L/T/U) é uma **pilha de
  painéis** com as alturas de `paineis_intervals_{face}` no contrato `P{n}.json`
  (ex.: P1 Passa, face A = 122 + 122 + 11). A largura da face é a desenhada
  (inclui o encosto): P1 = 88 / 88 / 19 / 19.
  **Atenção:** o desenho omite a linha de painel onde a viga chega ou passa, então
  as células não fecham. Por isso o portal lê a pilha do contrato e não a
  geometria. `h1_*` = 2 cm é cinta, não painel.
- **ABCD — sarrafos:** `SARR_2.2x7` + `Sarrafo de Pressão`.
- **Grades:** sem painel; sarrafos `SARR_2.2x7`, `SARR_2.2x10` e `SARR_3.5x7`
  (meio pontalete). Largura da grade: `grade_1 = faces AB + 22` (11 cm de cada
  lado, `SEMANTICA-PILAR-NOVA.md` §3); L/T/U em `CALCULOS_ALGORITMOS.md` §8.

## 5. Como o portal mede (`consulta-publica-api/services/materiais_service.py`)

- **Painel** = célula fechada pelas linhas da layer `Painéis`/`PAINEIS`
  (poligonização). Célula não retangular = **recortado** (a medida mostrada é o
  retângulo envolvente). No ABCD do pilar vale a pilha do contrato (§4.4).
- **Sarrafo** = 1 entidade por peça (linha de centro, retângulo ou bloco). A
  bitola vem do nome da layer. Retângulo mede o lado maior.
- **Duplicata** (entidade idêntica sobreposta) conta uma vez — ver §7 D1.
- LV: um DXF por viga × lado; o item mostra "Lado A" e "Lado B".
- **Grades desenham cada peça como retângulo de 4 LINEs**: o medidor reconstrói o
  retângulo (lado menor ≤ 12,5 cm) e conta **1 peça** com o lado maior. Só vale
  retângulo cujos 4 lados são LINEs inteiras com cantos coincidentes: no FV, as duas
  barras a 5 cm + os montantes das pontas também fecham um "retângulo" (447 × 5 no
  V309A S1) e eram lidos como 1 sarrafo de 447 cm — erro do medidor, não do gerador
  (o gerador parte a barra na união quando a corrida passa de 300 cm). Antes de
  28/09 cada LINE contava como sarrafo (grades infladas ~4×).
- **Sarrafo dentro do painel:** cada sarrafo vai para o painel sobre o qual mais
  corre (sobreposição no eixo longo da peça). No ABCD a caixa do painel vem da pilha
  do contrato empilhada a partir da base desenhada da coluna da face. Sarrafo que
  não corre sobre painel = "fora de painel". A lista de painéis mostra, na linha de
  cada painel, os sarrafos dele.
- **Grades do pilar:** cada grade é o rótulo `P{n}.{face}` (layer NOMENCLATURA) à
  esquerda dela; a aba lista grade por grade (lado A, lado B...) com o material.
- **Laje — classe do painel:** célula dentro de um HATCH (a LJ hachura a faixa
  estreita da união, layer `Hachura`/`REAPROVEITAMENTO`) = **Tira de escoramento**,
  não reaproveitável; demais = **Painel comum**, reaproveitável (dono, 28/09).

## 6. Material de compra — plano de corte (`services/plano_de_corte.py`)

- **Barras (1D):** Best Fit e First Fit Decreasing na barra de 300 cm, vence a de
  menos barras. **Perda de 1 cm por corte** também na barra (dono, 28/09): 150 + 149
  cabe, 150 + 150 não. Peça maior que 3 m = **emenda** (barras inteiras + resto).
- **Chapas (2D):** guilhotina com rotação livre, **otimizada por múltiplas
  estratégias** (5 ordens das peças × 3 regras de encaixe × 4 direções de corte =
  60 planos). Vence o de menos chapas; no empate, o que concentra a sobra em
  pedaços maiores (reaproveitáveis). Determinístico. Para cedo se atingir o limite
  inferior de área. Peça maior que a chapa vira faixas (244 / 122) = **emenda**.
- **Perda de corte na chapa = 1 cm por corte** (horizontal ou vertical, dono
  28/09): numa faixa de 122 cabem 102 + 19, não 102 + 20. Exemplo L301: 3 chapas
  sem a perda → **4 com a perda** — mínimo verificado à mão (50 + 1 + 194 = 245 > 244;
  61 + 1 + 61 = 123 > 122). Sem % de quebra.
- As peças de todos os grupos do item saem do mesmo estoque (sobra do lado A
  corta peça do lado B).
- **Numeração e ID Painel (todas as classes, dono 28/09):** 1 linha por painel
  físico, em ordem de leitura do desenho (ABCD: face a face, de baixo p/ cima). Cada
  painel tem Nº (1..N no item) e **ID rastreável**
  `{OBRA}-{PAV}-{CLASSE}-{ITEM}-P{nn}`, ex. `TREINO_1-13PAV-LAJ-L301-P01`,
  `TREINO_1-13PAV-PIL-P1.PASSA-P03`, `TREINO_1-13PAV-FV-V309A.S1-P02`,
  `TREINO_1-13PAV-LV-V309A.PARA-P05`. OBRA = rótulo da obra sem "Obra_"; ITEM =
  título público (+ modo no pilar/LV, + segmento no fundo). O ID aparece na lista e
  no viewer de chapas; faixa de emenda herda o ID + letra. Objetivo: listagem de
  painéis disponíveis para reaproveitamento no próximo pavimento (a fazer: Q8).
- **Viewer de chapas:** uma mini-aba por chapa comprada; desenha a chapa
  244 × 122 com cada peça na posição de corte (x, y a partir do canto superior
  esquerdo), o número do painel, a medida e a sobra hachurada e numerada (S1,
  S2…). Tabela: nº, de onde é o painel (lado/face) ou "Sobra", e a medida.
  Pan/zoom por viewBox. A aba tem 2 sub-abas: "Painéis e sarrafos" e "Material de compra".

## 7. Divergências e defeitos conhecidos (medidos em 28/09, 13_PAV)

| ID | Onde | O quê | Efeito no quantitativo |
|---|---|---|---|
| D1 | LV (gerador) | Sarrafos horizontais desenhados **2×** em todos os 132 DXFs (2516 entidades duplicadas) | Neutralizado pelo dedupe; o desenho ainda está duplicado |
| D2 | PIL ABCD Para | 126 duplicatas em 38 DXFs | Idem |
| D3 | PIL ABCD | Linha de painel ausente onde a viga chega/passa | Geometria subconta (P1 Passa: 4 contra 7); o portal usa o contrato |
| D4 | PIL P26, P27, P29–P32 Passa | O desenho não separa as faces como o contrato (P29–P32: 5 colunas, uma de 10 cm) | Largura da face vem da ficha (larg1+2+3); aviso na aba |
| D5 | LV painel < 15 cm | O gerador usa sarrafo de 5 cm, mas grava na layer `SARR_2.2x7` | Conta como 2,2 × 7 — ver Q4 |
| D6 | LV lateral | Painéis de **124 cm** de altura (> 122 da chapa) | Viram "emenda" no plano de corte — ver Q2 |

## 8. Perguntas abertas ao dono

- **Q1** — Meio pontalete: a seção é 3,5 × 7 cm (a layer das grades é
  `SARR_3.5x7`) ou 3,5 × 2,2 como está no chat de 28/09?
- **Q2** — Lateral de 124 cm: é chapa de 122 + complemento de 2 cm (sarrafo ou
  sobra), ou existe chapa maior para lateral? Hoje conta como emenda.
- ~~Q3~~ — **Respondida (D-67, 28/09):** o sarrafo de pressão (layer "Sarrafo de
  Pressão", linha HIDDEN, desenhado só pelo eixo) é **2,2 × 7** da barra de 3 m.

## 9. Montagem painéis (3D)

Sub-aba "Montagem painéis": uma aba por painel medido; three.js anima a chapa
já cortada entrando na bancada e os sarrafos descendo um a um até a posição
medida no N3 (`montagem` por painel na API: x, y, w, h em cm a partir do canto
inferior esquerdo do painel). Ordem: peças mais longas primeiro, pressão por
último, pregado na **face de trás** (linha HIDDEN; dono, 28/09). Chapa com 1,8 cm
de espessura (só visual). Grades ainda não têm animação.

**Sarrafo de painel = par de linhas (dono, 28/09).** No painel (LV, FV, ABCD) o
sarrafo é desenhado pelas duas bordas: duas linhas paralelas = 1 sarrafo; linha
sozinha faz par com a borda do painel. `_parear_linhas` escolhe o par cuja
distância bate com a largura da bitola (±1,5 cm) — FV 19 cm com linhas em 7 e 12
= 2 sarrafos de 7 contra as bordas. Antes cada linha contava 1 peça (LV V309A:
9 → 6 por painel; a compra caiu junto). Linha sem par (recortes do ABCD junto à
viga) continua 1 peça, com 7 cm centrados.
- **Q4** — LV com painel < 15 cm: comprar sarrafo 2,2 × 5 (como o gerador
  posiciona) ou 2,2 × 7 (como a layer diz)?
- **Q5** — Perda: aplicar % de quebra ou perda de serra na compra, ou manter o
  mínimo físico?
- ~~Q7~~ — perda de 1 cm por corte na barra: **sim** (dono, 28/09), aplicada.
- **Q8** — Registro de reaproveitamento: onde a equipe marca que o painel
  `...-P03` foi desmontado e está disponível, e como o próximo pavimento o consome?
- **Q6** — Lista do pavimento: somar a compra por pavimento (reaproveitando
  sobra entre itens) é o que a equipe usa para pedir material?

## 9. Mapa do código

| Peça | Arquivo |
|---|---|
| Medição do DXF N3 | `consulta-publica-api/services/materiais_service.py` |
| Plano de corte | `consulta-publica-api/services/plano_de_corte.py` |
| Endpoint | `GET /api/v1/ficha/{code}/materiais` (`routers/materiais_routes.py`) |
| Aba no portal | `consulta-publica-web/components/ficha/MateriaisTab.tsx` |
| Viewer de chapas | `consulta-publica-web/components/ficha/ChapasViewer.tsx` |
| Testes | `consulta-publica-api/tests/test_materiais_service.py` |

## 10. Sobras rastreáveis (28/09)

Toda sobra do plano de corte tem ID no formato do painel, para o registro de
reaproveitamento (Q8): chapa `{OBRA}-{PAV}-{CLS}-{ITEM}-CH{nn}-S{k}` (S1 = maior
sobra daquela chapa) e barra `{OBRA}-{PAV}-{CLS}-{ITEM}-{MAT}-B{nn}` (MAT = S7,
S10, S5 ou MP = meio pontalete; o que resta da barra nn depois dos cortes, já
descontado 1 cm por corte). A API devolve a lista em `compra.sobras`; o portal
mostra "Sobras para reaproveitamento" no Material de compra. **Q9 respondida
(D-68): por enquanto nada é descarte** — toda sobra entra na lista, sem filtro
de tamanho mínimo.

## 11. Painéis recortados (aberturas) — 28/09

Painel cuja célula não é retangular (entalhe de viga/pilar, borda diagonal)
leva na API `contorno` (+ `furos`) em cm locais (origem no canto inferior
esquerdo do retângulo envolvente, y para cima). O plano de corte continua
cortando o retângulo; no Material de compra a área de recorte (retângulo −
contorno) aparece hachurada em vermelho na chapa, e a linha leva a tag
"recortado". Na Montagem painéis a chapa é a extrusão do contorno (abertura
vazada). No 13_PAV: L319 P06 (entalhe 81,4 × 65) e P09 (diagonal), L326 P01/P03.
Limite: faixa de emenda (ex. P09a/b, painel > 122) leva só a tag, sem a forma.

**Pilar (ABCD):** a HATCH do ABCD é o concreto da viga/laje que chega na face
(sem layer — só o tipo HATCH). Painel = retângulo da pilha − hachura:
entalhe (ex. P1 face A, 11 × 30 no painel de 244); viga que cruza a face inteira
parte o painel em **2 peças** (`partes`, ex. P1 face C 138 + 36); viga tomando a
largura toda de um lado apenas estreita o painel (P1 face A topo = 77 × 34, não
88). Linha de sarrafo junto do entalhe pareia com a aresta do recorte (antes
ficava solta). LV e FV (132 + 34 DXFs do 13_PAV) não têm hachura nem célula não
retangular: sem recorte, retângulo correto.

**Recorte vira sobra (D-69):** o que sai do retângulo cortado (retângulo −
peças, menos 1 cm de serra) é sobra com ID (`recorte_de` = painel de origem).
Encostado numa sobra do plano, os dois viram uma sobra só (polígono, com o
maior retângulo útil em `util`). No empacotamento, o maior retângulo útil do
recorte vira espaço livre na hora: peça menor que vem depois pode ser cortada
ali (`em_sobra`, tag "na sobra"). 13_PAV: 108 peças de pilar cortadas em
recortes; 638 sobras de recorte rastreadas; 578 chapas (antes 580).

## 12. Reaproveitamento entre pavimentos (dono, 29/09 — D-70..D-73)

Conhecimento de campo do dono: **não perder**. Fonte: chat 2026-09-29.

### 12.1 Ideia

Quando um pavimento é desformado, seus painéis **montados** (chapa + sarrafos
pregados) e as **sobras** (chapa e barra, com ID — §10, D-68/D-69) sobem para o
pavimento seguinte. O pavimento novo consome primeiro o que já existe e só
compra o que falta. Tudo é rastreável pelos IDs (`{OBRA}-{PAV}-{CLS}-{ITEM}-P{nn}`,
`…-CH{nn}-S{k}`, `…-{MAT}-B{nn}`).

### 12.2 Ordem de alocação (D-70)

Cada etapa roda para **todos os itens da classe** antes da próxima ("todos
usam o máximo de si mesmos primeiro"):

| Etapa | De onde vem | Medida |
|---|---|---|
| 1 | Painéis montados **do próprio item** no pavimento anterior | só **idêntica** |
| 1.5 | Painéis montados do próprio item | **outra medida**, cortando conforme a regra da classe (§12.3) |
| — | O que os donos não usaram vira a lista **temporária** "sobra de painéis montados" (existe só para as etapas 2/2.5) | |
| 2 | Painéis montados **de outros itens** da mesma classe (lista temporária), item por item | só idêntica |
| 2.5 | Idem | outra medida, regra da classe |
| 3 | **Sobras de chapa** (inclusive recortes) do pavimento anterior → monta o painel com o sarrafo necessário | pedaço já na medida |
| 3.5 | Sobras de chapa | cortando a sobra em outra medida |
| 4 | **Estoque acumulado** dos pavimentos mais antigos (o que sobrou e não foi usado) — só depois de tudo acima | mesmas sub-etapas |
| Novo | **Fornecimento de material novo**: plano de corte igual ao "Material de compra", só para o que faltou | — |

"Próprio item" = mesmo item no pavimento anterior. Pilar mantém o nome (P10 ↔
P10); viga e laje trocam o dígito do pavimento (V301 ↔ V401, L301 ↔ L401) — é o
padrão, mas **não precisa casar** (o item pode mudar de lugar): o par é só por
nome/número.

### 12.3 Regras de corte por classe (D-71)

O **sarrafo é cortado junto** com o painel (o painel montado não se desmonta);
por isso cada classe só aceita cortar na direção que não estraga a montagem.

| Classe | Condição para reaproveitar | Corte permitido |
|---|---|---|
| **LV** (lateral de viga) — a mais restrita | **Tipo idêntico** (gradeado só em gradeado, sarrafeado só em sarrafeado); **comprimento igual** (nem menor nem maior); **match de sarrafos/grades das extremidades** (ver abaixo) | Só a **altura**: corta-se a **parte de baixo** do reaproveitado |
| **PIL** (pilar) | **Largura igual**: largura diferente não reutiliza | Só a **altura**, cortando **de cima** |
| **FV** (fundo de viga) | **Largura igual** (a espessura/montagem dos sarrafos não se corta); **match de sarrafos das extremidades** | Só o **comprimento** |
| **LAJ** (laje) | **Tira de escoramento nunca** reaproveita (D-66); painel comum sim | Painel comum corta em **qualquer direção** |

**Nunca entre classes diferentes** (painel de pilar não vai para lateral/laje/fundo).

**Match de extremidade (LV e FV).** O painel ocupa uma posição no segmento e
isso aparece nos sarrafos das pontas. Ex.: segmento de LV com 3 painéis — o
P1 tem o sarrafo vertical na extremidade **esquerda**, o P2 **nenhum**, o P3 na
**direita**. Só se reaproveita painel cujo padrão de extremidade (esquerda /
direita / nenhuma / ambas) é **o mesmo** do lugar onde vai entrar: painel com
sarrafo de extremidade **não** vai para o meio de outro segmento, e painel de
meio não vai para a ponta. No FV, ao cortar o comprimento, a ponta cortada fica
sem sarrafo de extremidade — o corte só pode sair da ponta que no destino não
precisa dele.

Detalhe do corte (esclarecido pelo dono, 29/09): LV corta embaixo; PIL corta em
cima; no FV "altura" = espessura (onde vão os sarrafos), por isso só o
comprimento se corta — a largura do fundo também não (os sarrafos
longitudinais correm junto às bordas).

### 12.4 Estoque acumula e se gasta (D-72)

O estoque **acumula** ao subir a obra e **se gasta** conforme é usado. Depois do
pavimento N, estão disponíveis: painéis montados do N (desformados) + o que
sobrou do estoque anterior sem uso + sobras novas do N (plano de corte, recortes
D-69 e os pedaços cortados nas etapas 1.5/2.5/3.5 — nada é descarte, D-68). A
tira de escoramento da laje não entra. O reaproveitamento do estoque antigo é a
**etapa 4** (depois das etapas do pavimento imediatamente anterior).

### 12.5 Portal (D-73)

Sub-aba "Material de compra" vira **"Material necessário, preparação e
reaproveitamento"**, com 3 sub-abas:
1. **Preparação com Materiais Novos** — o plano de corte atual (tudo novo).
2. **Preparação com Materiais Reaproveitados e Novos** — resultado da alocação
   §12.2: cada painel com a etapa e o ID de origem; material novo só do que falta.
3. **Materiais Disponíveis dos Pavimentos Anteriores** — sobras **todas juntas,
   sem proveniência**; painéis montados (com sarrafos) **separados por item** da
   mesma classe (ex.: 14_PAV/pilares lista os pilares do 13_PAV e seus painéis).

Teste de referência: Obra_TREINO_1, **13_PAV → 14_PAV** (SA + N3 do 14 rodados no
portal em 29/09). Casamento só por medida idêntica (±1 cm), antes das regras de
corte: pilares 219/326 painéis no próprio item; laterais 94/235; fundos
230/435; lajes 17/147 (lajes e laterais ganham mais nas etapas 2/2.5).

### 12.6 Implementação (29/09 — `services/reaproveitamento_service.py`)

Rota `GET /api/v1/ficha/{code}/reaproveitamento`. O cálculo é por **cenário
(D-78)**: **Para** = pilares Para + laterais Para + fundos + lajes; **Passa** =
pilares Passa + laterais Passa + fundos + lajes. Os dois cenários são estoques
independentes (nunca se misturam). Fundo e laje entram nos dois e a ficha deles
não cita Para/Passa: usam o cenário do comportamento da obra; em Misto, mostram
Para. Cada cenário roda o pavimento inteiro (todos os
itens de todas as classes) etapa por etapa, em segundo plano: a API responde
**202 `{calculando: true}`** até ficar pronto (≈40 s a frio) e a ficha repete a
consulta a cada 5 s; o resultado vale 5 min e é renovado em segundo plano.

**Critérios que o código aplica** (além da tabela §12.3):

- **Ponta com sarrafo** = peça em pé encostada na borda esquerda/direita da
  montagem do painel (`pontas: [esq, dir]`). **Gradeado** = painel com peça de
  bitola grade/pontalete na montagem; senão sarrafeado.
- **Medida idêntica** = ±1 cm. Painel recortado (D-69) só é idêntico se a forma
  bate (diferença de área ≤ 2%); no pilar, mesma medida e destino com chegada de
  viga que o reaproveitado não tem = etapa cortada ("recorta a chegada de viga").
- **Escolha dentro da etapa:** menor fonte que serve (best-fit por área); nas
  etapas cortadas os painéis maiores escolhem primeiro.
- **Painel montado só volta na própria classe** (etapas 1–2,5 e a parte de
  montados da 4/4,5), rodada classe a classe.
- **Sobra de chapa** (etapas 3/3.5 e 4/4.5): usa o retângulo **útil** da sobra;
  corte em guilhotina, pode girar; o resto do corte volta na mesma etapa.
  Painel feito de sobra leva **sarrafo** — que sai primeiro de **sobra de barra**
  do mesmo material (maior peça primeiro), depois de barra nova. Painel montado
  reaproveitado já vem com os sarrafos (cortados junto, D-71).
- **Peças fora de painel** (grades, avulsos) são sempre preparadas de novo
  (podem sair de sobra de barra).
- **Retalho** de um corte (ID `{fonte}-R{n}`) só entra no estoque do **próximo**
  pavimento — não é reusado no mesmo pavimento em que nasceu, exceto o resto de
  sobra de chapa (acima).
- **Compra nova** = plano de corte (§6) só dos painéis/peças que faltaram; ID com
  sufixo `-N` quando existe estoque (a "Preparação com materiais novos" guarda os
  IDs sem sufixo).
- **Cadeia de pavimentos (D-74):** usa a ordem de **todos** os pavimentos gravada
  no portal de fôrmas em `portal_obra_pavimentos` (`ordem`, `repete_de`,
  `repete_ate`). Pavimento sem DXF ou item continua na cadeia. Enquanto a obra
  não tiver essa ordem cadastrada, há fallback provisório pela ordenação do nome.
  O estoque começa do zero no primeiro; o imediatamente anterior alimenta as
  etapas 1–3.5 e o estoque acumulado mais antigo, as etapas 4/4.5. O pavimento
  TIPO é **um cadastro**: uma faixa 2–10 gera nove concretagens consecutivas
  no cálculo. A peça que sai do TIPO (2º) pode atender o TIPO (3º), e a que sai
  do TIPO (10º) pode atender o 11º. A ficha do TIPO representa a última
  concretagem da faixa. Cada repetição recebe IDs de estoque próprios, sem
  duplicar o cadastro nem confundir peças de concretagens diferentes.
- **Comportamento da obra (D-78):** `portal_obras.comportamento` aceita `para`,
  `passa` e `misto` (padrão das obras existentes). A publicação e a API pública
  ocultam os pilares/laterais do outro modo. Os estoques Para e Passa continuam
  independentes; fundo/laje usam Passa na obra Passa e Para na obra Para ou
  Misto. Alterar ordem, faixa TIPO ou comportamento não apaga materiais.
- **Sobra limpa entre classes (D-75) e maiores primeiro (D-77):** sobra de chapa
  do plano de corte (e o resto dela depois de cortada) é **limpa** e forma um
  estoque só para todas as classes do cenário, mantendo ID, pavimento e classe de
  origem (`fonte_classe`, mostrada na ficha). Nas etapas 3/3,5 e 4/4,5 os painéis
  pendentes de **todas** as classes são ordenados por área, do maior para o menor
  — não há ordem de classes — e cada um pega a menor sobra que serve. Retalho de
  painel montado (`-R`, leva sarrafo) e sobra de barra ficam na própria classe.
- **Cache:** a medição de cada item fica em disco (`$TMP/consulta_reaproveitamento`),
  chaveada pelos DXFs medidos + mtime (o `publish_batch` NÃO entra: o auto-publish
  o troca a cada ~20 s). Primeira chamada do pavimento ≈ 30 s por classe; depois < 1,5 s.

**Resultado TERREO → 13_PAV → 14_PAV (Obra_TREINO_1), painéis por etapa (D-74..D-78):**

| Cenário · classe | 1 | 1,5 | 2 | 2,5 | 3 | 3,5 | 4 | novo |
|---|---|---|---|---|---|---|---|---|
| Para · pilares | 127 | 60 | 7 | 16 | 14 | 96 | 5 | 1 |
| Para · laterais | 92 | 1 | 68 | 8 | 8 | 58 | – | – |
| Passa · pilares | 310 | 5 | – | 5 | – | 5 | 1 | – |
| Passa · laterais | 95 | 12 | 64 | 14 | 8 | 42 | – | – |
| fundos (os dois) | 215 | 35 | 25 | 54 | 16 | 77 | – | 13 |
| lajes (as duas) | 13 | 65 | 26 | 36 | – | 1 | – | 6 |

Antes do D-75/D-77 (cada classe só com as próprias sobras) eram 40 painéis novos
nos pilares Para e 33/28 nas laterais: o estoque limpo dos pavimentos de baixo
(1.230 sobras no cenário Para) cobre quase tudo. Invariantes conferidos na VPS:
nenhuma fonte usada duas vezes, toda peça cabe na sobra, só chapa de compensado
cruza classes. Conferidos no portal: P10 (10/10 reaproveitados; P04 de sobra de
laje L309, P05 de sobra de lateral V328; 21 sarrafos de sobra de barra); fundo
V410 e laje L401 sem citar cenário; lateral V410 Passa com sobra de laje.
