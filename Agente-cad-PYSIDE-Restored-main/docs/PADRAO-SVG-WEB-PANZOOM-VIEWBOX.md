# Padrão canônico — SVG web com pan/zoom (viewBox)

**Status:** OBRIGATÓRIO para qualquer ficha HTML / CLI Arete / portal que mostre N1 ou recorte estrutural em SVG.  
**Aprovado (dono):** 2026-07-31 — looping PIL + referência FV V302.  
**NÃO negociar:** zoom por CSS `transform: scale` é **proibido** (pixeliza).

---

## 1. Regra de ouro

| Correto | Errado |
|---------|--------|
| Pan/zoom **alterando o `viewBox`** do SVG | `transform: scale()` / `zoom` CSS no container |
| SVG `width/height: 100%` no viewport fixo | Bitmap re-escalado ou CSS scale no inner |
| Vetor nítido em qualquer zoom | Blur/pixelização ao dar zoom |

**Prova de referência (canônica FV):**  
`http://127.0.0.1:8765/fundos_viga/V302.html`  
Implementação: `src/ui/widgets/fv_hifi_n1_render.py` → `initPanZoom` / `PANZOOM_VIEWBOX_JS`.

**PIL (mesmo contrato):**  
`src/core/pil_qa_notes_chrome.py` → `initPilPanZoom`  
Fichas: `scripts/arete/export_pilares_abcd_fichas.py` + `serve_abcd_fichas.py`

---

## 2. Contrato técnico

### 2.1 Container
```html
<div id="{cid}" class="…-panzoom" data-panzoom="1" style="height:560px;overflow:hidden;cursor:grab">
  <button type="button" data-pz-reset="{cid}">Reset zoom</button>
  <div class="…-panzoom-inner" style="position:absolute;inset:0">
    <!-- 1+ SVGs HI-FI -->
    <svg viewBox="0 0 W H" preserveAspectRatio="xMidYMid meet"
         style="width:100%;height:100%;display:block">…</svg>
  </div>
</div>
```

### 2.2 Comportamento JS (obrigatório)
1. Ler `viewBox` home do SVG ativo: `{x,y,w,h}`.
2. **Wheel:** recalcular `w/h` com fator ~0.88/1.14, âncora no cursor (`clientToSvg` via `getScreenCTM().inverse()`), atualizar `viewBox`.
3. **Drag:** delta em coordenadas SVG (não pixels CSS), subtrair de `x/y`.
4. **Reset / dblclick:** restaurar home.
5. **Nunca** aplicar `style.transform = scale(...)` no inner para zoom.

### 2.3 Dual layer (SA + Agêntico)
- Ambos HI-FI matplotlib costumam ser `viewBox="0 0 W H"` → classe **`fv-sync-vb` / `pil-sync-vb`** e **mesmo viewBox** no pan/zoom.
- Proposta CAD com viewBox distinto: sincronizar **relativamente** (razão de zoom + offset normalizado) — ver `applyAgentRelative` no FV.
- Ao carregar SVG de proposta via `fetch`, rodar `_prep*Svg` e `outer._pzApply()`.

### 2.4 Prep de todo SVG embutido
```
remove width/height attributes
style width/height 100%
preserveAspectRatio = xMidYMid meet
dataset.homeVb = viewBox inicial
class sync se viewBox começa com "0 0 "
```

---

## 3. Onde reutilizar (não reinventar)

| Domínio | Módulo / viewer |
|---------|-----------------|
| **FV HI-FI N1** | `src/ui/widgets/fv_hifi_n1_render.py` (`wrap_panzoom_viewer`, `initPanZoom`) |
| **PIL ABCD / agêntico** | `src/core/pil_qa_notes_chrome.py` (`initPilPanZoom`, `wrap_n1_panzoom`, `n1_layer_toggle_and_layers`) |
| **Export PIL** | `scripts/arete/export_pilares_abcd_fichas.py` |
| **Servir fichas PIL** | `scripts/arete/serve_abcd_fichas.py` |
| **Servir FV** | `scripts/arete/tmp/fv_notes_server.py` |
| **Portal / web** | Preferir o mesmo contrato viewBox; se o portal tiver viewer próprio, **não** voltar a CSS scale |

### CLIs Arete
Qualquer novo HTML gerado por:
- `export_pilares_abcd_fichas.py`
- `pil_agentic_highlight_draw.py` (SVG de proposta deve ser **SVG real**, não PNG)
- preficha / `headless_sa_analise.py` com SVG no HTML
- pipelines `qa_*_n1_contextual*`

**deve** usar pan/zoom viewBox (copiar FV ou `pil_qa_notes_chrome`, não inventar CSS scale).

---

## 4. Erro registrado (não repetir)

| Erro | Sintoma | Fix |
|------|---------|-----|
| CSS `transform: scale` + `translate` no inner | Zoom “pixelado”, blur | viewBox pan/zoom FV |
| SVG sem viewBox / width fixo em px | Zoom quebra ou distorce | garantir viewBox + 100% |
| SA e agent com viewBox em espaços diferentes sem sync | Layers “descolam” ao pan | `*-sync-vb` ou relative sync |
| Agente julga em SVG web zoomado | Fora do contrato vision | Agente lê **PNG** full-render; humano usa SVG (`QA-VISAO-EVIDENCIA-CANONICA.md`) |

---

## 5. Checklist de PR / agente

- [ ] Viewer HTML de SVG usa **viewBox**, não CSS scale  
- [ ] Botão Reset zoom + wheel + drag + dblclick  
- [ ] Dual layer (se houver) sincronizado  
- [ ] Proposta agêntica = SVG vetorial (DXF/HI-FI), não raster “falso SVG”  
- [ ] Docs / CLAUDE apontam este padrão  

---

## 6. Preferência de desenvolvimento (memória)

> **Preferência do dono (2026-07-31):**  
> Todos os viewers SVG web do CAD-ANALYZER (fichas Arete, FV, PIL, futuros LAJ/LV)  
> devem copiar a tecnologia do **FV V302** (`initPanZoom` por viewBox).  
> Qualquer CLI que gere ficha HTML com N1 SVG **herda** este padrão.  
> CSS scale para zoom = regressão proibida.

Relacionado:
- `docs/LOOPING-AGENTICO-INTERPRETACAO-PILARES-ABCD.md`
- `docs/PROCEDIMENTO-QA-PIL-N1-CONTEXTUAL.md`
- `docs/PROCEDIMENTO-QA-FV-N1-CONTEXTUAL.md`
- `docs/QA-VISAO-EVIDENCIA-CANONICA.md` (PNG agente vs SVG humano)

---

*Registro de desenvolvimento — padrão UI web SVG pan/zoom.*
