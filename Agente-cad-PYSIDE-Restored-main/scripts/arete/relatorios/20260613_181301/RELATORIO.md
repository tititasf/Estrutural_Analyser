# Relatório Arete — PIL / TERREO
**Rodada:** 20260613_181301

## Resultado: 12P / 10F / 0B  |  Arete 54.5%

| Elemento | G0 | G1 | G2 | Final | Golden |
|----------|----|----|-----|-------|--------|
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
| P20 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P21 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P23 | PASS | PASS | FAIL | ✗ FAIL |  |
| P24 | PASS | PASS | FAIL | ✗ FAIL |  |
| P26 | PASS | PASS | FAIL | ✗ FAIL |  |
| P27 | PASS | PASS | FAIL | ✗ FAIL |  |
| P28 | PASS | PASS | FAIL | ✗ FAIL |  |
| P29 | PASS | PASS | FAIL | ✗ FAIL |  |
| P30 | PASS | PASS | FAIL | ✗ FAIL |  |
| P31 | PASS | PASS | FAIL | ✗ FAIL |  |
| P32 | PASS | PASS | FAIL | ✗ FAIL |  |

## FAILs — Causas e Próximas Ações

### P15
- **G2 FAIL** — ent=9 geom=2 txt=4
  - `ABCD` texto ausente em N4: "4 sar"
  - `ABCD` texto ausente em N4: "4 sar"
  - `ABCD` texto ausente em N4: "8 sar"
  - `ABCD` texto ausente em N4: "8 sar"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/painel`: ref=35 n4=13
  - `ABCD/perfil`: ref=0 n4=1
  - `ABCD`: 81.8% divergência
  - `CIMA`: 57.1% divergência

### P23
- **G2 FAIL** — ent=9 geom=2 txt=4
  - `ABCD` texto ausente em N4: "4 sar"
  - `ABCD` texto ausente em N4: "4 sar"
  - `ABCD` texto ausente em N4: "8 sar"
  - `ABCD` texto ausente em N4: "8 sar"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/painel`: ref=37 n4=13
  - `ABCD/perfil`: ref=0 n4=1
  - `ABCD`: 80.0% divergência
  - `CIMA`: 100.0% divergência

### P24
- **G2 FAIL** — ent=9 geom=2 txt=2
  - `ABCD` texto ausente em N4: "P24C"
  - `ABCD` texto extra em N4: "P24.C"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/painel`: ref=47 n4=13
  - `ABCD/perfil`: ref=0 n4=1
  - `ABCD`: 83.3% divergência
  - `CIMA`: 62.5% divergência

### P26
- **G2 FAIL** — ent=8 geom=2 txt=21
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "3 sar"
  - `ABCD` texto ausente em N4: "3 sar"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/painel`: ref=64 n4=13
  - `ABCD/perfil`: ref=0 n4=1
  - `ABCD`: 78.2% divergência
  - `CIMA`: 91.8% divergência

### P27
- **G2 FAIL** — ent=8 geom=2 txt=22
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "2 sar"
  - `ABCD` texto ausente em N4: "3 sar"
  - `ABCD` texto ausente em N4: "4 sar"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/painel`: ref=70 n4=13
  - `ABCD/perfil`: ref=0 n4=1
  - `ABCD`: 82.8% divergência
  - `CIMA`: 92.0% divergência

### P28
- **G2 FAIL** — ent=9 geom=2 txt=2
  - `ABCD` texto extra em N4: "P28.D"
  - `CIMA` texto extra em N4: "D"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/painel`: ref=27 n4=13
  - `ABCD/perfil`: ref=0 n4=1
  - `ABCD`: 82.4% divergência
  - `CIMA`: 100.0% divergência

### P29
- **G2 FAIL** — ent=9 geom=2 txt=2
  - `ABCD` texto extra em N4: "P29.D"
  - `CIMA` texto extra em N4: "D"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/painel`: ref=28 n4=13
  - `ABCD/perfil`: ref=0 n4=1
  - `ABCD`: 82.4% divergência
  - `CIMA`: 85.7% divergência

### P30
- **G2 FAIL** — ent=8 geom=2 txt=2
  - `ABCD` texto extra em N4: "P30.A"
  - `CIMA` texto extra em N4: "A"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/painel`: ref=37 n4=13
  - `ABCD/perfil`: ref=0 n4=1
  - `ABCD`: 82.4% divergência
  - `CIMA`: 100.0% divergência

### P31
- **G2 FAIL** — ent=8 geom=2 txt=2
  - `ABCD` texto extra em N4: "P31.A"
  - `CIMA` texto extra em N4: "A"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/painel`: ref=45 n4=13
  - `ABCD/perfil`: ref=0 n4=1
  - `ABCD`: 84.2% divergência
  - `CIMA`: 100.0% divergência

### P32
- **G2 FAIL** — ent=8 geom=2 txt=2
  - `ABCD` texto extra em N4: "P32.A"
  - `CIMA` texto extra em N4: "A"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/painel`: ref=37 n4=13
  - `ABCD/perfil`: ref=0 n4=1
  - `ABCD`: 82.4% divergência
  - `CIMA`: 100.0% divergência

## Próxima ação
Atacar G2-FAIL em P15: texto ausente em N4 na parte `ABCD`: "4 sar".

_Gerado em 20260613_181301 — Arete Quality Gates_