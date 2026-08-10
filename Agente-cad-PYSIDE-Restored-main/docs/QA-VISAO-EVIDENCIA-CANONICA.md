# QA — Visão canónica de evidência (nível de qualidade obrigatório)

**Status:** canónico (2026-07-17, rev. dual-mode PNG/SVG)  
**Aplica-se a:** **todo agente** (humano ou AI) e a **todas as classes** PIL / LAJ / FV / LV  
em **qualquer etapa** que use visão: N1-V, G2-V, G4-V, G5-V, review de ficha HTML,
Comparison Engine, harness CLI, inventário geométrico, **portal web**.

**Complementa:**  
`docs/QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md`,  
`docs/ARETE-PLAYWRIGHT-QA-VISUAL.md`,  
`docs/LOOPING-CANONICO.md`,  
`docs/VISION-VALIDACAO-CAMINHOS.md`,  
`scripts/arete/g2v_harness.py`,  
manuais `docs/SA-ANALISE/CLASSES/{PIL,LAJ,FV,LV}.md`.

---

## 1. Princípio (não negociável)

> **Validação visual sem a profundidade deste documento é ruído, não validação.**

Score, contagem de entidades, plot filtrado de LINEs, “parece igual”, overlay
aproximado ou checklist genérico **sem** evidência visual de profundidade
**não** autorizam PASS, selo, promoção RAG nem fechamento de gate.

Se o agente não consegue ver o que o humano vê no Comparison Engine (ou
equivalente render full do DXF), o veredito é **inválido** por construção.

---

## 2. Dual-mode: PNG para agente · SVG para humano/web/app

Quase todos os LLMs multimodais (Claude, GPT, Gemini, Grok, …) **veem raster**
(PNG/JPEG). SVG no CLI costuma falhar como “visão”. Por isso:

| Consumidor | Formato | Porquê |
|------------|---------|--------|
| **Agente CLI** (Grok/Claude/Codex/…) | **PNG** (render full layers do DXF, 150–160 dpi) | ferramenta Read/vision lê pixels |
| **Humano no desktop / CE** | DXF nativo ou HTML+**SVG** | zoom e camadas |
| **App PySide (fichas persistidas)** | HTML com **SVG** embutido | zoom, DOM, cotas selecionáveis |
| **Portal web / formulários** | HTML com **SVG** embutido | zoom e visualização no browser |

### 2.1 Headless **sem** `--persist-db` (loop dinâmico / agente)

- Objetivo: feedback rápido, iteração, visão do agente.
- Entregável mínimo: **PNG** (ou pack vision lado a lado) do recorte N2 e do N4/N3.
- SVG **não** é obrigatório neste modo (pode omitir para ser dinâmico e barato).
- Continua obrigatório: profundidade visual (full layers no render, não plot LINE-only)
  + inventário mínimo se for fechar PASS.

```text
headless_sa_analise.py ... --secao ... --item ... --wait
  (sem --persist-db)
→ imagens PNG para o agente ler com vision
→ opcional: inventário JSON em relatorios/
```

### 2.2 Headless **com** `--persist-db` (popular app / HTML oficial)

- Objetivo: materializar estado na app e no HTML de curadoria.
- Entregável **completo**: ficha HTML + **SVG** nos cards N1–N4 + DXF + diagnósticos.
- PNG de snapshot pode existir como anexo; **não** substitui o SVG no HTML.

```text
headless_sa_analise.py ... --secao ... --item ... --persist-db --wait
→ pack html_fichas com SVG inline (uso humano + app)
```

### 2.3 Portal web / solicitações via formulário

- Sempre **SVG incluído** no artefacto entregue ao utilizador web (zoom/visualização).
- Se o pipeline também servir o agente, gerar **também** PNG de vision a partir do
  mesmo DXF (não em vez do SVG).

### 2.4 G2-V / N1-V / G5-V (gates visuais S/G)

| Quem julga | O que materializar | Como ler |
|------------|--------------------|----------|
| Agente CLI | PNG render full (N2×N4 ou par do gate) + manifesto | `Read` nos PNG |
| Humano / harness HTML | SVG da ficha ou DXF→SVG | browser / DOM |
| Harness `g2v_harness --backend cli` | continua a exportar SVG da ficha; **agente deve rasterizar ou usar pack PNG vision** antes do veredito | não declarar PASS só “olhei o path do SVG” sem pixels |

Ordem FAIL-closed (todas as classes):

```text
1. Resolver path N2 (DB) e path N3/N4
2. Materializar evidência:
   - modo agente / headless sem persist → PNG full-render
   - modo persist / portal / HTML app → SVG (+ PNG opcional)
3. Inventário mínimo (ids + status)
4. gate0 geométrico se aplicável
5. Agente: Read nos PNG | Humano: SVG/CE
6. Checklist + inventario.path + confianca
7. Só então PASS|FAIL|SUSPEITO
```

---

## 3. O que é “evidência visual de profundidade” (conteúdo)

Independente de PNG ou SVG, o **conteúdo** tem de ser full-render:

| Camada | Obrigatório | Proibido tratar como N2/N3/N4 |
|--------|-------------|------------------------------|
| **Todas as camadas relevantes** | Painéis, SARR*, COTA/TEXT, Hachura/REAPROVEITAMENTO, frames | extract só `Painéis`+`SARR` |
| **Mesmo ficheiro-fonte** | `recorte_path` do DB / DXF N4 gerado | path “parecido” |
| **Âncora explícita** | crop/bbox da parte (face A, CIMA, segmento) | origem aleatória |
| **Inventário mínimo** | LINE/cota/texto com status | só contagem |

### 3.1 N2 (gabarito reverso)

- Fonte: `reverse_eng_recortes.recorte_path` (`_sel_` > `_motor_`).
- CE (fluxo reverso): DXF FULL — autoridade visual humana.
- Plot LINE-only = audit interno; prefixo obrigatório  
  `extract_geom (Painéis+SARR only) — NÃO é CE`.

### 3.2 N3 / N4

- DXF gerado + render full.
- LV: `VIEW_A` / `VIEW_B` / `CORTE` separados.

---

## 4. Etapas (gates G / S) — todas as classes

| Etapa | Par | Agente lê | Persist/app/web |
|-------|-----|-----------|-----------------|
| N1-V / G4-V | N1×N2 | PNG do par | SVG na ficha se persist |
| G2-V | N2×N4 | PNG N2×N4 | SVG se ficha/portal |
| G5-V | N3×N4 | PNG do par | SVG se ficha/portal |
| Review CE | qualquer | — (humano no CE) | DXF nativo |
| Portal form | entrega | — | **SVG obrigatório** |

---

## 5. Mecanismos (reutilizar)

| Uso | Ferramenta |
|-----|------------|
| Harness gates | `scripts/arete/g2v_harness.py --backend cli` |
| PNG vision (agente) | DXF→PNG full (ex. `scripts/arete/tmp/_v301_vision_compare.py`) |
| SVG (humano/web) | `dxf_to_svg_casos.render` / ficha HTML com SVG inline |
| Headless único | `scripts/arete/headless_sa_analise.py` |
| Inventário | `docs/QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md` |

---

## 6. Anti-padrões

1. PASS sem o agente ter lido **PNG** (ou raster equivalente) no modo CLI.  
2. Headless com `--persist-db` **sem** SVG nas fichas HTML.  
3. Portal web **sem** SVG (só PNG).  
4. Chamar de N2 um extract LINE-only.  
5. Confundir botão **Para/Passa** com **PASS** visual.  
6. Aprovar por score/contagem.

---

## 7. Por classe

| Classe | Manual (secção visão) |
|--------|------------------------|
| LV | `docs/SA-ANALISE/CLASSES/LV.md` |
| PIL | `docs/SA-ANALISE/CLASSES/PIL.md` |
| FV | `docs/SA-ANALISE/CLASSES/FV.md` |
| LAJ | `docs/SA-ANALISE/CLASSES/LAJ.md` |
| Todas | `docs/SA-ANALISE/CLASSES/README.md` |

---

## 8. Changelog

| Data | Mudança |
|------|---------|
| 2026-07-17 | Criado (SVG-first após divergência V301). |
| 2026-07-17 | Dual-mode: **PNG para agente**; **SVG para persist/app/web/portal**; headless sem persist = imagem dinâmica. |
