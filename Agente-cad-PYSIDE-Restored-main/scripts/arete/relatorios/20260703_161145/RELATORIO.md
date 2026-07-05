# Relatório Arete — LV / 13_PAV
**Rodada:** 20260703_161145

## Resultado: 21P / 11F / 0B  |  Arete 65.6%

| Elemento | G0 | G1 | G2 | Final | Golden |
|----------|----|----|-----|-------|--------|
| V13 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V301 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V302 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V303 | PASS | FAIL | PASS | ✗ FAIL |  |
| V304 | PASS | FAIL | PASS | ✗ FAIL |  |
| V305 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V306 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V308 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V310 | PASS | FAIL | PASS | ✗ FAIL |  |
| V311 | PASS | FAIL | PASS | ✗ FAIL |  |
| V312 | PASS | FAIL | PASS | ✗ FAIL |  |
| V314 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V315 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V316 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V317 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V318 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V319 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V320 | PASS | FAIL | PASS | ✗ FAIL |  |
| V321 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V322 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V323 | PASS | FAIL | PASS | ✗ FAIL |  |
| V324 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V325 | PASS | FAIL | PASS | ✗ FAIL |  |
| V326 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V327 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V328 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V329 | PASS | FAIL | PASS | ✗ FAIL |  |
| V330 | PASS | FAIL | PASS | ✗ FAIL |  |
| V331 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V332 | PASS | FAIL | PASS | ✗ FAIL |  |
| VF203 | PASS | PASS | PASS | ✓ PASS | ✓ |
| VF301 | PASS | PASS | PASS | ✓ PASS | ✓ |

## FAILs — Causas e Próximas Ações

### V303
- **G1 FAIL** — 1 diffs no round-trip:
  - `h_B`: N2=44.0 N2′=43.0 [dim]

### V304
- **G1 FAIL** — 3 diffs no round-trip:
  - `total_height`: N2=168.0 N2′=0.0 [dim]
  - `h_A`: N2=168.0 N2′=0.0 [dim]
  - `h_B`: N2=168.0 N2′=0.0 [dim]

### V310
- **G1 FAIL** — 3 diffs no round-trip:
  - `total_height`: N2=38.0 N2′=40.0 [dim]
  - `h_A`: N2=38.0 N2′=40.0 [dim]
  - `h_B`: N2=40.0 N2′=38.0 [dim]

### V311
- **G1 FAIL** — 1 diffs no round-trip:
  - `h_B`: N2=44.0 N2′=43.0 [dim]

### V312
- **G1 FAIL** — 1 diffs no round-trip:
  - `h_B`: N2=109.0 N2′=103.0 [dim]

### V320
- **G1 FAIL** — 1 diffs no round-trip:
  - `h_B`: N2=110.0 N2′=103.0 [dim]

### V323
- **G1 FAIL** — 3 diffs no round-trip:
  - `total_height`: N2=40.0 N2′=54.0 [dim]
  - `h_A`: N2=40.0 N2′=54.0 [dim]
  - `h_B`: N2=54.0 N2′=40.0 [dim]

### V325
- **G1 FAIL** — 1 diffs no round-trip:
  - `h_B`: N2=109.0 N2′=103.0 [dim]

### V329
- **G1 FAIL** — 3 diffs no round-trip:
  - `total_height`: N2=50.0 N2′=64.0 [dim]
  - `h_A`: N2=50.0 N2′=64.0 [dim]
  - `h_B`: N2=64.0 N2′=50.0 [dim]

### V330
- **G1 FAIL** — 1 diffs no round-trip:
  - `h_B`: N2=107.0 N2′=58.0 [dim]

### V332
- **G1 FAIL** — 3 diffs no round-trip:
  - `total_height`: N2=44.0 N2′=59.0 [dim]
  - `h_A`: N2=44.0 N2′=59.0 [dim]
  - `h_B`: N2=59.0 N2′=44.0 [dim]

## Próxima ação
Atacar G1-FAIL em V303: campo `h_B` diverge N2=44.0 vs N2′=43.0 [dim].

_Gerado em 20260703_161145 — Arete Quality Gates_