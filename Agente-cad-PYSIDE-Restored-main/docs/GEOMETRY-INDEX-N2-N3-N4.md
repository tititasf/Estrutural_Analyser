# GeometryIndex — camada estruturada N2 · N3 · N4

**Status:** implementado (2026-07-19) · protótipo LV multi-unidade  
**Não é RAG.** Retrieval exato + set-diff. PNG fora deste módulo.

## Módulos

| Ficheiro | Papel |
|----------|--------|
| `scripts/arete/geometry_index.py` | `GeometryIndex.from_dxf`, `query`, `diff` |
| `scripts/arete/geometry_lv_units.py` | âncora multi-unidade + pareamento N2↔N4 |
| `scripts/arete/run_geometry_gate_lv.py` | CLI gate LV |
| `scripts/arete/inventario_geometria_fidelidade.py` | extract_ledger (motor de parse) |

## Uso

```bash
python scripts/arete/run_geometry_gate_lv.py V301
python scripts/arete/run_geometry_gate_lv.py V301 --no-regen
```

Saídas: `scripts/arete/relatorios/g2v/v301_geometry_gate/`

## API mental

```text
idx_n2 = GeometryIndex.from_dxf(n2, origin, h, w, widths, clip, ...)
idx_n4 = GeometryIndex.from_dxf(n4, ...)
report = GeometryIndex.diff(idx_n2, idx_n4)  # PASS|FAIL|SUSPEITO
idx.query(family="Painéis", orient="V", bbox=(...))
```

## Vereditos

- **PASS E2E** — R≥80%, G≥50%, sem cotas inventadas  
- **FAIL E2E** — inventadas claras ou EXTRA estrutural excessivo  
- **SUSPEITO** — residual / ledger fraco / sem âncora (ex. CORTE)

## Ligação Arete

Esta camada é a fonte primária do gate de **desenho** (G2/G5 estruturado).  
G2-V visual (PNG) continua como evidência secundária.
