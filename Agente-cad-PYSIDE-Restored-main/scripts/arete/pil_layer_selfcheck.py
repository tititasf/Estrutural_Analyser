#!/usr/bin/env python
"""Auto-avaliação de uma camada desenhada: o agente confere o PRÓPRIO desenho
contra a geometria antes de pedir validação humana.

Para cada linha da tabela da camada, responde: existe contato real medido que
sustente essa entrada? (predicado único gap+extensão — `pil_geom_contato.py`).
Classifica cada linha em:
  OK        — contato medido sustenta o papel;
  CONVENCAO — sem contato próprio, mas justificada por regra do doc
              (dualidade AC/BC↔C: a passa em C espelha a chega em A/B);
  SEM_BASE  — nenhum contato e nenhuma regra → precisa arbitragem humana.

Veredito: valida só se não houver SEM_BASE.

Uso:
  py -3.12 scripts/arete/pil_layer_selfcheck.py --pack <pack> --item P24 --layer L3
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.arete.pil_agentic_highlight_draw import load_project  # noqa: E402
from scripts.arete.pil_l2_evidence_check import _beam_contours, _is_horizontal  # noqa: E402
from scripts.arete.pil_geom_contato import relacao  # noqa: E402

EMPTY = ("", "—", "-", "nenhuma", None)


def _real(rows):
    return [r for r in (rows or []) if (r.get("nome") or "") not in EMPTY]


def avaliar(faces, pillar, beams_by_name):
    xs = [p[0] for p in pillar["points"]]
    ys = [p[1] for p in pillar["points"]]
    px0, py0, px1, py1 = min(xs), min(ys), max(xs), max(ys)
    horiz = _is_horizontal(px0, py0, px1, py1)

    # relação medida por (viga, face, tipo) — alinhamento (passa) x perpendicular (chega)
    contatos = {}
    for nome, b in beams_by_name.items():
        for seg in _beam_contours(b):
            for fid in "ABCD":
                c = relacao(seg, fid, px0, py0, px1, py1, horizontal=horiz)
                if c:
                    prev = contatos.get((nome, fid, c.tipo))
                    if not prev or c.extensao > prev.extensao:
                        contatos[(nome, fid, c.tipo)] = c

    # chegas registradas em A/B (para justificar passa dual em C)
    chegas_ab = {(r.get("nome"), (r.get("canto") or "").upper())
                 for fid in ("A", "B") for r in _real((faces.get(fid) or {}).get("chega"))}

    # Caso 4 do doc — pilar DENTRO do corpo da viga: se a mesma viga passa nas
    # DUAS faces longas (A e B), as faces curtas (C e D) são limites internos.
    # Confirmado pelo humano no P24: "a face C está no interior de V321".
    passa_a = {r.get("nome") for r in _real((faces.get("A") or {}).get("passa"))}
    passa_b = {r.get("nome") for r in _real((faces.get("B") or {}).get("passa"))}
    engloba = passa_a & passa_b

    linhas = []
    for fid in "ABCD":
        for kind in ("passa", "chega", "interior"):
            for r in _real((faces.get(fid) or {}).get(kind)):
                nome = r.get("nome")
                canto = (r.get("canto") or "").upper()
                # 'interior' aceita sustentação de chega (viga que morre no pilar)
                tipos = {"passa": ("passa",), "chega": ("chega",), "interior": ("chega", "passa")}[kind]
                c = next((contatos[(nome, fid, t)] for t in tipos if (nome, fid, t) in contatos), None)
                if c:
                    st, why = "OK", c.detalhe
                elif fid == "C" and kind == "passa" and canto in ("CA", "CB") and \
                        (nome, "AC" if canto == "CA" else "BC") in chegas_ab:
                    st, why = "CONVENCAO", f"dual da chega {'A@AC' if canto=='CA' else 'B@BC'} (regra do doc)"
                elif kind == "interior" and fid in ("C", "D") and nome in engloba:
                    st, why = "CONVENCAO", (f"Caso 4 do doc: {nome} passa em A e B → o pilar está no "
                                            f"corpo da viga, logo a face {fid} é limite interno")
                else:
                    st, why = "SEM_BASE", "nenhum contato medido nesta face e nenhuma regra que sustente"
                linhas.append({"face": fid, "familia": kind, "nome": nome, "canto": canto,
                               "status": st, "motivo": why})
    return linhas


def rasterizar(svg_path: Path, faces, pillar, item: str, layer: str, only_fam: str | None) -> Path:
    """2ª camada de raciocínio (§3.6): transforma o desenho em imagem para o
    agente LER. `only_fam` isola uma família — com 8 tags juntas é impossível
    saber de quem é cada ponto."""
    import copy as _copy
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter, QGuiApplication
    from PySide6.QtSvg import QSvgRenderer
    from scripts.arete.pil_agentic_highlight_draw import render_agentic_svg

    src = svg_path
    if only_fam:
        t = {"faces": _copy.deepcopy(faces), "orientation": None}
        for fid in "ABCD":
            for k in ("lajes", "passa", "chega", "interior"):
                if k != only_fam:
                    t["faces"][fid][k] = []
        dxf, *_ = load_project(ROOT.parent / "project_data.vision",
                               "dd238e47-1dc6-4f63-a760-4e7ce19a7386", "Obra_TREINO_1", "13_PAV")
        src = svg_path.parent / f"_vision_{item}_{layer}_{only_fam}.svg"
        src.write_text(render_agentic_svg(dxf, pillar["points"], t, layer=layer.lower()),
                       encoding="utf-8")

    if QGuiApplication.instance() is None:
        QGuiApplication([])
    r = QSvgRenderer(str(src))
    W, H = 9000, 4166
    img = QImage(W, H, QImage.Format_ARGB32)
    img.fill(Qt.black)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    r.render(p)
    p.end()
    out = ROOT / "scripts" / "arete" / "relatorios" / f"_vision_{item}_{layer}{'_'+only_fam if only_fam else ''}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.copy(W // 2 - 380, H // 2 - 450, 760, 900).save(str(out))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True)
    ap.add_argument("--item", required=True)
    ap.add_argument("--layer", default="L3")
    ap.add_argument("--obra", default="Obra_TREINO_1")
    ap.add_argument("--pav", default="13_PAV")
    ap.add_argument("--port", type=int, default=18765)
    ap.add_argument("--project-id", default="dd238e47-1dc6-4f63-a760-4e7ce19a7386")
    ap.add_argument("--gravar", action="store_true", help="grava veredito na caixa da camada")
    ap.add_argument("--vision", action="store_true",
                    help="rasteriza o SVG da camada (2ª camada de raciocínio, §3.6) — "
                         "o agente DEVE ler o PNG antes de fechar a camada")
    ap.add_argument("--vision-only", metavar="FAM",
                    help="isola uma família (passa|chega|interior|lajes) no render de "
                         "conferência — com 8 tags juntas não se sabe de quem é cada ponto")
    args = ap.parse_args()

    prop = Path(args.pack) / "propostas"
    p = prop / f"{args.item}_qa_{args.layer}_tables.json"
    if not p.is_file():
        print(f"[ERR] sem {p.name}")
        return 2
    d = json.loads(p.read_text(encoding="utf-8"))
    faces = d.get("faces") or d["tables"]["faces"]

    _dxf, _sh, _sn, _sp, beams, pillars = load_project(
        ROOT.parent / "project_data.vision", args.project_id, args.obra, args.pav)
    pillar = next(x for x in pillars if x["name"] == args.item)
    linhas = avaliar(faces, pillar, {b.get("name"): b for b in beams})

    n = {"OK": 0, "CONVENCAO": 0, "SEM_BASE": 0}
    print(f"AUTO-AVALIAÇÃO {args.item} · {args.layer}\n")
    for l in linhas:
        n[l["status"]] += 1
        print(f"  [{l['status']:9s}] {l['face']}.{l['familia']:8s} {l['nome']}@{l['canto']:3s} — {l['motivo']}")
    veredito = "validou" if n["SEM_BASE"] == 0 else "invalidou"
    print(f"\n  OK={n['OK']}  CONVENCAO={n['CONVENCAO']}  SEM_BASE={n['SEM_BASE']}")
    print(f"  [camada 1 · geometria] {veredito.upper()}")

    if args.vision:
        png = rasterizar(prop / f"{args.item}_qa_{args.layer}.svg", faces, pillar,
                         args.item, args.layer, args.vision_only)
        print(f"\n  [camada 2 · visão] PNG gerado → {png}")
        print("  ⚠ O AGENTE DEVE LER ESTA IMAGEM antes de fechar a camada (doc §3.6).")
        print("    Checklist: tag no elemento certo? ponto da chega DENTRO do corpo da viga?")
        print("    tags sobrepostas? a imagem bate com a tabela?")
        print("  [camada 3 · contradição] se visão discordar da geometria: NÃO decidir —")
        print("    registrar apontamento estruturado e devolver para arbitragem humana.")
    else:
        print("  [camada 2 · visão] NÃO EXECUTADA — camada não pode ser fechada sem --vision (§3.6)")

    if args.gravar:
        base = f"{args.obra}_{args.pav}_{args.item}"
        ln = args.layer.lower()
        txt = (f"[Auto-avaliação da {args.layer} · contato medido gap+extensão]\n"
               + "\n".join(f"[{l['status']}] {l['face']}.{l['familia']} {l['nome']}@{l['canto']} — {l['motivo']}"
                           for l in linhas)
               + f"\n\nOK={n['OK']} CONVENCAO={n['CONVENCAO']} SEM_BASE={n['SEM_BASE']} → {veredito.upper()}")
        with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/api/notes/{args.item}", timeout=10) as r:
            notes = json.loads(r.read().decode("utf-8")).get("notes") or {}
        notes[f"aten_pil_ctx_agent_{ln}_{base}"] = txt
        notes[f"aten_pil_ctx_agent_verdict_{ln}_{base}"] = veredito
        req = urllib.request.Request(
            f"http://127.0.0.1:{args.port}/api/notes/{args.item}",
            data=json.dumps({"notes": notes}, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=10).read()
        print(f"  gravado em aten_pil_ctx_agent_{ln}_*")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
