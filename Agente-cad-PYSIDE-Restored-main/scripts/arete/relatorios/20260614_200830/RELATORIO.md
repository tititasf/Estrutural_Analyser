# Relatório Arete — PIL / 13_PAV
**Rodada:** 20260614_200830

## Resultado: 32P / 3F / 0B  |  Arete 91.4%

| Elemento | G0 | G1 | G2 | Final | Golden |
|----------|----|----|-----|-------|--------|
| P1 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P10 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P11 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P12 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P13 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P14 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P15 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P16 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P17 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P18 | PASS | PASS | FAIL | ✗ FAIL |  |
| P19 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P2 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P20 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P21 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P22 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P23 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P24 | PASS | PASS | PASS | ✓ PASS | ✓ |
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

### P18
- **G2 FAIL** — ent=10 geom=2 txt=8
  - `ABCD` texto ausente em N4: "CAMBOTA"
  - `ABCD` texto ausente em N4: "CORTE A-A"
  - `ABCD` texto ausente em N4: "ENCH."
  - `ABCD` texto ausente em N4: "P18.C"
  - `ABCD` texto extra em N4: "P18.A"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/hachura`: ref=3 n4=0
  - `ABCD/painel`: ref=71 n4=21
  - `ABCD`: 94.9% divergência
  - `CIMA`: 85.2% divergência

### P26
- **G2 FAIL** — ent=10 geom=2 txt=31
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "5 sar"
  - `ABCD` texto ausente em N4: "5 sar"
  - `ABCD` texto ausente em N4: "5 sar"
  - `ABCD/chapa`: ref=2 n4=1
  - `ABCD/hachura`: ref=1113 n4=0
  - `ABCD/painel`: ref=104 n4=21
  - `ABCD`: 92.3% divergência
  - `CIMA`: 100.0% divergência

### P27
- **G2 FAIL** — ent=10 geom=2 txt=24
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "3 sar"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/hachura`: ref=8 n4=0
  - `ABCD/painel`: ref=198 n4=21
  - `ABCD`: 82.8% divergência
  - `CIMA`: 88.2% divergência

## Próxima ação
Atacar G2-FAIL em P18: texto ausente em N4 na parte `ABCD`: "CAMBOTA".

_Gerado em 20260614_200830 — Arete Quality Gates_