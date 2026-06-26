# Relatório Arete — PIL / COBERTURA
**Rodada:** 20260613_181539

## Resultado: 24P / 5F / 0B  |  Arete 82.8%

| Elemento | G0 | G1 | G2 | Final | Golden |
|----------|----|----|-----|-------|--------|
| P10 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P11 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P12 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P14 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P16 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P17 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P18 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P19 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P20 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P21 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P22 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P23 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P24 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P25 | PASS | PASS | FAIL | ✗ FAIL |  |
| P26 | PASS | PASS | FAIL | ✗ FAIL |  |
| P27 | PASS | PASS | FAIL | ✗ FAIL |  |
| P28 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P29 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P30 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P31 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P32 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P33 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P34 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P35 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P43 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P46 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P47 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P49 | PASS | PASS | FAIL | ✗ FAIL |  |
| P51 | PASS | PASS | FAIL | ✗ FAIL |  |

## FAILs — Causas e Próximas Ações

### P25
- **G2 FAIL** — ent=10 geom=2 txt=1
  - `ABCD` texto extra em N4: "P25.B"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/hachura`: ref=3 n4=0
  - `ABCD/painel`: ref=15 n4=13
  - `ABCD`: 80.0% divergência
  - `CIMA`: 60.0% divergência

### P26
- **G2 FAIL** — ent=8 geom=2 txt=45
  - `ABCD` texto ausente em N4: "A"
  - `ABCD` texto ausente em N4: "B"
  - `ABCD` texto ausente em N4: "C"
  - `ABCD` texto ausente em N4: "D"
  - `ABCD` texto ausente em N4: "E"
  - `ABCD/chapa`: ref=2 n4=1
  - `ABCD/hachura`: ref=1113 n4=0
  - `ABCD/painel`: ref=0 n4=13
  - `ABCD`: 100.0% divergência
  - `CIMA`: 85.5% divergência

### P27
- **G2 FAIL** — ent=8 geom=2 txt=35
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "2sar"
  - `ABCD` texto ausente em N4: "3 sar"
  - `ABCD` texto ausente em N4: "3sar"
  - `ABCD` texto ausente em N4: "3sar"
  - `ABCD/chapa`: ref=2 n4=1
  - `ABCD/hachura`: ref=1113 n4=0
  - `ABCD/painel`: ref=80 n4=13
  - `ABCD`: 88.9% divergência
  - `CIMA`: 75.0% divergência

### P49
- **G2 FAIL** — ent=10 geom=2 txt=2
  - `ABCD` texto extra em N4: "P49.A"
  - `CIMA` texto ausente em N4: "P49.A"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/hachura`: ref=3 n4=0
  - `ABCD/painel`: ref=39 n4=13
  - `ABCD`: 80.6% divergência
  - `CIMA`: 50.0% divergência

### P51
- **G2 FAIL** — ent=10 geom=2 txt=4
  - `ABCD` texto extra em N4: "P51.A"
  - `ABCD` texto extra em N4: "P51.B"
  - `CIMA` texto ausente em N4: "P51.A"
  - `CIMA` texto ausente em N4: "P51.B"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/hachura`: ref=2 n4=0
  - `ABCD/painel`: ref=29 n4=13
  - `ABCD`: 83.3% divergência
  - `CIMA`: 64.7% divergência

## Próxima ação
Atacar G2-FAIL em P25: texto extra em N4 na parte `ABCD`: "P25.B".

_Gerado em 20260613_181539 — Arete Quality Gates_