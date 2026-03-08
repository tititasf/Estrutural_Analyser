# Story CAD-5.5 — Auto-fill Fichas Completas por Robô

**Epic:** 5 — Extração Dimensional Completa
**Sprint:** 2
**Status:** Done
**Criado:** 2026-03-08
**Assignee:** @dev (aios-dev)

---

## Objetivo

Integrar todos os dados extraídos (CAD-5.1 a CAD-5.4) em fichas completas compatíveis
com cada robô de geração DXF. Script único consolida todas as fontes.

## Fontes Integradas

| Fonte | Dados | N |
|-------|-------|---|
| `pilares_bh.json` | B/H via inverse-proximity | 34 pilares |
| `vigas_dim.json` | comprimento + altura_lateral | 33 vigas |
| `garfos_evg.json` | garfo_count por viga | 20 vigas com garfo |
| `lajes_data.json` | n_paineis + area + dims | 20 lajes |

## Acceptance Criteria

- [x] **AC-1:** Script `integrar_fichas_completas.py` criado e executado
- [x] **AC-2:** `ficha_pilares.json` — 34 pilares com B/H, altura, faces
      33 com B/H extraídos | 1 fallback (sem DIMENSION próxima)
- [x] **AC-3:** `ficha_laterais_vigas.json` — 33 vigas com comprimento + altura
      Ranges: comprimento 180-1205cm | altura 38-310cm
- [x] **AC-4:** `ficha_fundos_vigas.json` — 33 vigas com comprimento + garfo_count
      20 com garfo (60%) | 13 sem garfo (sem EVG no 12 PAV)
- [x] **AC-5:** `ficha_lajes.json` — 20 lajes com painéis e bbox estimado
      10 com AUX00 panels | 10 apenas com label (source: label-only)
- [x] **AC-6:** `vigas_ground_truth.json` atualizado — 64 campos preenchidos
      comprimento + h para todas as 33 vigas

## Output

```
Fase-3_Interpretacao_Extracao/Fichas_Completas/
  fichas_completas.json      ← Todas as fichas consolidadas
  ficha_pilares.json         ← Robo_Pilares
  ficha_laterais_vigas.json  ← Robo_Laterais_de_Vigas
  ficha_fundos_vigas.json    ← Robo_Fundos_de_Vigas
  ficha_lajes.json           ← Robo_Lajes
```

## Samples

**Pilar P1:** B=38cm | H=60cm | altura=652cm | faces=[A,B,C,D] | conf=80%
**Viga V22 (lateral):** comprimento=558cm | alt_lateral=310cm | conf=84%
**Viga V12 (fundo+garfo):** comprimento=244cm | garfo=28 (aditivo) | conf=90%

## Próximos Passos (CAD-6.x)

- NVIDIA NIM visual para validar B/H extraídos (CAD-6.2)
- ChromaDB + sentence-transformers para RAG multimodal (CAD-6.1)
- Score >= 90% em dimensões (CAD-6.3)

---

*Story CAD-5.5 | Sprint 2 | Integração Fichas | CAD-ANALYZER v3.0*
