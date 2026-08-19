"""Chrome de QA dinâmico PIL — espelho do looping FV (validadores + anotações + layers).

Chaves: aten_pil_* (nunca aten_fv_*).
Ver: docs/PROMPT-LOOPING-DESTAQUE-AGENTICO-FV-PARA-PIL.md

Pan/zoom SVG: OBRIGATÓRIO viewBox (initPilPanZoom) — proibido CSS scale.
Padrão canônico: docs/PADRAO-SVG-WEB-PANZOOM-VIEWBOX.md
Ref FV: src/ui/widgets/fv_hifi_n1_render.py (initPanZoom / V302).
"""
from __future__ import annotations

import html as html_lib
import json
from typing import Optional


def pil_keys(obra: str, pav: str, item: str) -> dict[str, str]:
    """Chaves aten_pil_* — espelho FV (SA + 3 camadas looping cego).

    Ref FV V303: ``fv_hifi_n1_render.agent_key_for_layer`` / human_hl_keys.
    """
    base = f"{obra}_{pav}_{item}".replace(" ", "_")
    return {
        "base": base,
        "human": f"aten_pil_ctx_human_{base}",
        # legado (= L1)
        "agent": f"aten_pil_ctx_agent_{base}",
        "agent_verdict": f"aten_pil_ctx_agent_verdict_{base}",
        # anotações agênticas por camada (looping cego L1→L2→L3)
        "agent_l1": f"aten_pil_ctx_agent_l1_{base}",
        "agent_l2": f"aten_pil_ctx_agent_l2_{base}",
        "agent_l3": f"aten_pil_ctx_agent_l3_{base}",
        "agent_verdict_l1": f"aten_pil_ctx_agent_verdict_l1_{base}",
        "agent_verdict_l2": f"aten_pil_ctx_agent_verdict_l2_{base}",
        "agent_verdict_l3": f"aten_pil_ctx_agent_verdict_l3_{base}",
        # Destaque SA = motor com tags (sempre gerado no N1)
        "hl_sa": f"aten_pil_hl_sa_human_{base}",
        "hl_l1": f"aten_pil_hl_l1_human_{base}",
        "hl_l2": f"aten_pil_hl_l2_human_{base}",
        "hl_l3": f"aten_pil_hl_l3_human_{base}",
        "hl_agent": f"aten_pil_hl_agent_human_{base}",  # legado = L1
    }


def css_pil_qa() -> str:
    return """
/* ── PIL QA chrome (espelho FV) ── */
.pil-layer-toggle{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 10px}
.pil-hl-btn{min-height:34px;padding:6px 10px;border-radius:8px;cursor:pointer;
  background:#1a1a1a;border:1px solid #333;color:#aaa;font:11px Consolas,monospace}
.pil-hl-btn:hover{border-color:#3d8bfd;color:#ddd}
.pil-hl-btn.active[data-hl='sa_plain']{background:#2a1515;border-color:#ef9a9a;color:#ffcdd2}
.pil-hl-btn.active[data-hl='sa']{background:#3b1515;border-color:#ff5252;color:#ffcdd2}
.pil-hl-btn.active[data-hl='l1'],.pil-hl-btn.active[data-hl='agent']{background:#00363a;border-color:#00e5ff;color:#b2ebf2}
.pil-hl-btn.active[data-hl='l2']{background:#3a1a3a;border-color:#e040fb;color:#f3c9ff}
.pil-hl-btn.active[data-hl='l3']{background:#3a2b00;border-color:#ffab00;color:#ffe0b2}
.pil-hl-legend{font-size:10px;color:#666;margin-left:4px;line-height:1.35;max-width:52em}
.pil-hl-legend b.sa{color:#ff8a80}.pil-hl-legend b.l1{color:#4dd0e1}
.pil-hl-legend b.l2{color:#e040fb}.pil-hl-legend b.l3{color:#ffab00}
.pil-n1-layers{position:relative;width:100%;height:100%;background:#0a0a0a}
.pil-layer{position:absolute;inset:0;width:100%;height:100%}
.pil-layer-hidden{display:none!important}
.pil-layer-sa,.pil-layer-sa-plain{z-index:1}
.pil-layer-l1,.pil-layer-l2,.pil-layer-l3,.pil-layer-agent{z-index:2;background:#0a0a0a}
.pil-layer .n1-svg{position:absolute;inset:0;width:100%;height:100%;margin:0;padding:0;box-sizing:border-box}
.pil-layer .n1-svg svg,.pil-layer svg,.pil-panzoom svg{
  display:block;width:100%;height:100%;max-width:100%;max-height:100%;
  background:#0a0a0a}
.pil-agent-placeholder{padding:16px;color:#4dd0e1;font-size:12px;line-height:1.45;background:#0a1520;border:1px dashed #2a6080;border-radius:6px;margin:8px}
/* abas anotação agêntica L1/L2/L3 (espelho FV) */
.pil-agent-tab-wrap{display:flex;flex-direction:column;gap:8px}
.pil-agent-tabs{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 4px}
.pil-agent-tab-btn{min-height:24px;padding:3px 8px;border-radius:5px;cursor:pointer;
  background:#121820;border:1px solid #2a4058;color:#8ab;font:10px Consolas,monospace}
.pil-agent-tab-btn:hover{border-color:#4dd0e1;color:#cff}
.pil-agent-tab-btn.active{background:#00363a;border-color:#00e5ff;color:#b2ebf2;font-weight:700}
.pil-agent-tab-panel{display:none}
.pil-agent-tab-panel.active{display:block}
.pil-human-hl-row.l2 .pil-human-hl-row-label{color:#e040fb}
.pil-human-hl-row.l3 .pil-human-hl-row-label{color:#ffab00}
/* pan/zoom N1 SVG — viewBox (igual FV), NÃO CSS scale */
.pil-panzoom{position:relative;width:100%;max-width:100%;height:560px;box-sizing:border-box;background:#0a0a0a;
  overflow:hidden;cursor:grab;border:1px solid #2a2a2a;border-radius:4px;touch-action:none;user-select:none}
.pil-panzoom:active{cursor:grabbing}
.pil-panzoom-inner{position:absolute;inset:0;width:100%;height:100%;margin:0;padding:0;box-sizing:border-box}
.pil-panzoom-reset{position:absolute;top:8px;right:8px;z-index:30;background:#2a2a2a;color:#ccc;
  border:1px solid #444;padding:4px 10px;cursor:pointer;font-size:11px;border-radius:4px}
.pil-panzoom-reset:hover{border-color:#7eb8f7;color:#fff}
.pil-panzoom-hint{position:absolute;bottom:6px;left:8px;z-index:30;font-size:10px;color:#666;pointer-events:none}
.pil-notes-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:4px}
@media(max-width:900px){.pil-notes-grid{grid-template-columns:1fr}}
.pil-human-box{background:#14120a;border:1px solid #554400;border-radius:8px;padding:8px 10px}
.pil-agent-box{background:#0a121c;border:1px solid #2a5080;border-radius:8px;padding:8px 10px}
.pil-human-box .box-title{color:#f0b840;font-size:12px;font-weight:700;margin-bottom:6px}
.pil-agent-box .box-title{color:#7ec8ff;font-size:12px;font-weight:700;margin-bottom:6px}
.pil-box-help,.pil-human-hl-help,.pil-agent-verdict-hint{display:none!important}
.pil-human-hl-grid{display:flex;flex-direction:column;gap:3px;margin-bottom:6px}
.pil-human-hl-row{display:flex;flex-wrap:wrap;align-items:center;gap:4px 6px}
.pil-human-hl-row-label{font-size:10px;font-weight:700;min-width:7.5em;color:#c9a050}
.pil-human-hl-row.sa .pil-human-hl-row-label{color:#ff8a80}
.pil-human-hl-row.l1 .pil-human-hl-row-label,.pil-human-hl-row.ag .pil-human-hl-row-label{color:#4dd0e1}
.pil-verdict{display:flex;flex-wrap:wrap;gap:3px;margin:0}
.pil-verdict-opt{display:inline-flex;align-items:center;gap:3px;min-height:18px;padding:1px 6px;
  border-radius:4px;border:1px solid #333;background:#151515;color:#aaa;font-size:10px;line-height:1.2;cursor:pointer}
.pil-verdict-opt input{accent-color:#4fc3a1;width:11px;height:11px;margin:0}
.pil-verdict-opt.validou:has(input:checked){border-color:#4fc3a1;background:#0b180b;color:#9fdfb0}
.pil-verdict-opt.invalidou:has(input:checked){border-color:#f07178;background:#1a0a0a;color:#f0a0a0}
.pil-agent-box.has-validou{outline:1px solid #2a6a4a}
.pil-agent-box.has-invalidou{outline:1px solid #6a2a2a}
.pil-agent-box.fv-incomplete,.pil-agent-box.pil-incomplete{outline:1px dashed #445;outline-offset:2px}
textarea.pil-ta-human{width:100%;min-height:64px;box-sizing:border-box;background:#1a1a0a;color:#f0b840;
  border:1px solid #554400;border-radius:6px;padding:6px 8px;font:12px/1.35 Consolas,monospace;resize:vertical}
/* ~+20% em Y vs 64px para equilibrar com coluna humana (validadores + atenção) */
textarea.pil-ta-agent{width:100%;min-height:80px;box-sizing:border-box;background:#0d1520;color:#7ec8ff;
  border:1px solid #2a5080;border-radius:6px;padding:6px 8px;font:12px/1.35 Consolas,monospace;resize:vertical}
textarea.pil-need-text{border-color:#f0b840!important}
.pil-notes-status{font-size:11px;color:#888;margin-top:8px}
.pil-notes-status.ok{color:#4fc3a1}.pil-notes-status.warn{color:#f0b840}.pil-notes-status.err{color:#f07178}
"""


def human_hl_validators_html(keys: dict[str, str], item: str) -> str:
    safe = html_lib.escape(item, quote=True)
    k_sa = html_lib.escape(keys["hl_sa"], quote=True)
    k_l1 = html_lib.escape(keys.get("hl_l1") or keys["hl_agent"], quote=True)
    k_l2 = html_lib.escape(keys.get("hl_l2") or "", quote=True)
    k_l3 = html_lib.escape(keys.get("hl_l3") or "", quote=True)
    # legado
    k_ag = html_lib.escape(keys["hl_agent"], quote=True)

    def row(kind: str, label: str, key: str, group: str) -> str:
        if not key:
            return ""
        return (
            f'<div class="pil-human-hl-row {kind}" data-hl-target="{kind}">'
            f'<span class="pil-human-hl-row-label">{label}</span>'
            f'<div class="pil-verdict" role="radiogroup">'
            f'<label class="pil-verdict-opt validou">'
            f'<input type="radio" name="{group}" data-atkey="{key}" '
            f'data-role="human-hl-verdict" value="validou" onchange="saveAtenTA(this)">'
            f"<span>Validou</span></label>"
            f'<label class="pil-verdict-opt invalidou">'
            f'<input type="radio" name="{group}" data-atkey="{key}" '
            f'data-role="human-hl-verdict" value="invalidou" onchange="saveAtenTA(this)">'
            f"<span>Invalidou</span></label>"
            f"</div></div>"
        )

    return (
        '<div class="pil-human-hl-validators">'
        '<div class="pil-human-hl-grid">'
        + row("sa", "🏷 SA tags", k_sa, f"pil_hl_sa_{safe}")
        + row("l1", "🔵 Camada 1", k_l1, f"pil_hl_l1_{safe}")
        + row("l2", "🟣 Camada 2", k_l2, f"pil_hl_l2_{safe}")
        + row("l3", "🟠 Camada 3", k_l3, f"pil_hl_l3_{safe}")
        + (
            f'<input type="hidden" data-atkey="{k_ag}" value="" data-role="legacy-hl-agent">'
            if k_ag and k_ag != k_l1
            else ""
        )
        + "</div></div>"
    )


def human_annotation_box_html(keys: dict[str, str], item: str) -> str:
    k = html_lib.escape(keys["human"], quote=True)
    safe = html_lib.escape(item)
    return (
        f'<div class="pil-human-box" id="pil-human-box">'
        f'<div class="box-title">✏️ Humano — {safe}</div>'
        f'{human_hl_validators_html(keys, item)}'
        f'<textarea class="pil-ta-human" data-atkey="{k}" data-atrole="human" '
        f'onblur="saveAtenTA(this)" oninput="saveAtenTA(this)" '
        f'placeholder="Atenção {safe}…"></textarea>'
        f"</div>"
    )


def agent_annotation_box_layer_html(
    keys: dict[str, str], item: str, *, layer: int
) -> str:
    """Uma caixa de anotação agêntica (L1/L2/L3) — espelho FV agent_annotation_box_html."""
    ly = int(layer)
    k_map = {1: "agent_l1", 2: "agent_l2", 3: "agent_l3"}
    v_map = {1: "agent_verdict_l1", 2: "agent_verdict_l2", 3: "agent_verdict_l3"}
    # L1 também grava nas chaves legadas agent / agent_verdict
    k = html_lib.escape(keys.get(k_map[ly]) or keys["agent"], quote=True)
    vk = html_lib.escape(keys.get(v_map[ly]) or keys["agent_verdict"], quote=True)
    safe = html_lib.escape(item)
    safe_q = html_lib.escape(item, quote=True)
    group = f"pil_agent_verdict_l{ly}_{safe_q}"
    titles = {
        1: "🔵 Camada 1",
        2: "🟣 Camada 2",
        3: "🟠 Camada 3",
    }
    default_ph = f"L{ly} · {safe}…"
    legacy_attrs = ""
    if ly == 1:
        leg_k = html_lib.escape(keys["agent"], quote=True)
        leg_vk = html_lib.escape(keys["agent_verdict"], quote=True)
        legacy_attrs = f' data-legacy-atkey="{leg_k}" data-legacy-verdict="{leg_vk}"'
    return (
        f'<div class="pil-agent-box" data-layer="{ly}"{legacy_attrs}>'
        f'<div class="box-title">🤖 {titles[ly]} · {safe}</div>'
        f'<div class="pil-verdict" role="radiogroup" aria-label="Veredito L{ly}">'
        f'<label class="pil-verdict-opt validou">'
        f'<input type="radio" name="{group}" data-atkey="{vk}" data-role="agent-verdict" '
        f'value="validou" onchange="onAgentVerdictChange(this)">'
        f"<span>Validou</span></label>"
        f'<label class="pil-verdict-opt invalidou">'
        f'<input type="radio" name="{group}" data-atkey="{vk}" data-role="agent-verdict" '
        f'value="invalidou" onchange="onAgentVerdictChange(this)">'
        f"<span>Invalidou</span></label>"
        f"</div>"
        f'<textarea class="pil-ta-agent" data-atkey="{k}" data-atrole="agent" data-layer="{ly}" '
        f'data-placeholder-default="{html_lib.escape(default_ph, quote=True)}" '
        f'onblur="saveAtenTA(this)" oninput="refreshAgentVerdictUI();saveAtenTA(this)" '
        f'placeholder="{html_lib.escape(default_ph, quote=True)}"></textarea>'
        f"</div>"
    )


def agent_annotation_boxes_html(keys: dict[str, str], item: str) -> str:
    """Mini-abas Camada 1/2/3 — looping cego (espelho FV V303)."""
    tabs = "".join(
        f'<button type="button" class="pil-agent-tab-btn{" active" if ly == 1 else ""}" '
        f'data-atab="{ly}">{"🔵" if ly==1 else "🟣" if ly==2 else "🟠"} Camada {ly}</button>'
        for ly in (1, 2, 3)
    )
    panels = "".join(
        f'<div class="pil-agent-tab-panel{" active" if ly == 1 else ""}" data-atab-panel="{ly}">'
        + agent_annotation_box_layer_html(keys, item, layer=ly)
        + "</div>"
        for ly in (1, 2, 3)
    )
    return (
        f'<div class="pil-agent-tab-wrap">'
        f'<div class="pil-agent-tabs" role="tablist">{tabs}</div>'
        f"{panels}</div>"
    )


def agent_annotation_box_html(keys: dict[str, str], item: str) -> str:
    """Compat: retorna as 3 abas (antes era caixa única)."""
    return agent_annotation_boxes_html(keys, item)


def notes_grid_html(obra: str, pav: str, item: str) -> str:
    keys = pil_keys(obra, pav, item)
    return (
        '<div class="sec"><div class="sec-title">Validação · humano + agêntico</div>'
        '<div class="sec-body">'
        '<div class="pil-notes-grid">'
        f"{human_annotation_box_html(keys, item)}"
        f"{agent_annotation_boxes_html(keys, item)}"
        "</div>"
        '<div id="pil-notes-status" class="pil-notes-status">—</div>'
        "</div></div>"
    )


def n1_layer_toggle_and_layers(
    *,
    sa_svg: str,
    sa_plain_svg: str = "",
    agent_svg: str = "",
    l1_svg: str = "",
    l2_svg: str = "",
    l3_svg: str = "",
    item: str,
    proposal_src: str = "",
    l1_src: str = "",
    l2_src: str = "",
    l3_src: str = "",
    sa_plain_src: str = "",
    sa_tags_src: str = "",
    viewer_id: str = "",
) -> str:
    """Toggle SA sem tags | SA com tags | L1 | L2 | L3 (uma visível) + pan/zoom.

    Duas abas SA:
      - ``sa_plain`` — N1 estrutural + marco vermelho (sem chips)
      - ``sa`` — interpretação do motor **com tags** (baseline QA)
    L1/L2/L3 = looping cego (espelho FV V303).
    """
    src_plain = sa_plain_src or f"../propostas/{item}_sa_plain.svg"
    src_tags = sa_tags_src or f"../propostas/{item}_sa_motor.svg"
    src_l1 = l1_src or proposal_src or f"../propostas/{item}_qa_L1.svg"
    src_l2 = l2_src or f"../propostas/{item}_qa_L2.svg"
    src_l3 = l3_src or f"../propostas/{item}_qa_L3.svg"
    src_l1_alt = proposal_src or f"../propostas/{item}_qa_proposta.svg"
    cid = viewer_id or f"pil-n1-pz-{item}"
    safe_cid = html_lib.escape(cid, quote=True)

    def _layer_inner(svg: str, src: str, label: str) -> str:
        if svg:
            return f'<div class="n1-svg">{svg}</div>'
        return (
            f'<div class="pil-agent-placeholder">'
            f"<b>{html_lib.escape(label)} — aguardando SVG.</b><br>"
            f"Esperado: <code>{html_lib.escape(src)}</code>"
            f"</div>"
        )

    l1_body = l1_svg or agent_svg
    # Default ativo: SA com tags (interpretação). Sem tags ao lado para contraste.
    toggle = (
        '<div class="pil-layer-toggle" role="toolbar" aria-label="Camadas de destaque">'
        '<button type="button" class="pil-hl-btn" data-hl="sa_plain">🔴 SA sem tags</button>'
        '<button type="button" class="pil-hl-btn active" data-hl="sa">🏷 SA com tags</button>'
        '<button type="button" class="pil-hl-btn" data-hl="l1">🔵 Ag. camada 1</button>'
        '<button type="button" class="pil-hl-btn" data-hl="l2">🟣 Ag. camada 2</button>'
        '<button type="button" class="pil-hl-btn" data-hl="l3">🟠 Ag. camada 3</button>'
        '<span class="pil-hl-legend">'
        '<b class="sa">SA</b> limpo · tags · '
        '<b class="l1">L1</b>/<b class="l2">L2</b>/<b class="l3">L3</b> · scroll=zoom</span></div>'
    )
    # Preferir fetch (data-proposal-src) — SVG embutido só se passado e pequeno.
    plain_inner = _layer_inner(sa_plain_svg, src_plain, "SA sem tags")
    sa_inner = _layer_inner(sa_svg, src_tags, "SA com tags")
    layers = (
        f'<div class="pil-n1-layers" data-ctx-layers="1" data-multi-layer="1">'
        f'<div class="pil-layer pil-layer-sa-plain pil-layer-hidden" data-layer="sa_plain" '
        f'data-visible="0" data-proposal-src="{html_lib.escape(src_plain, quote=True)}">'
        f"{plain_inner}</div>"
        f'<div class="pil-layer pil-layer-sa" data-layer="sa" data-visible="1" '
        f'data-proposal-src="{html_lib.escape(src_tags, quote=True)}">'
        f"{sa_inner}</div>"
        f'<div class="pil-layer pil-layer-l1 pil-layer-agent pil-layer-hidden" '
        f'data-layer="l1" data-visible="0" '
        f'data-proposal-src="{html_lib.escape(src_l1, quote=True)}" '
        f'data-proposal-src-alt="{html_lib.escape(src_l1_alt, quote=True)}">'
        f"{_layer_inner(l1_body, src_l1, 'Camada 1')}</div>"
        f'<div class="pil-layer pil-layer-l2 pil-layer-hidden" '
        f'data-layer="l2" data-visible="0" '
        f'data-proposal-src="{html_lib.escape(src_l2, quote=True)}">'
        f"{_layer_inner(l2_svg, src_l2, 'Camada 2')}</div>"
        f'<div class="pil-layer pil-layer-l3 pil-layer-hidden" '
        f'data-layer="l3" data-visible="0" '
        f'data-proposal-src="{html_lib.escape(src_l3, quote=True)}">'
        f"{_layer_inner(l3_svg, src_l3, 'Camada 3')}</div>"
        f"</div>"
    )
    viewer = (
        f'<div id="{safe_cid}" class="pil-panzoom" data-panzoom="1" data-pil-pz="1">'
        f'<button type="button" class="pil-panzoom-reset" data-pz-reset="{safe_cid}">Reset zoom</button>'
        f'<div class="pil-panzoom-hint">scroll zoom · arrastar · duplo-clique reset</div>'
        f'<div class="pil-panzoom-inner" data-pz-inner="1">{layers}</div>'
        f"</div>"
    )
    return toggle + viewer


def wrap_n1_panzoom(svg_markup: str, *, viewer_id: str) -> str:
    """Viewer pan/zoom para um SVG isolado (ex. N1 distante)."""
    safe_cid = html_lib.escape(viewer_id, quote=True)
    inner = svg_markup or '<p class="muted">indisponível</p>'
    return (
        f'<div id="{safe_cid}" class="pil-panzoom" data-panzoom="1" data-pil-pz="1">'
        f'<button type="button" class="pil-panzoom-reset" data-pz-reset="{safe_cid}">Reset zoom</button>'
        f'<div class="pil-panzoom-hint">scroll zoom · arrastar · duplo-clique reset</div>'
        f'<div class="pil-panzoom-inner" data-pz-inner="1">'
        f'<div class="n1-svg">{inner}</div></div></div>'
    )

def notes_store_tag(initial: Optional[dict] = None) -> str:
    payload = initial or {"version": 1, "updated_at": "", "notes": {}}
    body = json.dumps(payload, ensure_ascii=False)
    return f'<script type="application/json" id="pil-notes-store">{body}</script>'


def js_pil_qa(*, notes_api_default: str = "http://127.0.0.1:18765") -> str:
    """JS autosave + layer toggle (compatível com serve_abcd /api/notes/{page})."""
    api = json.dumps(notes_api_default)
    return f"""
<script id="pil-qa-notes">
(function(){{
  var DEFAULT_API={api};
  function _pageStem(){{
    var p=location.pathname.split('/').pop()||'page';
    return p.replace(/\\.html?$/i,'');
  }}
  function _notesEl(){{ return document.getElementById('pil-notes-store'); }}
  function _readStore(){{
    var el=_notesEl();
    if(!el) return {{version:1, updated_at:'', notes:{{}}}};
    try {{ return JSON.parse(el.textContent||'{{}}') || {{version:1,notes:{{}}}}; }}
    catch(e){{ return {{version:1, updated_at:'', notes:{{}}}}; }}
  }}
  function _writeStore(obj){{
    var el=_notesEl();
    if(!el){{
      el=document.createElement('script');
      el.type='application/json'; el.id='pil-notes-store';
      (document.body||document.documentElement).appendChild(el);
    }}
    obj.version=1;
    obj.updated_at=new Date().toISOString();
    el.textContent=JSON.stringify(obj, null, 2);
    return obj;
  }}
  function setStatus(msg, cls){{
    var st=document.getElementById('pil-notes-status');
    if(!st) return;
    st.textContent=msg;
    st.className='pil-notes-status'+(cls?(' '+cls):'');
  }}
  function collectNotes(){{
    var notes={{}};
    document.querySelectorAll('textarea[data-atkey]').forEach(function(ta){{
      var k=ta.dataset.atkey; if(!k) return;
      notes[k]=ta.value||'';
    }});
    document.querySelectorAll('input[type="radio"][data-atkey]:checked').forEach(function(el){{
      notes[el.dataset.atkey]=el.value;
    }});
    return notes;
  }}
  function applyNotes(notes){{
    if(!notes) return;
    document.querySelectorAll('textarea[data-atkey]').forEach(function(ta){{
      var k=ta.dataset.atkey;
      if(notes.hasOwnProperty(k)) ta.value=notes[k];
    }});
    document.querySelectorAll('input[type="radio"][data-atkey]').forEach(function(el){{
      var k=el.dataset.atkey;
      if(!notes.hasOwnProperty(k)) return;
      el.checked=String(notes[k])===String(el.value);
    }});
    refreshAgentVerdictUI();
  }}
  function refreshAgentVerdictUI(root){{
    root=root||document;
    root.querySelectorAll('.pil-agent-box').forEach(function(box){{
      var checked=box.querySelector('input[type="radio"][data-role="agent-verdict"]:checked');
      var ta=box.querySelector('textarea[data-atrole="agent"]');
      var v=checked?checked.value:'';
      box.classList.toggle('has-validou', v==='validou');
      box.classList.toggle('has-invalidou', v==='invalidou');
      if(ta){{
        var base=ta.getAttribute('data-placeholder-default')||'…';
        if(v==='validou') ta.placeholder='VALIDOU · '+base;
        else if(v==='invalidou') ta.placeholder='INVALIDOU · '+base;
        else ta.placeholder=base;
        var txt=(ta.value||'').trim();
        var incomplete=!!v && txt.length<12;
        ta.classList.toggle('pil-need-text', incomplete);
        box.classList.toggle('pil-incomplete', incomplete||!v);
      }}
    }});
  }}
  window.refreshAgentVerdictUI=refreshAgentVerdictUI;
  window.onAgentVerdictChange=function(el){{
    refreshAgentVerdictUI(el&&el.closest?el.closest('.pil-agent-box')||document:document);
    saveAtenTA(el);
  }};
  function _notesApiBase(){{
    if(window.PIL_NOTES_API) return String(window.PIL_NOTES_API).replace(/\\/$/,'');
    if(location.protocol==='http:'||location.protocol==='https:') return location.origin;
    return DEFAULT_API;
  }}
  var _pushTimer=null;
  function _pushNotesToServer(payload, quiet){{
    if(_pushTimer) clearTimeout(_pushTimer);
    _pushTimer=setTimeout(function(){{
      var url=_notesApiBase()+'/api/notes/'+encodeURIComponent(_pageStem());
      fetch(url,{{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify(payload)
      }}).then(function(r){{
        if(!r.ok) throw new Error('HTTP '+r.status);
        return r.json();
      }}).then(function(){{
        if(!quiet) setStatus('salvo no disco · '+new Date().toLocaleTimeString(), 'ok');
        else setStatus('salvo · '+new Date().toLocaleTimeString(), 'ok');
      }}).catch(function(err){{
        setStatus('local ok · disco offline ('+err+') — use serve_abcd_fichas', 'warn');
      }});
    }}, 350);
  }}
  function persistAllNotes(quiet){{
    var notes=collectNotes();
    var payload={{version:1, updated_at:new Date().toISOString(), page:_pageStem(), notes:notes}};
    try{{
      Object.keys(notes).forEach(function(k){{
        if(notes[k]) localStorage.setItem(k, notes[k]); else localStorage.removeItem(k);
      }});
      localStorage.setItem('pil_notes_pack_'+_pageStem(), JSON.stringify(payload));
    }}catch(e){{}}
    _writeStore(payload);
    _pushNotesToServer(payload, quiet);
    refreshAgentVerdictUI();
    return payload;
  }}
  window.saveAtenTA=function(el){{
    if(el && el.dataset && el.dataset.atkey){{
      try{{
        var v=(el.type==='radio'||el.type==='checkbox')?(el.checked?el.value:(el.value||'')):(el.value||'');
        if(el.type==='radio'){{ if(el.checked) localStorage.setItem(el.dataset.atkey, el.value); }}
        else if(v) localStorage.setItem(el.dataset.atkey, v);
        else localStorage.removeItem(el.dataset.atkey);
      }}catch(e){{}}
    }}
    persistAllNotes(true);
  }};
  window.persistAllNotes=persistAllNotes;

  /* ── pan/zoom por viewBox (mesma tech do FV V302 — vetorial, sem pixelar) ── */
  function _activeSvg(outer){{
    var all=outer.querySelectorAll('svg');
    for(var i=0;i<all.length;i++){{
      var el=all[i];
      var layer=el.closest('.pil-layer');
      if(layer && layer.classList.contains('pil-layer-hidden')) continue;
      if(el.offsetParent!==null || !layer) return el;
    }}
    return outer.querySelector('svg');
  }}
  function _allSyncSvgs(outer){{
    var list=[].slice.call(outer.querySelectorAll(
      '.pil-layer-sa svg, .pil-layer-sa-plain svg, .pil-layer-l1 svg, .pil-layer-l2 svg, .pil-layer-l3 svg, ' +
      'svg.pil-sync-vb, .pil-layer-agent svg.pil-sync-vb, .pil-panzoom-inner > .n1-svg > svg'
    ));
    return list.filter(function(s,i,a){{
      var layer=s.closest && s.closest('.pil-layer');
      var lid=layer && layer.getAttribute('data-layer');
      if(layer && lid && lid!=='sa' && lid!=='sa_plain'
         && !s.classList.contains('pil-sync-vb')) {{
        var vb=(s.getAttribute('viewBox')||'').trim();
        if(!/^0 +0 +/.test(vb) && s.dataset.hifiAgent!=='1') return false;
      }}
      return a.indexOf(s)===i;
    }});
  }}
  function _prepPilSvg(s){{
    if(!s) return;
    if(!s.getAttribute('viewBox')) s.setAttribute('viewBox','0 0 900 640');
    var vb=s.getAttribute('viewBox')||'';
    // matplotlib HI-FI "0 0 W H" → sincroniza com SA
    var isHifi = s.classList.contains('pil-sync-vb') || /^0 +0 +/.test(vb.trim());
    if(!s.dataset.homeVb) s.dataset.homeVb=vb;
    s.setAttribute('preserveAspectRatio','xMidYMid meet');
    s.classList.add('pil-hifi-svg');
    if(isHifi){{ s.classList.add('pil-sync-vb'); s.dataset.hifiAgent='1'; }}
    else {{ s.classList.remove('pil-sync-vb'); s.dataset.hifiAgent='0'; }}
    s.removeAttribute('width'); s.removeAttribute('height');
    s.style.width='100%'; s.style.height='100%';
    s.style.maxWidth='100%'; s.style.maxHeight='100%';
    s.style.display='block'; s.style.background='#0a0a0a';
  }}
  function initPilPanZoom(cid){{
    var outer=typeof cid==='string'?document.getElementById(cid):cid;
    if(!outer||outer.dataset.pzInit==='1') return;
    var svg=_activeSvg(outer);
    if(!svg) return;
    outer.dataset.pzInit='1';
    function prep(s){{
      if(!s.getAttribute('viewBox')) s.setAttribute('viewBox','0 0 900 640');
      s.setAttribute('preserveAspectRatio','xMidYMid meet');
      s.classList.add('pil-sync-vb');
      s.style.width='100%'; s.style.height='100%';
      s.style.display='block'; s.style.background='#0a0a0a';
      s.removeAttribute('width'); s.removeAttribute('height');
      if(!s.dataset.homeVb) s.dataset.homeVb=s.getAttribute('viewBox')||'';
    }}
    prep(svg);
    _allSyncSvgs(outer).forEach(prep);
    outer.querySelectorAll('.pil-layer-agent svg, .pil-layer-l1 svg, .pil-layer-l2 svg, .pil-layer-l3 svg').forEach(_prepPilSvg);

    var base=svg.viewBox.baseVal;
    var home={{x:base.x,y:base.y,w:base.width,h:base.height}};
    if(!isFinite(home.w)||home.w<=0){{
      var parts=(svg.getAttribute('viewBox')||'0 0 900 640').replace(/,/g,' ').trim().split(/ +/).map(parseFloat);
      home={{x:parts[0]||0,y:parts[1]||0,w:parts[2]||900,h:parts[3]||640}};
    }}
    var state={{x:home.x,y:home.y,w:home.w,h:home.h}};
    var drag=false,lx=0,ly=0;

    function applyAgentRelative(){{
      var zx=state.w/home.w, zy=state.h/home.h;
      var rx=(state.x-home.x)/home.w;
      var ry=(state.y-home.y)/home.h;
      outer.querySelectorAll('.pil-layer-agent svg, .pil-layer-l1 svg, .pil-layer-l2 svg, .pil-layer-l3 svg').forEach(function(ag){{
        if(ag.dataset.hifiAgent==='1'||ag.classList.contains('pil-sync-vb')) return;
        _prepPilSvg(ag);
        var _vbRaw=(ag.dataset.homeVb||ag.getAttribute('viewBox')||'0 0 100 100');
        var parts=_vbRaw.replace(/,/g,' ').trim().split(/ +/).map(parseFloat);
        if(parts.length<4||parts.some(function(n){{return !isFinite(n);}})) return;
        var hx=parts[0], hy=parts[1], hw=parts[2], hh=parts[3];
        ag.setAttribute('viewBox', (hx+rx*hw)+' '+(hy+ry*hh)+' '+(hw*zx)+' '+(hh*zy));
      }});
    }}
    function apply(){{
      var vb=state.x+' '+state.y+' '+state.w+' '+state.h;
      _allSyncSvgs(outer).forEach(function(s){{ s.setAttribute('viewBox', vb); }});
      applyAgentRelative();
    }}
    function reset(){{ state={{x:home.x,y:home.y,w:home.w,h:home.h}}; apply(); }}
    outer._pzReset=reset;
    outer._pzApply=apply;
    outer._prepPilSvg=_prepPilSvg;

    function clientToSvg(cx,cy){{
      var act=_activeSvg(outer)||svg;
      var pt=act.createSVGPoint(); pt.x=cx; pt.y=cy;
      var ctm=act.getScreenCTM();
      if(!ctm) return {{x:state.x+state.w/2,y:state.y+state.h/2}};
      return pt.matrixTransform(ctm.inverse());
    }}
    outer.addEventListener('wheel',function(e){{
      e.preventDefault();
      var factor=e.deltaY<0?0.88:1.14;
      var nextW=state.w*factor, nextH=state.h*factor;
      var minW=home.w*0.03, maxW=home.w*4.5;
      if(nextW<minW){{ factor=minW/state.w; nextW=minW; nextH=state.h*factor; }}
      if(nextW>maxW){{ factor=maxW/state.w; nextW=maxW; nextH=state.h*factor; }}
      var p=clientToSvg(e.clientX,e.clientY);
      state.x=p.x-(p.x-state.x)*(nextW/state.w);
      state.y=p.y-(p.y-state.y)*(nextH/state.h);
      state.w=nextW; state.h=nextH; apply();
    }},{{passive:false}});
    outer.addEventListener('mousedown',function(e){{
      if(e.button!==0) return;
      if(e.target&&e.target.closest&&e.target.closest('button,textarea,a,input,.pil-layer-toggle')) return;
      drag=true; lx=e.clientX; ly=e.clientY;
      outer.style.cursor='grabbing'; e.preventDefault();
    }});
    window.addEventListener('mousemove',function(e){{
      if(!drag) return;
      var act=_activeSvg(outer)||svg;
      var ctm=act.getScreenCTM(); if(!ctm) return;
      var inv=ctm.inverse();
      var p0=act.createSVGPoint(); p0.x=lx; p0.y=ly;
      var p1=act.createSVGPoint(); p1.x=e.clientX; p1.y=e.clientY;
      var a=p0.matrixTransform(inv), b=p1.matrixTransform(inv);
      state.x-=(b.x-a.x); state.y-=(b.y-a.y);
      lx=e.clientX; ly=e.clientY; apply();
    }});
    window.addEventListener('mouseup',function(){{
      if(!drag) return; drag=false; outer.style.cursor='grab';
    }});
    outer.addEventListener('dblclick',function(e){{
      if(e.target&&e.target.closest&&e.target.closest('button,textarea')) return;
      reset();
    }});
    var btn=outer.querySelector('[data-pz-reset]');
    if(btn) btn.addEventListener('click', function(e){{ e.preventDefault(); e.stopPropagation(); reset(); }});
    apply();
  }}
  window.initPilPanZoom=initPilPanZoom;
  window.resetPilZoom=function(cid){{
    var el=document.getElementById(cid);
    if(el && el._pzReset) el._pzReset();
  }};
  window._prepPilSvg=_prepPilSvg;

  /* layer toggle SA | L1 | L2 | L3 — uma visível (espelho FV V303, sem "ambos") */
  var PIL_LAYER_MODES=['sa_plain','sa','l1','l2','l3'];
  var PIL_SVG_NS_SEQ=0;
  function _namespacePilSvg(svg, layerEl){{
    if(!svg || svg.getAttribute('data-pil-ids-namespaced')==='1') return;
    var layer=(layerEl&&layerEl.getAttribute('data-layer'))||'layer';
    var prefix='pil-'+_pageStem()+'-'+layer+'-'+(++PIL_SVG_NS_SEQ)+'-';
    var ids={{}};
    svg.querySelectorAll('[id]').forEach(function(el){{
      var oldId=el.getAttribute('id');
      if(!oldId) return;
      var newId=prefix+oldId;
      ids[oldId]=newId;
      el.setAttribute('id',newId);
    }});
    svg.querySelectorAll('*').forEach(function(el){{
      Array.prototype.slice.call(el.attributes||[]).forEach(function(attr){{
        var value=attr.value||'';
        var changed=value;
        changed=changed.replace(/#([A-Za-z0-9_.:-]+)/g,function(all,oldId){{
          return ids[oldId]?('#'+ids[oldId]):all;
        }});
        if(changed!==value) el.setAttribute(attr.name,changed);
      }});
    }});
    svg.setAttribute('data-pil-ids-namespaced','1');
  }}
  window._namespacePilSvg=_namespacePilSvg;
  function _auditPilSvgNamespaces(){{
    var seen={{}}, duplicates=[];
    document.querySelectorAll('.pil-layer svg [id]').forEach(function(el){{
      var id=el.getAttribute('id');
      if(!id) return;
      if(seen[id]) duplicates.push(id);
      else seen[id]=1;
    }});
    var unresolved=[];
    document.querySelectorAll('.pil-layer svg').forEach(function(svg){{
      var local={{}};
      svg.querySelectorAll('[id]').forEach(function(el){{ local[el.getAttribute('id')]=1; }});
      svg.querySelectorAll('use').forEach(function(el){{
        var href=el.getAttribute('href')||el.getAttribute('xlink:href')||'';
        if(href.charAt(0)==='#' && !local[href.slice(1)]) unresolved.push(href);
      }});
    }});
    var ok=!duplicates.length && !unresolved.length;
    if(document.body){{
      document.body.dataset.pilSvgIdsOk=ok?'1':'0';
      document.body.dataset.pilSvgDuplicateIds=String(duplicates.length);
      document.body.dataset.pilSvgUnresolvedRefs=String(unresolved.length);
    }}
    if(!ok && window.console) console.error('PIL SVG namespace inválido', {{duplicates:duplicates, unresolved:unresolved}});
    return {{ok:ok, duplicates:duplicates, unresolved:unresolved}};
  }}
  window.auditPilSvgNamespaces=_auditPilSvgNamespaces;
  function _loadLayerSvg(layerEl, outer, done){{
    if(!layerEl) return;
    function after(){{
      var s=layerEl.querySelector('svg');
      if(s){{
        _namespacePilSvg(s,layerEl); _prepPilSvg(s);
        _auditPilSvgNamespaces();
        if(outer&&outer._pzApply) outer._pzApply();
      }}
      if(done) done();
    }}
    if(layerEl.querySelector('svg')){{ after(); return; }}
    if(layerEl.getAttribute('data-loaded')==='1'){{ after(); return; }}
    var srcs=[layerEl.getAttribute('data-proposal-src'), layerEl.getAttribute('data-proposal-src-alt')].filter(Boolean);
    if(!srcs.length){{ after(); return; }}
    function tryFetch(i){{
      if(i>=srcs.length){{ after(); return; }}
      fetch(srcs[i],{{cache:'no-store'}}).then(function(r){{ return r.ok?r.text():null; }}).then(function(txt){{
        if(txt && txt.indexOf('<svg')>=0){{
          layerEl.innerHTML='<div class="n1-svg">'+txt+'</div>';
          layerEl.setAttribute('data-loaded','1');
          after();
        }} else tryFetch(i+1);
      }}).catch(function(){{ tryFetch(i+1); }});
    }}
    tryFetch(0);
  }}
  function setHlMode(mode){{
    var root=document.querySelector('[data-ctx-layers]');
    if(!root) return;
    if(mode==='agent'||mode==='c1') mode='l1';
    if(mode==='c2') mode='l2';
    if(mode==='c3') mode='l3';
    if(mode==='both') mode='sa';
    if(mode==='sa_tags'||mode==='tags') mode='sa';
    if(mode==='plain'||mode==='sa_raw') mode='sa_plain';
    if(PIL_LAYER_MODES.indexOf(mode)<0) mode='sa';
    var outer=root.closest('[data-panzoom]')||root.closest('.pil-panzoom');
    root.querySelectorAll('.pil-layer').forEach(function(el){{
      var id=el.getAttribute('data-layer')||'';
      if(!id){{
        if(el.classList.contains('pil-layer-sa-plain')) id='sa_plain';
        else if(el.classList.contains('pil-layer-sa')) id='sa';
        else if(el.classList.contains('pil-layer-l1')||el.classList.contains('pil-layer-agent')) id='l1';
        else if(el.classList.contains('pil-layer-l2')) id='l2';
        else if(el.classList.contains('pil-layer-l3')) id='l3';
      }}
      var on=(id===mode);
      el.classList.toggle('pil-layer-hidden', !on);
      el.setAttribute('data-visible', on?'1':'0');
      el.style.display=on?'':'none';
      el.style.opacity='1';
      /* todas as camadas: embutido se já tem <svg>, senão fetch data-proposal-src */
      if(on) _loadLayerSvg(el, outer);
    }});
    document.querySelectorAll('.pil-hl-btn').forEach(function(b){{
      var bh=b.getAttribute('data-hl');
      if(bh==='agent') bh='l1';
      b.classList.toggle('active', bh===mode);
    }});
    try{{ localStorage.setItem('pil_ctx_hl_mode_'+_pageStem(), mode); }}catch(e){{}}
  }}
  window.setPilHlMode=setHlMode;

  function setAgentTab(n, root){{
    root=root||document;
    var wrap=root.querySelector('.pil-agent-tab-wrap')||root;
    wrap.querySelectorAll('.pil-agent-tab-btn').forEach(function(b){{
      b.classList.toggle('active', b.getAttribute('data-atab')===String(n));
    }});
    wrap.querySelectorAll('.pil-agent-tab-panel').forEach(function(p){{
      p.classList.toggle('active', p.getAttribute('data-atab-panel')===String(n));
    }});
  }}
  window.setPilAgentTab=setAgentTab;

  document.addEventListener('DOMContentLoaded', function(){{
    document.querySelectorAll('.pil-hl-btn').forEach(function(btn){{
      btn.addEventListener('click', function(){{ setHlMode(btn.getAttribute('data-hl')||'sa'); }});
    }});
    document.querySelectorAll('.pil-agent-tabs').forEach(function(bar){{
      if(bar.dataset.bound==='1') return;
      bar.dataset.bound='1';
      bar.querySelectorAll('.pil-agent-tab-btn').forEach(function(btn){{
        btn.addEventListener('click', function(e){{
          e.preventDefault();
          setAgentTab(btn.getAttribute('data-atab'), bar.closest('.pil-agent-tab-wrap')||document);
        }});
      }});
    }});
    document.querySelectorAll('[data-pil-pz], .pil-panzoom[data-panzoom]').forEach(function(el){{
      if(el.id) initPilPanZoom(el.id);
    }});
    /* Namespace TODAS as camadas inline antes de qualquer troca/visibilidade.
       Matplotlib reutiliza IDs de glifos (DejaVuSans-*). Sem esta passagem,
       <use href="#..."> pode resolver no SVG de outra camada e exibir nomes
       aleatórios apesar do rótulo correto no artefato. */
    document.querySelectorAll('.pil-layer-sa svg, .pil-layer-sa-plain svg, .pil-layer-l1 svg, .pil-layer-l2 svg, .pil-layer-l3 svg, .pil-layer-agent svg').forEach(function(s){{
      _namespacePilSvg(s, s.closest('.pil-layer'));
      _prepPilSvg(s);
    }});
    _auditPilSvgNamespaces();
    try{{
      var m=localStorage.getItem('pil_ctx_hl_mode_'+_pageStem());
      if(m) setHlMode(m);
      else setHlMode('sa'); /* carrega SA com tags sob demanda */
    }}catch(e){{ setHlMode('sa'); }}
    // load notes: server > store > localStorage
    function boot(notes){{
      applyNotes(notes||{{}});
      if(notes && Object.keys(notes).length) setStatus('notas carregadas', 'ok');
      else setStatus('sem notas — valide destaques e escreva atenção', '');
    }}
    var localPack=null;
    try{{ localPack=JSON.parse(localStorage.getItem('pil_notes_pack_'+_pageStem())||'null'); }}catch(e){{}}
    var store=_readStore();
    var fromStore=(store && store.notes) ? store.notes : {{}};
    if(location.protocol==='http:'||location.protocol==='https:'){{
      fetch(_notesApiBase()+'/api/notes/'+encodeURIComponent(_pageStem()))
        .then(function(r){{ return r.ok?r.json():null; }})
        .then(function(data){{
          var n=(data && data.notes) ? data.notes : null;
          if(n && Object.keys(n).length) boot(n);
          else if(localPack && localPack.notes) boot(localPack.notes);
          else boot(fromStore);
        }})
        .catch(function(){{
          if(localPack && localPack.notes) boot(localPack.notes); else boot(fromStore);
        }});
    }} else {{
      if(localPack && localPack.notes) boot(localPack.notes); else boot(fromStore);
      setStatus('file:// — use serve_abcd_fichas p/ gravar no disco', 'warn');
    }}
    refreshAgentVerdictUI();
  }});
}})();
</script>
"""
