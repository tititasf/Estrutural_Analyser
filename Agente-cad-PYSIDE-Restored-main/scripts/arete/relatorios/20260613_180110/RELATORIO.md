# Relatório Arete — PIL / 2_PAV
**Rodada:** 20260613_180110

## Resultado: 30P / 5F / 0B  |  Arete 85.7%

| Elemento | G0 | G1 | G2 | Final | Golden |
|----------|----|----|-----|-------|--------|
| P1 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P10 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P11 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P12 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P13 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P14 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P15 | PASS | PASS | FAIL | ✗ FAIL |  |
| P16 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P17 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P18 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P19 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P2 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P20 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P21 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P22 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P23 | PASS | PASS | FAIL | ✗ FAIL |  |
| P24 | PASS | PASS | FAIL | ✗ FAIL |  |
| P25 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P26 | PASS | PASS | FAIL | ✗ FAIL |  |
| P27 | PASS | PASS | FAIL | ✗ FAIL |  |
| P28 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P29 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P3 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P30 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P31 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P32 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P33 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P34 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P35 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P4 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P5 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P6 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P7 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P8 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P9 | PASS | PASS | PASS | ✓ PASS | ✓ |

## FAILs — Causas e Próximas Ações

### P15
- **G2 FAIL** — ent=10 geom=2 txt=2
  - `ABCD` texto ausente em N4: "8 sar"
  - `ABCD` texto ausente em N4: "8 sar"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/hachura`: ref=4 n4=0
  - `ABCD/painel`: ref=22 n4=13
  - `ABCD`: 77.1% divergência
  - `CIMA`: 60.0% divergência

### P23
- **G2 FAIL** — ent=10 geom=2 txt=2
  - `ABCD` texto ausente em N4: "8 sar"
  - `ABCD` texto ausente em N4: "8 sar"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/hachura`: ref=4 n4=0
  - `ABCD/painel`: ref=24 n4=13
  - `ABCD`: 77.8% divergência
  - `CIMA`: 100.0% divergência

### P24
- **G2 FAIL** — ent=10 geom=2 txt=2
  - `ABCD` texto ausente em N4: "P24C"
  - `ABCD` texto extra em N4: "P24.C"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/hachura`: ref=4 n4=0
  - `ABCD/painel`: ref=26 n4=13
  - `ABCD`: 80.0% divergência
  - `CIMA`: 62.5% divergência

### P26
- **G2 FAIL** — ent=8 geom=2 txt=31
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "5 sar"
  - `ABCD` texto ausente em N4: "5 sar"
  - `ABCD` texto ausente em N4: "5 sar"
  - `ABCD/chapa`: ref=2 n4=1
  - `ABCD/hachura`: ref=1113 n4=0
  - `ABCD/painel`: ref=36 n4=13
  - `ABCD`: 90.2% divergência
  - `CIMA`: 71.4% divergência

### P27
- **G2 FAIL** — ent=9 geom=2 txt=24
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "3 sar"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/hachura`: ref=8 n4=0
  - `ABCD/painel`: ref=76 n4=13
  - `ABCD`: 84.4% divergência
  - `CIMA`: 92.0% divergência

## Próxima ação
Atacar G2-FAIL em P15: texto ausente em N4 na parte `ABCD`: "8 sar".

_Gerado em 20260613_180110 — Arete Quality Gates_