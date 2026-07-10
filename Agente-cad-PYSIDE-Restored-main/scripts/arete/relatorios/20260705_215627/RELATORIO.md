# Relatório Arete — PIL / TERREO
**Rodada:** 20260705_215627

## Resultado: 18P / 5F / 0B  |  Arete 78.3%

| Elemento | G0 | G1 | G2 | Final | Golden |
|----------|----|----|-----|-------|--------|
| GRADES | FAIL | — | — | ✗ FAIL |  |
| P101 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P102 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P103 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P11 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P12 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P13 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P15 | PASS | FAIL | PASS | ✗ FAIL |  |
| P16 | PASS | FAIL | PASS | ✗ FAIL |  |
| P17 | PASS | FAIL | PASS | ✗ FAIL |  |
| P18 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P19 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P20 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P21 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P23 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P24 | PASS | PASS | FAIL | ✗ FAIL |  |
| P26 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P27 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P28 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P29 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P30 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P31 | PASS | PASS | PASS | ✓ PASS | ✓ |
| P32 | PASS | PASS | PASS | ✓ PASS | ✓ |

## FAILs — Causas e Próximas Ações

### GRADES

### P15
- **G1 FAIL** — 1 diffs no round-trip:
  - `paineis_intervals_D`: N2=None N2′=None [list_len]

### P16
- **G1 FAIL** — 1 diffs no round-trip:
  - `paineis_intervals_D`: N2=None N2′=None [list_len]

### P17
- **G1 FAIL** — 1 diffs no round-trip:
  - `paineis_intervals_D`: N2=None N2′=None [list_len]

### P24
- **G2 FAIL** — ent=6 geom=2 txt=1
  - `ABCD` texto ausente em N4: "P24C"
  - `ABCD/chapa`: ref=0 n4=1
  - `ABCD/painel`: ref=47 n4=27
  - `ABCD/perfil`: ref=0 n4=1
  - `ABCD`: 52.9% divergência
  - `CIMA`: 72.7% divergência

## Próxima ação
Investigar GRADES: verificar visualmente o PNG.

_Gerado em 20260705_215627 — Arete Quality Gates_