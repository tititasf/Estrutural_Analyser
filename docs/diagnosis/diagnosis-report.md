# DIAGNOSIS REPORT — CAD-FICHAS-V2
## Handoff H1: Fase C → Fase A
**Conductor | CAD Pipeline Orchestrator | 2026-03-19**

---

## STATUS DO GATE H1

```
✅ C-1: entity_inventory — 17 tipos PL / 17 tipos LV / 11 tipos LJ (gate: >= 10 ✅)
✅ C-2: layer_aliases — 28+ PL / 30+ LV / 22+ LJ mapeados, 4 famílias documentadas
✅ C-3: gap_matrix — 25 gaps (12 CRÍTICOS, 8 IMPORTANTES, 5 NICE-TO-HAVE)

GATE H1: PASS → FASE A autorizada
```

---

## SUMMARY EXECUTIVO

As fichas instrutivas atuais (75 páginas PDF) têm **score 1.5/10** para o robô
porque respondem "como funciona engenharia de formas" em vez de
"dada esta entidade DXF, quais campos JSON extrair".

**O robô realmente usa:**
- TEXT/MTEXT → regex para detectar IDs (RE_PILAR, RE_VIGA, RE_LAJE)
- LWPOLYLINE fechada → contorno de pilar ou laje
- LWPOLYLINE aberta + LINE → geometria de viga
- Lógica de 3 raios para associar texto→geometria (800mm/1200mm/1500mm)
- confidence ≥ 0.80 para auto-assign, abaixo → revisão humana

**~90% do conteúdo atual é irrelevante para o robô.**

---

## ARQUIVOS PRODUZIDOS

| Arquivo | Tamanho | Conteúdo |
|---|---|---|
| `C1-entity-inventory.md` | 17 entity types × 3 elementos | Atributos ezdxf + código Python |
| `C2-layer-aliases.md` | 80+ layers mapeados | Canonical names + 4 famílias |
| `C3-gap-matrix.md` | 25 gaps listados | Prioritização CRÍTICO/IMPORTANTE/NICE |

---

## CAMPOS JSON TOTAIS A DOCUMENTAR NA FASE A

```
Pilares: 17 campos (1 atualmente documentado → 0 úteis)
Vigas:   15 campos (0 documentados)
Lajes:   10 campos (0 documentados)
Infra:   regex + raios + família + confidence (0 documentados)
Total:   ~50 itens operacionais ausentes
```

---

## INSTRUÇÕES PARA FASE A

### SPEC-PILARES.md deve incluir:
1. RE_PILAR = `r'^(PC?\.?-?\d+([A-Z]|\.\d+|-\d+)?|P-\d+[A-Z]?)$'`
2. Como acessar `e.dxf.text` e `e.dxf.insert` para TEXT
3. LWPOLYLINE + `is_closed=True` → contorno pilar
4. RE_DIM → `comprimento = max(dim_l, dim_a)`, `largura = min(dim_l, dim_a)`
5. PILAR_SEARCH_RADIUS = 800mm
6. `confidence >= 0.80` → auto-assign
7. Pilar especial: `bulge > 0.3` → `pilar_especial=True`
8. Exemplo: texto "P17 20x40" em layer NOMENCLATURA + LWPOLYLINE fechada na Painéis

### SPEC-VIGAS.md deve incluir:
1. RE_VIGA = `r'^(V|BA|VB|VT|VC)\.?-?\d+([A-Z]|\.\d+|/\d+)?$'`
2. RE_DIM_BH = `r'b\s*=\s*(\d{1,3}).*?h\s*=\s*(\d{1,3})'`
3. LINE entities (não LWPOLYLINE) para geometria
4. layer `fundo` → FV, layer `Painéis` → LV
5. VIGA_SEARCH_RADIUS = 1200mm
6. INSERT "GARFOS" → `garfos` dict

### SPEC-LAJES.md deve incluir:
1. RE_LAJE = `r'^(L\d+[A-Za-z]?|Y\d+|X\d+|LAJ[-_]?\d+|LAJE[-_\s]*\d+)$'`
2. RE_LAJE_H = `r'h\s*[=:]\s*([\d,.]+)'` → `espessura`
3. LAJE_SEARCH_RADIUS = 1500mm
4. Laje SYNTHETIC: clusters de h= sem texto L→ CLUSTER_RADIUS=500mm
5. layer `Vázio` (acento corrompido!) → abertura
6. `normalize_layer()` para lidar com CP1252 vs UTF-8

### CONFIG-LAYERS.yaml deve incluir:
- Algoritmo de família: TQS (numeric) / BIM (descriptive) / METHODUS (MTH-) / EBERICK (TX)
- Canonical name para cada layer + aliases
- Encoding fix: normalização de acentos

### DECISION-MATRIX.md deve incluir:
- confidence thresholds: 0.80 (auto) / 0.50 (human review) / <0.50 (reject)
- fallback chain: Raio1 → Raio2 → Raio3 → synthetic
- casos: pilar sem texto próximo, laje sem texto L1, viga com dimensão b=h

---

*Diagnosis Report COMPLETO | Gate H1: PASS | Fase A autorizada ✅*
*Arquivo: D:/Agente-cad-PYSIDE/docs/diagnosis/diagnosis-report.md*
