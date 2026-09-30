# Padrão canônico — tags do destaque PIL (SA + camadas QA)

**Status:** obrigatório para **SA motor** e **camadas agênticas L1/L2/L3**.  
**Código:** `scripts/arete/pil_agentic_highlight_draw.py` (`render_agentic_svg`)  
**Loop:** `docs/LOOPING-AGENTICO-INTERPRETACAO-PILARES-ABCD.md`  
**Viewer SVG:** `docs/PADRAO-SVG-WEB-PANZOOM-VIEWBOX.md` (pan/zoom só viewBox)  
**Espelho FV:** V303 — SA + 3 camadas (`fv_hifi_n1_render.py`)

---

## 1. Onde entra no sistema

| Camada | Responsável | Tags |
|--------|-------------|------|
| **Motor SA (N1)** | `export` → `render_agentic_svg(layer="sa")` | **sempre** (não opcional) |
| **Ag.L1 / L2 / L3** | mesmo render com `layer=l1|l2|l3` | mesmas tags; banner diferente |
| **Tabelas ABCD** | `pillar_abcd_tables` | numérico (fonte dos chips) |
| **HTML** | `pil_qa_notes_chrome` toggle SA\|L1\|L2\|L3 | uma camada visível |

```bash
# Export já gera SA+tags + L1/L2/L3 (sem flag)
py -3.12 scripts/arete/export_pilares_abcd_fichas.py --project-id <id> …

# Re-desenho pontual
py -3.12 scripts/arete/pil_agentic_highlight_draw.py --pack <pack> --items P1 …
```

---

## 2. Cores por face (inalteráveis)

| Face | Parede (linha) | Chip / seta / texto de viga |
|------|----------------|-----------------------------|
| **A** | `#ffeb3b` amarelo | `#ff9800` laranja |
| **B** | `#81c784` verde claro | `#1b5e20` verde escuro |
| **C** | `#9c27b0` roxo | `#f48fb1` rosa |
| **D** | `#4fc3f7` azul claro | `#0d47a1` azul escuro |

- Laje: chip na **cor da parede** da face.  
- Passa/chega/interior: chip e seta na **cor de texto** da face.  
- Contraste do texto dentro do chip: claro se fundo escuro, escuro se fundo claro.

---

## 3. Chip (tag) — forma e tipografia

### 3.1 Visual
- Chip **mini** arredondado (`round`, pad pequeno ~0.10–0.14).  
- **Contorno branco fino** (`#ffffff`, linewidth ~0.35).  
- Fundo opaco ~0.92–0.94.  
- **Sem** moldura branca grossa; **sem** CSS scale no viewer.  
- Texto embutido como **path** no SVG (`svg.fonttype=path`) para sempre aparecer.  
- Fonte compacta (~1.7–2.5 pt path); **não** voltar a pills enormes.  
- Anti-overlap: stack + gap; tags **fora** da parede do pilar.  
- z-order alto: tags por cima do DXF (rebaixar artists do estrutural).

### 3.2 Quebra de linha (obrigatória)

**4 linhas** (omitir linha se campo vazio):

```
{tipo} {marca}
{nome}
{dim}
{nivel}
```

| Tipo | Linha 1 (tipo) |
|------|----------------|
| laje | `laje` |
| passa | `V.passa` |
| chega | `V.chega` |
| interior | `V.interior` |

**Marca (um único token por tag — nunca composto):**

| Situação | Marca |
|----------|--------|
| No canto | `AC` **ou** `AD` **ou** `BC` **ou** `BD` **ou** `CA` **ou** `CB` **ou** `DA` **ou** `DB` |
| Chega fora de esquina (meio da face) | `AA` / `BB` / `CC` / `DD` |
| Proibido | `AC-AD`, `BC/BD`, dois cantos na mesma tag |

**Exemplos:**

```
V.chega BC
VF301
19/66
852.19cm
```

```
V.passa AD
V309A
19/120
852.19cm
```

```
laje
L301
12
852.12cm
```

---

## 4. Pontinho de indicação (seta → contato)

| Tipo | Onde fica o pontinho |
|------|----------------------|
| **V.passa** | **Esquina** de contato (AC/AD/… um só) |
| **V.chega** | **Centro da viga que chega** (meio do trecho na face + leve offset para fora) — **não** na esquina do pilar |
| **V.interior** | **Centro da parede** da face |
| **laje** | **Centro do contato** laje–parede (meio do span na face) |

- Bolinha **miúda** (markersize ~1.4 ou menor).  
- Seta **fina** (`lw` ~0.4, ponta pequena).  
- Setas e bolinhas **não** competem com o chip: chip compacto; seta/bolinha estáveis.

---

## 5. Como gerar (CLI e HTML)

### 5.1 Export (caminho principal — SA+tags SEMPRE)

```bash
py -3.12 scripts/arete/export_pilares_abcd_fichas.py \
  --project-id <id> --obra Obra_TREINO_1 --pav 13_PAV --item P1 P2 …

py -3.12 scripts/arete/serve_abcd_fichas.py --dir <pack> --open
```

Gera **sempre**:
- N1 HTML com **SA motor + tags** (interpretação legível na hora)
- `propostas/{P}_sa_motor.svg` + `_qa_L1.svg` + `_qa_L2.svg` + `_qa_L3.svg`
- toggle SA | Camada 1 | 2 | 3 (espelho FV V303)

`--with-agentic` = **no-op** (legado).  
`--no-layers` = só SA tags (raro).

### 5.2 CLI de re-desenho

```bash
py -3.12 scripts/arete/pil_agentic_highlight_draw.py \
  --pack scripts/arete/html_fichas/Obra_TREINO_1/<ts>_pilares_abcd \
  --items P1 P2 …
```

### 5.3 Motor SA (app PySide)?

| | CLI / HTML Arete | App SA (Qt) |
|--|------------------|-------------|
| Tabelas ABCD | sim | sim |
| N1 SA **com tags** | **sim (export)** | canvas Qt ainda sem chips |
| Toggle 3 camadas | sim (ficha HTML) | não |

---

## 6. Artefatos

```
{pack}/
  pilares/{P}.html
  pilares/{P}.notes.json
  propostas/{P}_sa_motor.svg      # SA + tags (baseline motor)
  propostas/{P}_qa_L1.svg         # camada 1
  propostas/{P}_qa_L2.svg
  propostas/{P}_qa_L3.svg
  propostas/{P}_qa_proposta.svg   # alias L1
  propostas/{P}_qa_proposta.json
```

---

## 7. Checklist anti-regressão

- [ ] SA N1 **sempre** com tags no export (sem depender de flag)  
- [ ] Tag multilinha: tipo+marca / nome / dim / nível  
- [ ] Um canto por tag (nunca `AC-AD`)  
- [ ] Chega → pontinho no **centro da viga**  
- [ ] Contorno chip **branco fino**; path SVG  
- [ ] L1/L2/L3 gerados; toggle uma camada por vez  
- [ ] Viewer pan/zoom **viewBox**  
- [ ] Cores A–D conforme §2  

---

*Atualizado 2026-08 — SA tagged obrigatório + 3 camadas (FV V303).*

