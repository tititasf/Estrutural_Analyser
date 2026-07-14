# STATUS — gerado automaticamente, NÃO editar à mão

**Gerado em:** 2026-07-14 02:43:47  
**Regenerar:** `python scripts/arete/gerar_status.py`  
**Fontes:** relatórios Arete + GOLDEN/ + triagem JSONL + DB (read-only). Em conflito com qualquer doc escrito à mão, ESTE arquivo vence (é o dado).

## Última rodada Arete por classe (relatório mais recente)

| Classe | Pav | Run | PASS | FAIL | BLOCKED | Arete % | Golden selado | Alerta |
|--------|-----|-----|------|------|---------|---------|---------------|--------|
| FV | 13_PAV | 20260703_164825 | 26 | 0 | 0 | 100.0% | 26 |  |
| LAJ | 13_PAV | 20260713_202844 | 31 | 0 | 0 | 100.0% | 31 |  |
| LV | 13_PAV | 20260703_164510 | 32 | 0 | 0 | 100.0% | 32 |  |
| LV | 14_PAV | 20260626_194156 | 10 | 17 | 0 | 37.0% | 10 | ❌ FAIL aberto |
| PIL | 12_PAV | 20260711_000051 | 34 | 2 | 0 | 94.4% | 34 | ❌ FAIL aberto |
| PIL | 13_PAV | 20260710_235326 | 35 | 0 | 0 | 100.0% | 35 |  |
| PIL | 14_PAV | 20260711_001309 | 27 | 1 | 0 | 96.4% | 27 | ❌ FAIL aberto |
| PIL | 1_PAV | 20260705_214623 | 15 | 23 | 0 | 39.5% | 34 | ❌ FAIL aberto · ⚠ golden (34) > última rodada (15) — REGRESSÃO vs selado |
| PIL | 2_PAV | 20260705_215126 | 34 | 2 | 0 | 94.4% | 34 | ❌ FAIL aberto |
| PIL | COBERTURA | 20260705_215925 | 6 | 23 | 0 | 20.7% | 25 | ❌ FAIL aberto · ⚠ golden (25) > última rodada (6) — REGRESSÃO vs selado |
| PIL | TERREO | 20260705_215627 | 18 | 5 | 0 | 78.3% | 20 | ❌ FAIL aberto · ⚠ golden (20) > última rodada (18) — REGRESSÃO vs selado |

## Golden selado (todas as obras/pavimentos)

| Obra | Pavimento | Classe | Itens selados |
|------|-----------|--------|---------------|
| Obra_TREINO_1 | 12_PAV | PIL | 34 |
| Obra_TREINO_1 | 13_PAV | FV | 26 |
| Obra_TREINO_1 | 13_PAV | LAJ | 31 |
| Obra_TREINO_1 | 13_PAV | LV | 32 |
| Obra_TREINO_1 | 13_PAV | PIL | 35 |
| Obra_TREINO_1 | 14_PAV | LV | 10 |
| Obra_TREINO_1 | 14_PAV | PIL | 27 |
| Obra_TREINO_1 | 1_PAV | PIL | 34 |
| Obra_TREINO_1 | 2_PAV | PIL | 34 |
| Obra_TREINO_1 | COBERTURA | PIL | 25 |
| Obra_TREINO_1 | TERREO | PIL | 20 |

## Triagem de erros (JSONL)

| Arquivo | Total | Por status | Por autor |
|---------|-------|------------|-----------|
| Obra_TREINO_1_13_PAV_fundos_viga.jsonl | 31 | aberto: 25, verificado: 6 | auto: 31 |
| Obra_TREINO_1_13_PAV_fundos_viga_posfix_20260707.jsonl | 9 | aberto: 5, corrigido_codigo_headless_pendente: 1, em_correcao: 1, verificado: 2 | auto: 9 |
| Obra_TREINO_1_13_PAV_fv_contaminacao_validacao.jsonl | 3 | corrigido_codigo_dados_historicos_pendentes: 1, corrigido_verificado: 1, corrigido_verificado_visual: 1 | auto: 2, humano: 1 |
| Obra_TREINO_1_13_PAV_lajes.jsonl | 144 | aberto: 64, verificado: 80 | auto: 111, dono: 16, humano: 17 |
| Obra_TREINO_1_13_PAV_laterais_viga.jsonl | 9 | aberto: 5, corrigido: 1, invalidado: 1, verificado: 2 | humano: 9 |
| Obra_TREINO_1_13_PAV_pilares.jsonl | 42 | aberto: 5, verificado: 37 | auto: 39, humano: 3 |
| Obra_TREINO_1_13_PAV_pilares_20260713.jsonl | 8 | aberto: 8 | auto: 8 |
| Obra_TREINO_1_13_PAV_pilares_20260713_postfix.jsonl | 4 | aberto: 1, verificado: 3 | auto: 4 |

## Banco de dados (read-only)

**Fichas N2 (`reverse_eng_fichas`):**

| Classe | Status | Qtde |
|--------|--------|------|
| FV | draft | 134 |
| FV | extracted | 137 |
| LAJ | draft | 181 |
| LV | draft | 229 |
| PIL | draft | 225 |

**Recortes (`reverse_eng_recortes`):**

| Status | Qtde |
|--------|------|
| aprovado | 734 |
| auto_aprovado | 63 |
| motor | 9 |

---
*Gerado por `scripts/arete/gerar_status.py` — MASTERPLAN-PRODUCAO-SOBERANIA WS-D.*
