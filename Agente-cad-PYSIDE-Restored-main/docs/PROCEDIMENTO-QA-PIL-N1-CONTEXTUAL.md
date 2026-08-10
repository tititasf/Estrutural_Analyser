# Procedimento QA — PIL N1 contextual + looping de destaque agêntico

**Classe:** PIL (pilares)  
**Espelho de:** `docs/PROCEDIMENTO-QA-FV-N1-CONTEXTUAL.md` +  
`docs/PROMPT-LOOPING-DESTAQUE-AGENTICO-FV-PARA-PIL.md`  
**Pack típico:** `scripts/arete/html_fichas/{obra}/{pav}_*_pilares_abcd/`  
**Servidor:** `python scripts/arete/serve_abcd_fichas.py --latest --open`  
→ `http://127.0.0.1:18765/pilares/P2.html`  

**Viewer SVG:** pan/zoom **viewBox** (não CSS scale) —  
`docs/PADRAO-SVG-WEB-PANZOOM-VIEWBOX.md` · ref FV `fv_hifi_n1_render.initPanZoom`.  

**Tags do destaque agêntico:** `docs/PADRAO-TAGS-DESTAQUE-AGENTICO-PIL.md`  
(CLI `pil_agentic_highlight_draw.py` ou export `--with-agentic`).

---

## 1. Duas camadas (não misturar custo)

| Camada | UI | Custo |
|--------|-----|--------|
| **Destaque SA** (vermelho) | interpretação do **motor** (tabelas ABCD + N1 com marco) | alto |
| **Destaque agêntico** (ciano/verde P#) | proposta geométrica do agente no N1 SVG | baixo (JSON/SVG) |

**Regra de ouro:** enquanto o humano não marcar **Destaque agêntico = Validou**,  
**não** fechar fix grande no motor SA/PIL. Só redesenhar P#.

---

## 2. Loop operacional (ordem fixa)

```
1. Export pack ABCD com N1 SVG (próximo + distante) + chrome QA
2. Abrir via serve_abcd_fichas (não file://)
3. Agente analisa N1 próximo + tabelas ABCD (sem inventar com N2/N3/N4)
4. Preenche Anotação agêntica (Agente validou/invalidou + texto)
5. Se invalidou: propose-draw → propostas/{P}_qa_proposta.svg|json
6. Humano: toggle SA | Agêntico | Ambos
7. Humano: validadores compactos (SA / Agêntico) + textarea atenção
8. Agente REFATORA só o desenho P# até humano Validou no agêntico
9. Só então: plano de fix no motor → reenrich → re-export
10. Humano marca Destaque SA Validou (ou nova rodada)
```

---

## 3. UI da ficha

### N1
- Abas: **N1 próximo** | **N1 distante**
- No **próximo**: toolbar **Destaque SA | Agêntico | Ambos**
- Base sempre **SVG** (não PNG) para overlay P#

### Anotação humana (esquerda)
- 🔴 Destaque SA → Validou | Invalidou  
- 🔵 Destaque agêntico → Validou | Invalidou  
- Textarea atenção  

### Anotação agêntica (direita)
- Agente validou | Agente invalidou  
- Textarea obrigatório  

### Chaves (`aten_pil_*`)

```
aten_pil_ctx_human_{obra}_{pav}_{pilar}
aten_pil_ctx_agent_{obra}_{pav}_{pilar}
aten_pil_ctx_agent_verdict_{obra}_{pav}_{pilar}
aten_pil_hl_sa_human_{obra}_{pav}_{pilar}
aten_pil_hl_agent_human_{obra}_{pav}_{pilar}
```

### Persistência
1. `localStorage`  
2. `#pil-notes-store` no HTML  
3. POST `/api/notes/{P}` → `pilares/{P}.notes.json`  
4. Agregado `atencao_notas.json` no pack  

---

## 4. Artefatos de proposta

```
{pack}/propostas/{PILAR}_qa_proposta.svg
{pack}/propostas/{PILAR}_qa_proposta.json
```

JSON mínimo:

```json
{
  "item": "P2",
  "class": "PIL",
  "proposed": [
    {"label": "1", "role": "face_A_chega", "points": [[x,y],...], "note": "..."}
  ]
}
```

CLI:

```bash
py -3.12 scripts/arete/qa_pil_n1_contextual_pipeline.py write-agent \
  --pack .../13_PAV_..._pilares_abcd --item P2 --verdict invalidou --text "..."

py -3.12 scripts/arete/qa_pil_n1_contextual_pipeline.py propose-draw \
  --pack ... --item P2 --json proposta.json

py -3.12 scripts/arete/qa_pil_n1_contextual_pipeline.py read-notes \
  --pack ... --item P2
```

**HI-FI:** a proposta ideal reutiliza o mesmo SVG estrutural do N1 SA  
(linhas DXF + contorno). SVG só de polígonos no preto = insuficiente  
(lição FV §1.5).

---

## 5. Checklist QA (extremista no N1)

1. Contorno do pilar bate com DXF.  
2. Faces A–D / lajes / passa / chega / interior coerentes.  
3. Dualidade AC↔CA, BC↔CB.  
4. d.esq/d.dir da faixa de topo (não confundir seção 19/66 com banda N–S).  
5. Tags/líderes no elemento certo.  
6. Dono do erro: motor face_beams / abcd_tables / enrich / UI.

---

## 6. Packs de 10

Não auditar 46 de uma vez: pack 1 (P1–P10) → atenções → ajuste agêntico  
→ (opcional) motor → pack 2.

Código de suporte:
- `src/core/pil_qa_notes_chrome.py`
- `scripts/arete/export_pilares_abcd_fichas.py`
- `scripts/arete/serve_abcd_fichas.py`
- `scripts/arete/qa_pil_n1_contextual_pipeline.py`
- `scripts/arete/_audit_abcd_pack.py`

---

*Alinhado ao padrão FV 2026-07; chaves e paths PIL isolados de FV.*
