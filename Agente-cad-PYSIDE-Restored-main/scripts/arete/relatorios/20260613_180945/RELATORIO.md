# Relatório Arete — PIL / 14_PAV
**Rodada:** 20260613_180945

## Resultado: 22P / 5F / 0B  |  Arete 81.5%

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
| P25 | PASS | PASS | PASS | ✓ PASS | ✓ |
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
| P43 | PASS | PASS | FAIL | ✗ FAIL |  |
| P47 | PASS | PASS | FAIL | ✗ FAIL |  |
| P49 | PASS | PASS | FAIL | ✗ FAIL |  |

## FAILs — Causas e Próximas Ações

### P26
- **G2 FAIL** — ent=8 geom=2 txt=40
  - `ABCD` texto ausente em N4: "A"
  - `ABCD` texto ausente em N4: "B"
  - `ABCD` texto ausente em N4: "C"
  - `ABCD` texto ausente em N4: "D"
  - `ABCD` texto ausente em N4: "E"
  - `ABCD/chapa`: ref=2 n4=1
  - `ABCD/hachura`: ref=1113 n4=0
  - `ABCD/painel`: ref=0 n4=13
  - `ABCD`: 100.0% divergência
  - `CIMA`: 83.0% divergência

### P27
- **G2 FAIL** — ent=8 geom=2 txt=32
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "3 sar"
  - `ABCD` texto ausente em N4: "4 sar"
  - `ABCD` texto ausente em N4: "5 sar"
  - `ABCD/chapa`: ref=2 n4=1
  - `ABCD/hachura`: ref=1113 n4=0
  - `ABCD/painel`: ref=75 n4=13
  - `ABCD`: 88.2% divergência
  - `CIMA`: 73.9% divergência

### P43
- **G2 FAIL** — ent=9 geom=2 txt=4
  - `ABCD` texto extra em N4: "P43.A"
  - `ABCD` texto extra em N4: "P43.B"
  - `CIMA` texto ausente em N4: "P43.A"
  - `CIMA` texto ausente em N4: "P43.B"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/painel`: ref=22 n4=13
  - `ABCD/perfil`: ref=0 n4=1
  - `ABCD`: 81.0% divergência
  - `CIMA`: 64.7% divergência

### P47
- **G2 FAIL** — ent=9 geom=2 txt=4
  - `ABCD` texto extra em N4: "P47.A"
  - `ABCD` texto extra em N4: "P47.B"
  - `CIMA` texto ausente em N4: "P47.A"
  - `CIMA` texto ausente em N4: "P47.B"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/painel`: ref=22 n4=13
  - `ABCD/perfil`: ref=0 n4=1
  - `ABCD`: 81.0% divergência
  - `CIMA`: 64.7% divergência

### P49
- **G2 FAIL** — ent=9 geom=2 txt=4
  - `ABCD` texto extra em N4: "P49.A"
  - `ABCD` texto extra em N4: "P49.B"
  - `CIMA` texto ausente em N4: "P49.A"
  - `CIMA` texto ausente em N4: "P49.B"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/painel`: ref=10 n4=13
  - `ABCD/perfil`: ref=0 n4=1
  - `ABCD`: 81.0% divergência
  - `CIMA`: 62.5% divergência

## Próxima ação
Atacar G2-FAIL em P26: texto ausente em N4 na parte `ABCD`: "A".

_Gerado em 20260613_180945 — Arete Quality Gates_