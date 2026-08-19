#!/usr/bin/env python
"""Camada 2 (Ag.L2) — aplica correções SOBRE a Camada 1, com travas de integridade.

TRAVAS (não negociáveis — nasceram do incidente de 2026-08-07, doc §3.3):

  T1. BASE = L1, NUNCA SA. A base é sempre ``{P}_qa_L1_tables.json``. Se não
      existir, o item é PULADO (não se reconstrói do motor SA — isso apagava
      todo o trabalho já validado da Camada 1).

  T2. GATE DE NÃO-REGRESSÃO. Antes de gravar, diff L1→L2. Toda linha removida
      precisa estar na lista de remoções justificadas por regra explícita.
      Remoção não justificada = ABORTA o item (não grava nada) e reporta.
      "Um ajuste não pode piorar a qualidade" vira invariante checado.

  T3. SEM CORREÇÃO ACIONÁVEL = NÃO TOCA NO DESENHO. Se não há mudança
      concreta a aplicar, só grava a nota de pendência. Nunca sobrescrever o
      SVG "de graça" (isso destruía L1 sem entregar nada em troca).

Regras de correção (só evidência dura, nunca suposição):
  - canto faltante (full-span) → ADICIONA linha espelhando a irmã existente.
  - papel duplicado (mesma viga+canto em passa E chega/interior) → REMOVE a
    entrada não-"passa" (única remoção justificada).
  - gap grande + candidato melhor → TROCA nome/dim pelo candidato mais próximo.
  - gap grande sem candidato, rótulo órfão, pilar em L, dualidade → só texto.

Uso:
  py -3.12 scripts/arete/pil_l2_apply_calibrated_fixes.py --pack <pack> --items P13 ...
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.arete.pil_agentic_highlight_draw import load_project, render_agentic_svg  # noqa: E402
from scripts.arete.pil_l2_evidence_check import _beam_contours, _full_span_faces, _is_horizontal  # noqa: E402
from scripts.arete.pil_geom_contato import relacao  # noqa: E402
from scripts.arete.pil_blind_l1_calibration import _min_gap, check_pillar_shape, GAP_TOL, BETTER_MARGIN  # noqa: E402
from scripts.arete.pil_qa_memoria import is_blocked  # noqa: E402

EMPTY = ("", "—", "-", "nenhuma", None)


def _real(rows):
    return [r for r in (rows or []) if (r.get("nome") or "") not in EMPTY]


def load_l1_tables(prop_dir: Path, name: str) -> dict | None:
    p = prop_dir / f"{name}_qa_L1_tables.json"
    if not p.is_file():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    t = d.get("tables")
    if not isinstance(t, dict) or "faces" not in t:
        return None
    return t


def signature(faces: dict) -> set:
    out = set()
    for fid in "ABCD":
        for kind in ("lajes", "passa", "chega", "interior"):
            for r in _real((faces.get(fid) or {}).get(kind)):
                out.add((fid, kind, r.get("nome"), r.get("canto")))
    return out


def corner_present(faces: dict, corner: str) -> bool:
    fid = corner[0]
    for kind in ("passa", "chega", "interior"):
        for r in _real((faces.get(fid) or {}).get(kind)):
            c = (r.get("canto") or "").upper()
            if c == corner.upper() or c == corner[::-1].upper():
                return True
    return False


def beams_in_tables(faces: dict) -> set:
    out = set()
    for fid in "ABCD":
        for kind in ("passa", "chega", "interior"):
            for r in _real((faces.get(fid) or {}).get(kind)):
                out.add(r.get("nome"))
    return out


CANTOS_DA_FACE = {"A": ("AC", "AD"), "B": ("BC", "BD"),
                  "C": ("CA", "CB"), "D": ("DA", "DB")}


def find_missing_corners(faces, beams_by_name, px0, py0, px1, py1) -> list[tuple[str, str]]:
    """(beam, corner) implicados pela geometria mas ausentes da tabela L1.

    Usa `pil_geom_contato.relacao` — ALINHAMENTO, como manda o doc — no lugar da
    detecção antiga por sobreposição de polígonos, que negava vigas colineares
    com o pilar (caso V321 × P24, corrigido pelo humano em 2026-08-08).
    Uma viga que PASSA numa face implica os dois cantos daquela face.
    """
    horizontal = _is_horizontal(px0, py0, px1, py1)
    out = []
    for bname in sorted(beams_in_tables(faces)):
        bdata = beams_by_name.get(bname)
        if not bdata:
            continue
        for seg in _beam_contours(bdata):
            for fid in "ABCD":
                rel = relacao(seg, fid, px0, py0, px1, py1, horizontal=horizontal)
                if not rel or rel.tipo != "passa":
                    continue
                for c in CANTOS_DA_FACE[fid]:
                    if not corner_present(faces, c) and (bname, c) not in out:
                        out.append((bname, c))
    return out


def _legado_full_span(faces, beams_by_name, px0, py0, px1, py1) -> list[tuple[str, str]]:
    horizontal = _is_horizontal(px0, py0, px1, py1)
    out = []
    for bname in sorted(beams_in_tables(faces)):
        bdata = beams_by_name.get(bname)
        if not bdata:
            continue
        for seg in _beam_contours(bdata):
            for _face, corners in _full_span_faces(seg, px0, py0, px1, py1, horizontal=horizontal).items():
                for c in corners:
                    if not corner_present(faces, c) and (bname, c) not in out:
                        out.append((bname, c))
    return out


def find_duplicate_roles(faces: dict) -> list[tuple[str, str, str, str]]:
    """(fid, kind_a_remover, nome, canto) — mesma viga+canto como passa E chega/interior."""
    out = []
    for fid in "ABCD":
        face = faces.get(fid) or {}
        passa_keys = {(r.get("nome"), r.get("canto")) for r in _real(face.get("passa"))}
        for kind in ("chega", "interior"):
            for r in _real(face.get(kind)):
                if (r.get("nome"), r.get("canto")) in passa_keys:
                    out.append((fid, kind, r.get("nome"), r.get("canto")))
    return out


def find_gap_issues(faces, beams_by_name, px0, py0, px1, py1):
    """Sobre a tabela L1: (fid, nome, canto, gap, melhor_nome, melhor_gap)."""
    horizontal = _is_horizontal(px0, py0, px1, py1)
    out = []
    for fid in "ABCD":
        for r in _real((faces.get(fid) or {}).get("passa")):
            bdata = beams_by_name.get(r.get("nome"))
            if not bdata:
                continue
            g = _min_gap(bdata, fid, px0, py0, px1, py1, horizontal)
            if g is None or g <= GAP_TOL:
                continue
            best = None
            for oname, odata in beams_by_name.items():
                if oname == r.get("nome"):
                    continue
                og = _min_gap(odata, fid, px0, py0, px1, py1, horizontal)
                if og is not None and (best is None or og < best[1]):
                    best = (oname, og)
            if best and best[1] + BETTER_MARGIN < g:
                out.append((fid, r.get("nome"), r.get("canto"), g, best[0], best[1]))
            else:
                out.append((fid, r.get("nome"), r.get("canto"), g, None, None))
    return out


def apply_item(name, pillar, dxf_path, beams_by_name, pack, obra, pav, port, repair=False):
    prop_dir = pack / "propostas"
    l1 = load_l1_tables(prop_dir, name)
    if l1 is None:
        return {"item": name, "aborted": "T1: sem {P}_qa_L1_tables.json — não reconstruo do SA"}

    base_faces = l1["faces"]
    tables2 = copy.deepcopy(l1)
    faces2 = tables2["faces"]

    xs = [pt[0] for pt in pillar["points"]]
    ys = [pt[1] for pt in pillar["points"]]
    px0, py0, px1, py1 = min(xs), min(ys), max(xs), max(ys)

    changes: list[str] = []
    unresolved: list[str] = []
    justified_removals: set = set()

    # --- regra 1: cantos faltantes (adiciona, nunca remove) ---
    for bname, corner in find_missing_corners(base_faces, beams_by_name, px0, py0, px1, py1):
        fid = corner[0]
        dim = nivel = ""
        for f in "ABCD":
            for kind in ("passa", "chega", "interior"):
                for r in _real((faces2.get(f) or {}).get(kind)):
                    if r.get("nome") == bname and r.get("dim"):
                        dim, nivel = r["dim"], r.get("nivel") or nivel
        lst = faces2[fid]["passa"]
        lst[:] = _real(lst)
        lst.append({
            "familia": "viga", "nome": bname, "dim": dim, "nivel": nivel,
            "canto": corner, "papel": "passa", "raw": "", "dist_esq": "—", "dist_dir": "—",
        })
        changes.append(f"ADICIONADO {fid}.passa {bname}@{corner} (canto implicado pela geometria, ausente na L1)")

    # --- regra 2: papel duplicado (única remoção justificada) ---
    for fid, kind, nome, canto in find_duplicate_roles(base_faces):
        lst = faces2[fid][kind]
        before = len(_real(lst))
        faces2[fid][kind] = [
            r for r in lst
            if (r.get("nome") or "") in EMPTY or not (r.get("nome") == nome and r.get("canto") == canto)
        ]
        if len(_real(faces2[fid][kind])) < before:
            justified_removals.add((fid, kind, nome, canto))
            changes.append(f"REMOVIDO {fid}.{kind} {nome}@{canto} (duplicado: já existe como passa no mesmo canto)")

    # --- regra 3: gap grande → troca identidade se houver candidato melhor ---
    for fid, nome, canto, gap, melhor, mgap in find_gap_issues(base_faces, beams_by_name, px0, py0, px1, py1):
        # blocklist: nunca (re)propor vínculo que o humano já reprovou
        if melhor and is_blocked(obra, pav, name, nome=melhor, face=fid, canto=canto):
            unresolved.append(
                f"{fid}.passa@{canto}: candidato {melhor} está na BLOCKLIST "
                f"(reprovado pelo humano) — mantido {nome}, precisa nova decisão"
            )
            melhor = None
        if melhor:
            row = next((r for r in _real(faces2[fid]["passa"])
                        if r.get("nome") == nome and r.get("canto") == canto), None)
            if row:
                bdata = beams_by_name.get(melhor) or {}
                new_dim = (bdata.get("fields") or {}).get("dimensao") or bdata.get("dim") or ""
                row["nome"] = melhor
                if new_dim:
                    row["dim"] = new_dim
                # troca é modificação rastreada, não perda: a linha continua
                # existindo no mesmo fid/kind/canto, só muda a identidade.
                justified_removals.add((fid, "passa", nome, canto))
                changes.append(
                    f"TROCADO {fid}.passa@{canto}: {nome} → {melhor} "
                    f"(gap real {gap:.0f}cm → {mgap:.0f}cm)"
                )
            else:
                unresolved.append(f"{fid}.passa@{canto}: {nome} gap ~{gap:.0f}cm — não localizei a linha p/ trocar")
        else:
            unresolved.append(
                f"{fid}.passa@{canto}: {nome} linkado como passa mas gap real ~{gap:.0f}cm "
                "(sem candidato melhor — precisa inspeção visual humana)"
            )

    unresolved += check_pillar_shape(pillar["points"])

    # ---------- T2: GATE DE NÃO-REGRESSÃO ----------
    sig_before, sig_after = signature(base_faces), signature(faces2)
    lost = sig_before - sig_after
    unjustified = {l for l in lost if l not in justified_removals}
    if unjustified:
        return {
            "item": name,
            "aborted": "T2: removeria linha(s) da L1 sem justificativa: "
                       + "; ".join(f"{f}.{k} {n}@{c}" for f, k, n, c in sorted(unjustified)),
        }

    # ---------- T3: sem correção acionável → não toca no desenho ----------
    # (exceção: --repair regenera o L2 a partir da L1 quando o SVG em disco
    #  ficou corrompido por rodada anterior que reconstruía do SA)
    if not changes and not repair:
        _write_note(name, obra, pav, port, changes, unresolved, drew=False)
        return {"item": name, "changes": [], "unresolved": unresolved, "drew": False}

    svg = render_agentic_svg(dxf_path, pillar.get("points") or [], tables2, layer="l2")
    (prop_dir / f"{name}_qa_L2.svg").write_text(svg, encoding="utf-8")
    (prop_dir / f"{name}_qa_L2_tables.json").write_text(
        json.dumps({
            "item": name, "base": "L1", "faces": faces2,
            "orientation": tables2.get("orientation"),
            "changes": changes, "unresolved": unresolved,
        }, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    _write_note(name, obra, pav, port, changes, unresolved, drew=True)
    return {"item": name, "changes": changes, "unresolved": unresolved, "drew": True}


def _write_note(name, obra, pav, port, changes, unresolved, *, drew: bool):
    base = f"{obra}_{pav}_{name}"
    txt = (
        f"[Camada 2 · {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')} · "
        "base = Camada 1 (preservada integralmente)]\n"
    )
    if changes:
        txt += "Aplicado sobre a L1 (evidência geométrica):\n" + "\n".join(f"- {c}" for c in changes) + "\n"
    else:
        txt += "Nenhuma correção automática aplicável — o desenho da L1 foi MANTIDO intacto.\n"
    if unresolved:
        txt += "Pendências (sem evidência suficiente p/ decidir sozinho):\n" + \
            "\n".join(f"- {u}" for u in unresolved) + "\n"
    txt += (
        "Veredito: INVALIDOU (há pendências) — peço validação humana.\n"
        if unresolved else "Veredito: correções aplicadas; peço validação humana.\n"
    )
    txt += (
        "Garantias desta rodada: nada que estava na Camada 1 foi removido sem regra explícita "
        "(gate de não-regressão). Se sobrar erro fora da lista acima, escreva a atenção — "
        "vira nova checagem no próximo refinamento."
    )
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/notes/{name}", timeout=10) as resp:
        doc = json.loads(resp.read().decode("utf-8"))
    notes = doc.get("notes") or {}
    notes[f"aten_pil_ctx_agent_l2_{base}"] = txt
    notes[f"aten_pil_ctx_agent_verdict_l2_{base}"] = "invalidou" if unresolved else "validou"
    payload = json.dumps({"notes": notes}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/notes/{name}", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    urllib.request.urlopen(req, timeout=10).read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", default="dd238e47-1dc6-4f63-a760-4e7ce19a7386")
    ap.add_argument("--db", default=str(ROOT.parent / "project_data.vision"))
    ap.add_argument("--obra", default="Obra_TREINO_1")
    ap.add_argument("--pav", default="13_PAV")
    ap.add_argument("--pack", required=True)
    ap.add_argument("--items", nargs="+", required=True)
    ap.add_argument("--port", type=int, default=18765)
    ap.add_argument("--repair", action="store_true",
                    help="regenera {P}_qa_L2.svg a partir da L1 mesmo sem mudanças "
                         "(conserta SVGs corrompidos por rodada que reconstruía do SA)")
    args = ap.parse_args()

    pack = Path(args.pack)
    dxf_path, _sh, _sn, _sp, beams, pillars = load_project(
        Path(args.db), args.project_id, args.obra, args.pav
    )
    pillars_by_name = {p["name"]: p for p in pillars}
    beams_by_name = {b.get("name"): b for b in beams}

    n_ok = n_abort = n_skip = 0
    for name in args.items:
        p = pillars_by_name.get(name)
        if not p:
            print(f"{name:5s} [ERR] não encontrado")
            continue
        try:
            r = apply_item(name, p, dxf_path, beams_by_name, pack, args.obra, args.pav,
                           args.port, repair=args.repair)
        except Exception as exc:  # noqa: BLE001
            print(f"{name:5s} [ERR] {exc}")
            continue
        if r.get("aborted"):
            n_abort += 1
            print(f"{name:5s} ABORTADO — {r['aborted']}")
            continue
        if not r.get("drew"):
            n_skip += 1
            print(f"{name:5s} L1 MANTIDA (nada acionável) — {len(r['unresolved'])} pendência(s)")
        else:
            n_ok += 1
            print(f"{name:5s} OK — {len(r['changes'])} mudança(s) sobre a L1, "
                  f"{len(r['unresolved'])} pendência(s)")
        for c in r.get("changes") or []:
            print(f"      + {c}")
        for u in r.get("unresolved") or []:
            print(f"      ? {u}")

    print(f"\n[RESUMO] redesenhados={n_ok}  L1_mantida={n_skip}  abortados={n_abort}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
