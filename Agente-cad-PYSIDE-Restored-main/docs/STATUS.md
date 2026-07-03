# STATUS — gerado automaticamente, NÃO editar à mão

**Gerado em:** 2026-07-03 12:23:13  
**Regenerar:** `python scripts/arete/gerar_status.py`  
**Fontes:** relatórios Arete + GOLDEN/ + triagem JSONL + DB (read-only). Em conflito com qualquer doc escrito à mão, ESTE arquivo vence (é o dado).

## Última rodada Arete por classe (relatório mais recente)

| Classe | Pav | Run | PASS | FAIL | BLOCKED | Arete % | Golden selado | Alerta |
|--------|-----|-----|------|------|---------|---------|---------------|--------|
| FV | 13_PAV | 20260703_114409 | 26 | 0 | 0 | 100.0% | 26 |  |
| LAJ | 13_PAV | 20260703_114248 | 31 | 0 | 0 | 100.0% | 31 |  |
| LV | 13_PAV | 20260703_101652 | 21 | 11 | 0 | 65.6% | 32 | ❌ FAIL aberto · ⚠ golden (32) > última rodada (21) — REGRESSÃO vs selado |
| LV | 14_PAV | 20260626_194156 | 10 | 17 | 0 | 37.0% | 10 | ❌ FAIL aberto |
| PIL | 12_PAV | 20260613_180530 | 31 | 4 | 0 | 88.6% | 31 | ❌ FAIL aberto |
| PIL | 13_PAV | 20260703_114452 | 35 | 0 | 0 | 100.0% | 35 |  |
| PIL | 14_PAV | 20260613_180945 | 22 | 5 | 0 | 81.5% | 22 | ❌ FAIL aberto |
| PIL | 1_PAV | 20260613_175011 | 31 | 6 | 0 | 83.8% | 31 | ❌ FAIL aberto |
| PIL | 2_PAV | 20260613_180110 | 30 | 5 | 0 | 85.7% | 30 | ❌ FAIL aberto |
| PIL | COBERTURA | 20260613_181539 | 24 | 5 | 0 | 82.8% | 24 | ❌ FAIL aberto |
| PIL | TERREO | 20260613_181301 | 12 | 10 | 0 | 54.5% | 12 | ❌ FAIL aberto |

## Golden selado (todas as obras/pavimentos)

| Obra | Pavimento | Classe | Itens selados |
|------|-----------|--------|---------------|
| Obra_TREINO_1 | 12_PAV | PIL | 31 |
| Obra_TREINO_1 | 13_PAV | FV | 26 |
| Obra_TREINO_1 | 13_PAV | LAJ | 31 |
| Obra_TREINO_1 | 13_PAV | LV | 32 |
| Obra_TREINO_1 | 13_PAV | PIL | 35 |
| Obra_TREINO_1 | 14_PAV | LV | 10 |
| Obra_TREINO_1 | 14_PAV | PIL | 22 |
| Obra_TREINO_1 | 1_PAV | PIL | 31 |
| Obra_TREINO_1 | 2_PAV | PIL | 30 |
| Obra_TREINO_1 | COBERTURA | PIL | 24 |
| Obra_TREINO_1 | TERREO | PIL | 12 |

## Triagem de erros (JSONL)

| Arquivo | Total | Por status | Por autor |
|---------|-------|------------|-----------|
| Obra_TREINO_1_13_PAV_fundos_viga.jsonl | 6 | verificado: 6 | auto: 6 |
| Obra_TREINO_1_13_PAV_lajes.jsonl | 40 | aberto: 17, verificado: 23 | auto: 23, humano: 17 |

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
| aprovado | 328 |
| auto_aprovado | 445 |
| manual_sel | 1 |
| motor | 5 |

---
*Gerado por `scripts/arete/gerar_status.py` — MASTERPLAN-PRODUCAO-SOBERANIA WS-D.*
