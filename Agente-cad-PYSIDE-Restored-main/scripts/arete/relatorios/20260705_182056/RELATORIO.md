# Relatório Arete — LAJ / 13_PAV
**Rodada:** 20260705_182056

## Resultado: 2P / 1F / 0B  |  Arete 66.7%

| Elemento | G0 | G1 | G2 | Final | Golden |
|----------|----|----|-----|-------|--------|
| L309 | PASS | PASS | PASS | ✓ PASS | ✓ |
| L318 | PASS | FAIL | PASS | ✗ FAIL |  |
| L326 | PASS | PASS | PASS | ✓ PASS | ✓ |

## FAILs — Causas e Próximas Ações

### L318
- **G1 FAIL** — 2 diffs no round-trip:
  - `linhas_verticais`: N2=None N2′=None [list_len]
  - `apoios_hachurados`: N2=None N2′=None [list_len]

## Próxima ação
Atacar G1-FAIL em L318: campo `linhas_verticais` diverge N2=None vs N2′=None [list_len].

_Gerado em 20260705_182056 — Arete Quality Gates_