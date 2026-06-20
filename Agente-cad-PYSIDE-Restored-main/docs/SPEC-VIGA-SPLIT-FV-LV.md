# SPEC — Separação da Viga em FV (Fundo) + LV (Lateral) em TODOS os níveis

**Versão:** 1.0
**Data:** 2026-06-20
**Origem:** decisão do dono (urgente) — alinhar N1 com N2/robôs, que já tratam FV e LV separadamente.
**Status:** SPEC para execução faseada e segura (não-destrutiva).

---

## 1. Regra de Domínio (do dono — fonte da verdade)

Cada **viga tem um nome** (ex.: `V1`). Ao ser interpretada, ela gera **exatamente 2 fichas** (não múltiplas), cada uma com **segmentos aninhados como sub-fichas**:

```
Viga V1
├── Ficha FV (Fundo)  — 1 por viga
│     └── sub-fichas: segmento_fundo_1, segmento_fundo_2, … (N segmentos de fundo)
└── Ficha LV (Lateral) — 1 por viga
      └── sub-fichas: seg_A_1…, seg_B_1…, VC_1… (segmentos lado A + lado B + visões-corte)
```

- **1 ficha FV + 1 ficha LV por viga** — **NÃO** criar múltiplas fichas por viga. Os segmentos vivem **dentro** da ficha (aninhados), não como fichas irmãs.
- **FV:** tem seu **número de segmentos de fundo** (cada um vira uma sub-ficha dentro da ficha FV da viga).
- **LV:** segmentos **lado A** + **lado B** + **N visões-corte (VC)**, conforme quantidade/variedade de segmentos e cruzamentos.
- **Cada viga é um caso** — o nº de segmentos diverge entre FV e LV e entre vigas.

**Estrutura já existente no N2 (reaproveitar):**
- FV `campos_json.segments_rich` = lista de segmentos do fundo (ex.: 16 segmentos numa viga).
- LV `campos_json` = `panels_A` / `panels_B` (segs A/B) + `section_views` (as visões-corte).
- ⚠️ **Bug a evitar/limpar:** o N2 atual tem **duplicação** (FV = 271 fichas para 137 vigas ≈ 2 por viga). O alvo é **1 ficha por viga**; a duplicação deve ser consolidada, não replicada para o N1.

**Confiabilidade do gabarito N2:**
- N2 do **Fundo (FV)** → **bom**, referência (mas consolidar a duplicação 271→137).
- N2 da **Lateral (LV)** → **ainda em ajuste pelo dono**, NÃO usar como gabarito firme ainda.

---

## 2. "Em todos os níveis" — onde aplicar

| Nível | Hoje | Alvo |
|-------|------|------|
| **Motor/Detecção** (`src/core/beam_tracer.py`) | `detect_beams` → 1 objeto por viga | decompor a viga em aspectos FV (segmentos de fundo) e LV (segs A + segs B + VCs) |
| **Persistência** (tabela `beams`) | 1 registro por viga (fundo+laterais juntos) | representar FV e LV como elementos próprios — **aditivo/versionado, sem migração destrutiva** |
| **Ficha F7/N1** (`fase3_fichas`) | 1 viga = 1 ficha | gerar fichas **FV** e **LV** separadas, por segmento |
| **Comparison Engine** | compara viga inteira | comparar **FV(N1) × FV(N2)** e **LV(N1) × LV(N2)** separadamente |
| **UI / card Fº7** | FV e LV mostram a mesma contagem (nº de vigas) | mostrar contagem real de **segmentos** FV vs LV (A+B+VC) |

---

## 2.1 Fonte de dados real do N1 (descoberto 2026-06-20)

A viga N1 (`beams.data_json`) **já carrega os segmentos**:
- **FV (fundo)** = `geometry.classified.seg_bottom` (lista de segmentos de fundo).
- **LV (lateral)** = `geometry.classified.seg_side_a` + `geometry.classified.seg_side_b` (+ campos `seg_a`/`seg_b` = contagens; `seg_a_dim`, `seg_a_h1`, `seg_a_comprimento_total`, `seg_a_laje_sup`, etc. por segmento).
- VC (visões-corte): ainda não há campo dedicado no N1 (existe no N2 `section_views`) — a extrair na Fase 3.
- **Validado (Obra_TREINO_1 pav 13):** 180 vigas → FV=655 segmentos, LV=860 segmentos (divergem ✅).

## 3. Execução Faseada (segura — não-destrutiva primeiro)

> **Invariante:** backup do `project_data.vision` antes de qualquer escrita estrutural. Nada de `DROP`/migração destrutiva. Abordagem **aditiva** (novos campos/tabela paralela ou flag), com a tabela `beams` preservada até a nova representação estar validada.

- **Fase 0 — Modelo de dados. ✅ CONCLUÍDA (2026-06-20).** Tabela aditiva `beam_elements` criada (`src/core/database.py · _create_tables_if_not_exist`): `id, project_id, parent_beam_id, viga_nome, classe∈{FV,LV}, campos_json, n_segmentos, is_validated, created_at, updated_at`. **1 linha por (viga × classe).** `beams` preservada.
- **Fase 1 — UI (display real, seguro). ✅ CONCLUÍDA (2026-06-20).** Card Fº7 lê de `beam_elements` (segmentos FV vs LV) → divergem na tela. (`main.py · _process_with_reverse_engineering`)
- **Fase 2 — Geração de fichas. ✅ CONCLUÍDA (2026-06-20).** `DatabaseManager.materialize_beam_elements(project_id)`: **agrega por nome de viga** (V302 fragmentado em 5 beams → 1 ficha FV + 1 LV, segmentos somados). Idempotente (UPSERT). Sincronizado ao abrir o card. **Pav 13: 136 vigas → 136 FV (655 segs) + 136 LV (860 segs).** Falta: aninhar dims/campos por segmento (hoje guarda geometria dos segmentos); espelhar schema N2 (`segments_rich`).
- **Fase 3 — Motor/detecção.** `beam_tracer` decompõe explicitamente a viga nos elementos FV/LV por segmento.
- **Fase 4 — Comparison.** Comparar FV e LV independentemente vs N2 (lembrando: N2-LV ainda em ajuste → marcar como referência fraca).

**Gate de cada fase:** contagens batem com a inspeção manual de 1 viga conhecida; nenhuma regressão nos robôs (FV/LV já consomem a viga) nem no Comparison.

---

## 4. Riscos
- Migrar `beams` destrutivamente → **proibido**; usar representação aditiva.
- Basear LV no N2 atual → N2-LV ainda em ajuste; tratar como referência fraca.
- Quebrar robôs FV/LV (que já leem a viga) → validar que continuam funcionando após Fase 2/3.

## 5. Referência
- `docs/MASTERPLAN-LOOP-TREINO-MOTOR.md` (mismatch FV/LV já anotado em §6)
- `docs/MASTERPLAN-FICHAS-F1-F9-HARMONIZACAO.md` (taxonomia 4 classes)
- `src/core/beam_tracer.py` (`detect_beams`, `merged_bottom_lengths`)
