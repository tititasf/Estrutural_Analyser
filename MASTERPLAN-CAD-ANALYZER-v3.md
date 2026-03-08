# MASTERPLAN CAD-ANALYZER v3.0 — Geração DXF por Robô + Comparação vs. Engenharia Reversa

**CEO-PLANEJAMENTO (Athena) — Versão 3.0 (ATUALIZADO 2026-03-08)**
**Objetivo:** Pipeline 100% headless — DXF STOG → fichas → motor → gerador DXF → score >= 95%

---

## OBJETIVO CENTRAL (Clarificado pelo Usuário)

> "Usar os robôs para gerar DXF unitário de cada item e comparar com o item dentro da engenharia
> reversa. Devemos ser capazes de gerar todos os itens com os robôs para chegar no resultado
> idêntico dos resultados de engenharia reversa."

### Fluxo Principal
```
DXF STOG original (12 PAV)   ← ground truth
        ↓
  Engenharia Reversa          ← Epic 5 CONCLUÍDO ✅
  (extrair fichas)
        ↓
  Motor Fase 4                ← Sprint 1 CONCLUÍDO ✅ (motor_fase4.py)
  (fichas → JSON robô)
        ↓
  Robô gera DXF               ← Epic 6 INICIANDO ← AQUI ESTAMOS
  (unitário por item)
        ↓
  Comparação                  ← Epic 6
  (gerado vs. original STOG)
        ↓
  Score >= 95%                ← META FINAL
```

---

## ESTADO ATUAL (2026-03-08) — Epic 5 Completo

### Formato Real dos JSONs (O que cada Robô Precisa)

**P{n}.json — Robo_Pilares:**
```
comprimento (H, cm), largura (B, cm), altura (pé-direito)
h1_A..h5_H   — distribuição altura por face (COMPUTADO) ✅
larg1_A..3_H — largura painéis por face (0 padrão) ✅
laje_A..H    — conexão laje por face (0 padrão) ✅
grade_1..3   — grades (0 padrão) ✅
par_1_2..8_9 — parafusos (0 padrão) ✅
STATUS: motor_fase4.py já gera todos os 33 pilares ✅ COMPLETO
```

**V{n}_A.json + V{n}_B.json — Robo_Laterais_de_Vigas:**
```
total_width  — B da viga (espessura, cm) — ❌ NÃO EXTRAÍDO
total_height — H da viga (altura lateral, cm) — ✅ extraído
panels[6]    — decomposição comprimento em 120cm — ✅ COMPUTADO
holes[4]     — furos (todos inactive) — ✅ padrão
STATUS: FALTA total_width do FV DXF ❌
```

**V{n}_fundo.json — Robo_Fundos_de_Vigas:**
```
side = "C" (fundo da viga)
total_width  — comprimento da viga
total_height — B da viga (espessura) — ❌ NÃO EXTRAÍDO
STATUS: FALTA largura_fundo do FV DXF ❌
```

**L{n}.json — Robo_Lajes:**
```
comprimento, largura         — ✅ parcial via AUX00
coordenadas [[x,y],...]      — ❌ CRÍTICO: polígono real não extraído
linhas_verticais             — ✅ COMPUTADO (cada 100cm)
linhas_horizontais           — ✅ padrão vazio
obstaculos                   — ✅ padrão vazio
STATUS: FALTA coordenadas reais do LJ DXF ❌ CRÍTICO
```

---

## EPIC 6 — Robô-Driven DXF Generation + Comparação (Sprint 3)

### CAD-6.1 — Audit Completo DXF → Campo Robô
**Objetivo:** Mapear CADA campo do JSON de robô para a entidade DXF exata.

Script `audit_dxf_robot_fields.py`:
- Inspeciona PL, LV, FV, LJ DXFs — lista TODAS as layers + entity counts
- Para PL: encontrar `total_width` da viga no FV DXF
- Para LJ: encontrar polígono real (LWPOLYLINE com maior área perto de cada label L{n})
- Produz `DXF_ROBOT_FIELDMAP.json` — mapeamento definitivo

### CAD-6.2 — Extração total_width das Vigas (FV DXF)
**Objetivo:** Extrair espessura da viga (B) do FV DXF.
- Layer "Cota Seção (2x)" do FV DXF: DIMENSION com valor < 60cm = largura_fundo
- Salvar em `vigas_largura.json` — alimenta motor para total_width

### CAD-6.3 — Extração coordenadas das Lajes (LJ DXF)
**Objetivo:** Extrair polígono real de cada laje.
- LJ DXF: LWPOLYLINE fechado de maior área próximo a cada label L{n}
- Normalizar para origem relativa
- Salvar em `lajes_poligono.json` — alimenta motor para coordenadas

### CAD-6.4 — Motor Fase 4 Completo (33V + 20L)
**Objetivo:** Gerar JSONs para TODOS os 33 V{n} e 20 L{n}.
- Hoje: motor_fase4.py só processa 4 vigas (sem fichas)
- Fix: usar vigas_dim.json (33V) + vigas_largura.json + garfos_evg.json
- Fix: usar lajes_poligono.json para coordenadas reais
- Saída: 66 JSON laterais + 33 JSON fundo + 20 JSON lajes

### CAD-6.5 — Gerador DXF Headless: Pilares (ezdxf puro)
**Objetivo:** Substituir Robo_Pilares GUI por gerador Python/ezdxf.
- Estudar PL DXF: identificar todas as layers + entidades por pilar
- Escrever `robo_pilares_ezdxf.py`: lê P{n}.json → gera P{n}_generated.dxf

### CAD-6.6 — Gerador DXF Headless: Vigas (ezdxf puro)
**Objetivo:** Substituir Robo_Laterais + Robo_Fundos GUI por Python/ezdxf.
- Estudar LV + FV DXF: padrão de entities por viga
- Escrever `robo_vigas_ezdxf.py`: lê V{n}_A.json → gera V{n}.A DXF unit

### CAD-6.7 — Gerador DXF Headless: Lajes (ezdxf puro)
**Objetivo:** Substituir Robo_Lajes GUI por Python/ezdxf.
- Estudar LJ DXF: polígono + linhas + texto L{n}
- Escrever `robo_lajes_ezdxf.py`: lê L{n}.json → gera L{n}_generated.dxf

### CAD-6.8 — Comparador DXF Gerado vs. STOG
**Objetivo:** Medir match_rate entre DXF gerado e elemento original STOG.
- Extrair elemento individual do DXF STOG (por proximidade ao label)
- Comparar: geometry_match, text_match, layer_match
- Score >= 95% = VALIDADO
- `comparar_dxf_gerado_original.py`

---

## MAPA DE CAMPOS (Completo)

| Campo JSON | Fonte DXF | Status |
|-----------|-----------|--------|
| P{n}.comprimento | PL "Cota Seção (2x)" proximity | ✅ |
| P{n}.largura | PL "Cota Seção (2x)" proximity | ✅ |
| P{n}.h1-h5_face | COMPUTADO (fórmula 2+244+...) | ✅ |
| P{n}.larg1-3_face | 0 (padrão motor) | ✅ |
| P{n}.grade/par | 0 (padrão motor) | ✅ |
| V{n}.total_height | LV "Cota Seção (2x)" | ✅ |
| V{n}.comprimento | LV "COTA" max >= 100cm | ✅ |
| V{n}.total_width | FV "Cota Seção (2x)" < 60cm | ❌ CAD-6.2 |
| V{n}.panels | COMPUTADO (120cm slots) | ✅ |
| L{n}.comprimento | LJ AUX00 MTEXT dims | ✅ parcial |
| L{n}.coordenadas | LJ LWPOLYLINE fechado | ❌ CAD-6.3 |
| L{n}.linhas_verticais | COMPUTADO cada 100cm | ✅ |

---

## SEQUÊNCIA DE EXECUÇÃO (Sprint 3)

```
CAD-6.1 (audit) → CAD-6.2 (viga_w) → CAD-6.3 (laje_poly) → CAD-6.4 (motor)
      → CAD-6.5 (gen_pilar) → CAD-6.6 (gen_viga) → CAD-6.7 (gen_laje) → CAD-6.8 (score)
```

---

*MASTERPLAN CAD-ANALYZER v3.0 | Athena (CEO-PLANEJAMENTO) | 2026-03-08*
*Meta: Score >= 95% por elemento | Pipeline 100% headless sem GUI*
