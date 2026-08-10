# Backlog de adaptadores FV / LV

**Estado (2026-07-16):** adaptadores **implementados** e `validation_ready`
com limites. Ver `scripts/arete/qa_fv_lv_adapters.py` e `authority_matrix.json`.

## Estado atual

| Classe | Modo | Review | Apply |
|---|---|---|---|
| FV | `validation_ready` | `FvEvidenceAuditor` (segmentos/área/dim/apoios) | `apply` explícito nos campos provados |
| LV | `validation_ready` | `LvEvidenceAuditor` (4 contratos + dims) | `apply` explícito nos campos/contratos provados |

## Já entregue (1.6.0)

1. FV `cortes` / `aberturas` nomeadas.
2. LV aberturas `viga_*_abert_pilar_*` (dist/larg + entidade).
3. Golden multi-item `qa_fv_lv_golden_regression.py` (13_PAV baseline).
4. Apply/snapshot beams sem `extra_data_json`.

## Próximos incrementos

1. Geometria própria de furo/recorte (não só nome/pos) e aberturas sem dist/larg.
2. G2-V institucional FV/LV (visual) além do golden N1 de decisões.
3. Pacote de regressão cross-obra (além de Obra_TREINO_1).
