# Relatório Arete — LAJ / 13_PAV
**Rodada:** 20260707_015013

## Resultado: 0P / 1F / 0B  |  Arete 0.0%

| Elemento | G0 | G1 | G2 | Final | Golden |
|----------|----|----|-----|-------|--------|
| L319 | PASS | FAIL | PASS | ✗ FAIL |  |

## FAILs — Causas e Próximas Ações

### L319
- **G1 FAIL** — 4 diffs no round-trip:
  - `linhas_horizontais[0].value`: N2=179.0 N2′=122.0 [dim]
  - `linhas_horizontais[1].value`: N2=331.1 N2′=244.0 [dim]
  - `linhas_horizontais[2].value`: N2=423.0 N2′=366.0 [dim]

## Próxima ação
Atacar G1-FAIL em L319: campo `linhas_horizontais[0].value` diverge N2=179.0 vs N2′=122.0 [dim].

_Gerado em 20260707_015013 — Arete Quality Gates_