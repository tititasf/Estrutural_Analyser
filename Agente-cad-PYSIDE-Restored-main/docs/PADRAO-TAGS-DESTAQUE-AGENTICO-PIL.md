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

## 2. Contrato de qualidade (falha fechada)

Uma camada só pode receber **PASS técnico** quando todos os eixos abaixo passam.
Eles têm a **mesma importância**: acertar o vínculo não compensa errar o ponto;
acertar a geometria não compensa nome, dimensão ou papel incorretos.

| Gate | Pergunta obrigatória |
|------|----------------------|
| **G1 — geometria do pilar** | O contorno e a orientação pertencem ao pilar nomeado? Em pilar especial, cada face física foi reconhecida sem completar a caixa envolvente? |
| **G2 — semântica** | Laje, `V.chega`, `V.passa` e `V.interior` estão classificados corretamente? |
| **G3 — vínculo** | Nome, face e canto correspondem à entidade CAD correta e a um vizinho físico possível? |
| **G4 — conteúdo** | Tipo, marca, nome, dimensão e nível vêm da mesma entidade, sem texto aleatório ou mistura entre SVGs/camadas? |
| **G5 — ponto** | A ponta da seta obedece integralmente ao §5? |
| **G6 — legibilidade** | Chip, seta e ponto são distinguíveis, não encobrem o contato e não criam linhas geométricas falsas? |
| **G7 — evidência visual** | O PNG da camada foi lido e confrontado com geometria e ficha? PASS de sidecar/JSON sozinho não aprova. |

Qualquer falha acima mantém o item **pendente** e gera uma nova camada somente para
esse item. O agente nunca altera o veredito humano nem reabre itens humanos já
validados sem uma regressão comprovada.

---

## 3. Cores por face (inalteráveis)

| Face | Parede (linha) | Chip / seta / texto de viga |
|------|----------------|-----------------------------|
| **A** | `#ffeb3b` amarelo | `#ff9800` laranja |
| **B** | `#81c784` verde claro | `#1b5e20` verde escuro |
| **C** | `#9c27b0` roxo | `#f48fb1` rosa |
| **D** | `#4fc3f7` azul claro | `#0d47a1` azul escuro |
| **E** (especial) | `#ff8a65` coral | `#ff8a65` coral |
| **F** (especial) | `#80cbc4` turquesa | `#80cbc4` turquesa |

- Laje: chip na **cor da parede** da face.  
- Passa/chega/interior: chip e seta na **cor de texto** da face.  
- Contraste do texto dentro do chip: claro se fundo escuro, escuro se fundo claro.

---

## 4. Chip (tag) — conteúdo, forma e tipografia

### 4.1 Identidade e conteúdo (antes de desenhar)

- `nome`, `dim` e `nivel` devem vir da **mesma entidade** associada ao vínculo.
- A dimensão é canônica (`largura/altura`, sem concatenação acidental com nome ou ID).
- O papel mostrado é exatamente um entre `laje`, `V.chega`, `V.passa` e
  `V.interior`; corrigir papel não autoriza trocar silenciosamente a viga.
- A marca começa pela face proprietária da linha: uma linha de A usa `AC`, `AD` ou
  `AA`; a reciprocidade física é explícita (`AC` e `CA` apontam o mesmo vértice).
- É proibido inventar abreviações, reaproveitar glifos de outra camada ou montar
  nomes a partir de IDs internos. Colisão de namespace SVG é **FAIL G4**.
- Um vínculo aparece uma vez por papel+face+canto. Duplicação, canto não adjacente
  ou duas marcas fundidas em um chip são **FAIL G3/G4**.

### 4.2 Visual
- Chip **mini** arredondado (`round`, pad pequeno ~0.10–0.14).  
- Pilar retangular: contorno branco fino (`#ffffff`, linewidth ~0.35) é permitido.  
- Pilar especial/denso: usar `stroke="none"` para o chip. O contorno do chip nunca
  pode parecer uma face, viga ou prolongamento geométrico.  
- Fundo opaco ~0.92–0.94.  
- **Sem** moldura branca grossa; **sem** CSS scale no viewer.  
- Texto embutido como **path** no SVG (`svg.fonttype=path`) para sempre aparecer.  
- IDs de glifos e demais `<defs>` devem receber **namespace único por página + camada**
  antes de a camada ser exibida. Toda referência `<use href="#…">` deve resolver
  dentro do próprio SVG; colisão entre SA/L1/L2/L3 é falha fechada, pois troca letras
  e produz nomes aparentemente aleatórios mesmo quando o texto-fonte está correto.  
- Fonte compacta (~1.7–2.5 pt path); **não** voltar a pills enormes.  
- Fonte interna das tags usa escala canônica `1.10` (aumento de 10% sobre o
  tamanho anterior); espaçamento de linhas e caixa crescem na mesma proporção.  
- Anti-overlap: stack + gap; tags **fora** da parede do pilar.  
- Roteamento `non_crossing_v1`: a posição final só é aceita quando o chip não
  sobrepõe outro chip e o segmento seta→ponto não cruza conectores existentes.
  Na primeira tentativa também é proibido atravessar outro chip; se a proximidade
  entre pontos tornar isso impossível, preservam-se obrigatoriamente chips
  separados e **zero cruzamento linha–linha**.  
- Dois conectores podem apenas compartilhar o mesmo ponto físico final; isso não
  é cruzamento. Tags permanecem inteiras dentro do viewBox, com margem óptica.  
- z-order alto: tags por cima do DXF (rebaixar artists do estrutural).

### 4.3 Quebra de linha (obrigatória)

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

## 5. Geometria da seta e do ponto (regra normativa)

| Tipo | Onde fica o pontinho |
|------|----------------------|
| **V.passa** | **Vértice físico exato** compartilhado pelas duas faces da marca. `AC=CA`, `AD=DA`, `BC=CB`, `BD=DB`; em especial vale o mesmo para todo par adjacente A–F. |
| **V.chega** | **Centro transversal da viga que chega**. Em retangular: meio do span na face com deslocamento externo de `0,9 × largura do contato`. Em pilar especial A–F: centro do contorno estrutural efetivo `viga_fundo_seg_*` mais próximo no eixo transversal, **exatamente sobre a linha de contato com a face**, sem deslocamento normal; o `bbox` geral da entidade é apenas fallback quando não houver contorno efetivo. Nunca usar a esquina só porque a marca é `AC/BC/...`. |
| **V.interior** | **Centro da parede** da face |
| **laje** | **Centro do contato** laje–parede (meio do span na face) |

- Bolinha com o tamanho atual **dobrado**: retangular `markersize=1.4` e
  `markeredgewidth=0.3`; especial `r=0.8` e `stroke-width=0.28`.  
- Seta **fina** (`lw` ~0.4, ponta pequena).  
- Setas e bolinhas **não** competem com o chip: chip compacto; seta/bolinha estáveis.
- A seta termina no ponto; não termina no texto, no meio do vazio ou em outra viga.
- Tags recíprocas de uma `V.passa` podem compartilhar o mesmo ponto físico. Isso é
  correto e não deve ser "desempilhado" deslocando o ponto para fora da esquina.

### 5.1 Pilares retangulares A–D

- Vertical: A=esquerda, B=direita, C=cima, D=baixo.
- Horizontal: A=baixo, B=cima, C=esquerda, D=direita.
- Somente a orientação muda; a marca sempre representa a interseção real das duas
  faces. `DA` é o mesmo vértice de `AD`, e `DB` o mesmo de `BD`.
- Uma `V.passa` em A/B pode ser a marca do vértice de uma viga colinear à face
  curta C/D. O selfcheck classifica como **CONVENÇÃO geométrica**, desde que nome,
  canto e contato colinear coincidam; o ponto continua no vértice exato.

### 5.2 Pilares especiais em L A–F

- O contorno real deve ter seis segmentos físicos. A–F são atribuídos a esses
  segmentos; é proibido desenhar A–D sobre a caixa envolvente retangular.
- A marca só pode combinar faces que compartilham um endpoint real do polígono.
- `V.passa` aponta para esse endpoint exato; `V.chega` aponta para o centro da viga
  incidente; `V.interior` para o meio do segmento; laje para o meio do contato.
- Linhas coloridas são responsabilidade das faces A–F. Tags acrescentam somente
  chip, seta e ponto — nunca uma segunda "parede" ou guia retangular falsa.
- Toda linha de destaque fica **exatamente sobre** a linha física do pilar:
  offset CAD zero. No retangular usa-se o próprio contorno; no especial A–F a
  transformação é calibrada pelo polígono vermelho já renderizado no SVG, nunca
  por margem/viewBox aproximados.

---

## 6. Protocolo obrigatório de revisão QA

Para cada item ainda pendente, e para cada camada proposta:

1. Confirmar identidade e contorno do pilar antes de interpretar tags.
2. Conferir a ficha/sidecar e a entidade CAD: papel, nome, dimensão, nível, face e canto.
3. Conferir exclusividade e reciprocidade: sem duplicações e sem cantos impossíveis.
4. Conferir visualmente **cada ponta** no PNG, incluindo chega, passa, interior e laje.
5. Conferir roteamento: zero linhas cruzadas, zero chips sobrepostos e nenhum chip
   cortado. Em especial A–F, `connector_crossings` deve ser lista vazia.
6. Conferir chip e namespace SVG (texto correto, sem glifos/nome aleatórios).
7. Só então registrar PASS técnico; o humano continua sendo o responsável pelo
   veredito final na ficha.

Ao corrigir uma regra, executar testes universais e regenerar apenas os itens
pendentes afetados. É proibido substituir a fórmula por exceção de P26/P27/P49 ou
qualquer outro nome de item.

---

## 7. Como gerar (CLI e HTML)

### 7.1 Export (caminho principal — SA+tags SEMPRE)

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

### 7.2 CLI de re-desenho

```bash
py -3.12 scripts/arete/pil_agentic_highlight_draw.py \
  --pack scripts/arete/html_fichas/Obra_TREINO_1/<ts>_pilares_abcd \
  --items P1 P2 …
```

### 7.3 Motor SA (app PySide)?

| | CLI / HTML Arete | App SA (Qt) |
|--|------------------|-------------|
| Tabelas ABCD | sim | sim |
| N1 SA **com tags** | **sim (export)** | canvas Qt ainda sem chips |
| Toggle 3 camadas | sim (ficha HTML) | não |

---

## 8. Artefatos

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

## 9. Checklist anti-regressão

- [ ] SA N1 **sempre** com tags no export (sem depender de flag)  
- [ ] Tag multilinha: tipo+marca / nome / dim / nível  
- [ ] Um canto por tag (nunca `AC-AD`)  
- [ ] Nome, dimensão, nível, papel, face e canto pertencem à mesma entidade  
- [ ] Sem duplicação e sem combinação de faces não adjacentes  
- [ ] Passa → ponto no **vértice físico exato**  
- [ ] Chega → ponto no **centro transversal da viga**  
- [ ] Interior → centro da face; laje → centro do contato  
- [ ] Retangular respeita orientação A–D e reciprocidade dos quatro vértices  
- [ ] Especial em L usa seis segmentos A–F, sem guias da caixa envolvente  
- [ ] Linhas de face coincidem com o contorno CAD (offset zero)  
- [ ] Todas as bolinhas usam 2× o tamanho da revisão anterior (`1.4` / `r=0.8`)  
- [ ] Fonte das tags em `1.10×`, incluindo line-height e caixa  
- [ ] `routing_policy=non_crossing_v1`; zero cruzamentos seta–seta  
- [ ] Chips separados e inteiros dentro do viewBox  
- [ ] Chip não cria contorno geométrico falso; path/namespace SVG íntegros  
- [ ] `document.body.dataset.pilSvgIdsOk === "1"`; zero IDs duplicados e zero
      referências de glifo não resolvidas entre SA/L1/L2/L3  
- [ ] L1/L2/L3 gerados; toggle uma camada por vez  
- [ ] Viewer pan/zoom **viewBox**  
- [ ] Cores A–F conforme §3  
- [ ] PNG revisado visualmente; sidecar PASS isolado não aprova  
- [ ] Veredito humano preservado  

---

*Atualizado 2026-08-18 — contrato QA uniforme, pontos chega/passa e pilares especiais A–F.*
