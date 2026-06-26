# Relatório Arete — PIL / 13_PAV
**Rodada:** 20260624_033432

## Resultado: 0P / 3F / 0B  |  Arete 0.0%

| Elemento | G0 | G1 | G2 | Final | Golden |
|----------|----|----|-----|-------|--------|
| P1 | PASS | FAIL | PASS | ✗ FAIL |  |
| P2 | PASS | FAIL | PASS | ✗ FAIL |  |
| P3 | PASS | FAIL | PASS | ✗ FAIL |  |

## FAILs — Causas e Próximas Ações

### P1
- **G1 FAIL** — 2 diffs no round-trip:
  - `paineis_intervals_C`: N2=None N2′=None [list_len]
  - `larg_c_geom`: N2=19.0 N2′=479.0 [dim]

### P2
- **G1 FAIL** — 2 diffs no round-trip:
  - `paineis_intervals_C`: N2=None N2′=None [list_len]
  - `larg_c_geom`: N2=19.0 N2′=479.0 [dim]

### P3
- **G1 FAIL** — 2 diffs no round-trip:
  - `paineis_intervals_C`: N2=None N2′=None [list_len]
  - `larg_c_geom`: N2=19.0 N2′=479.0 [dim]

## Próxima ação
Atacar G1-FAIL em P1: campo `paineis_intervals_C` diverge N2=None vs N2′=None [list_len].

_Gerado em 20260624_033432 — Arete Quality Gates_