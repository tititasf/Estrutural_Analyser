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

## 6. Material de compra — plano de corte (`services/plano_de_corte.py`)

- **Barras (1D):** First Fit Decreasing na barra de 300 cm, por material. Peça
  maior que 3 m = **emenda** (barras inteiras + resto), contada à parte.
- **Chapas (2D):** guilhotina, "best short side fit", rotação livre, chapa
  244 × 122. Peça que não cabe em nenhuma orientação é dividida em faixas
  (244 / 122) e contada como **emenda**.
- Sem perda de serra e sem % de quebra: o número é o **mínimo físico** para
  cortar o que está desenhado. O aproveitamento (%) aparece ao lado.
- As peças de todos os grupos do item saem do mesmo estoque (sobra do lado A
  corta peça do lado B).

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
- **Q3** — Sarrafo de pressão (ABCD do pilar): sai da barra 2,2 × 7 × 3 m? Hoje
  está assumido que sim.
- **Q4** — LV com painel < 15 cm: comprar sarrafo 2,2 × 5 (como o gerador
  posiciona) ou 2,2 × 7 (como a layer diz)?
- **Q5** — Perda: aplicar % de quebra ou perda de serra na compra, ou manter o
  mínimo físico?
- **Q6** — Lista do pavimento: somar a compra por pavimento (reaproveitando
  sobra entre itens) é o que a equipe usa para pedir material?

## 9. Mapa do código

| Peça | Arquivo |
|---|---|
| Medição do DXF N3 | `consulta-publica-api/services/materiais_service.py` |
| Plano de corte | `consulta-publica-api/services/plano_de_corte.py` |
| Endpoint | `GET /api/v1/ficha/{code}/materiais` (`routers/materiais_routes.py`) |
| Aba no portal | `consulta-publica-web/components/ficha/MateriaisTab.tsx` |
| Testes | `consulta-publica-api/tests/test_materiais_service.py` |
