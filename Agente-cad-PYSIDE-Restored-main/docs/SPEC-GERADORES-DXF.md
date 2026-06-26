# Especificação Completa dos Geradores DXF — STOG Quality

**Versão:** 1.0 — 2026-05-23
**Meta:** 100% de cada elemento validado via DXF + imagem + prompt NIM
**Referência:** Engenharia reversa dos SCRs + audit de fidelidade (52 pavimentos)

---

## Scores atuais por gerador (baseline 2026-05-23)

| Gerador | Score médio | Certificados (≥meta) | Meta |
|---------|------------|----------------------|------|
| LJ — Lajes | 88.0% | 73% | 75% |
| PL — Pilares | 76.6% | 36% | 85% |
| LV — Laterais de Vigas | 69.6% | 44% | 85% |
| FV — Fundos de Vigas | 56.8% | 0% | 80% |

---

## PL — Pilares

### Vista CIMA
| # | Elemento | Layer | Tipo DXF | Validação |
|---|----------|-------|----------|-----------|
| PL-C01 | Retângulo do concreto (corpo) | `hachura-chapa` | LWPOLYLINE | count≥1, fechado |
| PL-C02 | Chapas metálicas nas 4 bordas | `hachura-chapa` | LWPOLYLINE | count≥4 |
| PL-C03 | Sarrafos (PLINEs horizontais e verticais) | `SARRAFO` | LWPOLYLINE | count≥6 |
| PL-C04 | Gravatas (reforços transversais) | `GRAVATA` | LWPOLYLINE | count≥2 |
| PL-C05 | Hachura concreto (interior) | `Hachura` | HATCH solid | count≥1 |
| PL-C06 | Blocos B1A.E e B1A.D (conexões laterais) | variados | INSERT | count≥2 (se dim>25cm) |
| PL-C07 | Blocos B1B.E e B1B.D | variados | INSERT | count≥2 (se dim>25cm) |
| PL-C08 | Blocos B2A.E | variados | INSERT | count≥1 (condicional) |
| PL-C09 | Blocos PAR.CIM / PAR.BAI / PAR.ESQ / PAR.DIR (parafusos) | variados | INSERT | count≥4 |
| PL-C10 | Bloco BCGV (gravata extra — pilar ≥90cm) | variados | INSERT | count≥1 se b ou h ≥90 |
| PL-C11 | Cotas DIMLINEAR (mínimo: largura + altura) | `COTA` | DIMENSION | count≥2, dimstyle=cotax2 |
| PL-C12 | Texto nomenclatura (nome do pilar) | `NOMENCLATURA` | TEXT | count≥1 |
| PL-C13 | Escala 2× aplicada ao final | — | _SCALE | verificar bbox≈2× original |

### Vista ABCD (4 faces lado a lado)
| # | Elemento | Layer | Tipo DXF | Validação |
|---|----------|-------|----------|-----------|
| PL-A01 | Moldura exterior (bloco MULDURA) | `Paineis` | INSERT | count=1 |
| PL-A02 | Painéis Face A (retângulos) | `Paineis` | LWPOLYLINE | count≥1 |
| PL-A03 | Painéis Face B | `Paineis` | LWPOLYLINE | count≥1 |
| PL-A04 | Painéis Face C | `Paineis` | LWPOLYLINE | count≥1 |
| PL-A05 | Painéis Face D | `Paineis` | LWPOLYLINE | count≥1 |
| PL-A06 | Sarrafos verticais DASHED (abaixo do concreto) | `SARR_2.2x7` | LWPOLYLINE | linetype=DASHED, count≥2 |
| PL-A07 | Sarrafos verticais CONTINUOUS (acima do concreto) | `SARR_2.2x7` | LWPOLYLINE | linetype=CONTINUOUS, count≥2 |
| PL-A08 | Sarrafos horizontais com anotação ("N sarr.") | `SARR_2.2x7` | LWPOLYLINE+TEXT | count≥2 |
| PL-A09 | Furação: 5 blocos `furacao` por face | `Paineis` | INSERT | count=20 total (4 faces × 5) |
| PL-A10 | SLIPTEE (2 blocos) | `Paineis` | INSERT | count=2 |
| PL-A11 | SLIPTDD (2 blocos) | `Paineis` | INSERT | count=2 |
| PL-A12 | Cotas individuais por face (PAINEL-NOVA) | `cota` | DIMENSION | count≥8 (2/face × 4) |
| PL-A13 | Nomenclatura por face | `nomenclatura` | TEXT | count≥4 |

### Vista GRADES
| # | Elemento | Layer | Tipo DXF | Validação |
|---|----------|-------|----------|-----------|
| PL-G01 | Grade1 — 14 retângulos × 4 LINEs (não PLINE!) | `SARR_2.2x7` | LINE | count=56 LINEs |
| PL-G02 | Grade2 — igual à Grade1, gap=22cm | `SARR_2.2x7` | LINE | count=56 LINEs |
| PL-G03 | Sarrafos verticais SARR_2.2x7 | `SARR_2.2x7` | LINE | count≥14 |
| PL-G04 | Sarrafos verticais SARR_3.5x7 | `SARR_3.5x7` | LINE | count≥14 |
| PL-G05 | Sarrafos horizontais SARR_2.2x10 × 4 posições | `SARR_2.2x10` | LINE | count≥8 (2 grades × 4) |
| PL-G06 | Blocos GRA-E (2) e GRA-D (2) | — | INSERT | count=4 |
| PL-G07 | Cotas (PAINEL-NOVA) | `COTA` | DIMENSION | count≥4 |
| PL-G08 | Nomenclatura | `NOMENCLATURA` | TEXT | count≥1 |

---

## LV — Laterais de Vigas

### Face A / Face B (por face, geradas separadamente)
| # | Elemento | Layer | Tipo DXF | Validação |
|---|----------|-------|----------|-----------|
| LV-F01 | Moldura/contorno do painel | `Paineis` | LWPOLYLINE | count≥1, fechado |
| LV-F02 | Sarrafos horizontais — 2× se h<30cm | `SARR_2.2x7` | LWPOLYLINE | count≥2 |
| LV-F03 | Sarrafos horizontais — 4× se 30≤h<80cm | `SARR_2.2x7` | LWPOLYLINE | count=4 |
| LV-F04 | Sarrafos horizontais — 8× se h≥80cm | `SARR_2.2x7` | LWPOLYLINE | count=8 |
| LV-F05 | Sarrafos SARR_2.2x5 (para h<15cm) | `SARR_2.2x5` | LWPOLYLINE | count=2 se h<15 |
| LV-F06 | Sarrafos verticais SARR_3.5x7 (modo grade) | `SARR_3.5x7` | LWPOLYLINE | count≥1 se grade mode |
| LV-F07 | Hachura laje superior (HHHH) | `Hachura` | HATCH | count≥1 se há laje sup |
| LV-F08 | Hachura laje inferior (HHHH) | `Hachura` | HATCH | count≥1 se há laje inf |
| LV-F09 | Painéis múltiplos (se viga >244cm) | `Paineis` | LWPOLYLINE | count = ceil(comp/244) |
| LV-F10 | Abertura esquerda topo (ABVET) | `Paineis` | LWPOLYLINE | count≥1 se pilar esq |
| LV-F11 | Abertura esquerda fundo (ABVEF) | `Paineis` | LWPOLYLINE | count≥1 se pilar esq |
| LV-F12 | Abertura direita topo (ABVDT) | `Paineis` | LWPOLYLINE | count≥1 se pilar dir |
| LV-F13 | Abertura direita fundo (ABVDF) | `Paineis` | LWPOLYLINE | count≥1 se pilar dir |
| LV-F14 | Hachura reaproveitamento (ANSI31) | `REAPROVEITAMENTO` | HATCH | count≥1 se painel reusado |
| LV-F15 | Obstáculo (retângulo 30cm + hachura) | `Paineis` | LWPOLYLINE | count≥1 se modo obstáculo |
| LV-F16 | Cotas horizontais (comprimento por painel) | `COTA` | DIMENSION | count≥1/painel |
| LV-F17 | Nomenclatura (V{n} + b×h) | `NOMENCLATURA` | TEXT | count≥1 |

### Visão de Corte (VC) — por par Face A+B
| # | Elemento | Layer | Tipo DXF | Validação |
|---|----------|-------|----------|-----------|
| LV-V01 | Retângulo painel Face A (4cm × h) | `Painéis` | LWPOLYLINE | count=1 |
| LV-V02 | Retângulo painel Face B | `Painéis` | LWPOLYLINE | count=1 |
| LV-V03 | Sarrafos MLINE (estilo SAR3, escala 4.4) | `SARRAFO_2_2X7` | MLINE | count≥1 |
| LV-V04 | Barras de ancoragem entre faces A e B | `BARRA_ANCORAGEM` | LWPOLYLINE | count≥2 |
| LV-V05 | Hachura concreto entre faces (HACHURACONCRETO) | `HACHURACONCRETO` | HATCH | count=1 |
| LV-V06 | Bloco PAR_ESQ | — | INSERT | count=1 |
| LV-V07 | Bloco PAR_FUNDO_ESQ | — | INSERT | count=1 |
| LV-V08 | Bloco PAR_FUNDO_DIR | — | INSERT | count=1 |
| LV-V09 | Bloco par_int_esq | — | INSERT | count=1 |
| LV-V10 | Bloco par_int_dir | — | INSERT | count=1 |
| LV-V11 | Cotas verticais (altura da viga) | `COTA` | DIMENSION | count≥1 |
| LV-V12 | Texto pontalete | `ESTRUTURACAO` | TEXT | count≥1 |
| LV-V13 | Texto nome viga + "(b×h)" | — | TEXT | count≥1 |

---

## FV — Fundos de Vigas

### Por viga (repetido para cada viga no pavimento)
| # | Elemento | Layer | Tipo DXF | Validação |
|---|----------|-------|----------|-----------|
| FV-01 | Nomenclatura — nome da viga (ex: "V207") | `NOMENCLATURA` | TEXT | count=1 por viga |
| FV-02 | Label "ESQ" (rotação 90°) | `5` | TEXT | count=1 |
| FV-03 | Label "DIR" (rotação 90°) | `5` | TEXT | count=1 |
| FV-04 | Retângulo topo de cada painel | `Painéis` | LWPOLYLINE | count=N_painéis |
| FV-05 | Retângulo base de cada painel | `Painéis` | LWPOLYLINE | count=N_painéis |
| FV-06 | Divisores verticais entre painéis adjacentes | `Painéis` | LINE | count=N_painéis-1 |
| FV-07 | Sarrafos horizontais por painel (quebram nas divisões) | `SARR_2.2x7` | LWPOLYLINE | count proporcional |
| FV-08 | Sarrafos verticais nas bordas ESQ e DIR (recuo 7cm) | `SARR_2.2x7` | LWPOLYLINE | count=2 |
| FV-09 | Sarrafos de edição (ex2 extend — borda dos painéis ext.) | `SARR_EDITAR` | LWPOLYLINE | count≥2 |
| FV-10 | Chanfros nos cantos dos painéis (biseau de encaixe) | `Painéis` | LWPOLYLINE | count≥4/viga |
| FV-11 | Reaproveitamento (hachura ANSI31) | `REAPROVEITAMENTO` | HATCH | count≥1 se painel reusado |
| FV-12 | Bloco nf1–nf10 no centro de cada painel | `COTA` | INSERT | count=N_painéis |
| FV-13 | Cota individual por painel (horizontal) | `COTA` | DIMENSION | count=N_painéis |
| FV-14 | Cota total da viga | `COTA` | DIMENSION | count=1 |
| FV-15 | Cota altura da viga (vertical) | `COTA` | DIMENSION | count=1 |

---

## LJ — Lajes

### Por laje — modo planta
| # | Elemento | Layer | Tipo DXF | Validação |
|---|----------|-------|----------|-----------|
| LJ-01 | Contorno exterior da laje | `Painéis` | LWPOLYLINE | count≥1, fechado |
| LJ-02 | Divisões de painel verticais (pares paralelos, gap=19cm) | `3` | LINE pair | count=2 × N_div_v |
| LJ-03 | Divisões de painel horizontais (pares paralelos, gap=19cm) | `3` | LINE pair | count=2 × N_div_h |
| LJ-04 | Hachura SOLID (área interna da laje) | `Hachura` | HATCH solid | count≥1 |
| LJ-05 | Retângulos de pilar interno | `7` | LWPOLYLINE 5pts | count=N_pilares |
| LJ-06 | Labels V{n} ou L{n} (tipo+número) | `4` | TEXT h=15 | count≥1 |
| LJ-07 | Escoras (linhas de suporte) | `9` | LINE | count≥1 se há escoras |
| LJ-08 | Marcadores X de reaproveitamento | `1` | LINE (X mark) | count≥1 se painel reusado |
| LJ-09 | Hachura ANSI31 reaproveitamento | `REAPROVEITAMENTO` | HATCH | count≥1 se painel reusado |
| LJ-10 | Cotas (COTA PAINEL-50) | `Painéis` | DIMENSION | count≥2 |
| LJ-11 | MTEXT dados do painel | `AUX00` | MTEXT | count≥1 |
| LJ-12 | Borda card / carimbo (modo cards) | `Folhas`/`CARIMBO` | LWPOLYLINE/TEXT | count≥1 em cards mode |

### Laje vertical / escada (LE1) — elementos extras
| # | Elemento | Layer | Tipo DXF | Validação |
|---|----------|-------|----------|-----------|
| LJ-E01 | PLINEs adicionais (2V + 2H formando retângulo interno) | `Painéis` | LWPOLYLINE | count≥4 extra |
| LJ-E02 | Segunda hachura HLAZ (1 por célula, 2 total em LE1) | `Hachura` | HATCH | count=2 |

---

## Critérios de Aprovação por Gerador

| Gerador | Score mínimo para certificação |
|---------|-------------------------------|
| PL | ≥ 90% dos elementos PL-C, PL-A, PL-G presentes |
| LV | ≥ 90% dos elementos LV-F e LV-V presentes |
| FV | ≥ 90% dos elementos FV-01 a FV-15 presentes |
| LJ | ≥ 90% dos elementos LJ-01 a LJ-12 presentes |

**Meta global:** score_fidelidade ≥ 85% em todos os geradores para cada pavimento.
