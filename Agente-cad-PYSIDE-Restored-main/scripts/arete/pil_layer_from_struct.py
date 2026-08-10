#!/usr/bin/env python
"""Desenha uma camada (L2/L3) a partir dos APONTAMENTOS ESTRUTURADOS da camada
anterior — sem reinterpretar português.

Fluxo: base = tabelas da camada anterior (L1/L2) + apontamentos estruturados
(`aten_pil_struct_l{N}_*`) → tabelas da camada alvo → SVG.

Mantém as travas do §3.3:
  T1 base = camada anterior (nunca SA);
  T2 gate de não-regressão (remoção só com apontamento explícito que a peça);
  T3 sem apontamento acionável → não redesenha.

Ações suportadas na tabela: falta · sobra · papel_errado · identidade_errada ·
dim_errada · canto_errado · duplicado.
Ações que NÃO mexem na tabela (viram pendência): geometria_invalida ·
pilar_especial · desenho.

Uso:
  py -3.12 scripts/arete/pil_layer_from_struct.py --pack <pack> --item P24 \\
      --base L1 --alvo L3 --struct-layer l2
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.arete.pil_agentic_highlight_draw import load_project, render_agentic_svg  # noqa: E402
from scripts.arete.pil_l2_evidence_check import _beam_contours, _is_horizontal  # noqa: E402
from scripts.arete.pil_geom_contato import contato_medido, relacao, medir_no_dxf  # noqa: E402

EMPTY = ("", "—", "-", "nenhuma", None)
TABELA = {"falta", "sobra", "papel_errado", "identidade_errada",
          "dim_errada", "canto_errado", "duplicado"}


def _real(rows):
    return [r for r in (rows or []) if (r.get("nome") or "") not in EMPTY]


def _load_tables(prop: Path, item: str, layer: str) -> dict | None:
    for cand in (f"{item}_qa_{layer}_tables.json", f"{item}_qa_{layer.upper()}_tables.json"):
        p = prop / cand
        if p.is_file():
            d = json.loads(p.read_text(encoding="utf-8"))
            return d.get("tables") or ({"faces": d["faces"], "orientation": d.get("orientation")}
                                       if "faces" in d else None)
    return None


def _find(faces, fid, nome, canto, kinds=("passa", "chega", "interior", "lajes")):
    for k in kinds:
        for r in _real((faces.get(fid) or {}).get(k)):
            if (not nome or r.get("nome") == nome) and (not canto or (r.get("canto") or "") == canto):
                return k, r
    return None, None


def _dim_de(faces, nome):
    for fid in "ABCD":
        for k in ("passa", "chega", "interior"):
            for r in _real((faces.get(fid) or {}).get(k)):
                if r.get("nome") == nome and r.get("dim"):
                    return r["dim"], r.get("nivel") or ""
    return "", ""


def ancorar_por_medicao(faces, pillar, beams_by_name, msp=None) -> list[str]:
    """Preenche dist_esq/dist_dir das vigas que CHEGAM com o trecho REAL medido.

    Assim o pontinho da tag cai no **centro da viga que chega** (padrão
    PADRAO-TAGS-DESTAQUE-AGENTICO-PIL) em vez de numa fração chutada ou na
    esquina do pilar. Vale para qualquer item — não é ajuste por pilar.

    **Fonte da medida (ordem):**
      1. LINHAS DO DXF (`medir_no_dxf`) — verdade de terra, é o que o humano vê;
      2. contorno de `beams.links.*_area_segs` — só como fallback.

    Por quê: em 2026-08-08 o contorno do DB do V304 (P24) estava deslocado 19 cm
    (uma largura de viga) em relação ao DXF — ancorar por ele punha o ponto fora
    da viga. O DXF dá y 2441..2460; o contorno dizia 2422..2441.
    """
    xs = [p[0] for p in pillar["points"]]
    ys = [p[1] for p in pillar["points"]]
    px0, py0, px1, py1 = min(xs), min(ys), max(xs), max(ys)
    horiz = _is_horizontal(px0, py0, px1, py1)
    face_len = {"A": py1 - py0, "B": py1 - py0, "C": px1 - px0, "D": px1 - px0}
    if horiz:
        face_len = {"A": px1 - px0, "B": px1 - px0, "C": py1 - py0, "D": py1 - py0}

    notas = []
    for fid in "ABCD":
        for r in _real((faces.get(fid) or {}).get("chega")):
            b = beams_by_name.get(r.get("nome"))
            if not b:
                continue
            # 0) NUNCA sobrescrever medida que já existe (lição do P24: o SA
            #    tinha de=61/dd=0 correto e a "correção" automática piorou).
            if str(r.get("dist_esq") or "").strip() not in EMPTY and \
               str(r.get("dist_dir") or "").strip() not in EMPTY:
                continue

            melhor, fonte = None, ""
            # 1) DXF — verdade de terra, mas SÓ em pilar vertical.
            #    Aferição de 2026-08-10 (51 chegadas do 13_PAV):
            #      vertical   → 33 OK / 8 divergem
            #      horizontal →  0 OK / 10 divergem  ← par de linhas errado
            #    Em horizontal a varredura casa paredes de outros elementos;
            #    até isso ser resolvido, não medir (melhor sem medida do que
            #    com medida errada).
            if msp is not None and not horiz:
                m = re.match(r"\s*(\d+(?:[.,]\d+)?)", str(r.get("dim") or ""))
                larg = float(m.group(1).replace(",", ".")) if m else 0.0
                if larg > 0:
                    melhor = medir_no_dxf(msp, fid, larg, px0, py0, px1, py1, horizontal=horiz)
                    fonte = "DXF"
            # 2) fallback: contorno do DB
            if not melhor:
                for seg in _beam_contours(b):
                    rel = relacao(seg, fid, px0, py0, px1, py1, horizontal=horiz)
                    if not rel or rel.tipo != "chega":
                        continue
                    cm = contato_medido(seg, fid, px0, py0, px1, py1, horizontal=horiz)
                    if cm and (melhor is None or (cm[1] - cm[0]) > (melhor[1] - melhor[0])):
                        melhor, fonte = cm, "contorno DB (fallback)"
            if not melhor:
                continue
            ini, fim = melhor
            fl = face_len[fid]
            r["dist_esq"] = f"{ini:.0f}cm"
            r["dist_dir"] = f"{fl - fim:.0f}cm"
            notas.append(f"ANCORADO {fid}.chega {r.get('nome')}@{r.get('canto')}: "
                         f"trecho {ini:.0f}..{fim:.0f}cm medido no {fonte} → ponto no centro da viga")
    return notas


def signature(faces):
    return {(f, k, r.get("nome"), r.get("canto")) for f in "ABCD"
            for k in ("passa", "chega", "interior", "lajes")
            for r in _real((faces.get(f) or {}).get(k))}


def aplicar(base: dict, entries: list) -> tuple[dict, list, list, set]:
    alvo = copy.deepcopy(base)
    faces = alvo["faces"]
    changes, pend, justificadas = [], [], set()

    for e in entries:
        acao = (e.get("acao") or "").strip()
        fid = (e.get("face") or "").strip().upper()
        canto = (e.get("canto") or "").strip().upper()
        papel = (e.get("papel") or "").strip()
        nome = (e.get("nome") or "").strip()
        obs = (e.get("obs") or "").strip()

        if acao not in TABELA:
            if acao:
                pend.append(f"[{acao}] {fid or '-'}{('@'+canto) if canto else ''} {nome} — {obs}")
            continue
        if not fid or fid not in faces:
            pend.append(f"[{acao}] sem face válida — {obs}")
            continue

        if acao == "falta":
            kind = papel or "passa"
            dim, nivel = _dim_de(faces, nome)
            lst = faces[fid].setdefault(kind, [])
            lst[:] = _real(lst)
            lst.append({"familia": "laje" if kind == "lajes" else "viga", "nome": nome or "?",
                        "dim": dim, "nivel": nivel, "canto": canto, "papel": kind,
                        "raw": "", "dist_esq": "—", "dist_dir": "—"})
            changes.append(f"ADICIONADO {fid}.{kind} {nome or '?'}@{canto} — {obs}")

        elif acao in ("sobra", "duplicado"):
            k, r = _find(faces, fid, nome, canto)
            if r:
                faces[fid][k] = [x for x in faces[fid][k] if x is not r]
                justificadas.add((fid, k, r.get("nome"), r.get("canto")))
                changes.append(f"REMOVIDO {fid}.{k} {r.get('nome')}@{r.get('canto')} ({acao}) — {obs}")
            else:
                pend.append(f"[{acao}] não localizei {fid} {nome}@{canto}")

        elif acao == "papel_errado":
            k, r = _find(faces, fid, nome, canto)
            if r and papel and papel != k:
                faces[fid][k] = [x for x in faces[fid][k] if x is not r]
                justificadas.add((fid, k, r.get("nome"), r.get("canto")))
                novo = dict(r); novo["papel"] = papel
                dst = faces[fid].setdefault(papel, [])
                dst[:] = _real(dst); dst.append(novo)
                changes.append(f"PAPEL {fid} {r.get('nome')}@{r.get('canto')}: {k} → {papel} — {obs}")
            else:
                pend.append(f"[papel_errado] não aplicável em {fid} {nome}@{canto}")

        elif acao in ("identidade_errada", "dim_errada", "canto_errado"):
            k, r = _find(faces, fid, nome, canto)
            if not r:
                pend.append(f"[{acao}] não localizei {fid} {nome}@{canto}")
                continue
            novo_val = obs.split("→")[-1].strip() if "→" in obs else ""
            if not novo_val:
                pend.append(f"[{acao}] {fid} {nome}@{canto}: informe o valor correto como 'atual → novo' na obs")
                continue
            campo = {"identidade_errada": "nome", "dim_errada": "dim", "canto_errado": "canto"}[acao]
            antigo = r.get(campo)
            justificadas.add((fid, k, r.get("nome"), r.get("canto")))
            r[campo] = novo_val
            changes.append(f"{campo.upper()} {fid}.{k}: {antigo} → {novo_val} — {obs}")

    return alvo, changes, pend, justificadas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True)
    ap.add_argument("--item", required=True)
    ap.add_argument("--base", default="L1")
    ap.add_argument("--alvo", default="L3")
    ap.add_argument("--struct-layer", default="l2")
    ap.add_argument("--obra", default="Obra_TREINO_1")
    ap.add_argument("--pav", default="13_PAV")
    ap.add_argument("--port", type=int, default=18765)
    ap.add_argument("--project-id", default="dd238e47-1dc6-4f63-a760-4e7ce19a7386")
    args = ap.parse_args()

    pack, item = Path(args.pack), args.item
    prop = pack / "propostas"
    base = _load_tables(prop, item, args.base)
    if base is None:
        print(f"[ERR] T1: sem tabelas da base {args.base} para {item}")
        return 2

    key = f"aten_pil_struct_{args.struct_layer}_{args.obra}_{args.pav}_{item}"
    with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/api/notes/{item}", timeout=10) as r:
        notes = (json.loads(r.read().decode("utf-8")).get("notes") or {})
    try:
        entries = json.loads(notes.get(key) or "[]")
    except Exception:
        entries = []
    if not entries:
        print(f"[T3] {item}: sem apontamento estruturado em {args.struct_layer} — não redesenha")
        return 0

    alvo, changes, pend, justif = aplicar(base, entries)

    perdidas = signature(base["faces"]) - signature(alvo["faces"])
    injustif = {p for p in perdidas if p not in justif}
    if injustif:
        print(f"[ABORTADO] T2: removeria sem justificativa: "
              + "; ".join(f"{f}.{k} {n}@{c}" for f, k, n, c in sorted(injustif)))
        return 3
    if not changes:
        print(f"[T3] {item}: nenhum apontamento acionável na tabela — não redesenha")
        for p in pend:
            print(f"   ? {p}")
        return 0

    dxf, _sh, _sn, _sp, beams, pillars = load_project(
        ROOT.parent / "project_data.vision", args.project_id, args.obra, args.pav)
    pillar = next(p for p in pillars if p["name"] == item)

    # ponto da tag "chega" vem da MEDIÇÃO (centro da viga), não de fração fixa
    import ezdxf as _ez
    _msp = _ez.readfile(str(dxf)).modelspace()
    changes += ancorar_por_medicao(alvo["faces"], pillar, {b.get("name"): b for b in beams}, msp=_msp)

    svg = render_agentic_svg(dxf, pillar.get("points") or [], alvo, layer=args.alvo.lower())
    (prop / f"{item}_qa_{args.alvo}.svg").write_text(svg, encoding="utf-8")
    (prop / f"{item}_qa_{args.alvo}_tables.json").write_text(
        json.dumps({"item": item, "base": args.base, "origem": f"struct_{args.struct_layer}",
                    "faces": alvo["faces"], "orientation": alvo.get("orientation"),
                    "changes": changes, "pendencias": pend},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] {item}: {args.alvo} desenhada a partir de {len(entries)} apontamento(s) de "
          f"{args.struct_layer} sobre {args.base}")
    for c in changes:
        print(f"   + {c}")
    for p in pend:
        print(f"   ? {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
