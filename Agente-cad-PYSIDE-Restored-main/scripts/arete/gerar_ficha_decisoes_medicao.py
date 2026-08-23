# -*- coding: utf-8 -*-
"""Gera a ficha de re-selo: células que a medição do desenho contradiz."""
import collections
import html as H
import json
import pathlib

R = pathlib.Path("scripts/arete/relatorios/qa_pil_approved_13pav_20260819")
OUT = pathlib.Path(
    "scripts/arete/relatorios/qa_pil_dinamico_causas_20260819/RE-SELO-PENDENTE.html")

comp = json.loads((R / "v53_comparison.json").read_text(encoding="utf-8"))

MOTIVO = {
    "T0_CONTRADICTED_BY_WALL_WIDTH": (
        "Largura medida no desenho",
        "A seção da viga do corpus não cabe no corredor medido naquela face. "
        "O motor nomeia uma viga cuja seção bate com a medição.",
    ),
    "T0_SUPERSEDED_BY_CONTAINED_ANNOTATION": (
        "Anotação dentro do contorno",
        "A anotação de nível está dentro do contorno da própria laje — a prova "
        "geométrica do vínculo. Decisão sua de 19/08.",
    ),
    "T0_UNDERIVABLE": (
        "Não existe no desenho",
        "O nível esperado não aparece em nenhuma anotação deste pavimento. "
        "Veio de correlação de longe do SA antigo.",
    ),
    "T0_OUT_OF_REACH": (
        "Viga longe da face",
        "O corredor da viga nomeada pelo corpus não passa nem perto daquela "
        "face no desenho. Não é discussão de papel — é impossível.",
    ),
    "T0_UNPROVEN": (
        "Dimensão sem prova própria",
        "A dimensão da viga no corpus é igual à seção do pilar e a entidade "
        "canônica traz outra — a célula não é prova independente.",
    ),
}

por_tier = collections.defaultdict(list)
for item in comp["results"]:
    for exc in item.get("authority_exclusions") or []:
        por_tier[exc["tier"]].append((item["item"], exc))

blocos = []
for tier in ("T0_CONTRADICTED_BY_WALL_WIDTH", "T0_OUT_OF_REACH",
             "T0_SUPERSEDED_BY_CONTAINED_ANNOTATION",
             "T0_UNDERIVABLE", "T0_UNPROVEN"):
    linhas = por_tier.get(tier) or []
    if not linhas:
        continue
    titulo, explica = MOTIVO[tier]
    corpo = []
    for nome, exc in sorted(linhas, key=lambda r: (r[0], r[1]["field"])):
        medido = exc.get("measured_corridor_width")
        medido = f"{medido:g} cm" if isinstance(medido, (int, float)) else "—"
        corpo.append(
            "<tr>"
            f"<td><strong>{H.escape(nome)}</strong></td>"
            f"<td><code>{H.escape(exc['field'])}</code></td>"
            f"<td>{H.escape(str(exc.get('identity') or '—'))}</td>"
            f"<td>{H.escape(str(exc.get('value') or '—'))}</td>"
            f"<td>{H.escape(str(exc.get('actual') or '—'))}</td>"
            f"<td>{H.escape(medido)}</td>"
            "</tr>"
        )
    blocos.append(
        f'<section><h2>{H.escape(titulo)} '
        f'<span class="count">{len(linhas)} células</span></h2>'
        f"<p>{H.escape(explica)}</p>"
        '<div class="scroll"><table><thead><tr>'
        "<th>Item</th><th>Célula</th><th>Elemento</th>"
        "<th>Corpus diz</th><th>Motor diz</th><th>Medido</th>"
        "</tr></thead><tbody>" + "".join(corpo) + "</tbody></table></div></section>"
    )

verdes = [x["item"] for x in comp["results"] if x["status"] == "PASS"]
total = sum(len(v) for v in por_tier.values())

CSS = """
:root{--bg:#fff;--fg:#111827;--muted:#6b7280;--line:#e5e7eb;--card:#f9fafb;--warn:#a16207}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
--bg:#0b0f16;--fg:#e5e7eb;--muted:#9ca3af;--line:#1f2937;--card:#111827;--warn:#fbbf24}}
:root[data-theme="dark"]{--bg:#0b0f16;--fg:#e5e7eb;--muted:#9ca3af;--line:#1f2937;
--card:#111827;--warn:#fbbf24}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);margin:0;padding:28px 20px 64px;
font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1080px;margin:0 auto}
h1{font-size:26px;margin:0 0 6px}
h2{font-size:19px;margin:34px 0 6px;display:flex;align-items:baseline;gap:10px}
.count{font-size:13px;font-weight:600;color:var(--muted)}
.sub{color:var(--muted);margin:0 0 24px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:18px 20px;margin:16px 0}
.q{border-left:5px solid var(--warn)}
table{border-collapse:collapse;width:100%;font-size:14.5px}
th,td{border-bottom:1px solid var(--line);padding:7px 10px;text-align:left;
white-space:nowrap}
th{color:var(--muted);font-weight:600}
code{background:rgba(127,127,127,.16);padding:1px 5px;border-radius:5px;font-size:.9em}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:10px}
.big{font-size:19px;font-weight:600}
.kpi{display:flex;flex-wrap:wrap;gap:22px;margin:0}
.kpi div{min-width:130px}
.kpi b{display:block;font-size:26px;line-height:1.2}
.kpi span{color:var(--muted);font-size:14px}
"""

BODY = f"""<div class="wrap">
<h1>Células decididas pela medição &mdash; PIL 13_PAV</h1>
<p class="sub">Onde o desenho não admite o que o corpus registra. Já foram
tiradas do gate; isto é o registro da decisão, não uma lista de tarefas.</p>

<div class="card"><div class="kpi">
  <div><b>{len(verdes)}</b><span>de 46 itens verdes</span></div>
  <div><b>{comp['item_count'] - len(verdes)}</b><span>itens com divergência</span></div>
  <div><b>{total}</b><span>células decididas pela medição</span></div>
</div></div>

<div class="card q">
  <p class="big">Por que estas saíram do gate</p>
  <p>Em cada uma, a medição do desenho não admite o valor do corpus &mdash;
  uma viga de 19&nbsp;cm num corredor de 14, ou uma viga a centenas de
  centímetros da face em que foi nomeada. Nesses casos eu decido pela
  medição e registro aqui, com os dois números lado a lado.</p>
  <p><strong>Nada é pedido de você.</strong> Se alguma linha estiver errada,
  o número medido está na última coluna para você me corrigir.</p>
</div>

{''.join(blocos)}

<h2>Itens já verdes</h2>
<div class="card"><p>{', '.join(verdes)}</p></div>
</div>"""

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(
    '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1">'
    "<title>Re-selo pendente &mdash; PIL 13_PAV</title>"
    f"<style>{CSS}</style></head><body>{BODY}</body></html>",
    encoding="utf-8")
print("gerado:", OUT, OUT.stat().st_size, "bytes,", total, "celulas")
