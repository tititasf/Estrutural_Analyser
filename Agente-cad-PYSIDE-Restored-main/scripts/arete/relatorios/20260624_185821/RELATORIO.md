# Relatório Arete — LV / 13_PAV
**Rodada:** 20260624_185821

## Resultado: 31P / 1F / 0B  |  Arete 96.9%

| Elemento | G0 | G1 | G2 | Final | Golden |
|----------|----|----|-----|-------|--------|
| V13 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V301 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V302 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V303 | PASS | FAIL | PASS | ✗ FAIL |  |
| V304 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V305 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V306 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V308 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V310 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V311 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V312 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V314 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V315 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V316 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V317 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V318 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V319 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V320 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V321 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V322 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V323 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V324 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V325 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V326 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V327 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V328 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V329 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V330 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V331 | PASS | PASS | PASS | ✓ PASS | ✓ |
| V332 | PASS | PASS | PASS | ✓ PASS | ✓ |
| VF203 | PASS | PASS | PASS | ✓ PASS | ✓ |
| VF301 | PASS | PASS | PASS | ✓ PASS | ✓ |

## FAILs — Causas e Próximas Ações

### V303
- **G1 FAIL** — 3 diffs no round-trip:
  - `total_height`: N2=43.0 N2′=44.0 [dim]
  - `h_A`: N2=43.0 N2′=44.0 [dim]
  - `h_B`: N2=44.0 N2′=43.0 [dim]

## Próxima ação
Atacar G1-FAIL em V303: campo `total_height` diverge N2=43.0 vs N2′=44.0 [dim].

_Gerado em 20260624_185821 — Arete Quality Gates_