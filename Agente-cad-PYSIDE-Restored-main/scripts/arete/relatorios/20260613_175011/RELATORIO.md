# Relatório Arete — PIL / 1_PAV
**Rodada:** 20260613_175011

## Resultado: 31P / 6F / 0B  |  Arete 83.8%

| Elemento | G0 | G1 | G2 | Final | Golden |
|----------|----|----|-----|-------|--------|
| P1 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P101 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P102 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P103 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P11 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P12 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P13 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P15 | PASS | PASS | FAIL | ✗ FAIL |  |
| P16 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P17 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P18 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P19 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P2 | PASS | PASS | FAIL | ✗ FAIL |  |
| P20 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P21 | PASS | PASS | PASS | ✓ PASS | ✓ |
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
| P61 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P62 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P7 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P8 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P9 | PASS | PASS | PASS | ✓ PASS | ✓ |

## FAILs — Causas e Próximas Ações

### P15
- **G2 FAIL** — ent=10 geom=2 txt=2
  - `ABCD` texto ausente em N4: "8 sar"
  - `ABCD` texto ausente em N4: "8 sar"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/hachura`: ref=5 n4=0
  - `ABCD/painel`: ref=27 n4=13
  - `ABCD`: 80.5% divergência
  - `CIMA`: 57.1% divergência

### P2
- **G2 FAIL** — ent=9 geom=2 txt=2
  - `ABCD` texto ausente em N4: "P2.B"
  - `ABCD` texto extra em N4: "P2.A"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/painel`: ref=31 n4=13
  - `ABCD/perfil`: ref=0 n4=1
  - `ABCD`: 72.7% divergência
  - `CIMA`: 62.5% divergência

### P23
- **G2 FAIL** — ent=10 geom=2 txt=2
  - `ABCD` texto ausente em N4: "8 sar"
  - `ABCD` texto ausente em N4: "8 sar"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/hachura`: ref=5 n4=0
  - `ABCD/painel`: ref=27 n4=13
  - `ABCD`: 80.0% divergência
  - `CIMA`: 100.0% divergência

### P24
- **G2 FAIL** — ent=10 geom=2 txt=2
  - `ABCD` texto ausente em N4: "P24C"
  - `ABCD` texto extra em N4: "P24.C"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/hachura`: ref=4 n4=0
  - `ABCD/painel`: ref=30 n4=13
  - `ABCD`: 83.3% divergência
  - `CIMA`: 62.5% divergência

### P26
- **G2 FAIL** — ent=9 geom=2 txt=24
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "3 sar"
  - `ABCD` texto ausente em N4: "3 sar"
  - `ABCD` texto ausente em N4: "5 sar"
  - `ABCD` texto ausente em N4: "5 sar"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/hachura`: ref=6 n4=0
  - `ABCD/painel`: ref=85 n4=13
  - `ABCD`: 86.5% divergência
  - `CIMA`: 91.8% divergência

### P27
- **G2 FAIL** — ent=8 geom=2 txt=42
  - `ABCD` texto ausente em N4: "A"
  - `ABCD` texto ausente em N4: "B"
  - `ABCD` texto ausente em N4: "C"
  - `ABCD` texto ausente em N4: "D"
  - `ABCD` texto ausente em N4: "E"
  - `ABCD/chapa`: ref=2 n4=1
  - `ABCD/hachura`: ref=1113 n4=0
  - `ABCD/painel`: ref=0 n4=13
  - `ABCD`: 100.0% divergência
  - `CIMA`: 86.5% divergência

## Próxima ação
Atacar G2-FAIL em P15: texto ausente em N4 na parte `ABCD`: "8 sar".

_Gerado em 20260613_175011 — Arete Quality Gates_