# Relatório Arete — LAJ / 13_PAV
**Rodada:** 20260706_162747

## Resultado: 0P / 1F / 0B  |  Arete 0.0%

| Elemento | G0 | G1 | G2 | Final | Golden |
|----------|----|----|-----|-------|--------|
| L318 | PASS | FAIL | PASS | ✗ FAIL |  |

## FAILs — Causas e Próximas Ações

### L318
- **G1 FAIL** — 2 diffs no round-trip:
  - `linhas_horizontais[0].segments`: N2=None N2′=None [list_len]
  - `linhas_horizontais[1].segments`: N2=None N2′=None [list_len]

## Próxima ação
Atacar G1-FAIL em L318: campo `linhas_horizontais[0].segments` diverge N2=None vs N2′=None [list_len].

_Gerado em 20260706_162747 — Arete Quality Gates_