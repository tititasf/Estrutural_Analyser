# Arete — QA visual das fichas granulares N1/N2/N3/N4

Como depurar rapidamente pilares/fundos de viga/lajes comparando as 4
evidências (N1 estrutural, N2 recorte humano, N3 robô via N1, N4 robô via N2)
— e o bug de renderização Playwright que precisa ser contornado quando algum
script tira screenshot dessas fichas.

## 0. Visão canónica + inventário — pré-requisito de validação válida

**Validação sem esta profundidade é ruído, não validação.**  
Documento mestre: [`docs/QA-VISAO-EVIDENCIA-CANONICA.md`](QA-VISAO-EVIDENCIA-CANONICA.md).

**Antes** de marcar ficha como ok, emitir veredito G2-V/G5-V ou selar item:

0. Materializar evidência de profundidade (DXF full layers, não plot LINE-only):
   - **Agente CLI:** **PNG** (Read/vision) — ver dual-mode em
     `QA-VISAO-EVIDENCIA-CANONICA.md`.
   - **HTML app / `--persist-db` / portal web:** **SVG** embutido (zoom humano).
   - Headless **sem** persist: pode ser só imagem (dinâmico).
1. Extrair o **inventário mínimo** do gabarito (N2) e do candidato (N3/N4):
   cada LINE estrutural, cada cota (valor+posição), cada texto de identidade.
2. Rastrear MATCH / NEAR / MISSING / EXTRA / VOID_JUNK — não só contagem.
3. Anexar path do inventário no veredito (`inventario.path`) e no bloco da ficha.
4. Agente: **ler os PNGs** com vision; humano: SVG/CE. Preencher checklist.

Sem inventário **ou** sem raster lido pelo agente (modo CLI), o PASS é **inválido**
(`g2v_harness.validar_veredito_cli`).

Inventário (schema):  
[`docs/QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md`](QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md).

LV (exemplo V301): N2 no CE = recorte `LV_*_motor_*.dxf` com hatch/cotas;
cotas no N2 costumam ser `TEXT`; N4 usa `DIMENSION`. Botão **Passa** no CE =
Para/Passa estrutural, **não** veredito visual.

Checklist obrigatório inclui: `inventario_minimo_extraido`,
`sem_aprovacao_por_contagem`, e em LV também
`linhas_estruturais_rastreadas`, `cotas_valores_rastreados`,
`textos_identidade_rastreados`.

> **Atualização 02/07/2026:** desde essa data os 4 cards de LAJ/PIL/FV são
> `<svg>` inline (não mais `<img>` PNG base64) — ver
> `docs/ARETE-LOOP-PROCEDIMENTO-GERAL.md` §5.1. Isso soma uma **terceira via**
> de leitura, além das duas descritas abaixo: extrair texto exato via DOM,
> sem gastar visão nem tirar screenshot —
> `page.eval_on_selector('svg.img-geo', "svg => Array.from(svg.querySelectorAll('text')).map(t => t.textContent)")`.
> Use DOM para rótulos/cotas exatos; reserve screenshot (abaixo) para
> julgamento visual genuíno (hachura, contorno, cruzamento de linha). Tudo
> que este doc descreve sobre medir `.main-wrap`/`.evidence-grid` continua
> valendo igual — a técnica de screenshot é agnóstica a `<img>` vs `<svg>`.

## Caminho mais rápido: triagem humana por checkbox (recomendado)

Ler dezenas de fichas ficha-a-ficha consome muito tempo/tokens de agente e é
mais lento que a pessoa que já conhece a obra bater o olho. Por isso toda
ficha granular de laje (`lajes/{nome}.html`) termina com um bloco
**"Marcação de erro (revisão humana)"** como último campo da página:

- checkbox **"Marcar esta ficha como ERRADA"**
- campo de texto livre para descrever o problema (ex: "N1 não destaca a laje
  certa", "N3 sem os 4 painéis que o N2 mostra")

Isso é salvo automaticamente em `localStorage` a cada mudança — não precisa
clicar em nada para persistir.

**Pegadinha:** `localStorage` não fica gravado no arquivo `.html` — fica
guardado no *perfil do navegador* que abriu o arquivo (é uma origem única no
Chromium, `location.origin === "file://"` para qualquer `.html` local, então
todas as fichas de um mesmo diretório compartilham a mesma gaveta). Se você
abrir com seu navegador padrão e o Claude tentar ler com um Playwright "do
zero", ele abre um perfil vazio e não vê nada — não é um bug do HTML, é assim
que `localStorage` sempre funciona.

A solução é usar `scripts/arete/qa_error_review.py`, que abre e relê sempre o
**mesmo perfil fixo em disco** (`scripts/arete/.qa_profiles/{obra}_{run}/`),
tanto para a janela que você usa quanto para a releitura do Claude depois.

### Fluxo de trabalho

1. Peça para o Claude rodar (ou rode você mesmo):
   ```bash
   D:/Agente-cad-PYSIDE/.venv/Scripts/python.exe scripts/arete/qa_error_review.py open \
       --dir "scripts/arete/html_fichas/Obra_TREINO_1/{RUN}/lajes"
   ```
   Isso abre uma janela de navegador de verdade (visível, maximizada). O
   comando fica bloqueado até você fechar a janela — normal.
2. Navegue pelas fichas nessa janela (links `próx. →`/`← anterior` da
   sidebar). Nas que estiverem erradas: marque o checkbox e escreva o motivo
   — salva sozinho, sem precisar clicar em nada.
3. Feche a janela quando terminar. O comando `open` retorna sozinho.
4. Peça para o Claude ler (ou rode você mesmo):
   ```bash
   D:/Agente-cad-PYSIDE/.venv/Scripts/python.exe scripts/arete/qa_error_review.py read \
       --dir "scripts/arete/html_fichas/Obra_TREINO_1/{RUN}/lajes"
   ```
   Isso reabre o mesmo perfil (headless, invisível) e lista tudo que foi
   marcado — sem exportar nada manualmente, sem copiar/colar JSON.

O perfil é fixo por obra/pavimento (não pelo timestamp do run), então
marcações sobrevivem mesmo que as fichas sejam regeneradas depois.

Esse mesmo padrão (`aten_erro_{classe}_{obra}_{pav}_{nome}` como chave de
`localStorage`, prefixo `aten_erro_` lido por `qa_error_review.py`) pode ser
estendido para pilares e fundos de viga se for útil — hoje só está
implementado em `preficha_laje_html.py` (`_error_marker_block`).

## Caminho alternativo: screenshot + leitura por agente

Quando não há revisão humana prévia (ex: conferência exploratória de um lote
novo, ou quando o próprio Claude precisa auditar do zero), use captura via
Playwright + leitura de imagem.

### Quando usar o quê

| Tipo de HTML | Função | Script |
|---|---|---|
| Relatório tabular largo, uma página só (`preficha_*.html` — tabela com N linhas) | `capture_html_pages()` | `scripts/arete/playwright_loop.py` |
| Ficha granular por item (`pilares/{CLASSIF}/{nome}.html`, `fundos_viga/{slug}.html`, `lajes/{nome}.html` — sidebar + navegação + cards N1/N2/N3/N4 empilhados) | `capture_granular_item_pages()` | `scripts/arete/playwright_loop.py` |

As fichas granulares são geradas por `_write_pilar_pages` (dentro de
`src/ui/widgets/pre_validation_dialog.py`), `preficha_fundo_html.py` e
`preficha_laje_html.py`. Todas seguem o mesmo padrão de layout: sidebar +
`.main-wrap{overflow:auto;height:100vh}` contendo `.main-content`, dentro do
qual há 4 `.evidence-card` empilhados verticalmente num `.evidence-grid`
(título N1/N2/N3/N4, selo disponível/ausente, legenda, imagem base64). O
conteúdo de `.main-wrap` costuma passar de 2500-4000px de altura.

### O bug: paint-culling do Chromium headless em páginas altas de 2 colunas

Ao tirar screenshot de um elemento (`locator.screenshot()`) ou até da página
inteira (`page.screenshot(full_page=True)`) numa página cujo conteúdo real
excede muito o viewport, o Chromium headless pode **não pintar** trechos que
nunca estiveram dentro do viewport — mesmo com as imagens já carregadas
(`img.complete && naturalHeight>0`). Os sintomas variam:

- PNG do tamanho certo mas com blocos pretos/vazios nas seções abaixo da
  dobra original;
- ou (mais sutil, achado numa 2ª rodada) um PNG aparentemente ok mas com a
  barra de navegação sticky "vazando" para dentro do recorte, com a seção N1
  em branco acima dela — sintoma de Playwright fazendo *stitching* de tiles
  de viewport insuficiente.

**Armadilha ao medir a altura real:** essas páginas usam layout de 2 colunas
(`.sidebar` + `.main-wrap{overflow:auto;height:100vh}`). Isso torna
`document.documentElement.scrollHeight` **auto-referente** — como os filhos
do `<body>` (flex-row) ficam limitados a `100vh`, o `scrollHeight` do
documento reporta basicamente a altura do viewport atual (~800px), não a
altura real do conteúdo. Usar esse valor para redimensionar o viewport
"corrige" páginas curtas por coincidência e falha silenciosamente nas mais
longas. A medição correta é o `scrollHeight` do **container que realmente
tem o scroll**, `.main-wrap`:

```python
height = page.evaluate(
    "(() => {"
    "  const w = document.querySelector('.main-wrap');"
    "  return Math.max(w ? w.scrollHeight : 0, document.documentElement.scrollHeight);"
    "})()"
)
page.set_viewport_size({"width": 1000, "height": min(int(height) + 100, 32000)})
page.wait_for_timeout(150)   # deixa o repaint assentar
page.locator(".evidence-grid").screenshot(path=out_path)
```

Isso já está encapsulado em `capture_granular_item_pages()` — não é preciso
reimplementar isso manualmente numa próxima rodada de QA. **Se outro tipo de
ficha granular usar um container de scroll diferente de `.main-wrap`, ajuste
o seletor medido ou os screenshots voltam a sair incompletos.**

### Uso rápido (CLI)

```bash
# Ambiente oficial: D:\Agente-cad-PYSIDE\.venv (já tem playwright + chromium instalados)
D:/Agente-cad-PYSIDE/.venv/Scripts/python.exe scripts/arete/playwright_loop.py \
    --granular-dir "scripts/arete/html_fichas/Obra_TREINO_1/{RUN}/lajes" \
    --granular-out "test_output/lj_qa_screenshots"
```

Ou como módulo, para filtrar/pós-processar:

```python
from pathlib import Path
from scripts.arete.playwright_loop import capture_granular_item_pages

results = capture_granular_item_pages(
    Path("scripts/arete/html_fichas/Obra_TREINO_1/{RUN}/fundos_viga"),
    out_dir=Path("test_output/fv_qa_screenshots"),
    recursive=False,   # fundos_viga/lajes são flat; pilares usa recursive=True (subpastas por classificação)
)
```

### Como interpretar os screenshots (protocolo de auditoria N1/N3)

Fonte de verdade primordial = **N2** (recorte humano). Fonte de verdade de
desenho já validada = **N4** (robô via engenharia reversa do N2).

- **N1 diverge** se o segmento/laje destacado em N1 (Structural Analyzer) não
  corresponde ao mesmo elemento mostrado em N2: geometria muito diferente,
  rótulo de texto mais próximo do destaque não bate com o nome do item desta
  ficha, card "ausente" enquanto N2 está disponível, ou imagem sem o destaque
  esperado (sem `SEGMENTO FV`/preenchimento colorido).
- **N3 diverge** de **N4**: número de painéis diferente, furos
  presentes/ausentes de forma diferente, comprimento/dimensões nas cotas
  muito diferentes, ou card "ausente" enquanto N4 está disponível.
- Diferenças de cor de fundo (N1/N2 = escuro, N3/N4 = branco) são esperadas e
  **não** contam como divergência — são só o estilo de cada camada.
- **Achado recorrente (2026-07-02, lote Obra_TREINO_1/13_PAV):** vários N4 de
  lajes mostram paleta antiga (nome ciano, cotas magenta, sem hatch cinza de
  união) enquanto o N3 irmão já usa a paleta nova (nome branco, cotas
  vermelhas, hatch cinza sólido) — não é erro de dado, é artefato **N4
  desatualizado em disco** que não foi regenerado após a migração de estilo
  visual das lajes. Selecionar o item de novo no Comparison Engine força a
  regeneração.

Depois de gerar os PNGs, leia cada um com a ferramenta `Read` (a imagem
inteira cabe numa leitura só) e monte duas listas: itens com N1 divergente e
itens com N3 divergente, com o motivo.

## Leitura em lote via Browser pane (g2v_harness --backend cli)

Quando o próprio agente CLI (Claude Code) precisa ler os SVGs exportados por
`g2v_harness.py --backend cli` (veredito visual G2-V/G5-V) usando a ferramenta
de Browser pane (não Playwright standalone), **não navegue e tire screenshot
item a item** — isso gasta 1 `navigate` + 1 `screenshot` por SVG (2-3 SVGs por
item = 4-6 chamadas de ferramenta por item, ~140-210 chamadas para 35 itens).
Confirmado (16/07, lote PIL n3xn4, 35 itens) que agrupar em uma página HTML
local reduz isso para ~1 chamada por item, sem perder resolução nem leitura
granular:

1. Gerar uma página HTML por lote de ~7-10 itens, servida pelo mesmo
   `python -m http.server` que já serve a pasta de saída do harness. Cada item
   vira um bloco empilhado verticalmente com rótulo + tag por estágio
   (`N3`/`N4` ou `N1`/`N2`), `<img src="ITEM_estagio.svg" style="width:660px">`
   — largura fixa por estágio, nunca lado a lado (perde resolução).
2. `resize_window` para viewport estreito (`700x1000`) — a screenshot do
   Browser pane é limitada a ~800px de largura; um viewport largo (ex.
   1400px) é reamostrado para caber nesse limite e a imagem perde nitidez.
   Com 700px de largura o viewport bate 1:1 com a screenshot, sem downscale.
3. `navigate` uma vez para a página do lote, depois `computer{action:scroll,
   scroll_amount:10}` + `screenshot` repetidamente. Cada scroll de amount 10
   avança ~1400px (calibrar por item real; usar `javascript_tool` para ler
   `window.scrollY` e o `offsetTop` de cada `.label` se precisar confirmar que
   nenhum item ficou só parcialmente visível entre dois screenshots).
4. Registrar o veredito de cada item assim que ele aparece inteiro na tela,
   sem esperar terminar o lote inteiro — mantém a leitura granular por item
   (mesmo julgamento individual de sempre, só a captura de tela é que virou
   lote).

Cuidados que já causaram erro numa rodada real:
- Um `screenshot` pode devolver um frame **obsoleto** logo após um scroll
  grande (visto no lote 26-34: um screenshot mostrou P26/P27 quando
  `window.scrollY` já estava perto do fim do documento). Sempre que o conteúdo
  não bater com a posição esperada, confirme `window.scrollY` via
  `javascript_tool` antes de seguir — e vá para trás para reler o trecho
  pulado, não assuma que "já viu" um item só porque o scroll passou por ele.
- `zoom` (crop de região) não é suportado no Browser pane — não peça zoom pra
  ler um cabeçalho pequeno; ou aumente a largura da imagem (`style="width:
  2400px"` numa página só com aquele SVG) ou aceite a resolução do lote.

## Ambiente

- Playwright só está instalado no `.venv` oficial do projeto
  (`D:/Agente-cad-PYSIDE/.venv/Scripts/python.exe`), não no Python 3.12 do
  `AppData` usado por `headless_sa_analise.py`. Use o `.venv` para os scripts
  de QA visual.
- Browsers do Playwright já instalados nesse `.venv`
  (`chromium-1228` em `C:\Users\Thierry\AppData\Local\ms-playwright\`).
