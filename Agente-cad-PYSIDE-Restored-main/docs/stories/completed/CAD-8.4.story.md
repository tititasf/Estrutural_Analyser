# CAD-8.4 — Pipeline Orquestrador E2E (Single Command)

**Epic:** CAD-8 — Multi-Pavimento + Multi-Obra Automation
**Status:** Done
**Dependências:** CAD-8.1, CAD-8.2, CAD-8.3
**Data:** 2026-03-08

---

## Objetivo

Criar `scripts/pipeline_e2e.py` — script único que executa TODAS as fases do pipeline
para uma obra, do zero até o relatório final, sem intervenção humana.

---

## CLI

```bash
# Uma obra completa
python scripts/pipeline_e2e.py --obra DADOS-OBRAS/Obra_TREINO_21

# Com pavimento específico
python scripts/pipeline_e2e.py --obra DADOS-OBRAS/Obra_TREINO_21 --pavimento "12 PAV"

# Dry run (mostra o que faria)
python scripts/pipeline_e2e.py --obra DADOS-OBRAS/Obra_TREINO_21 --dry-run
```

---

## Fases Executadas em Sequência

```
1. descobrir_obras.py        ← scan DXFs
2. engenharia_reversa_dxf.py ← ground truth por pav
3. extrair_bh_pilares.py     ← dimensões pilares
   extrair_vigas_lv.py       ← dimensões vigas
   extrair_lajes_lj.py       ← dimensões lajes
   extrair_garfos_evg.py     ← garfos
   extrair_largura_vigas.py  ← largura vigas
   extrair_assembly_pl.py    ← grades/chapas
4. motor_fase4.py            ← Fase-3 → Fase-4
5. gerar_dxf_pilares.py      ← DXF individual pilares
   gerar_dxf_vigas.py        ← DXF individual vigas
   gerar_dxf_lajes.py        ← DXF individual lajes
6. comparar_dxf.py           ← score individual
7. gerar_obras_salvas.py     ← formato robô
8. pipeline_report.json      ← relatório final
```

---

## Acceptance Criteria

- [ ] AC-1: Um único comando processa obra completa Fase-1 → Fase-8
- [ ] AC-2: Cada fase pode ser retomada (skip se output já existe, `--force` para refazer)
- [ ] AC-3: Exit code: 0=sucesso total, 1=sucesso parcial (algumas fases falharam), 2=falha crítica
- [ ] AC-4: Cria `Fase-8_Revisao_Entrega/pipeline_report.json` com score por pav + por tipo
- [ ] AC-5: Idempotente — re-executar não quebra outputs anteriores (sem `--force`)

---

## pipeline_report.json

```json
{
  "obra": "Obra_TREINO_21",
  "timestamp": "2026-03-08T...",
  "pavimentos": {
    "12 PAV": {
      "phases_completed": 8,
      "phases_failed": 0,
      "scores": {
        "pilares_ids": 1.0,
        "vigas_ids": 1.0,
        "lajes_ids": 1.0,
        "pilares_dxf": 1.0,
        "vigas_dxf": 1.0,
        "lajes_dxf": 1.0
      },
      "aprovado": true
    }
  },
  "global_score": 1.0,
  "status": "APROVADO"
}
```

---

## File List

- [ ] `scripts/pipeline_e2e.py` (CRIAR)
- [ ] `DADOS-OBRAS/Obra_TREINO_21/Fase-8_Revisao_Entrega/pipeline_report.json` (GERADO)

---

*CAD-8.4 Backlog | Sprint 5 | 2026-03-08*
