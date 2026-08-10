# QA — Comparação N2·N3·N4 com fidelidade real (não “parece igual”)

**Status:** canónico (2026-07-18)  
**Caso âncora:** LV V301 face A (sessão laterais / cota inventada `40,2`)  
**Família:** N2, N3 e N4 são **desenhos** — mesma técnica de inventário/overlay/visão.  
N1 é interpretação (procedimento separado).  
**Pipeline operacional:** `docs/PIPELINE-VISAO-N2-N3-N4-ANTIALUCINACAO.md`  
**Complementa:** `docs/QA-VISAO-EVIDENCIA-CANONICA.md`,  
`docs/QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md`,  
`docs/VISION-VALIDACAO-CAMINHOS.md`

---

## 1. Problema que este protocolo resolve

Agentes (e humanos com pressa) falham em N2×N4 quando:

1. **Auditam o N4 contra o N4** (coerência interna / limpeza visual).
2. **Confundem geometria com rótulo** (“o vão tem 40,2 cm ⇒ a cota `40,2` está certa”).
3. **Olham só PNG inteiro** e perdem `40` vs `40,2`, ou ausência total de um rótulo.
4. **Usam `DIMENSION` no N2** — no recorte LV as cotas são quase sempre **`TEXT`**.
5. **Dynamic patching / visão sem set-diff** — descreve ladrilho legível, não proveniência.

O caso V301.A: N4 emitia `40,2` (soma 19+21,2 de marco) e `445,7` (total da face).  
**Nenhum dos dois existe como rótulo no N2 da face.** A geometria do vão pode ser real; o **rótulo é invenção**.

---

## 2. Três camadas de verdade (nunca misturar)

| Camada | Pergunta | Fonte |
|--------|----------|--------|
| **G — Geometria** | O vão / aresta / painel existe? | LINE/LWPOLYLINE Painéis·SARR |
| **R — Rótulo** | O N2 **escreve** este valor de cota? | TEXT/MTEXT (N2) · DIMENSION/text (N4) |
| **P — Política do motor** | O gerador *deveria* agrupar / cotar total? | `gerar_*_dxf_*.py` |

**Regra de ouro**

```text
R_N4 ⊆ R_N2_own_face     →  nunca inventar rótulo
G_N4 ≈ G_N2_struct       →  estrutura (não ticks/lixo)
P só com evidência em R  →  agrupar estreitos só se N2 rotula a soma
```

`G ∧ P ⇏ R`. Largura real **não autoriza** cota desenhada.

---

## 3. Pipeline obrigatório (ordem FAIL-closed)

**Aplica-se a qualquer par de desenho:** N2×N4 (G2), N3×N4 (G5), N2×N3 (diagnóstico).  
Substituir mentalmente “N4” por **candidato** e “N2” por **gabarito** do par.  
Detalhe + selo laranja + N1 separado: `PIPELINE-VISAO-N2-N3-N4-ANTIALUCINACAO.md`.

```text
0. Resolver paths
   N2 = reverse_eng_recortes.recorte_path (_sel_ > _motor_)
   N3 = DXF gerado rota produtiva (Fase-5 / ficha N1 convertida)
   N4 = DXF gerado da ficha N2 (LV: VIEW_A | VIEW_B | CORTE)
   Par do gate: (gabarito, candidato) ∈ {N2,N3,N4}²

1. Âncora da face/parte
   origem body (x0,y0), h_body, panel_widths, clip_rel
   (motor reverso / inventário — NÃO crop aleatório)

2. Inventário vetorial completo (determinístico — rodar ANTES da visão)
   2a. LINEs estruturais (Painéis, SARR*) → MATCH | MISSING_cand | EXTRA_cand
       + classes de lixo: N2_CONTEXTO_VIZINHO | N2_VOID_JUNK | TICK_DIAG
   2b. Cotas gabarito = TEXT numérico (N2) ou DIM/TEXT (N3/N4)
       Cotas candidato = DIMENSION/TEXT
       → set-diff de valores normalizados (","→".", 50,5≡50.5)
   2c. Textos de nomenclatura (V301.A, …)
   2d. Hachuras / materiais (presença de família, não pixel)

3. Vereditos automáticos (hard fail)
   - qualquer cota EXTRA no candidato (own-face)     → FAIL inventário R
   - qualquer cota MISSING own-face no candidato     → FAIL omissão R
   - EXTRA estrutural Painéis (não stub dim)         → FAIL geometria G
   (contexto vizinho e ticks NÃO contam como FAIL)
   - G5 (N3×N4): exigir G2 N2×N4 já PASS na parte

4. Evidência visual (só depois do inventário)
   Agente CLI: PNG full-render gabarito × candidato
              + overlay em CAMADAS:
                · lines (Painéis/SARR)
                · cotas (TEXT × DIM conforme lado)
                · vermelho = só candidato / azul = só gabarito
   Humano/web: SVG na ficha / CE

5. Visão com grounding (se ainda houver dúvida)
   Dynamic patching PAREADO (mesmo bbox nos dois lados), faixa de cotas separada
   Saída forçada JSON: dim_labels[] + bounding_box
   Código faz set-diff — LLM não “julga se parece ok”

6. Só então PASS | FAIL | SUSPEITO
```

### 3.1 O que NÃO é validação

| Anti-padrão | Porquê falha |
|-------------|--------------|
| “Li o N4 e as cotas estão legíveis” | Não prova ⊆ N2 |
| “Ladrilho r0c2 limpo” só no N4 | Patching unilateral |
| `msp.query('DIMENSION')` no N2 LV | Lista vazia ≠ sem cotas |
| Score / contagem de entidades | Não captura `40,2` inventado |
| Overlay só de linhas sem layer de cotas | Miss de rótulo |

---

## 4. Normalização de cotas

```text
"50,5" → 50.5
"40"   → 40
"40,2" → 40.2
"<>" + measurement → usar measurement
tol valor match: 0.2 cm
own-face: -1 ≤ x_insert ≤ width_face + 1
fora → N2_CONTEXTO_VIZINHO_nao_copiar (não copiar, não é gap)
```

---

## 5. Classificação de LINEs residual

Nem todo MISSING_N4 é bug do motor:

| Classe | Exemplo V301.A | Ação |
|--------|----------------|------|
| `TICK_DIAG` (L≈4,24 @ 45°) | cantos de cota no layer Painéis | **não copiar** |
| `H_PARCIAL` coberto por H contínua | 408–427 quando existe 408–449 | OK se full existe |
| `SARR_SUBSEGMENTO` | 294–301 ⊂ 244–398 @ y=65 | OK se long MATCH |
| `STUB_ACIMA_MARCO` | V 424 de 124→142 | provável tick; não copiar |
| `N2_VOID_JUNK` | lixo abaixo do corpo | não copiar |
| `N2_CONTEXTO_VIZINHO` | geometria do item ao lado | não copiar |
| **MISSING estrutural real** | divisor de painel, ombro, marco | **corrigir motor** |

---

## 6. Política do motor LV (P) alinhada a R

Em `scripts/gerar_lv_dxf_stog.py` (`draw_lv_face`):

1. **`_panel_widths_for_horizontal_dims`** — exclui painéis da zona de marco (estreitos finais) da cadeia de cotas horizontais.  
   Geometria do marco **continua**; some só o rótulo inventado (`40,2`).
2. **`group_panel_dims`** — agrupa estreitos consecutivos do **corpo** (estilo N2 `50,5`).
3. **Cota intermediária** se ≥3 grupos — resto após o 1º grupo (N2 `161,5` = 50,5+111).
4. **Sem `dim_total` cego** da face unit (N2 costuma não ter `445,7`).
5. **Divisor de marco** em dois trechos (corpo + extensão), como o N2.

---

## 7. Ferramentas (reuso)

| Uso | Path |
|-----|------|
| Inventário + trace V301 | `scripts/arete/tmp/_v301_n2_inventory.py` |
| Set-diff estrutural | `scripts/arete/tmp/_v301_struct_diff.py` |
| Overlay camadas lines/cotas | `scripts/arete/tmp/_v301_diff_overlay.py` |
| Pack HTML+SVG revisão | `scripts/arete/tmp/_v301_final_review_html.py` |
| Vision PNG pareado | `scripts/arete/tmp/_v301_vision_compare.py` |
| Gate genérico de rótulos | `scripts/arete/gate_n2_n4_fidelidade.py` |
| Motor LV | `scripts/gerar_lv_dxf_stog.py` |

Saídas típicas:  
`scripts/arete/relatorios/g2v/v301_n2_inventory/`  
(`trace_n2_n4_faceA.json`, inventários MD/JSON).

---

## 8. Checklist rápido do agente (copiar)

```text
[ ] Paths N2 e N4 resolvidos (DB + DXF gerado)
[ ] Origem face (x0,y0,h,widths) fixada
[ ] Inventário R: EXTRA_N4 cotas == 0
[ ] Inventário R: MISSING own-face cotas == 0
[ ] Inventário G: EXTRA estrutural == 0 (ignorando ticks)
[ ] Overlay lines + cotas regenerado pós-fix
[ ] PNG N2×N4 lido (agente) OU SVG (humano)
[ ] Nenhuma cota justificada só por "a geometria tem essa largura"
[ ] Veredito PASS só com inventário + evidência
```

---

## 9. Evidência V301.A (2026-07-18)

| Métrica | Antes | Depois |
|---------|-------|--------|
| EXTRA cotas N4 | `40,2`, `445,7` | **0** |
| Cotas own-face N2 | 161,5 missing; 40 matched errado a 40,2 | **todas MATCH / POS_OFF** |
| EXTRA lines N4 | V 424,5 contínuo 0→124 | **0** (split corpo+marco) |
| Cadeia horizontal N4 | 244\|50,5\|111\|**40,2** + total | **244\|50,5\|111\|161,5** |

Residual MISSING_N4 de linhas = ticks diagonais, H parciais cobertas, subsegmentos SARR, stub acima do marco — **não** inventário de cotas.

---

## 10. Inventário geométrico de reprodução (coordenadas totais)

Para **reprodução 100%** (não só PASS de inventário semântico), cada entidade
precisa de coordenadas em cm:

| Entidade | Campos obrigatórios |
|----------|---------------------|
| LINE / segmento | `abs{x1,y1,x2,y2}` + `rel{…}` + `orient` + `length_cm` + `flags` |
| Cota N2 TEXT | `insert_abs/rel` + `measurement_cm` + `content` + `height` + `rotation_deg` |
| Cota N4 DIMENSION | `p1_rel` + `p2_rel` + `text_mid_rel` + `measurement_cm` + `defpoints{}` |
| Hatch | `bbox_rel` + `pattern` |

**Flags:** `must_reproduce` | `void_junk` | `context_neighbor` | `tick` | `dim_geometry`

**Ferramenta:**

```bash
py -3 scripts/arete/inventario_geometria_fidelidade.py \
  --n2 <recorte_N2.dxf> --n4 <N4_VIEW_A.dxf> \
  --face A --label V301.A \
  --origin-n2 x,y --origin-n4 0,-259 \
  --h-body 109 --widths 244,28.7,21.8,111,19,21.2 \
  --out scripts/arete/relatorios/g2v/v301_reproducao
```

**Saídas:**

| Arquivo | Uso |
|---------|-----|
| `ledger_n2_faceA.json` | todas as entidades N2 com coords |
| `ledger_n4_faceA.json` | todas as entidades N4 com coords |
| `recipe_n2_faceA.json` | **só `must_reproduce`** — receita de replay |
| `trace_reproducao_faceA.json` | MATCH/MISSING/EXTRA com Δcm |
| `reproducao_faceA.md` | tabela humana |

Regra de ouro da reprodução:

```text
N4_must ≈ recipe_n2.must_reproduce
  (mesmo rel em cm, tol ≤ 1.0 cm endpoints / 0.15 cm valor de cota)
```

O motor heurístico (`gerar_lv_dxf_stog`) aproxima a recipe; o alvo final é
**replay da recipe** (ou diff zero na recipe) — não “parecer igual no PNG”.

---

## 11. Changelog

| Data | Mudança |
|------|---------|
| 2026-07-18 | Protocolo G/R/P; caso 40,2; patch motor LV; gate de inventário. |
| 2026-07-18 | Inventário geométrico de reprodução (`inventario_geometria_fidelidade.py`). |
| 2026-07-18 | Escopo explícito **N2·N3·N4** (mesma técnica); ver pipeline anti-alucinação. |
