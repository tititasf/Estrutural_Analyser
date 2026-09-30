# Biblioteca de Anormalidades — PIL (v1, baseline 7 pisos)

Catálogo vivo de pilares "especiais" (fora do modelo padrão 4-faces ABCD do
gerador `scripts/gerar_pl_dxf_stog.py`). Alimentado pelos FAILs do G2
canônico (`comparar_pil_canonico`, AR-1'). **Amostra atual: 7 pavimentos da
Obra_TREINO_1** (1_PAV, 2_PAV, 12_PAV, 13_PAV, 14_PAV, TERREO, COBERTURA),
baseline canônico de 2026-06-13.

> Schema da ficha (`reverse_eng_fichas` / Fase-4 JSON) já tem campos para
> 8 faces (`h1..h5_A..H`, `larg1..3_A..H`, `laje_A..H`, `posicao_laje_A..H`)
> — mas o GERADOR (`gerar_pl_dxf_stog.py`) só lê A-D (`comprimento`/`largura`,
> ZONE_ABCD com `FACE_SPACING`, ver linhas 26-32 e 441-537). E/F/G/H nunca
> são consumidos hoje.

## Status geral

Decisão do usuário (sessão 2026-06-13): **validar primeiro os pilares
"comuns"** (já feito — 182/220 = 82.7% PASS, sealados em
`GOLDEN/Obra_TREINO_1/{pav}/PIL/`). Os 38 FAILs abaixo são todos pilares
"especiais" (subtipos não-retangulares ou variantes de recorte/rotulagem).
**Ambos os grupos (U-shape e os 3 padrões novos) ficam PENDENTES** — apenas
registrados aqui com evidências cross-pavimento. Investigação/desenvolvimento
profundo só quando houver mais obras (mais amostras por padrão).

| Pavimento | Itens | PASS (golden) | FAIL (especiais) | Arete % |
|---|---|---|---|---|
| 1_PAV | 37 | 31 | 6 | 83.8% |
| 2_PAV | 35 | 30 | 5 | 85.7% |
| 12_PAV | 35 | 31 | 4 | 88.6% |
| 13_PAV | 35 | 32 | 3 | 91.4% |
| 14_PAV | 27 | 22 | 5 | 81.5% |
| TERREO | 22 | 12 | 10 | 54.5% |
| COBERTURA | 29 | 24 | 5 | 82.8% |
| **TOTAL** | **220** | **182** | **38** | **82.7%** |

---

## Caso 1 — P18: "pilar diagonal cambotado" (CAMBOTA / CORTE A-A)

**Exceção:** `EXC-PIL-P18-CAMBOTA` (`scripts/arete/arete_config.py`)

**Sintoma (G2 canônico, ABCD+CIMA FAIL em `textos`):**
- REF#ABCD tem blocos extras `CAMBOTA` + `CORTE A-A` (2 vistas trapezoidais,
  cotas 267.6 / 266.0 / 31.2) que substituem onde N4 desenharia `P18.A`/`P18.D`.
- REF#CIMA tem `ENCH.` (enchimento) + `P18.A` extras sem par em N4.

**Interpretação do usuário:** pilar com seção vertical NÃO retangular
(variação de ângulo) — possui recortes/cortes horizontais ("cambotas") em
certos painéis para compensar o formato diagonal. `CORTE A-A` é a vista de
corte que documenta essa geometria extra.

**Novas amostras (baseline 7 pisos):**

| Pavimento | Item | Sintoma |
|---|---|---|
| 13_PAV | P18 | `CAMBOTA`+`CORTE A-A`+`ENCH.` ausentes em N4; `P18.C` ausente, `P18.A` extra |
| 12_PAV | P18 | `P18.C`/`P18.E` ausentes; `P18.A`/`P18.B`/`P18.D` extras em N4 (sem CAMBOTA neste piso) |

**Estado:** P18 confirmado especial em 12_PAV e 13_PAV, mas com sintomas
DIFERENTES entre pisos (13_PAV tem CAMBOTA/CORTE A-A; 12_PAV tem só
trocas de letra de face A-E sem CAMBOTA). Ainda 1 elemento_id só — **aguardando
mais obras** para separar "cambota real" de "troca de rotulagem de face".

---

## Caso 2 — P26 + P27 + P15 + P23: Pilar em U (CONFIRMADO, 7 pavimentos)

**Exceção:** `EXC-PIL-U-SHAPE-EFGH` (status PENDENTE, `arete_config.py`)

**Confirmado pelo usuário:** P26 e P27 são pilares em U em TODOS os 7
pavimentos (recortes `_sel_*` refeitos item a item). Baseline 7 pisos mostra
que **P15 e P23 pertencem à mesma família** (mesmo padrão de rótulos `"N sar"`
ausentes em N4#ABCD).

**Duas variantes visuais do mesmo defeito** (a vista CIMA real, em U, é
projetada/decomposta dentro do bloco ABCD do recorte; o gerador atual só
desenha a seção retangular A-D):

- **Variante "N sar"** — REF#ABCD tem rótulos de contagem de sarrafo
  (`"2 sar"`, `"3 sar"`, `"4 sar"`, `"5 sar"`, `"8 sar"`) ausentes em N4.
- **Variante "letra solta A-E"** — REF#ABCD tem rótulos de face única
  (`"A"`,`"B"`,`"C"`,`"D"`,`"E"`) ausentes em N4 (5 faces em vez de 4 = pilar
  em U/L com face extra).

| Pavimento | P15 | P23 | P26 | P27 |
|---|---|---|---|---|
| 1_PAV | "8 sar"×2 | "8 sar"×2 | "2 sar","3 sar"×2,"5 sar"×2 | "A","B","C","D","E" |
| 2_PAV | "8 sar"×2 | "8 sar"×2 | "2 sar"×2,"5 sar"×3 | "2 sar"×4,"3 sar" |
| 12_PAV | — | — | "5 sar"×4,"A" | "3 sar"×2,"4 sar","5 sar"×2 |
| 13_PAV | — | — | "2 sar"×2,"5 sar"×3 | "2 sar"×4,"3 sar" |
| 14_PAV | — | — | "A","B","C","D","E" | "2 sar"×2,"3 sar","4 sar","5 sar" |
| TERREO | "4 sar"×2,"8 sar"×2 | "4 sar"×2,"8 sar"×2 | "2 sar"×3,"3 sar"×2 | "2 sar"×3,"3 sar","4 sar" |
| COBERTURA | — | — | "A","B","C","D","E" | "2 sar"×2,"2sar"×1,"3 sar"×2 (sic, sem espaço) |

P15/P23 só FAIL em 1_PAV, 2_PAV, TERREO (nos outros pisos passam — talvez
não existam ou tenham geometria simples nesses pisos).

**Estado:** 19 amostras (P26×7 + P27×6 + P15×3 + P23×3) = dataset de treino
da Fase C (extração por fórmula do U, popular `*_E`/`*_F`) e Fase D (modo
EFGH no gerador, portado de `grade_calculator.py`). **PENDENTE** — aguardando
mais obras antes de iniciar Fase C/D.

---

## Caso 3 — P28-32 (TERREO): possível "pilar de canto" (3 faces, NOVO)

**Exceção:** `EXC-PIL-CORNER-3FACE` (status PENDENTE, `arete_config.py`)

**Sintoma (G2 canônico, só TERREO até agora, 5 itens):** padrão INVERSO ao
Caso 2 — N4 gera um rótulo de face EXTRA que o REF não tem:

| Item | ABCD extra em N4 | CIMA extra em N4 |
|---|---|---|
| P28 | "P28.D" | "D" |
| P29 | "P29.D" | "D" |
| P30 | "P30.A" | "A" |
| P31 | "P31.A" | "A" |
| P32 | "P32.A" | "A" |

**Hipótese (não confirmada):** pilares de canto/extremidade com apenas 3
faces físicas (uma face encostada em parede/viga, sem painel visível) — REF
não desenha essa face, mas N4 sempre desenha as 4 faces padrão A-D. Faces
"D" (P28/P29) e "A" (P30/P31/P32) sugerem posição geométrica consistente
(cantos opostos do pavimento).

**Estado:** só 1 pavimento (TERREO) tem esses 5 itens em FAIL — **PENDENTE**,
aguardando mais obras/pisos para confirmar se é subtipo "pilar de canto" ou
peculiaridade do recorte TERREO.

---

## Caso 4 — P43/P47/P49/P51/P25: rótulo de face A/B em ABCD vs CIMA (NOVO)

**Exceção:** `EXC-PIL-LABEL-PLACEMENT-CIMA-ABCD` (status PENDENTE,
`arete_config.py`)

**Sintoma (G2 canônico, 14_PAV + COBERTURA, 6 ocorrências):** N4 desenha os
rótulos `"PXX.A"`/`"PXX.B"` na parte ABCD, mas o REF espera esses rótulos na
parte CIMA (e não tem o equivalente em ABCD):

| Pavimento | Item | ABCD extra em N4 | CIMA ausente em N4 |
|---|---|---|---|
| 14_PAV | P43 | "P43.A","P43.B" | "P43.A","P43.B" |
| 14_PAV | P47 | "P47.A","P47.B" | "P47.A","P47.B" |
| 14_PAV | P49 | "P49.A","P49.B" | "P49.A","P49.B" |
| COBERTURA | P49 | "P49.A" | "P49.A" |
| COBERTURA | P51 | "P51.A","P51.B" | "P51.A","P51.B" |
| COBERTURA | P25 | "P25.B" | (sem par ausente — só extra) |

**Hipótese (não confirmada):** parece um bug sistemático de *placement* no
gerador (rótulo vai para a parte errada), não um problema de subtipo —
poderia ser um "fix de causa única" de alto impacto (6 itens, 2 pisos). Mas
por decisão do usuário, fica **PENDENTE** até reunir evidência de mais
obras/pisos (verificar se o mesmo padrão aparece em 1_PAV-13_PAV também, onde
hoje passam — pode ser que esses pisos não tenham itens com sufixo A/B
isolado).

---

## Caso 5 — P24: "P24C" (REF) vs "P24.C" (N4) — convenção de nome de face (NOVO)

**Exceção:** `EXC-PIL-P24-NAMING-DOT` (status PENDENTE, `arete_config.py`)

**Sintoma (G2 canônico, 4 pavimentos: 1_PAV, 2_PAV, 12_PAV, TERREO — mesmo
item, mesmo bug em todos):**
- REF#ABCD tem texto `"P24C"` (sem separador).
- N4#ABCD gera `"P24.C"` (com ponto).

**Hipótese (não confirmada):** ou (a) bug de normalização no comparador
canônico (`forma_canonica_pil.py` deveria tratar `"P24C"` ≡ `"P24.C"`), ou
(b) o recorte de P24 usa genuinamente uma convenção de nome de face sem ponto
(possível erro de digitação no desenho original STOG, recorrente porque é
"copy-paste" do mesmo bloco entre pavimentos). **PENDENTE** — não passa em
13_PAV/14_PAV/COBERTURA (talvez P24 não exista nesses pisos ou já bata).

---

## Caso 6 — P2 (1_PAV): troca de letra de face A↔B (NOVO)

**Sintoma (G2 canônico, 1_PAV apenas):**
- REF#ABCD tem `"P2.B"` ausente em N4; N4#ABCD gera `"P2.A"` extra.

**Hipótese:** rotação/espelhamento da numeração de faces específica deste
item (vizinho de canto?). **PENDENTE** — 1 amostra só, aguardando mais obras.

---

## Resumo / próximos passos

| Caso | Itens (amostras) | Padrão | Status |
|------|-------------------|--------|--------|
| 1 — CAMBOTA | P18 (2: 12_PAV,13_PAV) | seção diagonal / troca de faces | PENDENTE, amostragem insuficiente |
| 2 — Pilar em U | P15,P23,P26,P27 (19 amostras, 7 pisos) | rótulos "N sar" ou "A-E" ausentes em N4#ABCD | PENDENTE — dataset pronto p/ Fase C/D quando retomado |
| 3 — Canto/3-face | P28-32 (5, TERREO) | rótulo extra "PXX.A/D" em N4 | PENDENTE, 1 piso só |
| 4 — Placement CIMA/ABCD | P43,P47,P49,P51,P25 (6, 14_PAV+COBERTURA) | rótulo "PXX.A/B" no bloco errado | PENDENTE, possível fix de causa única |
| 5 — Naming dot P24 | P24 (4 pisos) | "P24C" vs "P24.C" | PENDENTE, possível bug de normalização |
| 6 — Face swap P2 | P2 (1, 1_PAV) | "P2.A"↔"P2.B" trocados | PENDENTE, 1 amostra |

**Decisão (sessão 2026-06-13):** baseline canônico dos 7 pisos está
COMPLETO (182/220 = 82.7%, golden sealado para os 182 PASS). Todos os 6
casos acima ficam **registrados e pendentes** — Fase C/D (subtipo + EFGH) só
retoma quando houver evidência de mais obras (mais amostras por padrão).
Próximo passo geral do AR-1' (Fase E/F) segue conforme priorização futura do
usuário.
