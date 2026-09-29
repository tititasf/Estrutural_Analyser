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
