# CAD-7.1 — Extração Assembly Data do DXF PL (CHAPA, GRADE, SP, Perfil Metálico)

**Epic:** CAD-7 — Assembly Layers (PL DXF)
**Status:** Done
**Data:** 2026-03-08
**Autor:** aios-dev

---

## Objetivo

Extrair dados de montagem do DXF PL (Pilares Layout) que não são capturados pela
extração de B/H nem pelo motor_fase4.py. Dados necessários para completar fichas de
robô com informações de grades, chapas e pontos de parafusos.

---

## Acceptance Criteria

- [x] AC-1: Script `extrair_assembly_pl.py` criado e funcional
- [x] AC-2: grade_1, grade_2 extraídos via nearest-pilar assignment (COTA GRADE annotations)
- [x] AC-3: CHAPA vert/horiz contados por pilar (deduplicados, tipo classificado por w/h)
- [x] AC-4: SP markers (Screw Points) contados por pilar total
- [x] AC-5: Perfil Metálico contado por pilar
- [x] AC-6: Output `pilares_assembly.json` em Fase-3_Interpretacao_Extracao/Pilares/
- [x] AC-7: 29/29 pilares com grade_1 (100% cobertura com fallback para não-anotados)
- [x] AC-8: motor_fase4.py integrado — grade_1/grade_2/distancia_1 populados em JSON_Pilares/

---

## Implementação

### Script: `scripts/extrair_assembly_pl.py`

**Input:** DXF PL do pavimento (detectado automaticamente na Fase-1)

**Output:** `Fase-3_Interpretacao_Extracao/Pilares/pilares_assembly.json`

### Campos extraídos

| Campo | Fonte DXF | Método |
|-------|-----------|--------|
| `grade_1` | COTA/Cota Seção (2x) DIMENSION com override `<>(GRADE)` ou `GRADE <>` | Nearest-pilar assignment |
| `grade_2` | Idem | Segunda grade mais próxima |
| `chapa_vert` | Layer `CHAPA` LWPOLYLINE com w<=10, h>10 | Raio 700cm por face |
| `chapa_horiz` | Layer `CHAPA` LWPOLYLINE com h<=10, w>10 | Raio 700cm por face |
| `chapa_total` | vert + horiz (deduplicado) | — |
| `sp_total` | Layer `texto` MTEXT terminando em `;SP}` | Raio 700cm por pilar |
| `sp_per_face` | Idem, por face A/B/C/D | Raio 700cm |
| `perfil_metalico` | Layer `Perfil Metálico` LWPOLYLINE | Raio 700cm |
| `confidence` | 0.85 se grade_1 direto, 0.60 se sem grade | — |

### Resultado (Obra_TREINO_21, 12° PAV)

```
Pilares processados: 29
Com grade_1: 29/29 (100%)
Com CHAPA: 28/29 (97%)
Com SP markers: 29/29 (100%)

Faixa de valores:
  grade_1: 60-122 cm
  grade_2: 62-100 cm (alguns pilares)
  chapa_vert: 0-4 placas verticais
  chapa_horiz: 0-4 placas horizontais
  sp_total: 4-16 marcadores SP
  perfil_metalico: 0-9 perfis
```

---

## Descobertas das Layers PL DXF (12° PAV)

### CHAPA Layer (183 LWPOLYLINE)
- **Tipos de placa:**
  - `w=3.6 h=38` (14x) → conector horizontal pequeno
  - `w=4 h=124-480` (73x) → placa lateral vertical (altura variável)
  - `w=38/80 h=3.6` (78x) → conector/grade horizontal
  - `w=244/378 h=4` (14x) → grade horizontal longa
- **Padrão:** CHAPAs vêm em pares duplicados no DXF (deduplicados no script)
- **Distribuição:** 4-14 únicas por pilar section, próximas às labels P{n}.{face}

### BARRA ANCORAGEM Layer (35 LWPOLY + 3 ARC)
- **DESCARTADA:** todas entidades clustered em (5920-6310, 16418-16638)
- Dist > 3379 de qualquer pilar → drawing de detalhe, não per-pilar
- Não extravível por pilar — ignorar para assembly data

### MEIO_PONT Layer (228 INSERT: 120 PONTALETE + 108 MEIO PONTALETE)
- **Distribuição:** spread na planta baixa (plan view), X=1020-6123, Y=8601-15717
- Sobrepõem área dos pilares — estão na planta, não na seção
- **Pendente:** extração por laje (para contagem de pontaletes por área)

### Perfil Metálico Layer (100 LWPOLYLINE)
- Distribuído por pilar section, raio ~700 das faces
- P34/P47/P48: 8-9 perfis (pilares com mais seções)

### SP Annotations (106 MTEXT no layer `texto`)
- Padrão MTEXT: `{\\fTahoma|b0|i0|c0|p34;\\C4;SP}` (cor 4 = cyan)
- 4 SP por face típico = 4 pontos de parafuso na seção
- P1: 4SP/A + 4SP/B + 4SP/C + 2SP/D = 14 total
- sp_total = proxy para densidade de parafusos por pilar

---

## Uso

```bash
# Processar obra
python scripts/extrair_assembly_pl.py --obra DADOS-OBRAS/Obra_TREINO_21

# Com pavimento específico
python scripts/extrair_assembly_pl.py --obra DADOS-OBRAS/Obra_TREINO_21 --pav "12"

# Output customizado
python scripts/extrair_assembly_pl.py --obra DADOS-OBRAS/Obra_TREINO_21 --output /tmp/assembly.json
```

---

## Integração com Pipeline

`pilares_assembly.json` complementa `pilares_bh.json` e `pilares.json`:

```
Fase-3_Interpretacao_Extracao/Pilares/
  pilares.json          ← IDs + b/h/altura
  pilares_bh.json       ← B/H via STOG gordo sections
  pilares_assembly.json ← GRADE, CHAPA, SP, Perfil (NOVO CAD-7.1)
```

Integração em obras_salvas.json:
```json
"grades": {
  "grade_1": "60",        // ← de pilares_assembly.json grade_1
  "distancia_1": "14",    // ← default (não extraível do DXF PL)
  "grade_2": "",
  "distancia_2": ""
}
```

---

## File List

- `scripts/extrair_assembly_pl.py` — script principal
- `DADOS-OBRAS/Obra_TREINO_21/Fase-3_Interpretacao_Extracao/Pilares/pilares_assembly.json` — output
- `docs/stories/active/CAD-7.1.story.md` — esta story

---

## File List

- `scripts/extrair_assembly_pl.py` — extração assembly do DXF PL
- `scripts/comparar_assembly_pl.py` — validação dos dados extraídos
- `scripts/motor_fase4.py` — integração grade_1/grade_2 em process_pilares()
- `DADOS-OBRAS/Obra_TREINO_21/Fase-3_Interpretacao_Extracao/Pilares/pilares_assembly.json` — output

---

*CAD-7.1 DONE | 2026-03-08 | Sprint 4*
