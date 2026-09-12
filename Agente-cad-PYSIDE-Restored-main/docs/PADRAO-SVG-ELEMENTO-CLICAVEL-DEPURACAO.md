# Padrão — SVG por elemento clicável para depuração N2×N4

**Status:** validado na prática — sessão V301/LV, 2026-09-08.
**Onde nasceu:** `scripts/arete/_build_segments_html_v301.py` (ficha de revisão
`V301_SEGMENTS_E2E.html`, servida por `scripts/arete/servidor_revisao_pil.py`).
**Motivação (dono):** anotações do tipo "essa linha aqui está errada" exigiam
que o agente recalculasse posição por pixel/porcentagem toda vez — sem
relação direta entre o que o dono aponta e a entidade real do DXF/o trecho de
código que a desenhou.

---

## 1. Ideia central

Em vez de renderizar o recorte DXF como **raster** (PNG via matplotlib —
o que a ficha fazia antes), cada entidade do DXF (`LINE`, `LWPOLYLINE`,
`HATCH`, `TEXT`/`MTEXT`, `DIMENSION`) vira **seu próprio elemento SVG** no
DOM, com atributos `data-*` que apontam de volta pra origem real:

```html
<g id="s6n4-16" data-layer="COTA" data-type="HATCH" data-handle="7C9"
   data-pattern="AR-CONC" class="dxf-el dxf-hatch">
  <path d="M ..." fill="url(#pat-s6n4-0)" .../>
</g>
```

Quando o dono clica numa linha e diz "essa aqui" — ou marca um ponto de
incoerência — o clique carrega `layer`/`type`/`handle`/`texto`/`comprimento`
direto, sem eu ter que adivinhar coordenada. Isso fechou o ciclo
achado→correção em várias rodadas desta sessão (ver §5).

---

## 2. Contrato técnico

### 2.1 Gerador (`render_dxf_clip_svg`)

Implementado em `scripts/arete/_build_segments_html_v301.py`. Lê o DXF com
`ezdxf`, itera `msp` dentro de uma janela de clip (+ padding), e emite SVG
**à mão** (sem passar pelo `Frontend`/`MatplotlibBackend` do ezdxf, que não
expõe id por entidade):

- Coordenada: `fy(y) = -y` (flip simples, sem `transform` — texto sai
  upright porque só o ancoramento do ponto é espelhado, não o glyph).
- `viewBox` cobre exatamente a janela de clip; sem pré-cálculo de pixel.
- Cor: `ezdxf.colors.aci2rgb` no ACI da entidade (se != BYLAYER/BYBLOCK) ou
  do layer (`_layer_color_map`, cacheado por doc).
- Cada entidade emitida via `emit()`: `<g id=... data-layer=... data-type=...
  data-handle=...>`, classe `dxf-el dxf-{tipo}`.
- `DIMENSION` é decomposto via `entity.virtual_entities()` (linhas +
  MTEXT/TEXT), herdando layer/cor do dimension pai quando o filho vem em
  `'0'`/BYBLOCK.
- `HATCH`: `is_solid = e.dxf.solid_fill`; se **não** for solid_fill, usa um
  `<pattern>` de verdade (diagonal 45° pra ANSI31-like, pontilhado pra
  AR-CONC) em vez de preenchimento sólido translúcido — ver §5, erro #1.

### 2.2 Área de clique maior que a linha visível ("ímã")

Linha real (`stroke-width="0.6"`, `vector-effect="non-scaling-stroke"`) fica
fininha de propósito. Por baixo dela, uma segunda linha **invisível**
(`stroke="transparent"`, `stroke-width="12"`, `pointer-events:stroke`) no
mesmo `<g>` capta o clique/hover numa faixa ~6× mais larga. `:hover` no CSS
mira `.dxf-el:hover line,...` — como o filtro de glow só aparece na linha
visível, o efeito "acende ao passar perto" funciona mesmo a alguns px de
distância.

### 2.3 Pan/zoom por viewBox

Mesma tecnologia do `docs/PADRAO-SVG-WEB-PANZOOM-VIEWBOX.md` (wheel = zoom
ancorado no cursor via `getScreenCTM().inverse()`, drag = pan, botão
"reset zoom", duplo-clique = reset). Implementado em `initSvgPanZoom(wrap)`
no `<script>` da própria ficha — não reaproveita `initPanZoom`/
`initPilPanZoom` porque esta ficha não tem o layer duplo (SA+agêntico) que
aqueles resolvem; se um dia precisar de multi-layer aqui, migrar pra lá.

### 2.4 Clique só marca ponto em cima de elemento real

```js
if((wrap._dragMoved||0)>4) return;           // foi pan, não clique
const target = e.target.closest('.dxf-el');
if(!target) return;                          // fundo vazio: nao marca nada
```

Sem isso, qualquer clique no SVG (inclusive em vazio estrutural genuíno)
virava ponto — o dono pediu explicitamente pra só contar clique em cima de
algo real.

### 2.5 Elemento já marcado trava e vai pro fundo

```js
function markPicked(target){
  if(!target||target.classList.contains('dxf-picked')) return;
  target.classList.add('dxf-picked');
  if(target.parentNode) target.parentNode.prepend(target);
}
```
+ CSS `.dxf-el.dxf-picked *{pointer-events:none!important}`.

Sem isso, o elemento já anotado ficava por cima (última posição na ordem de
pintura do DXF) e sua faixa de clique de 12px continuava competindo com
vizinhos empilhados no mesmo lugar — o dono não conseguia selecionar o que
estava embaixo. `markPicked` é chamado tanto no clique novo quanto no
`renderDots` (restauração de pontos salvos), então o estado sobrevive a
reload.

### 2.6 Ponto acompanha o elemento, não a tela

O ponto salvo guarda `element.id`; `renderDots` procura o elemento vivo por
esse id em cada render e recalcula `x/y` (fração da wrap) a partir do
`getBoundingClientRect()` dele. Assim o marcador segue o elemento durante
pan/zoom e continua correto entre regenerações (enquanto o id apontar pra
algo existente — se a entidade sumir na nova geração, cai no fallback do
`x/y` salvo).

---

## 3. Onde reutilizar

| Precisa de... | Reaproveitar |
|---|---|
| SVG por elemento com `data-*` a partir de um DXF | `render_dxf_clip_svg` (copiar pattern, não reinventar solid-fill) |
| Pan/zoom viewBox simples (sem multi-layer) | `initSvgPanZoom` nesta ficha |
| Pan/zoom viewBox com layer SA+agêntico | `initPanZoom` (FV) / `initPilPanZoom` (PIL) — `PADRAO-SVG-WEB-PANZOOM-VIEWBOX.md` |
| Ponto de anotação humano ligado a uma entidade real | `markPicked` + `data-handle`/`data-layer`/`data-type` no clique |

Se outra classe (PIL/FV/LAJ) quiser o mesmo "aponta e sabe o que é",
portar `render_dxf_clip_svg` + o bloco de JS (pan/zoom, click handler,
`markPicked`, `renderDots`) em vez de recriar do zero.

---

## 4. Quando usar SVG-por-elemento vs PNG raster

- **Ficha de revisão por segmento** (poucos elementos por card, precisa
  clique/anotação): SVG por elemento.
- **Visão geral/overview** (recorte inteiro, dezenas de ocorrências): manter
  PNG (matplotlib). Um SVG com centenas de `<g>` + `<pattern>` por card
  começou a estourar o compositor do headless browser usado pra QA (ver
  §5, erro #4) — igual valeria pra um humano com hardware fraco.

---

## 5. Erros registrados (não repetir)

| # | Erro | Sintoma | Fix |
|---|---|---|---|
| 1 | `HATCH` de padrão (ANSI31/AR-CONC) desenhado como preenchimento sólido translúcido | Duas hachuras adjacentes (cores iguais, ambas `color=7`) viravam um "bloco cinza" só, dono achou que a correção "piorou" | `<pattern>` de verdade (diagonal/pontilhado) via `<defs>`, não fill sólido |
| 2 | Clique conta mesmo se veio de um drag (pan) | Arrastar pra mover a imagem virava ponto de anotação indesejado | Medir `_dragMoved` acumulado no `mousemove`; só conta clique se `<=4px` |
| 3 | Elemento já marcado continua clicável e por cima | Dono clicava querendo selecionar o vizinho e reacertava o mesmo elemento de sempre | `markPicked`: trava (`pointer-events:none` nos filhos) + manda pro início do `<g>` pai (pinta primeiro = fica atrás) |
| 4 | SVG com muitos `<pattern>`/`filter` empilhados na página inteira | Screenshot do browser headless (Claude Browser pane) parava de compositar frames ao rolar — sintoma: print volta preto sólido, `getComputedStyle` do elemento continua correto | Não é bug da página — é o compositor do headless não renderizar aba fora de foco/scroll pesado. Validar por **medição DOM** (`getBoundingClientRect`, `%` de largura) quando o screenshot falhar, não insistir cegamente no print |
| 5 | Assumir posição de hachura por inferência (`marco_h_min + marco_h_base` sempre aditivo) em vez de medir a entidade real do N2 | Fix "certo" pra um caso (V301.B#1, gap real de 18,8cm) quebrou outro (V301.B nominal, gap de ruído ~4cm) | Só tratar como faixa aditiva separada quando a diferença entre os dois sinais for grande (>8cm); perto disso é o mesmo dado com ruído — usar o valor base puro |

O erro #5 não é do SVG em si, mas foi **encontrado através dele** — é o
argumento prático de por que esse padrão vale a pena: sem o clique
apontando pro handle exato (`7C9`, `COTA`, `AR-CONC`), a causa raiz (que
morava em `gerar_lv_dxf_stog.py`, três camadas de código adiante do que
estava na tela) teria sido muito mais lenta de achar.

---

## 6. Checklist de PR / agente

- [ ] Cada entidade relevante do DXF virou `<g data-layer data-type
      data-handle>` individual, não um blob de path único
- [ ] Hit-area de linha fina tem faixa invisível mais larga (ímã), sem
      engordar a linha visível
- [ ] Clique só marca ponto se `e.target.closest('.dxf-el')` existir
- [ ] Elemento marcado trava (`dxf-picked`) e vai pro início do `<g>` pai
- [ ] Hachura de padrão usa `<pattern>`, nunca fill sólido translúcido
      genérico pra qualquer tipo de hachura
- [ ] Pan/zoom por viewBox (nunca CSS `transform: scale`) — ver
      `PADRAO-SVG-WEB-PANZOOM-VIEWBOX.md`
- [ ] Se o screenshot do browser falhar, validar por medição DOM antes de
      insistir/desistir

---

*Registro de desenvolvimento — padrão de depuração visual DXF↔SVG.*
