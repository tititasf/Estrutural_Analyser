#!/usr/bin/env python3
"""
Script: create_interpretacao_docs.py
Gera os documentos HTML de gabarito de interpretação para todas as abas da preficha estrutural.
"""

import os

BASE_DIR = (
    "D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts/arete/"
    "html_fichas/Obra_TREINO_1/13_PAV_20260630_203509"
)

# ─── CSS compartilhado (extraído de interpretacao_abcd.html) ────────────────
SHARED_CSS = """  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #111; color: #ccc; font-family: 'Segoe UI', sans-serif; font-size: 13px; line-height: 1.5; }
  h1 { color: #4fc3a1; font-size: 18px; border-bottom: 2px solid #4fc3a1; padding-bottom: 6px; margin-bottom: 16px; }
  h2 { color: #7eb8f7; font-size: 14px; margin: 24px 0 8px; border-left: 3px solid #7eb8f7; padding-left: 8px; }
  h3 { color: #f0b840; font-size: 12px; margin: 16px 0 6px; }
  .page { max-width: 960px; margin: 0 auto; padding: 24px 20px; }
  .intro { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 6px; padding: 12px 16px; margin-bottom: 20px; color: #aaa; font-size: 12px; }
  .intro b { color: #4fc3a1; }

  /* ── Tabela de faces ── */
  table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 12px; }
  th { background: #1e1e1e; color: #4fc3a1; padding: 6px 10px; text-align: left; border-bottom: 1px solid #333; }
  td { padding: 5px 10px; border-bottom: 1px solid #222; vertical-align: top; }
  tr:hover td { background: #181818; }
  .lbl-A { color: #4fc3a1; font-weight: bold; }
  .lbl-B { color: #7eb8f7; font-weight: bold; }
  .lbl-C { color: #c47ef7; font-weight: bold; }
  .lbl-D { color: #f0b840; font-weight: bold; }

  /* ── Casos ── */
  .caso { background: #161616; border: 1px solid #2a2a2a; border-radius: 6px; padding: 14px 16px; margin: 12px 0; }
  .caso-title { font-size: 13px; font-weight: bold; color: #4fc3a1; margin-bottom: 8px; }
  .caso-body { display: flex; gap: 24px; flex-wrap: wrap; align-items: flex-start; }
  .caso-text { flex: 1; min-width: 200px; font-size: 12px; color: #aaa; }
  .caso-text ul { margin: 6px 0 0 16px; }
  .caso-text li { margin: 3px 0; }
  .caso-diag { flex-shrink: 0; }

  /* Diagrama ASCII melhorado */
  .ascii { background: #0d0d0d; border: 1px solid #222; border-radius: 4px; padding: 10px 14px; font-family: 'Courier New', Courier, monospace; font-size: 12px; line-height: 1.55; white-space: pre; color: #aaa; font-variant-ligatures: none; -webkit-font-feature-settings: 'liga' 0; font-feature-settings: 'liga' 0; letter-spacing: 0; }
  .ascii .viga { color: #7eb8f7; }
  .ascii .laje { color: #4fc3a1; }
  .ascii .pilar { color: #f0b840; }
  .ascii .faceC { color: #c47ef7; }
  .ascii .faceD { color: #f0b840; }
  .ascii .faceA { color: #4fc3a1; }
  .ascii .faceB { color: #7eb8f7; }

  .tag { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 10px; font-weight: bold; margin-left: 4px; }
  .tag-viga { background: #1a2030; color: #7eb8f7; }
  .tag-laje { background: #102010; color: #4fc3a1; }
  .tag-nulo { background: #222; color: #666; }

  .result-row { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
  .result-face { padding: 4px 10px; border-radius: 3px; font-size: 11px; font-weight: bold; border-left: 3px solid; }
  .rf-A { background: #122012; border-color: #4fc3a1; color: #4fc3a1; }
  .rf-B { background: #12122a; border-color: #7eb8f7; color: #7eb8f7; }
  .rf-C { background: #2a1228; border-color: #c47ef7; color: #c47ef7; }
  .rf-D { background: #2a1e10; border-color: #f0b840; color: #f0b840; }

  .rule-box { background: #0d1a0d; border: 1px solid #2a4a2a; border-radius: 4px; padding: 10px 14px; margin: 12px 0; font-size: 12px; }
  .rule-box .rule-title { color: #4fc3a1; font-weight: bold; margin-bottom: 6px; }

  hr { border: none; border-top: 1px solid #222; margin: 20px 0; }
  code { background: #1e1e1e; color: #e67; padding: 1px 4px; border-radius: 2px; font-size: 11px; }

  /* ── Carrossel de exemplos ── */
  .carousel { display: flex; flex-direction: column; gap: 0; }
  .carousel-slides { position: relative; }
  .carousel-slide { display: none; }
  .carousel-slide.active { display: block; }
  .slide-label {
    text-align: center; font-size: 10px; color: #555; margin-top: 4px;
    font-style: italic; letter-spacing: 0.03em;
  }
  .slide-label.real { color: #4fc3a1; }
  .carousel-nav {
    display: flex; align-items: center; justify-content: center;
    gap: 10px; margin-top: 8px;
  }
  .carousel-btn {
    background: #1e1e1e; color: #888; border: 1px solid #333;
    padding: 3px 14px; cursor: pointer; border-radius: 3px;
    font-size: 16px; line-height: 1; transition: background 0.15s;
    user-select: none;
  }
  .carousel-btn:hover { background: #2a2a2a; color: #ccc; }
  .carousel-btn:active { background: #333; }
  .carousel-counter {
    color: #555; font-size: 11px; min-width: 48px;
    text-align: center; font-variant-numeric: tabular-nums;
  }
  .carousel-img { max-width: 100%; border-radius: 4px; border: 1px solid #2a2a2a; display: block; }
  .slide-placeholder {
    background: #111; border: 1px dashed #2a2a2a; border-radius: 4px;
    padding: 28px 40px; text-align: center; color: #333; font-size: 11px;
    font-style: italic; min-width: 260px;
  }"""

# ─── JS compartilhado ───────────────────────────────────────────────────────
SHARED_JS = """<script>
function _carouselMove(id, dir) {
  const el = document.getElementById(id);
  const slides = el.querySelectorAll('.carousel-slide');
  const counter = document.getElementById(id + '-counter');
  let cur = Array.from(slides).findIndex(s => s.classList.contains('active'));
  slides[cur].classList.remove('active');
  cur = (cur + dir + slides.length) % slides.length;
  slides[cur].classList.add('active');
  counter.textContent = (cur + 1) + ' / ' + slides.length;
}
function prevSlide(id) { _carouselMove(id, -1); }
function nextSlide(id) { _carouselMove(id, +1); }
</script>"""

# ─── Helper ─────────────────────────────────────────────────────────────────

def html_doc(title, body_content):
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
{SHARED_CSS}
</style>
</head>
<body>
<div class="page">

  <p style="font-size:11px; color:#555; margin-bottom:16px;">
    <a href="../index.html" style="color:#7eb8f7; text-decoration:none;">&#8592; Voltar ao índice</a>
  </p>

{body_content}

</div>
{SHARED_JS}
</body>
</html>"""


def carousel(cid, slides):
    """slides = list of (label, html_content, is_real)"""
    total = len(slides)
    inner = ""
    for i, (label, content, is_real) in enumerate(slides):
        active = " active" if i == 0 else ""
        lbl_class = "slide-label real" if is_real else "slide-label"
        inner += f"""
            <div class="carousel-slide{active}">
{content}
              <div class="{lbl_class}">{label}</div>
            </div>"""
    return f"""<div class="carousel" id="{cid}">
          <div class="carousel-slides">{inner}
          </div>
          <div class="carousel-nav">
            <button class="carousel-btn" onclick="prevSlide('{cid}')">&#8249;</button>
            <span class="carousel-counter" id="{cid}-counter">1 / {total}</span>
            <button class="carousel-btn" onclick="nextSlide('{cid}')">&#8250;</button>
          </div>
        </div>"""


def placeholder():
    return '              <div class="slide-placeholder">— sem exemplo real ainda —</div>'


def caso(n, title, text_html, carousel_html):
    return f"""
  <div class="caso">
    <div class="caso-title">Caso {n} — {title}</div>
    <div class="caso-body">
      <div class="caso-text">
{text_html}
      </div>
      <div class="caso-diag">
        {carousel_html}
      </div>
    </div>
  </div>"""


# ════════════════════════════════════════════════════════════════════════════
# 1. laterais_viga/interpretacao_laterais.html
# ════════════════════════════════════════════════════════════════════════════

def build_laterais():
    body = """  <h1>Guia de Interpretação das Laterais de Viga — A/B e Para/Passa</h1>

  <div class="intro">
    <b>O que é isso?</b> Este documento é o gabarito visual da interpretação das laterais de viga
    (A = lado esquerdo, B = lado direito) e da posição do segmento (Para = extremo, Passa = interior).
    <br><br>
    <b>Como usar:</b> Consulte antes de avaliar qualquer ficha LV. A direção C→D define o que é
    esquerda (A) e direita (B). A posição do corte dentro da viga define Para vs Passa.
  </div>

  <!-- ═══════════════════════════════════════════════════════════ -->
  <h2>1. Convenção A/B e Para/Passa</h2>

  <h3>Lado A vs Lado B — visão de planta (topo)</h3>
  <div class="ascii"><span class="faceC">C (início da viga — ponto norte)</span>
         │
         ↓  direção C → D

<span class="faceA">A</span> ←──║══════════════════ Viga V10 ══════════════════║──→ <span class="faceB">B</span>
(oeste)    ←──────────────── 19/60 ────────────────→           (leste)
         │
<span class="faceD">D (fim da viga — ponto sul)</span>

<span class="faceA">A = esquerda olhando de C em direção a D</span>
<span class="faceB">B = direita  olhando de C em direção a D</span></div>

  <h3>Para vs Passa — posição do segmento na viga</h3>
  <div class="ascii">  PARA — extremo da viga (encosta em pilar ou parede):

     Pilar ████
     ████████████╦══════════════════════════════════════╗
                 ║         Viga V10 (segmento A-Para)   ║
     Pilar ████  ╚══════════════════════════════════════╝
     ████████████
                 ↑ aqui a viga PARA — encosta no pilar
         laje L301 só do lado oposto (direita)


  PASSA — ponto interior da viga (continua dos dois lados):

     ╔══════════════╦══════════════════╦══════════════╗
     ║  Viga V10   ║   ponto de corte  ║  Viga V10   ║
     ╚══════════════╩══════════════════╩══════════════╝
                    ↑ viga PASSA aqui — laje pode estar dos dois lados</div>

  <table>
    <tr><th>Conceito</th><th>Descrição</th><th>Quando ocorre</th></tr>
    <tr>
      <td><span class="lbl-A">A</span></td>
      <td>Lado esquerdo olhando de C para D</td>
      <td>Sempre definido pela orientação da viga</td>
    </tr>
    <tr>
      <td><span class="lbl-B">B</span></td>
      <td>Lado direito olhando de C para D</td>
      <td>Sempre definido pela orientação da viga</td>
    </tr>
    <tr>
      <td><b style="color:#c47ef7">Para</b></td>
      <td>Segmento no extremo — viga encosta em pilar/parede</td>
      <td>Extremo C ou D da viga</td>
    </tr>
    <tr>
      <td><b style="color:#f0b840">Passa</b></td>
      <td>Segmento interior — viga continua nos dois lados</td>
      <td>Ponto interno da viga (cruzamento, interseção)</td>
    </tr>
  </table>

  <!-- ═══════════════════════════════════════════════════════════ -->
  <h2>2. Casos de Interpretação</h2>"""

    # Caso 1 — A-Para
    c1_ascii = """              <div class="ascii"><span class="faceA">A-Para: extremo norte da viga encosta em pilar</span>

     Pilar ████████████
     ████████████████████╦══════════════════════════════╗
                         ║   Viga V10  (lado A-Para)    ║
     Pilar ████████████  ╚══════════════════════════════╝
     ████████████████████
                         ↑ C (extremo Norte = Para)
     <span class="laje">Laje L301 à direita (lado B)</span>
     <span class="tag-nulo">Lado A = nulo (pilar bloqueia)</span></div>"""

    c1 = caso(1, "A-Para — extremo C da viga encosta em pilar",
              """        <p>O segmento A-Para ocorre quando olhamos o lado A (<b>esquerdo C→D</b>)
        no ponto <b>C (extremo norte/início)</b> da viga, que encosta diretamente num pilar.</p>
        <ul>
          <li>Lado A fica <b>bloqueado pelo pilar</b> — sem laje → <span class="tag tag-nulo">nulo</span></li>
          <li>Lado B pode ter laje (depende do vão oposto)</li>
          <li>É o caso mais comum em vigas de borda junto ao núcleo de pilares</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-A">A = nulo (pilar)</div>
          <div class="result-face rf-B">B = L301</div>
        </div>""",
              carousel("lv1", [("Diagrama de referência", c1_ascii, False),
                                ("", placeholder(), False)]))

    # Caso 2 — B-Para
    c2_ascii = """              <div class="ascii"><span class="faceB">B-Para: extremo norte — lado B encosta em pilar</span>

     ╔══════════════════════════════╦████████████████████
     ║   Viga V10  (lado B-Para)    ║████████████ Pilar ████
     ╚══════════════════════════════╩████████████████████
                                    ↑ C (extremo Norte = Para)
     <span class="laje">Laje L301 à esquerda (lado A)</span>
     <span class="tag-nulo">Lado B = nulo (pilar bloqueia)</span></div>"""

    c2 = caso(2, "B-Para — extremo C da viga; lado B bloqueado por pilar",
              """        <p>Espelho do Caso 1: o lado B (<b>direito C→D</b>) no extremo C encosta em pilar.
        O lado A tem laje livre enquanto B fica nulo.</p>
        <ul>
          <li>Lado B = nulo — pilar bloqueia o lado direito</li>
          <li>Lado A = laje do vão esquerdo (L301 ou o que existir)</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-A">A = L301</div>
          <div class="result-face rf-B">B = nulo (pilar)</div>
        </div>""",
              carousel("lv2", [("Diagrama de referência", c2_ascii, False),
                                ("", placeholder(), False)]))

    # Caso 3 — A-Passa
    c3_ascii = """              <div class="ascii"><span class="faceA">A-Passa: ponto interior da viga</span>

     ╔════════════════════════╦════════════════════════╗
     ║   Viga V10 (trecho W)  ║   Viga V10 (trecho E)  ║
     ╚════════════════════════╩════════════════════════╝
                              ↑ ponto de cruzamento (Passa)
     <span class="laje">Lado A = Laje L301 (vão norte)</span>
     <span class="laje">Lado B = Laje L302 (vão sul) ou mesmo vão</span></div>"""

    c3 = caso(3, "A-Passa — ponto interior; viga continua dos dois lados",
              """        <p>No ponto interno da viga (Passa), a viga <b>não para</b> — continua além.
        O lado A vê o vão de laje imediatamente à esquerda deste ponto.</p>
        <ul>
          <li>Lado A = laje do vão que fica à esquerda do cruzamento</li>
          <li>Pode ser a mesma laje de B ou diferente (depende se outra viga divide)</li>
          <li>Nunca é nulo em Passa — há sempre espaço dos dois lados</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-A">A = L301</div>
        </div>""",
              carousel("lv3", [("Diagrama de referência", c3_ascii, False),
                                ("", placeholder(), False)]))

    # Caso 4 — B-Passa
    c4_ascii = """              <div class="ascii"><span class="faceB">B-Passa: ponto interior — lado direito</span>

     ╔════════════════════════╦════════════════════════╗
     ║   Viga V10 (trecho W)  ║   Viga V10 (trecho E)  ║
     ╚════════════════════════╩════════════════════════╝
                              ↑ ponto de cruzamento (Passa)
     <span class="laje">Lado B = Laje L302 (vão sul)</span>
     <span class="laje">Lado A = Laje L301 (vão norte)</span></div>"""

    c4 = caso(4, "B-Passa — lado direito do mesmo cruzamento interior",
              """        <p>Espelho do Caso 3 para o lado B. No mesmo ponto de Passa,
        o lado B vê o vão de laje à direita do cruzamento.</p>
        <ul>
          <li>Lado B = laje do vão à direita</li>
          <li>Se nenhuma outra viga divide o vão norte/sul → A = B = mesma laje</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-B">B = L302</div>
        </div>""",
              carousel("lv4", [("Diagrama de referência", c4_ascii, False),
                                ("", placeholder(), False)]))

    # Caso 5 — A-Para exterior
    c5_ascii = """              <div class="ascii"><span class="faceA">A-Para exterior: borda do edifício, sem laje</span>

     ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
       exterior (sem laje)                      │
     └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
     ╔══════════════════════════════════════════╗
     ║            Viga de borda V10             ║
     ╚══════════════════════════════════════════╝
     <span class="laje">Interior: Laje L301</span>

     <span class="tag-nulo">A = nulo (borda exterior sem laje)</span>
     <span class="laje">B = L301 (interior do edifício)</span></div>"""

    c5 = caso(5, "A-Para exterior — borda do edifício; lado A = nulo",
              """        <p>A viga está na <b>borda exterior</b> do edifício. O lado A fica voltado
        para fora — sem nenhuma laje. Mesmo sendo um Para, o nulo vem da ausência de laje,
        não de um pilar bloqueando.</p>
        <ul>
          <li>Lado A = <span class="tag tag-nulo">nulo</span> — exterior livre, sem laje</li>
          <li>Lado B = laje interior (L301)</li>
          <li>Ocorre nas vigas de fachada e beirais</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-A">A = nulo (exterior)</div>
          <div class="result-face rf-B">B = L301</div>
        </div>""",
              carousel("lv5", [("Diagrama de referência", c5_ascii, False),
                                ("", placeholder(), False)]))

    # Caso 6 — A-Passa com viga secundária
    c6_ascii = """              <div class="ascii"><span class="faceA">A-Passa com viga secundária cruzando</span>

     Viga NS (secundária)
     ║         ║
     ║  L301   ║  L302
     ║         ║
     ╔═════════╬════════════════════════════════╗
     ║ V10 W   ║         V10 E (continua)       ║
     ╚═════════╬════════════════════════════════╝
               ║  L303   ║   L304
               ║         ║
     Viga NS (secundária)

     <span class="laje">Ponto de Passa: 2 lajes diferentes cada lado da V-NS</span>
     <span class="faceA">A = L301</span>  (noroeste do ponto)
     <span class="faceB">B = L303</span>  (sudoeste do ponto)</div>"""

    c6 = caso(6, "A-Passa com interseção de viga secundária — dois vãos diferentes",
              """        <p>Uma viga secundária N-S cruza a viga principal no ponto de Passa.
        Isso cria <b>4 vãos</b> de laje distintos. O lado A vê apenas o vão
        que está imediatamente ao noroeste do cruzamento.</p>
        <ul>
          <li>Viga secundária N-S divide o espaço: cada quadrante é uma laje diferente</li>
          <li>A = laje do quadrante noroeste (L301)</li>
          <li>B = laje do quadrante sudoeste (L303)</li>
          <li>A ≠ B pois a viga NS separa os vãos</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-A">A = L301 (NO)</div>
          <div class="result-face rf-B">B = L303 (SO)</div>
        </div>""",
              carousel("lv6", [("Diagrama de referência", c6_ascii, False),
                                ("", placeholder(), False)]))

    body += c1 + c2 + c3 + c4 + c5 + c6

    body += """

  <!-- ═══════════════════════════════════════════════════════════ -->
  <h2>3. Campos da Ficha Lateral de Viga</h2>

  <table>
    <tr><th>Campo</th><th>Descrição</th><th>Exemplo</th></tr>
    <tr>
      <td><code>laje_name</code></td>
      <td>Nome da laje adjacente ao lado analisado</td>
      <td>L301, L302, nulo</td>
    </tr>
    <tr>
      <td><code>nivel_laje</code></td>
      <td>Cota (z) do topo da laje em cm</td>
      <td>852.19</td>
    </tr>
    <tr>
      <td><code>altura_laje</code></td>
      <td>Espessura da laje em cm</td>
      <td>12</td>
    </tr>
    <tr>
      <td><code>viga_name</code></td>
      <td>Nome da viga sendo analisada</td>
      <td>V10, VE301</td>
    </tr>
    <tr>
      <td><code>largura_viga</code></td>
      <td>Largura da seção transversal da viga em cm</td>
      <td>19</td>
    </tr>
    <tr>
      <td><code>nivel_viga</code></td>
      <td>Cota (z) do topo da viga em cm</td>
      <td>852.19</td>
    </tr>
  </table>"""

    return html_doc("Guia de Interpretação das Laterais de Viga — A/B e Para/Passa", body)


# ════════════════════════════════════════════════════════════════════════════
# 2. fundos_viga/interpretacao_fundos.html
# ════════════════════════════════════════════════════════════════════════════

def build_fundos():
    body = """  <h1>Guia de Interpretação dos Fundos de Viga (FV)</h1>

  <div class="intro">
    <b>O que é isso?</b> Este documento explica como interpretar o Fundo de Viga (FV):
    a face inferior (sofito) da viga. O FV pode ter uma laje abaixo (do pavimento inferior)
    ou ser exposto — sem laje. A cota do fundo e a laje abaixo são os dados essenciais.
    <br><br>
    <b>Como usar:</b> Consulte ao preencher qualquer ficha FV. O ASCII de corte transversal
    abaixo mostra a posição exata do fundo.
  </div>

  <!-- ═══════════════════════════════════════════════════════════ -->
  <h2>1. Convenção — Posição do Fundo de Viga</h2>

  <div class="ascii"> Corte transversal da viga (visão N-S)

 <span class="laje">════════════════════════════════════════════</span>  ← topo da laje (nivel_topo)
 │                                          │
 │              Viga V10                    │
 │           19 cm × 60 cm                 │
 │    (largura × altura da seção)           │
 └──────────────────────────────────────────┘  ← <span class="faceD">Fundo da Viga (FV)</span>
       <span class="laje">Laje L201 — espessura 12 cm</span>           ← ou <span class="tag-nulo">nulo</span> (sem laje)
 <span class="laje">════════════════════════════════════════════</span>  ← nível do pavimento inferior

 O FV está na cota:  nivel_topo  −  altura_viga
 Ex: 852.19 − 60 = 792.19 cm</div>

  <div class="rule-box">
    <div class="rule-title">Regra de classificação do FV</div>
    <ol style="margin-left:16px; color:#aaa; font-size:12px;">
      <li>Há laje do pavimento <b>inferior</b> alinhada com o fundo? → preencher <code>laje_name</code> + <code>nivel_fundo</code></li>
      <li>Fundo exposto (borda livre, platibanda, viga aérea)? → <span class="tag tag-nulo">nulo</span></li>
      <li>Viga escalonada (em cota diferente)? → usar a cota real do fundo da seção menor</li>
    </ol>
  </div>

  <!-- ═══════════════════════════════════════════════════════════ -->
  <h2>2. Casos de Interpretação</h2>"""

    # Caso 1
    c1_ascii = """              <div class="ascii"> <span class="laje">══════════════════════════════════════</span>   ← topo L301 (pav atual)
 │                                    │
 │          Viga V10  19×60           │
 └────────────────────────────────────┘   ← <span class="faceD">Fundo da Viga</span>
     <span class="laje">Laje L201  espessura 12 cm</span>
 <span class="laje">══════════════════════════════════════</span>   ← topo L201 (pav inferior)</div>"""

    c1 = caso(1, "FV com laje abaixo — caso padrão",
              """        <p>O fundo da viga está imediatamente acima da laje do pavimento inferior.
        É o caso mais comum em lajes de edifícios multi-pavimento.</p>
        <ul>
          <li><code>laje_name</code> = nome da laje inferior (ex: L201)</li>
          <li><code>nivel_fundo</code> = cota do fundo da viga</li>
          <li><code>largura</code> = largura da seção em cm</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-A">laje_name = L201</div>
          <div class="result-face rf-B">nivel_fundo = 792.19</div>
        </div>""",
              carousel("fv1", [("Diagrama de referência", c1_ascii, False),
                                ("", placeholder(), False)]))

    # Caso 2
    c2_ascii = """              <div class="ascii">           exterior (vazio — sem laje abaixo)
 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─

 <span class="laje">══════════════════════════════════════</span>   ← topo L301
 │                                    │
 │     Viga de borda V10  19×60       │
 └────────────────────────────────────┘   ← <span class="faceD">Fundo da Viga</span>  <span class="tag-nulo">nulo</span>

 Sem laje abaixo — fundo exposto ao exterior</div>"""

    c2 = caso(2, "FV sem laje — fundo exposto (borda livre ou nulo)",
              """        <p>A viga está na borda do edifício ou numa posição onde não há laje
        imediatamente abaixo. O fundo fica exposto.</p>
        <ul>
          <li><code>laje_name</code> = <span class="tag tag-nulo">nulo</span></li>
          <li>Ocorre em vigas de fachada, marquises, vigas sobre o solo</li>
          <li><code>nivel_fundo</code> ainda é preenchido (cota real do fundo)</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-A">laje_name = nulo</div>
          <div class="result-face rf-B">nivel_fundo = 792.19</div>
        </div>""",
              carousel("fv2", [("Diagrama de referência", c2_ascii, False),
                                ("", placeholder(), False)]))

    # Caso 3
    c3_ascii = """              <div class="ascii"> <span class="laje">══════════════════════════════════════</span>   ← topo L301 (pav atual)
 │                                    │
 │    Viga principal V10  19×80       │   cota topo: 852.19
 └──────────────┐                     │   ← fundo principal: 772.19
                │   Viga menor V10b   │   ← fundo escalonado: 812.19
                │   19×40             │
                └────────────────────┘
     <span class="laje">Laje L201 / nulo (depende do vão)</span>

 Usar a cota do FUNDO da seção que está sendo analisada</div>"""

    c3 = caso(3, "FV com escalonamento — seção em cota diferente",
              """        <p>Algumas vigas têm seções de alturas diferentes ao longo do comprimento
        (escalonamento). O FV de cada segmento usa a cota do fundo <b>daquele trecho</b>.</p>
        <ul>
          <li>Cada segmento é tratado independentemente</li>
          <li><code>nivel_fundo</code> = cota real do fundo do trecho</li>
          <li><code>nivel_topo</code> = cota real do topo do trecho</li>
          <li>A laje abaixo pode variar por trecho</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-A">nivel_fundo = 812.19 (trecho menor)</div>
        </div>""",
              carousel("fv3", [("Diagrama de referência", c3_ascii, False),
                                ("", placeholder(), False)]))

    body += c1 + c2 + c3

    body += """

  <!-- ═══════════════════════════════════════════════════════════ -->
  <h2>3. Campos da Ficha Fundo de Viga</h2>

  <table>
    <tr><th>Campo</th><th>Descrição</th><th>Exemplo</th></tr>
    <tr>
      <td><code>laje_name</code></td>
      <td>Nome da laje do pavimento inferior abaixo do fundo</td>
      <td>L201, nulo</td>
    </tr>
    <tr>
      <td><code>nivel_fundo</code></td>
      <td>Cota (z) do fundo (sofito) da viga em cm</td>
      <td>792.19</td>
    </tr>
    <tr>
      <td><code>largura</code></td>
      <td>Largura da seção transversal da viga em cm</td>
      <td>19</td>
    </tr>
    <tr>
      <td><code>nivel_topo</code></td>
      <td>Cota (z) do topo da viga em cm</td>
      <td>852.19</td>
    </tr>
  </table>"""

    return html_doc("Guia de Interpretação dos Fundos de Viga (FV)", body)


# ════════════════════════════════════════════════════════════════════════════
# 3. lajes/interpretacao_lajes.html
# ════════════════════════════════════════════════════════════════════════════

def build_lajes():
    body = """  <h1>Guia de Identificação das Lajes (LAJ)</h1>

  <div class="intro">
    <b>O que é isso?</b> Este documento explica como identificar e nomear lajes no pavimento.
    Uma laje é <b>delimitada por vigas</b> — o pilar interno NÃO divide lajes.
    A nomenclatura segue o padrão <b>L</b> + número do pavimento + sequência (ex: L301).
    <br><br>
    <b>Regra fundamental:</b> Todo ponto dentro do mesmo vão (mesma área entre vigas)
    pertence à <b>mesma laje</b>, independentemente de pilares internos.
  </div>

  <!-- ═══════════════════════════════════════════════════════════ -->
  <h2>1. Convenção de Nomenclatura e Delimitação</h2>

  <div class="ascii"> Visão de planta — pavimento 3

 ╔═══════════════════╦═══════════════════╦═══════════════╗
 ║                   ║                   ║               ║
 ║     <span class="laje">L 3 0 1</span>           ║     <span class="laje">L 3 0 2</span>           ║   <span class="laje">L 3 0 3</span>       ║
 ║    (vão inteiro)  ║    (vão inteiro)  ║               ║
 ║                   ║                   ║               ║
 ║       [P12]       ║                   ║               ║
 ║    pilar interno  ║                   ║               ║
 ║   (NÃO divide     ║                   ║               ║
 ║    a laje!)       ║                   ║               ║
 ║                   ║                   ║               ║
 ╠═══════════════════╬═══════════════════╩═══════════════╣
 ║                   ║                                   ║
 ║     <span class="laje">L 3 0 4</span>           ║         <span class="laje">L 3 0 5</span>                   ║
 ║                   ║    (laje grande — sem viga interna)║
 ╚═══════════════════╩═══════════════════════════════════╝

 ═══  = viga (limita / separa lajes)
 [P12] = pilar (NÃO limita lajes — a laje L301 passa por cima)</div>

  <h2>2. Casos de Identificação</h2>"""

    c1_ascii = """              <div class="ascii"> ╔════════════════════╦═══════════════════╗
 ║  Viga N (norte)    ║  Viga N (norte)   ║
 ╠════════════════════╬═══════════════════╣
 ║                    ║                   ║
 ║     <span class="laje">L 3 0 1</span>          ║    <span class="laje">L 3 0 2</span>          ║
 ║  4 vigas (N/S/E/W) ║                   ║
 ║                    ║                   ║
 ╠════════════════════╬═══════════════════╣
 ║  Viga S (sul)      ║  Viga S (sul)     ║
 ╚════════════════════╩═══════════════════╝

 L301 = delimitada por 4 vigas ortogonais (caso padrão)</div>"""

    c1 = caso(1, "Laje padrão — delimitada por vigas nos 4 lados",
              """        <p>A laje mais comum: 4 vigas formam um retângulo fechado.
        Todo o interior desse retângulo é <b>uma única laje</b> com o mesmo nome.</p>
        <ul>
          <li>Viga ao norte, sul, leste e oeste → define exatamente o vão</li>
          <li>Pilares internos NÃO dividem — L301 cobre todo o retângulo</li>
          <li>Nomenclatura: L + nº pavimento + sequência (301, 302…)</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-A">L301 — vão fechado nos 4 lados</div>
        </div>""",
              carousel("laj1", [("Diagrama de referência", c1_ascii, False),
                                  ("", placeholder(), False)]))

    c2_ascii = """              <div class="ascii"> Exterior (sem viga — borda livre)
 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
 ╔═══════════════════════════════════════════╗
 ║                                           ║  Viga sul
 ╠══════════════════╦════════════════════════╣
 ║     <span class="laje">L 3 0 1</span>         ║     <span class="laje">L 3 0 2</span>           ║
 ║  2 lados = vigas ║                        ║
 ║  2 lados = borda ║                        ║
 ╚══════════════════╩════════════════════════╝
   Viga oeste          Viga este</div>"""

    c2 = caso(2, "Laje de borda — 2 lados com vigas, 2 lados = borda exterior",
              """        <p>Lajes na periferia do edifício têm 2 lados delimitados por vigas
        e 2 lados abertos (borda/fachada). O vão é definido pelas vigas presentes.</p>
        <ul>
          <li>L301: limitada ao sul e leste por vigas; norte e oeste = borda</li>
          <li>A laje se estende até a borda do edifício nesse lado</li>
          <li>Nomenclatura: mesmo padrão L3XX</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-A">L301 — borda norte + oeste livres</div>
        </div>""",
              carousel("laj2", [("Diagrama de referência", c2_ascii, False),
                                  ("", placeholder(), False)]))

    c3_ascii = """              <div class="ascii"> ╔═══════════════════════════════════════════╗
 ║                                           ║
 ║                 <span class="laje">L 3 0 1</span>                   ║
 ║                                           ║
 ║        [P15]                 [P16]        ║
 ║     pilar interno          pilar interno  ║
 ║   (NÃO divide L301)       (NÃO divide!)  ║
 ║                                           ║
 ║                 <span class="laje">L 3 0 1</span>                   ║  ← mesma laje!
 ║                                           ║
 ╚═══════════════════════════════════════════╝

 A laje L301 é CONTÍNUA acima de P15 e P16.
 Pilares nunca dividem lajes — apenas vigas dividem.</div>"""

    c3 = caso(3, "Laje grande com pilar interno — pilar NÃO divide a laje",
              """        <p>Mesmo com pilares dentro do vão, a laje é <b>uma só</b> porque
        nenhuma viga cruza o vão para dividi-lo. O pilar simplesmente apoia a laje,
        sem criar fronteira entre vãos.</p>
        <ul>
          <li>P15 e P16 estão dentro do vão de L301 → L301 continua ao redor deles</li>
          <li><b>Regra de ouro:</b> somente uma viga pode separar duas lajes</li>
          <li>Situação comum em lajes planas de grandes vãos</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-A">L301 — inteira, inclui área com pilares</div>
        </div>""",
              carousel("laj3", [("Diagrama de referência", c3_ascii, False),
                                  ("", placeholder(), False)]))

    c4_ascii = """              <div class="ascii"> ╔═══════════════╦═══════════════════════════════╗
 ║               ║                               ║
 ║   <span class="laje">L 3 0 1</span>       ║          <span class="laje">L 3 0 2</span>             ║
 ║               ║                               ║
 ╠═══════════════╣       (vão maior)              ║
 ║  Viga E-W     ╠═══════════════════════════════╣
 ║  divide aqui  ║                               ║
 ╠═══════════════╣          <span class="laje">L 3 0 3</span>             ║
 ║   <span class="laje">L 3 0 4</span>       ║                               ║
 ╚═══════════════╩═══════════════════════════════╝

 A viga E-W central (esquerda) divide L301 / L304.
 A viga E-W direita divide L302 / L303.</div>"""

    c4 = caso(4, "Duas lajes diferentes — separadas por uma viga",
              """        <p>Quando uma viga cruza o espaço, ela <b>divide obrigatoriamente</b> as lajes
        em dois vãos distintos. Cada vão recebe um nome diferente.</p>
        <ul>
          <li>L301 e L304 são diferentes porque a viga E-W as separa</li>
          <li>L302 e L303 são diferentes pela viga E-W do lado direito</li>
          <li>Sem a viga → seria uma única laje grande</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-A">L301 ≠ L304 (viga separa)</div>
          <div class="result-face rf-B">L302 ≠ L303 (viga separa)</div>
        </div>""",
              carousel("laj4", [("Diagrama de referência", c4_ascii, False),
                                  ("", placeholder(), False)]))

    body += c1 + c2 + c3 + c4

    body += """

  <!-- ═══════════════════════════════════════════════════════════ -->
  <h2>3. Campos da Ficha de Laje</h2>

  <table>
    <tr><th>Campo</th><th>Descrição</th><th>Exemplo</th></tr>
    <tr>
      <td><code>nome</code></td>
      <td>Identificador da laje (L + pavimento + sequência)</td>
      <td>L301, L302</td>
    </tr>
    <tr>
      <td><code>nivel</code></td>
      <td>Cota (z) do topo da laje em cm</td>
      <td>852.19</td>
    </tr>
    <tr>
      <td><code>espessura</code></td>
      <td>Espessura da laje em cm</td>
      <td>12, 15, 20</td>
    </tr>
    <tr>
      <td><code>tipo</code></td>
      <td>Tipo construtivo da laje</td>
      <td>maciça, nervurada, protendida</td>
    </tr>
  </table>"""

    return html_doc("Guia de Identificação das Lajes (LAJ)", body)


# ════════════════════════════════════════════════════════════════════════════
# 4. visao_cortes/interpretacao_cortes.html
# ════════════════════════════════════════════════════════════════════════════

def build_cortes():
    body = """  <h1>Guia de Interpretação da Visão de Cortes</h1>

  <div class="intro">
    <b>O que é isso?</b> O corte vertical mostra uma seção do pavimento —
    pilares e vigas aparecem como retângulos em corte transversal ou longitudinal.
    Este guia explica como ler cada elemento num corte.
    <br><br>
    <b>Quando usar:</b> Ao interpretar qualquer ficha que requer análise de cota
    vertical (FV, laterais, pilar).
  </div>

  <!-- ═══════════════════════════════════════════════════════════ -->
  <h2>1. Elementos num Corte Vertical</h2>

  <div class="ascii"> Corte vertical N-S (olhando para leste)

 nivel topo laje: 852.19
 <span class="laje">══════════════════════════════════════════════════</span>
                   │            │             │
 <span class="viga">viga E-W</span>         │ <span class="pilar">▓▓▓▓▓▓▓▓▓▓▓▓</span> │             │
 ┌─────────────────┤ <span class="pilar">▓ Pilar P12 ▓</span> ├─────────────┤
 │     Viga V10    │ <span class="pilar">▓  19×100   ▓</span> │   Viga V11  │
 │    19 × 60 cm   │ <span class="pilar">▓▓▓▓▓▓▓▓▓▓▓▓</span> │  19 × 55 cm │
 └─────────────────┘             └─────────────┘
 nivel fundo viga: 792.19
                    │            │
 <span class="laje">══════════════════════════════════════════════════</span>
 nivel topo laje inferior: 780.00

 <span class="pilar">▓▓▓</span> = pilar (em corte ou em vista)
 ═══ = laje
 └──┘ = viga (seção transversal)</div>

  <h2>2. Casos de Leitura</h2>"""

    c1_ascii = """              <div class="ascii"> Corte passando pelo eixo do pilar:

 <span class="laje">════════════════════════════════════</span>  nivel: 852.19
         │                      │
         │  <span class="pilar">▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓</span>  │
         │  <span class="pilar">▓  Pilar P12    ▓</span>  │
         │  <span class="pilar">▓  largura: 19  ▓</span>  │
         │  <span class="pilar">▓  altura: 100  ▓</span>  │
         │  <span class="pilar">▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓</span>  │
         │                      │
 <span class="laje">════════════════════════════════════</span>  nivel inferior

 O pilar aparece como retângulo maciço.
 Dimensões = seção transversal (largura × altura visível)</div>"""

    c1 = caso(1, "Corte de Pilar — leitura da seção transversal",
              """        <p>No corte passando pelo eixo do pilar, ele aparece como retângulo maciço.
        As dimensões visíveis correspondem à seção transversal.</p>
        <ul>
          <li>Largura visível = dimensão ortogonal ao corte</li>
          <li>Altura visível = dimensão ao longo do corte</li>
          <li>Nível de topo = cota da face superior</li>
          <li>Nível de base = cota da face inferior</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-A">seção visível = 19 × 100 cm</div>
        </div>""",
              carousel("co1", [("Diagrama de referência", c1_ascii, False),
                                ("", placeholder(), False)]))

    c2_ascii = """              <div class="ascii"> Corte transversal da viga (olhando ao longo do eixo):

 <span class="laje">════════════════════════════════════</span>  nivel: 852.19
                 │        │
                 │ Viga   │
                 │ V10    │  largura: 19 cm
                 │ 19×60  │  altura: 60 cm
                 └────────┘
                           ← nivel fundo: 792.19
 <span class="laje">════════════════════════════════════</span>  nivel laje inferior

 A viga aparece como retângulo oco (contorno).
 Fundo da viga = nivel topo − altura</div>"""

    c2 = caso(2, "Corte de Viga — leitura do sofito (fundo)",
              """        <p>No corte transversal da viga, ela aparece como retângulo de contorno.
        O ponto inferior = fundo da viga (sofito).</p>
        <ul>
          <li>Largura = dimensão horizontal da seção</li>
          <li>Altura = distância entre topo e fundo</li>
          <li><code>nivel_fundo</code> = nivel_topo − altura_viga</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-A">nivel_fundo = 852.19 − 60 = 792.19</div>
        </div>""",
              carousel("co2", [("Diagrama de referência", c2_ascii, False),
                                ("", placeholder(), False)]))

    c3_ascii = """              <div class="ascii"> Corte passando por pilar + viga E-W simultâneos:

 <span class="laje">════════════════════════════════════════════════════</span>
 │                │              │                  │
 │  <span class="pilar">▓▓▓▓▓▓▓▓▓▓▓▓</span>   │  <span class="viga">┌──────────┐</span>   │  <span class="pilar">▓▓▓▓▓▓▓▓▓▓</span>  │
 │  <span class="pilar">▓ Pilar P1  ▓</span>   │  <span class="viga">│  Viga V9 │</span>   │  <span class="pilar">▓ Pilar P2▓</span>  │
 │  <span class="pilar">▓▓▓▓▓▓▓▓▓▓▓▓</span>   │  <span class="viga">│  19×45   │</span>   │  <span class="pilar">▓▓▓▓▓▓▓▓▓▓</span>  │
 │                │  <span class="viga">└──────────┘</span>   │                  │
 │                │              │                  │
 <span class="laje">════════════════════════════════════════════════════</span>

 Pilares em extremos + viga no meio = corte composto</div>"""

    c3 = caso(3, "Corte composto — interseção pilar + viga",
              """        <p>Cortes que passam por um pilar e por uma viga no mesmo plano
        mostram ambos simultaneamente. Cada elemento tem seu nível e seção próprios.</p>
        <ul>
          <li>Pilar: retângulo maciço — nível de topo pode ser diferente da viga</li>
          <li>Viga: retângulo de contorno entre os dois pilares</li>
          <li>O fundo da viga pode ser diferente do fundo do pilar</li>
          <li>Verificar cotas individuais de cada elemento</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-A">Pilar P1 topo = 852.19</div>
          <div class="result-face rf-B">Viga V9 fundo = 807.19</div>
        </div>""",
              carousel("co3", [("Diagrama de referência", c3_ascii, False),
                                ("", placeholder(), False)]))

    body += c1 + c2 + c3

    body += """

  <!-- ═══════════════════════════════════════════════════════════ -->
  <h2>3. Síntese de Leitura de Corte</h2>

  <table>
    <tr><th>Elemento</th><th>Aparência no corte</th><th>Dados a extrair</th></tr>
    <tr>
      <td><span class="lbl-A">Pilar</span></td>
      <td>Retângulo maciço (hatched)</td>
      <td>seção (l × h), nivel topo, nivel base</td>
    </tr>
    <tr>
      <td><span class="lbl-B">Viga</span></td>
      <td>Retângulo de contorno</td>
      <td>largura, altura, nivel topo, nivel fundo</td>
    </tr>
    <tr>
      <td><span class="lbl-C">Laje</span></td>
      <td>Linha ou faixa horizontal</td>
      <td>nivel topo, espessura</td>
    </tr>
  </table>"""

    return html_doc("Guia de Interpretação da Visão de Cortes", body)


# ════════════════════════════════════════════════════════════════════════════
# 5. pilares_especiais/interpretacao_especiais.html
# ════════════════════════════════════════════════════════════════════════════

def build_especiais():
    body = """  <h1>Guia de Interpretação de Pilares Especiais</h1>

  <div class="intro">
    <b>O que é isso?</b> Pilares especiais são aqueles com geometria não-retangular:
    seção em L, T, C, diagonal, chanfrado ou com entalhe. As regras de faces ABCD
    do gabarito padrão se aplicam, mas requerem atenção extra à geometria.
    <br><br>
    <b>Referência base:</b> <a href="../pilares/interpretacao_abcd.html" style="color:#7eb8f7;">Guia ABCD padrão dos pilares</a>
  </div>

  <!-- ═══════════════════════════════════════════════════════════ -->
  <h2>1. Tipos de Seção Especial</h2>

  <div class="ascii"> Geometrias comuns de pilares especiais:

 Seção em L:          Seção em T:          Com entalhe:

 ████████             ████████████         ████████████
 ████████             ████████████         ████████████
 ████                     ████             ████    ████
 ████                     ████             ████    ████
 ████                     ████             ████████████
 ████                     ████             ████████████

 Pilar diagonal:      Chanfrado:
                      ████████
   ██                 ███████
  ████                ██████
 ██████               █████
  ████                ████
   ██                 ███████████</div>

  <h2>2. Casos de Interpretação</h2>"""

    c1_ascii = """              <div class="ascii"> Pilar em seção L — visão de planta:

           ████████████████████████
           ████                ████  ← face curta C (topo)
           ████  <span class="pilar">seção em L</span>   ████
           ████                    ← face A (esquerda longa)
           ████
           ████████████████████████
           ████████████████████████  ← base D (fundo)

 Faces ABCD: mesma regra que pilar retangular
 mas o polígono da seção é não-convexo.
 Lajes podem encavalhar na reentrância da seção L.

 <span class="faceA">A = face longa esquerda exterior</span>
 <span class="faceB">B = face longa direita exterior</span>
 <span class="faceC">C = face curta topo</span>
 <span class="faceD">D = face curta base</span></div>"""

    c1 = caso(1, "Pilar em L — seção não-convexo",
              """        <p>O pilar tem seção em L. As faces ABCD continuam sendo definidas
        pelo bounding box da seção (retângulo mínimo envolvente).
        A reentrância pode criar bolso onde uma laje encavalha.</p>
        <ul>
          <li>Bounding box define A/B/C/D como para pilar retangular</li>
          <li>A reentrância da seção L pode conter laje de outro vão</li>
          <li>Checar se a laje está dentro ou fora do polígono real</li>
          <li>Orientação (VERTICAL/HORIZONTAL) pelo bounding box: maior dimensão = longa</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-A">A = face longa oeste</div>
          <div class="result-face rf-B">B = face longa leste</div>
          <div class="result-face rf-C">C = face curta norte</div>
          <div class="result-face rf-D">D = face curta sul</div>
        </div>""",
              carousel("pe1", [("Diagrama de referência", c1_ascii, False),
                                ("", placeholder(), False)]))

    c2_ascii = """              <div class="ascii"> Pilar com entalhe (rebaixo num lado):

 ╔══════════════════════════╗
 ║      corpo principal     ║   ← face C (topo)
 ╠══════════════╗           ║
 ║   entalhe    ║           ║   ← A (esquerda)
 ╠══════════════╝           ║
 ║      corpo principal     ║   ← face D (base)
 ╚══════════════════════════╝

 No entalhe: laje pode entrar no vazio criado
 Verificar se há laje no bolso ou se é nulo

 <span class="faceA">A = lado com entalhe — pode ter 2 lajes diferentes</span>
 acima e abaixo do entalhe (ou nulo no entalhe)</div>"""

    c2 = caso(2, "Pilar com entalhe — rebaixo em uma face",
              """        <p>O pilar tem um recorte/entalhe em uma das faces.
        O vazio do entalhe pode conter uma laje ou ser nulo.
        A face A tem geometria complexa — parte da face pode ser viga
        e parte pode ser laje (ou nulo no entalhe).</p>
        <ul>
          <li>Entalhe = recorte no polígono da seção</li>
          <li>O rebaixo pode abrigar laje de altura diferente</li>
          <li>Tratar como dois segmentos de face: acima e abaixo do entalhe</li>
          <li>Consultar DXF original para medir o entalhe</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-A">A = parte laje + parte nulo (entalhe)</div>
        </div>""",
              carousel("pe2", [("Diagrama de referência", c2_ascii, False),
                                ("", placeholder(), False)]))

    body += c1 + c2

    body += """

  <!-- ═══════════════════════════════════════════════════════════ -->
  <h2>3. Regras para Pilares Especiais</h2>

  <div class="rule-box">
    <div class="rule-title">Protocolo de análise</div>
    <ol style="margin-left:16px; color:#aaa; font-size:12px;">
      <li>Calcular o <b>bounding box</b> (retângulo mínimo envolvente) da seção</li>
      <li>Determinar orientação: <b>VERTICAL</b> se altura &gt; largura do bbox, senão <b>HORIZONTAL</b></li>
      <li>Aplicar regra ABCD do <a href="../pilares/interpretacao_abcd.html" style="color:#7eb8f7;">guia padrão</a> sobre o bbox</li>
      <li>Verificar se a laje encontrada está dentro do <b>polígono real</b> (não só do bbox)</li>
      <li>Para entalhes: tratar o recorte como área que pode ter laje diferente ou nulo</li>
    </ol>
  </div>

  <table>
    <tr><th>Tipo especial</th><th>Desafio principal</th><th>Solução</th></tr>
    <tr>
      <td>Seção em L / T / C</td>
      <td>Reentrância atrai laje indevida</td>
      <td>Checar sobreposição com polígono real, não só bbox</td>
    </tr>
    <tr>
      <td>Pilar diagonal</td>
      <td>Orientação ambígua</td>
      <td>Usar ângulo da maior dimensão para definir A/B</td>
    </tr>
    <tr>
      <td>Com entalhe</td>
      <td>Face tem geometria dupla</td>
      <td>Dividir face em segmentos acima/abaixo do entalhe</td>
    </tr>
    <tr>
      <td>Chanfrado</td>
      <td>Vértice recortado pode confundir vizinhança</td>
      <td>Usar bbox — ignorar chanfro para atribuição ABCD</td>
    </tr>
  </table>"""

    return html_doc("Guia de Interpretação de Pilares Especiais", body)


# ════════════════════════════════════════════════════════════════════════════
# 6. convencao_niveis/interpretacao_niveis.html
# ════════════════════════════════════════════════════════════════════════════

def build_niveis():
    body = """  <h1>Guia de Convenção de Níveis</h1>

  <div class="intro">
    <b>O que é isso?</b> Este documento define a hierarquia de cotas (níveis Z) usada
    em toda a estrutura. Cada elemento tem sua cota de referência: topo da laje,
    fundo da viga, topo do pilar, etc. Conhecer a hierarquia evita erros de
    preenchimento das fichas.
    <br><br>
    <b>Unidade:</b> todas as cotas em <b>centímetros</b>, relativas ao datum do projeto.
  </div>

  <!-- ═══════════════════════════════════════════════════════════ -->
  <h2>1. Hierarquia de Níveis — Corte Vertical</h2>

  <div class="ascii"> Seção vertical — hierarquia completa de níveis

 ↑ nivel_topo_pilar = nivel_topo_laje (pav atual)
 │
 <span class="laje">═══════════════════════════════════════════</span>  ← nivel_topo_laje  (ex: 852.19)
 │  Laje: espessura 12 cm
 <span class="laje">───────────────────────────────────────────</span>  ← nivel_fundo_laje (ex: 840.19)
 │
 │  <span class="pilar">│ Pilar │</span>            Viga V10
 │  <span class="pilar">│       │</span>        ┌──────────────┐  ← nivel_topo_viga = nivel_fundo_laje
 │  <span class="pilar">│ P12   │</span>        │   19 × 60    │
 │  <span class="pilar">│       │</span>        │              │
 │  <span class="pilar">│       │</span>        └──────────────┘  ← nivel_fundo_viga (ex: 792.19)
 │  <span class="pilar">│       │</span>
 │
 <span class="laje">═══════════════════════════════════════════</span>  ← nivel_topo_laje_inf (pav anterior)

 Relações:
   nivel_fundo_laje  = nivel_topo_laje  − espessura_laje
   nivel_topo_viga   = nivel_topo_laje  (em geral: viga encosta na laje)
   nivel_fundo_viga  = nivel_topo_viga  − altura_viga</div>

  <h2>2. Casos e Variações de Nível</h2>"""

    c1_ascii = """              <div class="ascii"> Caso padrão — laje + viga alinhadas no mesmo nível:

 <span class="laje">══════════════════════════════════════</span>  852.19  ← nivel_topo_laje
 │  Laje  12 cm
 <span class="laje">──────────────────────────────────────</span>  840.19  ← nivel_fundo_laje
        │  Viga V10  19×60              │  840.19  ← nivel_topo_viga
        │                               │
        └───────────────────────────────┘  780.19  ← nivel_fundo_viga
 <span class="laje">══════════════════════════════════════</span>  768.00  ← laje pav inferior</div>"""

    c1 = caso(1, "Padrão — laje e viga no mesmo nível de topo",
              """        <p>O caso mais comum: topo da viga alinhado com o fundo da laje.
        A laje pousa diretamente sobre a viga.</p>
        <ul>
          <li><code>nivel_topo_laje</code> = cota da superfície da laje</li>
          <li><code>nivel_topo_viga</code> = <code>nivel_fundo_laje</code></li>
          <li><code>nivel_fundo_viga</code> = nivel_topo_viga − altura_viga</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-A">topo_laje = 852.19</div>
          <div class="result-face rf-B">topo_viga = 840.19</div>
          <div class="result-face rf-C">fundo_viga = 780.19</div>
        </div>""",
              carousel("ni1", [("Diagrama de referência", c1_ascii, False),
                                ("", placeholder(), False)]))

    c2_ascii = """              <div class="ascii"> Viga rebaixada — topo da viga abaixo do fundo da laje:

 <span class="laje">══════════════════════════════════════</span>  852.19  ← nivel_topo_laje
 │  Laje  12 cm
 <span class="laje">──────────────────────────────────────</span>  840.19  ← nivel_fundo_laje

      ← espaço vazio (folga) →

        │  Viga rebaixada V10b │  825.00  ← nivel_topo_viga (rebaixado)
        │       19×45          │
        └──────────────────────┘  780.00  ← nivel_fundo_viga

 <span class="laje">══════════════════════════════════════</span>  768.00  ← laje pav inferior

 Folga = nivel_fundo_laje − nivel_topo_viga = 15 cm</div>"""

    c2 = caso(2, "Viga rebaixada — topo abaixo do fundo da laje",
              """        <p>A viga tem seu topo abaixo do fundo da laje — há uma folga entre eles.
        Ocorre em vigas de escalonamento ou em detalhes especiais de projeto.</p>
        <ul>
          <li><code>nivel_topo_viga</code> &lt; <code>nivel_fundo_laje</code> → folga entre eles</li>
          <li>A folga pode ser preenchida com outro elemento ou ser espaço livre</li>
          <li>Checar cotas separadamente — não assumir que são iguais</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-A">topo_laje = 852.19</div>
          <div class="result-face rf-B">fundo_laje = 840.19</div>
          <div class="result-face rf-C">topo_viga = 825.00 (rebaixado)</div>
        </div>""",
              carousel("ni2", [("Diagrama de referência", c2_ascii, False),
                                ("", placeholder(), False)]))

    c3_ascii = """              <div class="ascii"> Pilar mais alto que a laje (pilar stub acima da laje):

 <span class="pilar">     │ Stub │</span>                      870.00  ← nivel_topo_pilar (acima laje)
 <span class="laje">═════╪══════╪═════════════════════</span>  852.19  ← nivel_topo_laje
 <span class="pilar">     │      │</span> Laje  12 cm
 <span class="laje">─────╪──────╪─────────────────────</span>  840.19  ← nivel_fundo_laje
 <span class="pilar">     │ P12  │</span>     Viga V10
 <span class="pilar">     │      │</span>  ┌────────────┐       840.19  ← nivel_topo_viga
 <span class="pilar">     │      │</span>  │   19×60    │
 <span class="pilar">     │      │</span>  └────────────┘       780.19  ← nivel_fundo_viga

 nivel_topo_pilar pode ser diferente (acima ou abaixo) de nivel_topo_laje</div>"""

    c3 = caso(3, "Pilar stub — topo do pilar diferente do topo da laje",
              """        <p>O pilar pode ter sua cota de topo diferente da laje (stub acima ou
        encerrado abaixo). Cada elemento tem sua cota própria — não assumir que
        topo do pilar = topo da laje.</p>
        <ul>
          <li><code>nivel_topo_pilar</code> pode estar acima da laje (stub) ou abaixo (pilar curto)</li>
          <li><code>nivel_base_pilar</code> = cota da fundação ou da laje inferior</li>
          <li>Para fichas de pilar: usar as cotas próprias do pilar, não da laje</li>
        </ul>
        <div class="result-row">
          <div class="result-face rf-A">topo_pilar = 870.00 (stub)</div>
          <div class="result-face rf-B">topo_laje = 852.19</div>
        </div>""",
              carousel("ni3", [("Diagrama de referência", c3_ascii, False),
                                ("", placeholder(), False)]))

    body += c1 + c2 + c3

    body += """

  <!-- ═══════════════════════════════════════════════════════════ -->
  <h2>3. Tabela de Referência de Níveis</h2>

  <table>
    <tr><th>Campo</th><th>Elemento</th><th>Descrição</th><th>Como calcular</th></tr>
    <tr>
      <td><code>nivel_topo_laje</code></td>
      <td>Laje</td>
      <td>Cota da superfície superior da laje</td>
      <td>Lido diretamente do DXF</td>
    </tr>
    <tr>
      <td><code>nivel_fundo_laje</code></td>
      <td>Laje</td>
      <td>Cota da face inferior da laje</td>
      <td>nivel_topo_laje − espessura_laje</td>
    </tr>
    <tr>
      <td><code>nivel_topo_viga</code></td>
      <td>Viga</td>
      <td>Cota do topo da seção da viga</td>
      <td>Em geral = nivel_fundo_laje</td>
    </tr>
    <tr>
      <td><code>nivel_fundo_viga</code></td>
      <td>Viga</td>
      <td>Cota do sofito (fundo) da viga</td>
      <td>nivel_topo_viga − altura_viga</td>
    </tr>
    <tr>
      <td><code>nivel_topo_pilar</code></td>
      <td>Pilar</td>
      <td>Cota do topo do pilar neste pavimento</td>
      <td>Lido diretamente do DXF</td>
    </tr>
    <tr>
      <td><code>nivel_base_pilar</code></td>
      <td>Pilar</td>
      <td>Cota da base do pilar neste pavimento</td>
      <td>Lido do DXF ou = nivel_topo_laje_inf</td>
    </tr>
  </table>"""

    return html_doc("Guia de Convenção de Níveis", body)


# ════════════════════════════════════════════════════════════════════════════
# MAIN — cria pastas e escreve arquivos
# ════════════════════════════════════════════════════════════════════════════

DOCS = [
    {
        "subdir": "laterais_viga",
        "filename": "interpretacao_laterais.html",
        "extra_dirs": ["imgs", "a_para", "b_para", "a_passa", "b_passa"],
        "builder": build_laterais,
    },
    {
        "subdir": "fundos_viga",
        "filename": "interpretacao_fundos.html",
        "extra_dirs": ["imgs"],
        "builder": build_fundos,
    },
    {
        "subdir": "lajes",
        "filename": "interpretacao_lajes.html",
        "extra_dirs": ["imgs"],
        "builder": build_lajes,
    },
    {
        "subdir": "visao_cortes",
        "filename": "interpretacao_cortes.html",
        "extra_dirs": ["imgs"],
        "builder": build_cortes,
    },
    {
        "subdir": "pilares_especiais",
        "filename": "interpretacao_especiais.html",
        "extra_dirs": ["imgs"],
        "builder": build_especiais,
    },
    {
        "subdir": "convencao_niveis",
        "filename": "interpretacao_niveis.html",
        "extra_dirs": ["imgs"],
        "builder": build_niveis,
    },
]


def main():
    created = []
    errors = []

    for doc in DOCS:
        subdir = os.path.join(BASE_DIR, doc["subdir"])
        os.makedirs(subdir, exist_ok=True)
        for ed in doc.get("extra_dirs", []):
            os.makedirs(os.path.join(subdir, ed), exist_ok=True)

        html_path = os.path.join(subdir, doc["filename"])
        try:
            content = doc["builder"]()
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(content)
            size = os.path.getsize(html_path)
            created.append((html_path, size))
            print(f"OK  {html_path}  ({size:,} bytes)")
        except Exception as e:
            errors.append((html_path, str(e)))
            print(f"ERR {html_path}  {e}")

    print()
    print(f"Criados: {len(created)} arquivos")
    if errors:
        print(f"Erros: {len(errors)}")
        for p, e in errors:
            print(f"  ERRO: {p} — {e}")
    else:
        print("Sem erros.")


if __name__ == "__main__":
    main()
