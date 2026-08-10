#!/usr/bin/env python
"""Aplica atenções humanas no pack ABCD → L1 corrigido + abas N3 (cima/ABCD/grades).

Uso:
  py -3.12 scripts/arete/apply_pil_aten_l1_n3_pack.py \\
    --pack scripts/arete/html_fichas/Obra_TREINO_1/13_PAV_..._pilares_abcd
"""
from __future__ import annotations

import argparse
import copy
import html as html_mod
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core.niveis_extractor import get_pavimento_niveis_abs  # noqa: E402
from src.core.pillar_abcd_tables import (  # noqa: E402
    build_abcd_tables_from_pillar,
    fill_cantos_all_rows,
    format_abcd_tables_html,
)
from src.core.pil_qa_notes_chrome import (  # noqa: E402
    css_pil_qa,
    js_pil_qa,
    n1_layer_toggle_and_layers,
    notes_grid_html,
    notes_store_tag,
    pil_keys,
    wrap_n1_panzoom,
)


def _natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s or "")]


def _strip_xml(s: str) -> str:
    return re.sub(r"<\?xml[^?]*\?>", "", s or "").strip()


def _real_rows(kind_rows):
    return [
        r
        for r in (kind_rows or [])
        if (r.get("nome") or "") not in ("", "—", "nenhuma", None)
    ]


def _read_human_note(notes_path: Path, keys: dict) -> str:
    if not notes_path.is_file():
        return ""
    try:
        doc = json.loads(notes_path.read_text(encoding="utf-8"))
        n = doc.get("notes") or {}
        return str(n.get(keys["human"]) or "").strip()
    except Exception:
        return ""


def _read_human_note_pack(pack: Path, name: str, keys: dict) -> str:
    """Lê atenção humana do .notes.json do item e/ou atencao_notas.json do pack."""
    texts: list[str] = []
    notes_path = pack / "pilares" / f"{name}.notes.json"
    t = _read_human_note(notes_path, keys)
    if t:
        texts.append(t)
    agg = pack / "atencao_notas.json"
    if agg.is_file():
        try:
            doc = json.loads(agg.read_text(encoding="utf-8"))
            it = (doc.get("items") or {}).get(name) or {}
            if it.get("text"):
                texts.append(str(it["text"]).strip())
            nn = it.get("notes") or {}
            # prefer ctx_human
            for k, v in nn.items():
                if not v or not str(v).strip():
                    continue
                if "ctx_human" in k or (
                    "human" in k.lower()
                    and "agent" not in k.lower()
                    and "verdict" not in k.lower()
                    and "hl_" not in k
                ):
                    texts.append(str(v).strip())
        except Exception:
            pass
    # unique preserve order
    seen = set()
    out = []
    for x in texts:
        x = x.strip()
        if x and x not in seen and x not in ("validou", "invalidou"):
            seen.add(x)
            out.append(x)
    return "\n".join(out)


def _mk_row(
    nome: str,
    *,
    dim: str = "—",
    nivel: str = "—",
    canto: str = "—",
    papel: str = "passa",
    fix: str = "",
) -> dict:
    r = {
        "familia": "viga",
        "nome": nome or "—",
        "dim": dim or "—",
        "nivel": nivel or "—",
        "canto": (canto or "—").upper(),
        "papel": papel,
        "raw": "",
        "dist_esq": "—",
        "dist_dir": "—",
    }
    if fix:
        r["_l1_fix"] = fix
    return r


def _drop_cantos(rows: list, cantos: set[str]) -> list:
    keep = []
    for r in rows or []:
        c = (r.get("canto") or "").upper()
        nome = r.get("nome") or ""
        if nome not in ("", "—", "nenhuma") and c in cantos:
            continue
        keep.append(r)
    return keep


def _move_chega_to_passa(faces: dict, face: str, canto: str, fixes: list) -> None:
    chega = faces.setdefault(face, {}).setdefault("chega", [])
    passa = faces.setdefault(face, {}).setdefault("passa", [])
    keep = []
    n = 0
    for r in chega:
        if (r.get("canto") or "").upper() == canto and (r.get("nome") or "") not in (
            "",
            "—",
            "nenhuma",
        ):
            nr = dict(r)
            nr["papel"] = "passa"
            nr["canto"] = canto
            nr["dist_esq"] = nr["dist_dir"] = "—"
            nr["_l1_fix"] = f"chega→passa @{canto}"
            if not any(
                p.get("nome") == nr["nome"] and (p.get("canto") or "").upper() == canto
                for p in passa
            ):
                passa.append(nr)
            n += 1
            continue
        keep.append(r)
    faces[face]["chega"] = keep
    if n:
        fixes.append(f"{face}.chega@{canto}→passa ({n})")


def _ensure_passa(
    faces: dict,
    face: str,
    canto: str,
    src: Optional[dict],
    fixes: list,
    *,
    label: str,
) -> None:
    if not src:
        return
    passa = faces.setdefault(face, {}).setdefault("passa", [])
    nome = src.get("nome")
    if any(
        p.get("nome") == nome and (p.get("canto") or "").upper() == canto
        for p in _real_rows(passa)
    ):
        return
    passa.append(
        _mk_row(
            str(nome),
            dim=str(src.get("dim") or "—"),
            nivel=str(src.get("nivel") or "—"),
            canto=canto,
            papel="passa",
            fix=label,
        )
    )
    fixes.append(label)


def _ensure_chega(
    faces: dict,
    face: str,
    canto: str,
    src: Optional[dict],
    fixes: list,
    *,
    label: str,
) -> None:
    if not src:
        return
    chega = faces.setdefault(face, {}).setdefault("chega", [])
    nome = src.get("nome")
    if any(
        p.get("nome") == nome and (p.get("canto") or "").upper() == canto
        for p in _real_rows(chega)
    ):
        return
    row = _mk_row(
        str(nome),
        dim=str(src.get("dim") or "—"),
        nivel=str(src.get("nivel") or "—"),
        canto=canto,
        papel="chega",
        fix=label,
    )
    chega.append(row)
    fixes.append(label)


def _ensure_interior_c(faces: dict, src: Optional[dict], fixes: list) -> None:
    if not src:
        # tenta promover algum passa CA/CB
        for r in _real_rows(faces.get("C", {}).get("passa")):
            src = r
            break
    if not src:
        for r in _real_rows(faces.get("D", {}).get("interior")):
            src = r
            break
    if not src:
        return
    if _real_rows(faces.get("C", {}).get("interior")):
        return
    faces.setdefault("C", {}).setdefault("interior", []).append(
        _mk_row(
            str(src.get("nome")),
            dim=str(src.get("dim") or "—"),
            nivel=str(src.get("nivel") or "—"),
            canto="CC",
            papel="interior",
            fix="C.interior (atenção humana)",
        )
    )
    fixes.append(f"C.interior←{src.get('nome')}")


def _clear_c_passa_ca_cb(faces: dict, fixes: list) -> None:
    before = len(_real_rows(faces.get("C", {}).get("passa")))
    faces.setdefault("C", {})["passa"] = _drop_cantos(
        faces.get("C", {}).get("passa"), {"CA", "CB"}
    )
    after = len(_real_rows(faces.get("C", {}).get("passa")))
    if before != after:
        fixes.append("removidos C.passa CA/CB")


def apply_human_corrections(
    name: str,
    tables: dict,
    human_note: str,
    *,
    pillar: Optional[dict] = None,
) -> tuple[dict, list[str]]:
    """Corrige tabelas ABCD conforme atenção humana (proposta L1 para aprovação).

    Regras **por padrão de texto** (sem hardcode de P#), cobrindo o pack 13_PAV
    2026-08-04. O motor SA recebe os mesmos padrões de forma geométrica.
    """
    t = copy.deepcopy(tables)
    faces = t.setdefault("faces", {})
    for fid in "ABCD":
        faces.setdefault(fid, {"lajes": [], "passa": [], "chega": [], "interior": []})
    fixes: list[str] = []
    note = (human_note or "").lower()
    note_n = (
        note.replace("pasas", "passa")
        .replace("pasa", "passa")
        .replace("ciga", "viga")
        .replace("vinga", "viga")
        .replace("inteiror", "interior")
        .replace("n nao", " nao")
    )

    if not note_n.strip():
        return t, fixes

    # ── Horizontal / L especial / geometria ──
    is_horizontal_note = any(
        x in note_n
        for x in (
            "pilar horizontal",
            "pilar ta horizontal",
            "viga horizontal",
            "horizontal mesmo problema",
            "lados abcd errados",
        )
    )
    # AD/BD + AA/BB só contam como horizontal se a GEOMETRIA já for H
    # (senão P18 vertical com “passa AD/BD” vira H por engano)
    geom_is_h = (t.get("orientation") or "").lower() == "horizontal"
    if not geom_is_h and pillar:
        try:
            pts = pillar.get("points") or []
            xs = [float(p[0]) for p in pts]
            ys = [float(p[1]) for p in pts]
            geom_is_h = (max(xs) - min(xs)) >= (max(ys) - min(ys))
        except Exception:
            geom_is_h = False
    is_horizontal_note = is_horizontal_note or (
        geom_is_h
        and ("passa" in note_n and ("bd" in note_n or "ad" in note_n))
        and (
            "chega aa" in note_n
            or "chega bb" in note_n
            or "interior aa" in note_n
            or "viga chega aa" in note_n
            or "lado a e no b" in note_n
            or "c e d ta errado" in note_n
            or "somente viga interior" in note_n
            or "passa bd" in note_n
            or "pasa bd" in note_n
        )
    )
    if is_horizontal_note or geom_is_h:
        t["orientation"] = "horizontal"
        t["_l1_flags"] = list(t.get("_l1_flags") or []) + ["horizontal_faces"]
        fixes.append(
            "ORIENTAÇÃO HORIZONTAL: A=sul · B=norte · C=oeste · D=leste"
        )

        # nota genérica ("mesmo problema" / só "horizontal") → heurística Caso 5
        generic_h = any(
            x in note_n
            for x in (
                "mesmo problema",
                "lados abcd errados",
                "pilar ta horizontal",
            )
        ) or note_n.strip() in (
            "viga horizontal",
            "pilar horizontal",
            "horizontal",
        )

        # ── Caso 5 / viga contínua: passa AD+BD nas longas ──
        want_ad_bd = (
            re.search(r"passa\s*b?d", note_n)
            and re.search(r"passa\s*a?d|faltou.*\bad\b|\bad\b.*passa", note_n)
        ) or (
            "passa bd" in note_n
            or "pasa bd" in note_n
            or "passa ad" in note_n
            or "pasa ad" in note_n
            or "bD AD" in (human_note or "")
            or "bd ad" in note_n
            or "ad e bd" in note_n
            or "bd e ad" in note_n
            or generic_h
        )
        # fonte: viga passa existente nas longas (AC/BC/AA/BB) ou C/D interior
        src_pass = None
        for fid in ("A", "B"):
            for r in _real_rows(faces[fid].get("passa")):
                src_pass = r
                break
            if src_pass:
                break
        if not src_pass:
            for fid in ("C", "D"):
                for r in _real_rows(faces[fid].get("interior")):
                    src_pass = r
                    break
                if src_pass:
                    break
        if want_ad_bd and src_pass:
            _ensure_passa(
                faces, "A", "AD", src_pass, fixes, label=f"A.passa@AD←{src_pass.get('nome')}"
            )
            _ensure_passa(
                faces, "B", "BD", src_pass, fixes, label=f"B.passa@BD←{src_pass.get('nome')}"
            )
        # defaults + nota específica
        aa_is_chega = False
        cd_only_int_flag = False
        if generic_h:
            if any(
                (r.get("canto") or "").upper() in ("AA", "BB", "")
                for fid in "AB"
                for r in _real_rows(faces[fid].get("interior"))
            ):
                aa_is_chega = True
            if any(_real_rows(faces[fid].get("passa")) for fid in ("C", "D")):
                cd_only_int_flag = True

        aa_is_chega = aa_is_chega or (
            "interior aa" in note_n
            or "chega aa" in note_n
            or "viga chega aa" in note_n
            or "chega bb" in note_n
            or "viga chega bb" in note_n
            or "aa e bb" in note_n
            or "aa e no b" in note_n
            or re.search(r"chega.*\baa\b", note_n)
            or re.search(r"chega.*\bbb\b", note_n)
            or "diferentes de casos viga interior" in note_n
        )

        if aa_is_chega:
            for face, mid in (("A", "AA"), ("B", "BB")):
                # interior mid → chega mid
                keep_int = []
                for r in faces[face].get("interior") or []:
                    nome = r.get("nome") or ""
                    c = (r.get("canto") or "").upper()
                    if nome not in ("", "—", "nenhuma") and c in (mid, "", "—", face + face):
                        faces[face].setdefault("chega", []).append(
                            _mk_row(
                                str(nome),
                                dim=str(r.get("dim") or "—"),
                                nivel=str(r.get("nivel") or "—"),
                                canto=mid,
                                papel="chega",
                                fix=f"interior@{mid}→chega central (≠ interior CC/DD)",
                            )
                        )
                        fixes.append(f"{face}.interior@{mid}→chega@{mid} (central)")
                        continue
                    keep_int.append(r)
                faces[face]["interior"] = keep_int
                # passa mid → chega mid
                keep_p = []
                for r in faces[face].get("passa") or []:
                    c = (r.get("canto") or "").upper()
                    nome = r.get("nome") or ""
                    if nome not in ("", "—", "nenhuma") and c == mid:
                        faces[face].setdefault("chega", []).append(
                            _mk_row(
                                str(nome),
                                dim=str(r.get("dim") or "—"),
                                nivel=str(r.get("nivel") or "—"),
                                canto=mid,
                                papel="chega",
                                fix=f"passa@{mid}→chega central",
                            )
                        )
                        fixes.append(f"{face}.passa@{mid}→chega@{mid}")
                        continue
                    keep_p.append(r)
                faces[face]["passa"] = keep_p
                # chega de canto AC/BC com nota "chega AA/BB" → reclassificar central
                if "aa e bb" in note_n or "chega aa" in note_n or "chega bb" in note_n:
                    for r in faces[face].get("chega") or []:
                        c = (r.get("canto") or "").upper()
                        if c in ("AC", "BC", "AD", "BD") and (r.get("nome") or "") not in (
                            "",
                            "—",
                            "nenhuma",
                        ):
                            # se também há passa do mesmo nome na face, chega é a transversal
                            r["canto"] = mid
                            r["_l1_fix"] = f"chega canto→{mid} central"
                            fixes.append(f"{face}.chega {c}→{mid} (central)")

        # P51: chega só BB, não em A
        if "nao temos viga chega no lado a" in note_n or (
            "chega bb" in note_n and "nao" in note_n and "lado a" in note_n
        ):
            faces["A"]["chega"] = [
                r
                for r in faces["A"].get("chega") or []
                if (r.get("nome") or "") in ("", "—", "nenhuma")
            ]
            fixes.append("A: sem chega (só B.chega@BB)")
            # se B não tem chega BB, promover passa mid ou flag
            if not any(
                (r.get("canto") or "").upper() == "BB"
                for r in _real_rows(faces["B"].get("chega"))
            ):
                src = next(iter(_real_rows(faces["B"].get("passa"))), None)
                if src:
                    _ensure_chega(
                        faces,
                        "B",
                        "BB",
                        src,
                        fixes,
                        label=f"B.chega@BB←{src.get('nome')}",
                    )

        # ── C e D: só interior, sem passa (Caso 5 extremos engolidos) ──
        cd_only_int = cd_only_int_flag or (
            "somente viga interior" in note_n
            or "so viga interior" in note_n
            or "c e d ta errado" in note_n
            or "o c e d ta errado" in note_n
            or "c ta errado nao tem viga passa" in note_n
            or (
                "nao tem viga passa" in note_n
                and ("interior" in note_n)
                and ("c" in note_n or "d" in note_n)
            )
        )
        if cd_only_int or (want_ad_bd and "interior" in note_n and ("c" in note_n or "d" in note_n)):
            for fid in ("C", "D"):
                for r in list(_real_rows(faces[fid].get("passa"))):
                    faces[fid].setdefault("interior", []).append(
                        _mk_row(
                            str(r.get("nome")),
                            dim=str(r.get("dim") or "—"),
                            nivel=str(r.get("nivel") or "—"),
                            canto={"C": "CC", "D": "DD"}[fid],
                            papel="interior",
                            fix=f"{fid}.passa→interior (horizontal)",
                        )
                    )
                faces[fid]["passa"] = [
                    r
                    for r in faces[fid].get("passa") or []
                    if (r.get("nome") or "") in ("", "—", "nenhuma")
                ]
                # remove chega residual em C/D
                faces[fid]["chega"] = [
                    r
                    for r in faces[fid].get("chega") or []
                    if (r.get("nome") or "") in ("", "—", "nenhuma")
                ]
            fixes.append("C/D: só interior (sem passa) — horizontal Caso 5")

        # P35: passa DA errado → DB
        if re.search(r"nao\s*tem\s*viga\s*passa\s*da", note_n) or (
            "passa da" in note_n and "sim db" in note_n
        ) or ("nao tem viga passa da e sim db" in note_n):
            for r in faces["D"].get("passa") or []:
                if (r.get("canto") or "").upper() == "DA":
                    r["canto"] = "DB"
                    r["_l1_fix"] = "DA→DB"
                    fixes.append("D.passa DA→DB")
            # se não há DB, promove
            src = next(iter(_real_rows(faces["D"].get("passa"))), None) or next(
                iter(_real_rows(faces["B"].get("chega"))), None
            )
            if src and not any(
                (r.get("canto") or "").upper() == "DB"
                for r in _real_rows(faces["D"].get("passa"))
            ):
                _ensure_passa(faces, "D", "DB", src, fixes, label="D.passa@DB")

        # bolinha chega mal posicionada — flag para render (AA/BB/BD mid-face)
        if "mal posicionad" in note_n or "ponoto" in note_n or "ponto da" in note_n or "bolinha" in note_n:
            t["_l1_flags"] = list(t.get("_l1_flags") or []) + ["tip_position_fix"]
            fixes.append(
                "PONTO/BOLINHA da seta: chega central AA/BB no MEIO da face longa; "
                "chega de canto no centro do trecho da viga (não na esquina isolada)."
            )

    if "pilar especial em l" in note_n or "pilar em l" in note_n or (
        "lados a b c d e f" in note_n
    ):
        t["_l1_flags"] = list(t.get("_l1_flags") or []) + ["l_shape_6faces"]
        fixes.append(
            "PILAR EM L: ficha 6 faces (A B C D E F) + tags por face — "
            "vertical: A esq, B dir, E/F no ramo horizontal, C tampa horiz, D tampa vert. "
            "L1 não inventa geometria; validar layout especial."
        )

    if "geometria vinculada errada" in note_n:
        t["_l1_flags"] = list(t.get("_l1_flags") or []) + ["bad_geometry_link"]
        # se pillar veio com reparo GOLDEN, anotar
        rep = (pillar or {}).get("_geometry_repaired") if pillar else None
        if rep:
            fixes.append(
                f"GEOMETRIA REPARADA (GOLDEN): contorno {rep.get('from')} → "
                f"retângulo {rep.get('to')} centrado — revisar N1 se o eixo "
                f"ainda estiver no lugar errado."
            )
        else:
            fixes.append(
                "GEOMETRIA VINCULADA ERRADA — contorno no DB truncado/degenerado; "
                "sem ficha GOLDEN para reconstruir. Corrigir points no SA."
            )

    # ── Fantasma chega AC / CA (só se AC é o alvo explícito do "não existe") ──
    if re.search(r"chega\s*ac\s*n[aã]o\s*existe", note_n) or re.search(
        r"chega\s*ac\s*n[aã]o\s*tem", note_n
    ):
        # não confundir com "CA e CB não existe" (outro padrão)
        if not re.search(r"\bca\s*e\s*cb\b", note_n):
            faces["A"]["chega"] = _drop_cantos(faces["A"].get("chega"), {"AC"})
            faces["C"]["passa"] = _drop_cantos(faces["C"].get("passa"), {"CA"})
            fixes.append("removidos fantasma A.chega@AC e C.passa@CA")

    # ── Dim BC/CB seção-pilar ──
    need_bc_dim = (
        "dimensao do pilar" in note_n
        or "dimensão do pilar" in note_n
        or "usou dimensao" in note_n
        or re.search(r"chega\s*bc.*(dimens|erra)", note_n)
        or re.search(r"bc\s*ta\s*com\s*dimens", note_n)
        or ("dimensao errada" in note_n and "bc" in note_n)
    )
    if need_bc_dim:
        ref_dim = None
        for r in _real_rows(faces["C"].get("passa")):
            if (r.get("canto") or "").upper() == "CA" and not re.search(
                r"/\s*66\b", str(r.get("dim") or "")
            ):
                ref_dim = r.get("dim")
                break
        if not ref_dim:
            for r in _real_rows(faces["A"].get("chega")):
                if (r.get("canto") or "").upper() == "AC" and not re.search(
                    r"/\s*66\b", str(r.get("dim") or "")
                ):
                    ref_dim = r.get("dim")
                    break
        ref_dim = ref_dim or "14/55"
        ch = 0
        for r in faces["B"].get("chega") or []:
            if (r.get("canto") or "").upper() == "BC" and r.get("dim") != ref_dim:
                r["dim"] = ref_dim
                ch += 1
        for r in faces["C"].get("passa") or []:
            if (r.get("canto") or "").upper() == "CB" and r.get("dim") != ref_dim:
                r["dim"] = ref_dim
                ch += 1
        if ch:
            fixes.append(f"BC/CB dim→{ref_dim} ({ch})")

    # ── Ponto/flecha da chega AC mal posicionado ──
    if (
        "chega ac" in note_n
        and ("flecha" in note_n or "ponoto" in note_n or "ponto" in note_n or "bolinha" in note_n)
    ) or "oponoto da flecha" in note_n:
        t["_l1_flags"] = list(t.get("_l1_flags") or []) + ["tip_position_fix"]
        # garantir canto AC na chega
        for r in faces["A"].get("chega") or []:
            if (r.get("nome") or "") not in ("", "—", "nenhuma"):
                if (r.get("canto") or "").upper() in ("", "—", "AA"):
                    r["canto"] = "AC"
                r["_l1_fix"] = (r.get("_l1_fix") or "") + " tip=centro-trecho-viga"
        fixes.append(
            "Chega AC: bolinha no CENTRO do trecho da viga na face A (não na esquina solta)"
        )

    # ── Faltou chega AC ──
    if re.search(r"faltou\s+viga\s+chega\s*ac", note_n) or (
        "faltou" in note_n and "chega ac" in note_n and "flecha" not in note_n and "ponoto" not in note_n
    ):
        src = None
        for r in _real_rows(faces["C"].get("passa")):
            if (r.get("canto") or "").upper() == "CA":
                src = r
                break
        if not src:
            for r in _real_rows(faces["A"].get("passa")):
                src = r
                break
        if not src:
            for r in _real_rows(faces["D"].get("interior")):
                src = r
                break
        _ensure_chega(
            faces,
            "A",
            "AC",
            src,
            fixes,
            label=f"A.chega@AC←{src.get('nome') if src else '?'}",
        )
        if src:
            _ensure_passa(
                faces,
                "C",
                "CA",
                src,
                fixes,
                label=f"C.passa@CA dual de chega AC ({src.get('nome')})",
            )

    # ── Faltou passa CA ──
    if re.search(r"faltou\s+viga\s+p+assa\s*ca", note_n) or (
        "passa ca" in note_n and "faltou" in note_n and "nao existe" not in note_n
    ):
        src = next(iter(_real_rows(faces["A"].get("passa"))), None) or next(
            iter(_real_rows(faces["A"].get("chega"))), None
        )
        _ensure_passa(
            faces,
            "C",
            "CA",
            src,
            fixes,
            label=f"C.passa@CA←{src.get('nome') if src else '?'}",
        )

    # ── CA e CB não existem / só interior C / passa AC BC (não chega) ──
    c_no_dual = (
        ("ca e cb nao existe" in note_n or "ca e cb não existe" in note_n)
        or (
            "somente interior" in note_n
            and ("lado c" in note_n or "viga c" in note_n or "de viga c" in note_n)
        )
        or (
            "nao tem viga passa" in note_n
            and "interior" in note_n
            and ("lado c" in note_n or "c nao" in note_n)
        )
        or (
            "lado c nao tem" in note_n
            and "interior" in note_n
            and ("ca" in note_n or "cb" in note_n)
        )
        or (
            "c nao tem viga passa so interior" in note_n
            or "c nao tem viga passa só interior" in note_n
        )
    )
    # P28 family: "Lado C nao tem viga passa só interior"
    if re.search(r"lado\s*c\s*nao\s*tem\s*viga\s*passa", note_n) and "interior" in note_n:
        c_no_dual = True
    if re.search(r"ca\s*e\s*cb\s*nao\s*existe", note_n):
        c_no_dual = True

    want_passa_ac_bc = (
        re.search(r"passa\s*ac", note_n)
        and re.search(r"passa\s*bc", note_n)
        and ("faltou" in note_n or "somente viga passa ac" in note_n or "so viga passa" in note_n)
    ) or (
        "somente viga passa ac" in note_n
        or "somente viga passa ac bc" in note_n
        or "viga passa ac bc" in note_n
    ) or (
        "faltou viga passa ac" in note_n and "bc" in note_n
    ) or (
        "faltou viga passa ac e" in note_n
    ) or re.search(r"faltou\s+viga\s+passa\s+ac", note_n)

    no_chega_ac_bc = (
        re.search(r"nao\s*tem\s*(ciga|viga)?\s*chega\s*ac", note_n)
        or re.search(r"nao\s*tem\s*chega\s*ac\s*nem\s*bc", note_n)
        or ("nao tem viga chega ac bc" in note_n)
        or ("nao tem viga chega ac" in note_n and "bc" in note_n)
        or ("viga chega ac n nao tem" in note_n)
        or ("viga chega ac nao tem" in note_n)
    )

    if c_no_dual or (
        "interior" in note_n
        and ("ca" in note_n or "cb" in note_n)
        and ("nao existe" in note_n or "nao tem" in note_n or "só" in note_n or "so" in note_n)
        and re.search(r"\bca\b", note_n)
    ):
        # 1) capturar dual CA/CB ANTES de apagar → viram passa AC/BC
        ca = next(
            (
                r
                for r in _real_rows(faces["C"].get("passa"))
                if (r.get("canto") or "").upper() == "CA"
            ),
            None,
        )
        cb = next(
            (
                r
                for r in _real_rows(faces["C"].get("passa"))
                if (r.get("canto") or "").upper() == "CB"
            ),
            None,
        )
        _move_chega_to_passa(faces, "A", "AC", fixes)
        _move_chega_to_passa(faces, "B", "BC", fixes)
        if ca:
            _ensure_passa(
                faces, "A", "AC", ca, fixes, label=f"A.passa@AC←C.CA {ca.get('nome')}"
            )
        if cb:
            _ensure_passa(
                faces, "B", "BC", cb, fixes, label=f"B.passa@BC←C.CB {cb.get('nome')}"
            )
        _clear_c_passa_ca_cb(faces, fixes)
        if not _real_rows(faces["C"].get("interior")):
            src = next(iter(_real_rows(faces["D"].get("interior"))), None)
            if not src:
                src = next(iter(_real_rows(faces["A"].get("passa"))), None)
            _ensure_interior_c(faces, src, fixes)

    if no_chega_ac_bc and not c_no_dual:
        if want_passa_ac_bc:
            _move_chega_to_passa(faces, "A", "AC", fixes)
            _move_chega_to_passa(faces, "B", "BC", fixes)
        else:
            faces["A"]["chega"] = _drop_cantos(faces["A"].get("chega"), {"AC"})
            faces["B"]["chega"] = _drop_cantos(faces["B"].get("chega"), {"BC"})
            faces["C"]["passa"] = _drop_cantos(faces["C"].get("passa"), {"CA", "CB"})
            fixes.append("removidos chega AC/BC (+ dual C)")

    if want_passa_ac_bc:
        # garantir passa AC/BC a partir de chega residual ou peer
        src_a = next(
            (
                r
                for r in _real_rows(faces["A"].get("chega"))
                if (r.get("canto") or "").upper() == "AC"
            ),
            None,
        ) or next(
            (
                r
                for r in _real_rows(faces["A"].get("passa"))
                if (r.get("canto") or "").upper() in ("AC", "AA", "—", "")
            ),
            None,
        )
        src_b = next(
            (
                r
                for r in _real_rows(faces["B"].get("chega"))
                if (r.get("canto") or "").upper() == "BC"
            ),
            None,
        ) or next(
            (
                r
                for r in _real_rows(faces["B"].get("passa"))
                if (r.get("canto") or "").upper() in ("BC", "BB", "—", "")
            ),
            None,
        )
        # se ainda em chega, move
        _move_chega_to_passa(faces, "A", "AC", fixes)
        _move_chega_to_passa(faces, "B", "BC", fixes)
        # se faltava de todo, clona de passa AD/BD ou D.interior com canto AC/BC
        # After moves, if still missing AC/BC: flag (sem inventar nome falso)
        for face, canto in (("A", "AC"), ("B", "BC")):
            has = any(
                (r.get("canto") or "").upper() == canto
                for r in _real_rows(faces[face].get("passa"))
            )
            if not has and "faltou" in note_n:
                fixes.append(
                    f"FALTA {face}.passa@{canto} — completar no face_beams (topo)"
                )

    # ── C interior não reconheceu ──
    if "c interior" in note_n or re.search(r"\bc\s+faltou\s+viga\s+interior", note_n):
        if "nao reconheceu" in note_n or "faltou" in note_n:
            src = next(iter(_real_rows(faces["D"].get("interior"))), None)
            if not src:
                src = next(iter(_real_rows(faces["A"].get("passa"))), None)
            _ensure_interior_c(faces, src, fixes)
            if want_passa_ac_bc or (
                "passa ac" in note_n and "passa bc" in note_n
            ):
                # often missing AC/BC passa from top H beam — use D.interior dual? no
                # use any remaining C.passa or create from AD beam's "top" sibling
                for face, canto, peer in (
                    ("A", "AC", "AD"),
                    ("B", "BC", "BD"),
                ):
                    has = any(
                        (r.get("canto") or "").upper() == canto
                        for r in _real_rows(faces[face].get("passa"))
                    )
                    if has:
                        continue
                    # se existe chega, move
                    _move_chega_to_passa(faces, face, canto, fixes)
                    has = any(
                        (r.get("canto") or "").upper() == canto
                        for r in _real_rows(faces[face].get("passa"))
                    )
                    if not has:
                        # marcar gap sem inventar nome falso
                        fixes.append(
                            f"FALTA {face}.passa@{canto} (sem fonte geométrica no SA — "
                            "revisar face_beams multi-seg topo)"
                        )

    # ── D: 2 passa; C só interior; A/B só laje + AD/BD (P28–P32) ──
    if (
        "lado d tem 2 vigas" in note_n
        or ("lado d tem 2" in note_n and "passa" in note_n)
        or (
            "tem bd e ad" in note_n
            and "nao tem viga chega ac" in note_n
        )
    ):
        _clear_c_passa_ca_cb(faces, fixes)
        faces["A"]["chega"] = _drop_cantos(faces["A"].get("chega"), {"AC", "BC"})
        faces["B"]["chega"] = _drop_cantos(faces["B"].get("chega"), {"AC", "BC"})
        # garante AD/BD a partir de passa existentes
        for r in _real_rows(faces["A"].get("passa")):
            if (r.get("canto") or "").upper() in ("", "—", "AA"):
                r["canto"] = "AD"
                r["_l1_fix"] = "canto AD"
        for r in _real_rows(faces["B"].get("passa")):
            if (r.get("canto") or "").upper() in ("", "—", "BB"):
                r["canto"] = "BD"
                r["_l1_fix"] = "canto BD"
        if not _real_rows(faces["C"].get("interior")):
            src = next(iter(_real_rows(faces["D"].get("interior"))), None)
            _ensure_interior_c(faces, src, fixes)
        # D com 2 passa: promover interior D se só 1; flag se faltar 2ª
        d_pass = _real_rows(faces["D"].get("passa"))
        d_int = _real_rows(faces["D"].get("interior"))
        if len(d_pass) < 2:
            fixes.append(
                f"D deve ter 2 vigas passa (agora passa={len(d_pass)} interior={len(d_int)}) "
                "— completar via geometria face_beams"
            )
        fixes.append("padrão P28: C só interior; A/B laje+AD/BD; sem chega AC/BC")

    # ── D é interior e não tem passa; faltou passa AD e BC (P43 family) ──
    if (
        ("d é interior" in note_n or "d e interior" in note_n or "d é inteiror" in note_n)
        and ("nao tem viga passa" in note_n or "nao temviga passa" in note_n)
    ) or (
        "faltou viga passa ad" in note_n and "bc" in note_n
    ):
        # D: interior only — move D.passa → D.interior
        for r in list(_real_rows(faces["D"].get("passa"))):
            faces["D"].setdefault("interior", []).append(
                _mk_row(
                    str(r.get("nome")),
                    dim=str(r.get("dim") or "—"),
                    nivel=str(r.get("nivel") or "—"),
                    canto="DD",
                    papel="interior",
                    fix="D.passa→interior",
                )
            )
        faces["D"]["passa"] = [
            r
            for r in faces["D"].get("passa") or []
            if (r.get("nome") or "") in ("", "—", "nenhuma")
        ]
        fixes.append("D: passa→interior (sem passa em D)")
        if "c faltou viga interior" in note_n or "c faltou" in note_n:
            src = next(iter(_real_rows(faces["D"].get("interior"))), None)
            _ensure_interior_c(faces, src, fixes)
        # AD / BC passa
        src_ad = next(iter(_real_rows(faces["A"].get("passa"))), None) or next(
            iter(_real_rows(faces["D"].get("interior"))), None
        )
        _ensure_passa(faces, "A", "AD", src_ad, fixes, label="A.passa@AD")
        # BC may be top dual style
        src_bc = next(
            (
                r
                for r in _real_rows(faces["B"].get("chega"))
                if (r.get("canto") or "").upper() == "BC"
            ),
            None,
        ) or next(iter(_real_rows(faces["B"].get("passa"))), None)
        if src_bc:
            _move_chega_to_passa(faces, "B", "BC", fixes)
            _ensure_passa(faces, "B", "BC", src_bc, fixes, label="B.passa@BC")

    # ── P41: chega AC errado, faltou passa AD; CA errado, faltou interior C;
    #         D interior sem passa; B faltou passa BC ──
    if (
        "viga chega ac errado" in note_n
        or (
            "chega ac errado" in note_n
            and "passa ad" in note_n
        )
        or (
            "faltou viga passa ad" in note_n
            and "interior c" in note_n
            and "passa bc" in note_n
        )
    ):
        # chega AC errado → remover; garantir passa AD
        faces["A"]["chega"] = _drop_cantos(faces["A"].get("chega"), {"AC"})
        faces["C"]["passa"] = _drop_cantos(faces["C"].get("passa"), {"CA"})
        fixes.append("removidos chega AC / passa CA errados")
        src = next(iter(_real_rows(faces["A"].get("passa"))), None) or next(
            iter(_real_rows(faces["D"].get("passa"))), None
        )
        _ensure_passa(faces, "A", "AD", src, fixes, label="A.passa@AD")
        # D: interior, sem passa
        for r in list(_real_rows(faces["D"].get("passa"))):
            faces["D"].setdefault("interior", []).append(
                _mk_row(
                    str(r.get("nome")),
                    dim=str(r.get("dim") or "—"),
                    nivel=str(r.get("nivel") or "—"),
                    canto="DD",
                    papel="interior",
                    fix="D→interior",
                )
            )
        faces["D"]["passa"] = [
            r
            for r in faces["D"].get("passa") or []
            if (r.get("nome") or "") in ("", "—", "nenhuma")
        ]
        _ensure_interior_c(
            faces, next(iter(_real_rows(faces["D"].get("interior"))), None), fixes
        )
        # B passa BC
        src_b = next(iter(_real_rows(faces["B"].get("chega"))), None) or next(
            iter(_real_rows(faces["B"].get("passa"))), None
        )
        _move_chega_to_passa(faces, "B", "BC", fixes)
        _ensure_passa(faces, "B", "BC", src_b, fixes, label="B.passa@BC")

    # ── P49: chega CC → interior; sem passa CB; chega BC errado; falta passa BC e AC ──
    if (
        "chega cc" in note_n
        or ("viga chega cc" in note_n)
        or (
            "nao tem viga passa cb" in note_n
            and "passa bc" in note_n
            and "ac" in note_n
        )
    ):
        # CC chega → interior
        for r in list(faces["C"].get("chega") or []):
            if (r.get("canto") or "").upper() in ("CC", "") or (
                r.get("nome")
                and (r.get("canto") or "").upper() not in ("CA", "CB")
            ):
                if (r.get("nome") or "") not in ("", "—", "nenhuma"):
                    faces["C"].setdefault("interior", []).append(
                        _mk_row(
                            str(r.get("nome")),
                            dim=str(r.get("dim") or "—"),
                            nivel=str(r.get("nivel") or "—"),
                            canto="CC",
                            papel="interior",
                            fix="chega CC→interior",
                        )
                    )
        faces["C"]["chega"] = [
            r
            for r in faces["C"].get("chega") or []
            if (r.get("nome") or "") in ("", "—", "nenhuma")
        ]
        faces["C"]["passa"] = _drop_cantos(faces["C"].get("passa"), {"CB"})
        if "chega bc errado" in note_n:
            faces["B"]["chega"] = _drop_cantos(faces["B"].get("chega"), {"BC"})
            faces["C"]["passa"] = _drop_cantos(faces["C"].get("passa"), {"CB"})
        # falta passa AC e BC
        for face, canto in (("A", "AC"), ("B", "BC")):
            src = next(
                (
                    r
                    for r in _real_rows(faces[face].get("passa"))
                    if (r.get("canto") or "").upper() == canto
                ),
                None,
            )
            if not src:
                src = next(iter(_real_rows(faces[face].get("passa"))), None)
            _ensure_passa(
                faces, face, canto, src, fixes, label=f"{face}.passa@{canto}"
            )
        fixes.append("P49: CC→interior; sem CB; passa AC/BC")

    # ── P18: faltou passa CB, BD, AD; chega BB mal posicionado ──
    if "faltou viga passa cb" in note_n or (
        "passa cb" in note_n and "faltou" in note_n
    ):
        src = next(
            (
                r
                for r in _real_rows(faces["B"].get("chega"))
                if (r.get("canto") or "").upper() in ("BC", "BB")
            ),
            None,
        ) or next(iter(_real_rows(faces["B"].get("passa"))), None)
        _ensure_passa(faces, "C", "CB", src, fixes, label="C.passa@CB")
        for face, canto in (("A", "AD"), ("B", "BD")):
            src2 = next(iter(_real_rows(faces[face].get("passa"))), None)
            if src2 and (src2.get("canto") or "").upper() in ("", "—", "AA", "BB", "AC", "BC"):
                # if only top cantos, add bottom from same beam interior D
                bot = next(iter(_real_rows(faces["D"].get("interior"))), None) or src2
                _ensure_passa(
                    faces, face, canto, bot, fixes, label=f"{face}.passa@{canto}"
                )
        # chega BB mal posicionado — se há chega BB, tentar BC
        for r in faces["B"].get("chega") or []:
            if (r.get("canto") or "").upper() == "BB":
                r["canto"] = "BC"
                r["_l1_fix"] = "BB→BC (posição)"
                fixes.append("B.chega BB→BC (reposição)")

    # ── P20–22: CB/DB/BC nome e dim incorretos ──
    if (
        "passa associada a cb ta incorreta" in note_n
        or "passa associada a cb" in note_n
        or (
            "lado db ta incorreta" in note_n
            or ("db ta incorreta" in note_n)
        )
    ):
        fixes.append(
            "CB/DB/BC: nome+dim incorretos no SA — dual topo ok em estrutura, "
            "mas identidade da viga no lado B/D deve vir da cota local (não copiar CA). "
            "L1 mantém dual e marca revisão de identidade (face_beams _pick_dim/_pick_name)."
        )
        t["_l1_flags"] = list(t.get("_l1_flags") or []) + ["cb_db_identity_wrong"]
        # se CA tem dim boa e CB igual a CA indevidamente com nome errado, não unificar
        ca = next(
            (
                r
                for r in _real_rows(faces["C"].get("passa"))
                if (r.get("canto") or "").upper() == "CA"
            ),
            None,
        )
        cb = next(
            (
                r
                for r in _real_rows(faces["C"].get("passa"))
                if (r.get("canto") or "").upper() == "CB"
            ),
            None,
        )
        if ca and cb and ca.get("nome") == cb.get("nome"):
            # leave structure; flag only
            pass

    # ── Passa CA errada não existe (legado P10) ──
    if re.search(r"pas+a\s*ca\s*(errada|n[aã]o\s*existe)", note_n):
        faces["C"]["passa"] = _drop_cantos(faces["C"].get("passa"), {"CA"})
        fixes.append("removido C.passa@CA (não existe)")

    # limpa linhas vazias duplicadas
    for fid in "ABCD":
        for kind in ("lajes", "passa", "chega", "interior"):
            rows = faces[fid].get(kind) or []
            real = _real_rows(rows)
            empty = [
                r
                for r in rows
                if (r.get("nome") or "") in ("", "—", "nenhuma")
            ]
            faces[fid][kind] = real if real else empty[:1]

    try:
        fill_cantos_all_rows(faces, vertical=t.get("orientation") != "horizontal")
    except Exception:
        pass

    if not fixes and human_note.strip():
        fixes.append("atenção registrada — sem regra automática aplicável; revisar N1")

    return t, fixes


def dxf_to_svg(
    dxf_path: Path,
    out_svg: Path,
    *,
    width: int = 900,
    height: int = 640,
    zoom_out: float = 2.4,
    y_shift_up_cm: float = 300.0,
    line_scale: float = 0.45,
    soft_hatch: bool = False,
) -> bool:
    """Render DXF→SVG (stack N1) com enquadramento sem cortar o topo.

    - ``zoom_out``: margem ao redor do conteúdo
    - ``y_shift_up_cm``: sobe o desenho **sem cortar o topo** (só aumenta
      padding embaixo; o ymax do conteúdo fica sempre com folga)
    - ``soft_hatch``: reduz alpha/linewidth de fills (vazios ABCD)
    """
    if not dxf_path.is_file():
        return False
    try:
        import ezdxf
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import Frontend, RenderContext
        from ezdxf.addons.drawing.config import Configuration
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
        from src.ui.widgets.svg_embed_utils import strip_fixed_size

        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        # Suaviza HATCH no DXF (só entidades HATCH) — não toca DIMENSION/TEXT/LINE
        if soft_hatch:
            try:
                from ezdxf.colors import rgb2int

                for hatch in msp.query("HATCH"):
                    try:
                        # padrão mais esparso (menos “mancha”)
                        try:
                            sc = float(getattr(hatch.dxf, "pattern_scale", 1.0) or 1.0)
                            hatch.dxf.pattern_scale = max(sc, 0.4) * 2.8
                        except Exception:
                            pass
                        # cor mais escura/baixa (fundo #0d0d0d → hatch discreto)
                        try:
                            hatch.dxf.color = 8  # dark gray ACI
                        except Exception:
                            pass
                        try:
                            # cinza bem escuro no fundo preto
                            hatch.dxf.true_color = rgb2int((55, 55, 55))
                        except Exception:
                            pass
                        try:
                            # se solid fill, ainda assim fica só um tom discreto
                            if bool(getattr(hatch.dxf, "solid_fill", 0)):
                                hatch.dxf.true_color = rgb2int((40, 40, 40))
                        except Exception:
                            pass
                    except Exception:
                        pass
            except Exception:
                pass
        dpi = 140
        cfg = Configuration(
            lineweight_scaling=max(0.25, float(line_scale)),
            min_lineweight=0.18,
            max_flattening_distance=0.02,
            circle_approximation_count=128,
        )
        with matplotlib.rc_context(
            {
                "svg.fonttype": "path",
                "path.simplify": False,
                "lines.linewidth": 0.55,
                "patch.linewidth": 0.55,
            }
        ):
            fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
            ax = fig.add_axes([0, 0, 1, 1])
            ax.set_facecolor("#0d0d0d")
            fig.patch.set_facecolor("#0d0d0d")
            Frontend(RenderContext(doc), MatplotlibBackend(ax), config=cfg).draw_layout(
                msp
            )
            # só cap de lineweight absurdo — sem mexer em alpha (preserva cotas/texto/dashed)
            try:
                for line in list(ax.lines):
                    try:
                        lw = float(line.get_linewidth() or 1.0)
                        if lw > 1.4:
                            line.set_linewidth(0.7)
                    except Exception:
                        pass
            except Exception:
                pass
            # Enquadramento: NUNCA cortar o topo.
            # Sobe o desenho = mais padding embaixo; topo sempre com folga.
            try:
                ax.relim()
                ax.autoscale_view(True, True, True)
                x0, x1 = ax.get_xlim()
                y0, y1 = ax.get_ylim()
                w = max(abs(x1 - x0), 1.0)
                h = max(abs(y1 - y0), 1.0)
                span = max(w, h)
                z = max(1.15, float(zoom_out))
                # margem base simétrica
                base_pad = span * (z - 1.0) * 0.5 + span * 0.06
                # folga extra no topo (anti-corte de cotas/texto)
                top_pad = base_pad + span * 0.12
                # sobe visual: padding inferior = base + y_shift
                bot_pad = base_pad + max(0.0, float(y_shift_up_cm))
                side_pad = base_pad
                ax.set_xlim(x0 - side_pad, x1 + side_pad)
                ax.set_ylim(y0 - bot_pad, y1 + top_pad)
            except Exception:
                pass
            ax.set_aspect("equal")
            ax.axis("off")
            import io

            buf = io.BytesIO()
            fig.savefig(
                buf,
                format="svg",
                dpi=dpi,
                facecolor="#0d0d0d",
                bbox_inches="tight",
                pad_inches=0.12,
            )
            plt.close(fig)
        buf.seek(0)
        svg = strip_fixed_size(buf.read().decode("utf-8"))
        out_svg.parent.mkdir(parents=True, exist_ok=True)
        out_svg.write_text(svg, encoding="utf-8")
        return True
    except Exception as exc:
        print(f"  [WARN] dxf→svg {dxf_path.name}: {exc}", flush=True)
        return False


def _field_input(
    key: str,
    value: Any,
    *,
    item: str,
    part: str,
    kind: str = "text",
    label: str | None = None,
    width: str = "7em",
) -> str:
    """Campo editável com data-atkey para autosave (aten_pil_n3_*)."""
    lab = label or key
    safe_key = re.sub(r"[^\w.\-]+", "_", f"aten_pil_n3_{part}_{item}_{key}")[:120]
    val = "" if value is None else str(value)
    if isinstance(value, (list, dict)):
        val = json.dumps(value, ensure_ascii=False)
    lab_e = html_mod.escape(lab)
    if kind == "checkbox":
        checked = " checked" if str(value).lower() in ("1", "true", "yes", "sim", "on") else ""
        return (
            f'<label class="n3-field n3-check"><span class="n3-lab">{lab_e}</span>'
            f'<input type="checkbox" data-atkey="{html_mod.escape(safe_key, quote=True)}" '
            f'data-n3-part="{html_mod.escape(part)}" data-n3-field="{html_mod.escape(key)}" '
            f'value="1"{checked} onchange="saveAtenTA(this)"></label>'
        )
    if kind == "textarea":
        return (
            f'<label class="n3-field n3-area"><span class="n3-lab">{lab_e}</span>'
            f'<textarea data-atkey="{html_mod.escape(safe_key, quote=True)}" '
            f'data-n3-part="{html_mod.escape(part)}" data-n3-field="{html_mod.escape(key)}" '
            f'rows="2" onblur="saveAtenTA(this)" oninput="saveAtenTA(this)">'
            f"{html_mod.escape(val)}</textarea></label>"
        )
    return (
        f'<label class="n3-field"><span class="n3-lab">{lab_e}</span>'
        f'<input type="text" style="width:{width}" data-atkey="{html_mod.escape(safe_key, quote=True)}" '
        f'data-n3-part="{html_mod.escape(part)}" data-n3-field="{html_mod.escape(key)}" '
        f'value="{html_mod.escape(val, quote=True)}" '
        f'onblur="saveAtenTA(this)" oninput="saveAtenTA(this)"></label>'
    )


def ficha_fields_html(
    ficha: dict,
    part: str,
    *,
    item: str,
    tables_abcd: Optional[dict] = None,
) -> str:
    """Formulário editável por parte (robô CIMA / ABCD / GRADES)."""
    ficha = ficha or {}
    abcd = (tables_abcd or {}).get("faces") or {}

    def g(key: str, default: Any = "") -> Any:
        return ficha[key] if key in ficha else default

    def section(title: str, body: str) -> str:
        return (
            f'<div class="n3-sec"><div class="n3-sec-title">{html_mod.escape(title)}</div>'
            f'<div class="n3-sec-body">{body}</div></div>'
        )

    if part == "cima":
        # Robô CIMA: comprimento/largura, parafusos, grades A/B (distâncias bloquinhos)
        geo = "".join(
            [
                _field_input("comprimento", g("comprimento"), item=item, part=part, label="Comprimento"),
                _field_input("largura", g("largura"), item=item, part=part, label="Largura"),
                _field_input("comprimento_geom", g("comprimento_geom"), item=item, part=part, label="Comp. geom"),
                _field_input("larg_c_geom", g("larg_c_geom"), item=item, part=part, label="Larg. C geom"),
            ]
        )
        pars = "".join(
            _field_input(f"par_{a}_{b}", g(f"par_{a}_{b}", 0), item=item, part=part, label=f"par {a}→{b}")
            for a, b in ((1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9))
        )
        grades = "".join(
            [
                _field_input("grade_1", g("grade_1"), item=item, part=part, label="grade_1 (lado A)"),
                _field_input("grade_2", g("grade_2"), item=item, part=part, label="grade_2 (lado B)"),
                _field_input("grade_3", g("grade_3"), item=item, part=part, label="grade_3"),
                _field_input(
                    "distancia_1",
                    g("distancia_1"),
                    item=item,
                    part=part,
                    label="distância bloquinho A (distancia_1)",
                    width="9em",
                ),
                _field_input(
                    "distancia_2",
                    g("distancia_2"),
                    item=item,
                    part=part,
                    label="distância bloquinho B (distancia_2)",
                    width="9em",
                ),
            ]
        )
        return (
            '<div class="n3-form" data-n3-form="cima">'
            '<div class="n3-form-help">Robô CIMA — edite e salva sozinho (aten_pil_n3_*). Indique o valor correto.</div>'
            + section("Geometria", geo)
            + section("Parafusos (espaçamentos)", pars)
            + section("Grades / bloquinhos A–B", grades)
            + "</div>"
        )

    if part == "abcd":
        # Níveis
        niveis = "".join(
            [
                _field_input("nivel_chegada", g("nivel_chegada"), item=item, part=part, label="Nível chegada"),
                _field_input("nivel_saida", g("nivel_saida"), item=item, part=part, label="Nível saída"),
                _field_input("altura", g("altura"), item=item, part=part, label="Altura"),
                _field_input("pd_pavimento_cm", g("pd_pavimento_cm"), item=item, part=part, label="Pé-direito pav"),
                _field_input(
                    "hatch_reaproveitamento",
                    g("hatch_reaproveitamento", False),
                    item=item,
                    part=part,
                    kind="checkbox",
                    label="Hatch reaproveitamento",
                ),
            ]
        )
        # Painéis por face A–D: h1..h5, larg1..larg3 (= l1 l2 l3)
        faces_html = []
        for fid in "ABCD":
            cells = []
            for hk in ("h1", "h2", "h3", "h4", "h5"):
                key = f"{hk}_{fid}"
                cells.append(
                    _field_input(key, g(key, 0), item=item, part=part, label=f"{hk}", width="5em")
                )
            for lk, lab in (("larg1", "l1"), ("larg2", "l2"), ("larg3", "l3")):
                key = f"{lk}_{fid}"
                cells.append(
                    _field_input(key, g(key, 0), item=item, part=part, label=lab, width="5em")
                )
            cells.append(
                _field_input(f"laje_{fid}", g(f"laje_{fid}", 0), item=item, part=part, label="laje", width="5em")
            )
            cells.append(
                _field_input(
                    f"posicao_laje_{fid}",
                    g(f"posicao_laje_{fid}", 0),
                    item=item,
                    part=part,
                    label="pos.laje",
                    width="5em",
                )
            )
            # intervals
            cells.append(
                _field_input(
                    f"paineis_intervals_{fid}",
                    g(f"paineis_intervals_{fid}", []),
                    item=item,
                    part=part,
                    label="intervals",
                    width="12em",
                )
            )
            faces_html.append(
                f'<div class="n3-face" data-face="{fid}"><div class="n3-face-h">Face {fid}</div>'
                f'<div class="n3-face-grid">{"".join(cells)}</div></div>'
            )

        # Aberturas (chega/para) a partir da interpretação + slots editáveis
        abert_bits = []
        for fid in "ABCD":
            data = abcd.get(fid) or {}
            for kind in ("chega", "passa", "interior"):
                for r in data.get(kind) or []:
                    nome = r.get("nome") or ""
                    if nome in ("", "—", "nenhuma"):
                        continue
                    abert_bits.append(
                        f"{fid}.{kind}: {nome} dim={r.get('dim')} canto={r.get('canto')} "
                        f"d.esq={r.get('dist_esq')} d.dir={r.get('dist_dir')}"
                    )
        abert_txt = "\n".join(abert_bits) if abert_bits else ""
        aberturas = _field_input(
            "aberturas_vigas",
            g("aberturas_vigas", abert_txt),
            item=item,
            part=part,
            kind="textarea",
            label="Aberturas (chega/para/passa) — edite se divergir",
        )

        # Vazios no topo (1..3) — laje/viga passa; multi-laje
        vazios = []
        for i in (1, 2, 3):
            vazios.append(
                f'<div class="n3-vazio-row"><span class="n3-vazio-n">Vazio {i}</span>'
                + _field_input(
                    f"vazio_{i}_ativo",
                    g(f"vazio_{i}_ativo", i == 1 and bool(abert_bits)),
                    item=item,
                    part=part,
                    kind="checkbox",
                    label="ativo",
                )
                + _field_input(
                    f"vazio_{i}_origem",
                    g(f"vazio_{i}_origem", "laje" if i == 1 else ""),
                    item=item,
                    part=part,
                    label="origem (laje/viga)",
                    width="8em",
                )
                + _field_input(
                    f"vazio_{i}_faces",
                    g(f"vazio_{i}_faces", ""),
                    item=item,
                    part=part,
                    label="faces",
                    width="6em",
                )
                + _field_input(
                    f"vazio_{i}_dist_topo",
                    g(f"vazio_{i}_dist_topo", ""),
                    item=item,
                    part=part,
                    label="dist. do topo",
                    width="6em",
                )
                + _field_input(
                    f"vazio_{i}_altura",
                    g(f"vazio_{i}_altura", ""),
                    item=item,
                    part=part,
                    label="altura vazio",
                    width="6em",
                )
                + _field_input(
                    f"vazio_{i}_posicao",
                    g(f"vazio_{i}_posicao", ""),
                    item=item,
                    part=part,
                    label="posição",
                    width="6em",
                )
                + "</div>"
            )

        return (
            '<div class="n3-form" data-n3-form="abcd">'
            '<div class="n3-form-help">Robô ABCD — painéis h1–h5 / l1–l3 por face, níveis, hatch, aberturas e vazios (até 3).</div>'
            + section("Níveis e hatch", niveis)
            + section("Painéis por face (h1–h5 · l1–l3)", "".join(faces_html))
            + section("Aberturas de vigas (chega / para / passa)", aberturas)
            + section("Vazios no topo (lajes / vigas passa) — multi-laje", "".join(vazios))
            + "</div>"
        )

    if part == "grades":
        body = "".join(
            [
                _field_input("grade_1", g("grade_1"), item=item, part=part, label="grade_1"),
                _field_input("grade_2", g("grade_2"), item=item, part=part, label="grade_2"),
                _field_input("grade_3", g("grade_3"), item=item, part=part, label="grade_3"),
                _field_input("distancia_1", g("distancia_1"), item=item, part=part, label="distancia_1"),
                _field_input("distancia_2", g("distancia_2"), item=item, part=part, label="distancia_2"),
                _field_input("modo_distribuicao", g("modo_distribuicao"), item=item, part=part, label="modo"),
                _field_input("comprimento", g("comprimento"), item=item, part=part, label="comprimento"),
                _field_input("largura", g("largura"), item=item, part=part, label="largura"),
            ]
        )
        # intervals por face (malha)
        for fid in "ABCD":
            body += _field_input(
                f"paineis_intervals_{fid}",
                g(f"paineis_intervals_{fid}", []),
                item=item,
                part=part,
                label=f"intervals {fid}",
                width="14em",
            )
        return (
            '<div class="n3-form" data-n3-form="grades">'
            '<div class="n3-form-help">Robô GRADES — campos editáveis (mesma semântica da malha).</div>'
            + section("Grades e distâncias", body)
            + "</div>"
        )

    return f'<p class="muted">parte {html_mod.escape(part)}</p>'


def find_n3_artifacts(
    item: str,
    *,
    obra: str = "Obra_TREINO_1",
    pav: str = "13_PAV",
) -> dict[str, Path]:
    """Localiza DXF N3 ficha 2.0: CIMA + ABCD/GRADES × {para,passa} + JSON.

    Ordem (dinâmica):
    1. ``DADOS-OBRAS/<obra>/Fase-6_Execucao_CAD/n3_variants/{para|passa}/``
    2. tmp/GOLDEN legados (CIMA + abcd/grades single → espelha para/passa)
    """
    out: dict[str, Path] = {}
    data_roots = [
        ROOT.parent / "DADOS-OBRAS" / obra / "Fase-6_Execucao_CAD",
        ROOT / "DADOS-OBRAS" / obra / "Fase-6_Execucao_CAD",
    ]
    for data in data_roots:
        if not data.is_dir():
            continue
        for pat in (
            f"PL_CIMA_preview_{item}.dxf",
            f"n3_variants/para/PL_CIMA_preview_{item}.dxf",
            f"n3_variants/passa/PL_CIMA_preview_{item}.dxf",
        ):
            p = data / pat
            if p.is_file() and "cima" not in out:
                out["cima"] = p
                break
        for mode in ("para", "passa"):
            vdir = data / "n3_variants" / mode
            if not vdir.is_dir():
                continue
            for part, fname in (
                (f"abcd_{mode}", f"PL_ABCD_preview_{item}.dxf"),
                (f"grades_{mode}", f"PL_GRADES_preview_{item}.dxf"),
            ):
                p = vdir / fname
                if p.is_file() and part not in out:
                    out[part] = p
            jp = vdir / f"{item}.json"
            if jp.is_file():
                out.setdefault(f"ficha_{mode}", jp)
                out.setdefault("ficha", jp)
        # CIMA frequentemente no tmp do item (não em n3_variants)
        break

    candidates = [
        ROOT / "scripts" / "arete" / "tmp" / f"PIL_{pav}_{item}" / "Fase-6_Execucao_CAD",
        ROOT / "scripts" / "arete" / "tmp" / f"PIL_13_PAV_{item}" / "Fase-6_Execucao_CAD",
        ROOT / "GOLDEN" / obra / pav / "PIL" / item,
    ]
    for base in candidates:
        if not base.is_dir():
            continue
        for part, pat in (
            ("cima", f"PL_CIMA_preview_{item}.dxf"),
            ("abcd_para", f"PL_ABCD_preview_{item}.dxf"),
            ("abcd_passa", f"PL_ABCD_preview_{item}.dxf"),
            ("grades_para", f"PL_GRADES_preview_{item}.dxf"),
            ("grades_passa", f"PL_GRADES_preview_{item}.dxf"),
            ("abcd", f"PL_ABCD_preview_{item}.dxf"),
            ("grades", f"PL_GRADES_preview_{item}.dxf"),
        ):
            p = base / pat
            if p.is_file() and part not in out:
                out[part] = p
        for jp in [
            base.parent / "Fase-4_Sincronizacao" / "JSON_Pilares" / f"{item}.json",
            base / "ficha.json",
            ROOT / "GOLDEN" / obra / pav / "PIL" / item / "ficha.json",
            ROOT
            / "scripts"
            / "arete"
            / "tmp"
            / f"PIL_13_PAV_{item}"
            / "Fase-4_Sincronizacao"
            / "JSON_Pilares"
            / f"{item}.json",
        ]:
            if jp.is_file() and "ficha" not in out:
                out["ficha"] = jp
                break

    if "abcd" in out:
        out.setdefault("abcd_para", out["abcd"])
        out.setdefault("abcd_passa", out["abcd"])
    if "grades" in out:
        out.setdefault("grades_para", out["grades"])
        out.setdefault("grades_passa", out["grades"])
    return out


def page_css() -> str:
    return """
body{background:#111;color:#d0d0d0;font:13px/1.45 Consolas,monospace;margin:0;padding:16px}
h2{color:#7eb8f7;font-size:18px;margin:0 0 10px}
.tag{display:inline-block;background:#282828;color:#999;font-size:11px;padding:2px 7px;border-radius:3px;margin-left:6px}
.tag.fix{background:#3b1515;color:#ffcdd2;border:1px solid #ff5252}
.tag.ok{background:#0b180b;color:#9fdfb0;border:1px solid #4fc3a1}
.sec{margin:12px 0;border:1px solid #2a2a2a;border-radius:4px}
.sec-title{background:#1e1e1e;color:#4fc3a1;padding:6px 10px;font-size:13px;font-weight:bold}
.sec-body{padding:10px}
.muted{color:#666}
.nav-bar{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 14px}
.nav-bar a{color:#7eb8f7;text-decoration:none;border:1px solid #335;padding:4px 10px;border-radius:3px;font-size:12px}
table.meta td{padding:4px 10px;border-bottom:1px solid #222;font-size:13px}
table.meta td:first-child{color:#888;width:160px}
.n1-tabs{display:flex;flex-wrap:wrap;gap:0;margin:0 0 8px;border-bottom:1px solid #333}
.n1-tab{background:transparent;border:1px solid transparent;border-bottom:none;color:#888;
  padding:6px 12px;font:12px/1 Consolas,monospace;cursor:pointer;border-radius:4px 4px 0 0;margin-bottom:-1px}
.n1-tab:hover{color:#ccc;background:#1a1a1a}
.n1-tab.active{color:#7eb8f7;background:#151515;border-color:#333;border-bottom-color:#151515;font-weight:bold}
.n1-tab[data-n1tab^='n3']{color:#c9a050}
.n1-tab[data-n1tab^='n3'].active{color:#ffd54f;border-color:#665500}
.n1-panel{display:none}.n1-panel.active{display:block}
.n1-svg{background:#0d0d0d;border:1px solid #222;border-radius:3px;padding:4px;overflow:auto}
.n1-svg svg{display:block;width:100%;height:auto;max-height:none}
.n3-form{margin-top:8px}
.n3-form-help{color:#888;font-size:11px;margin:0 0 10px;line-height:1.35}
.n3-sec{margin:0 0 12px;border:1px solid #2a2a2a;border-radius:6px;background:#121212}
.n3-sec-title{background:#1a1a14;color:#ffd54f;font-size:11px;font-weight:700;padding:6px 10px;border-bottom:1px solid #333}
.n3-sec-body{padding:10px;display:flex;flex-wrap:wrap;gap:8px 12px;align-items:flex-end}
.n3-field{display:inline-flex;flex-direction:column;gap:2px;font-size:11px;color:#aaa}
.n3-field input[type=text]{background:#0d0d0d;border:1px solid #444;border-radius:4px;color:#e0e0e0;
  padding:4px 6px;font:12px Consolas,monospace}
.n3-field input[type=text]:focus{border-color:#7eb8f7;outline:none}
.n3-field textarea{background:#0d0d0d;border:1px solid #444;border-radius:4px;color:#e0e0e0;
  padding:6px 8px;font:12px Consolas,monospace;min-width:100%;width:100%;box-sizing:border-box;resize:vertical}
.n3-field.n3-area{flex:1 1 100%}
.n3-field.n3-check{flex-direction:row;align-items:center;gap:6px;min-height:28px}
.n3-lab{color:#9aa;font-size:10px}
.n3-face{flex:1 1 46%;min-width:280px;border:1px solid #2a2a2a;border-radius:6px;padding:8px;background:#0e0e0e}
.n3-face-h{color:#7eb8f7;font-weight:700;font-size:12px;margin:0 0 6px}
.n3-face-grid{display:flex;flex-wrap:wrap;gap:6px 8px}
.n3-vazio-row{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:flex-end;width:100%;
  border-bottom:1px dashed #2a2a2a;padding:6px 0}
.n3-vazio-n{color:#c9a050;font-weight:700;font-size:11px;min-width:4.5em}
.fix-box{background:#1a1208;border:1px solid #665500;border-radius:8px;padding:10px;margin:0 0 10px;font-size:12px;line-height:1.4}
.fix-box b{color:#ffd54f}
.l1-diff{background:#0a1520;border:1px solid #2a5080;border-radius:6px;padding:8px;margin:8px 0;font-size:12px;color:#7ec8ff}
"""


def build_page(
    *,
    name: str,
    idx: int,
    total: int,
    names: list[str],
    obra: str,
    pav: str,
    niveis: dict,
    tables_sa: dict,
    tables_l1: dict,
    fixes: list[str],
    human_note: str,
    sa_plain: str,
    sa_tags: str,
    l1_svg: str,
    n3_svgs: dict[str, str],
    n3_fields: dict[str, str],
    notes_store: str,
) -> str:
    nav = []
    if idx > 1:
        nav.append(f'<a href="{names[idx-2]}.html">◀ {names[idx-2]}</a>')
    nav.append('<a href="../index.html">Índice</a>')
    if idx < total:
        nav.append(f'<a href="{names[idx]}.html">{names[idx]} ▶</a>')

    near = n1_layer_toggle_and_layers(
        sa_svg=sa_tags,
        sa_plain_svg=sa_plain,
        l1_svg=l1_svg,
        l2_svg="",
        l3_svg="",
        item=name,
        sa_plain_src=f"../propostas/{name}_sa_plain.svg",
        sa_tags_src=f"../propostas/{name}_sa_motor.svg",
        l1_src=f"../propostas/{name}_qa_L1.svg",
        l2_src=f"../propostas/{name}_qa_L2.svg",
        l3_src=f"../propostas/{name}_qa_L3.svg",
        viewer_id=f"pil-n1-near-{name}",
    )
    far = wrap_n1_panzoom(
        sa_plain or '<p class="muted">indisponível</p>',
        viewer_id=f"pil-n1-far-{name}",
    )

    def n3_panel(part: str) -> str:
        """Mesmo viewer pan/zoom do N1 (``wrap_n1_panzoom`` / initPilPanZoom)."""
        svg = n3_svgs.get(part) or ""
        if svg:
            # classe idêntica ao N1 distante — mesmo chrome JS/CSS
            return wrap_n1_panzoom(svg, viewer_id=f"pil-n3-{part}-{name}")
        return f'<p class="muted">DXF/SVG N3 {part} não encontrado em tmp/GOLDEN</p>'

    fix_html = ""
    if fixes:
        fix_html = (
            '<div class="fix-box"><b>Proposta L1 (para você aprovar)</b><ul style="margin:6px 0 0 18px">'
            + "".join(f"<li>{html_mod.escape(f)}</li>" for f in fixes)
            + f'</ul><div style="margin-top:6px;color:#aaa">Sua atenção: '
            + html_mod.escape(human_note or "—")
            + "</div></div>"
        )

    tables_sa_html = format_abcd_tables_html(tables_sa, compact=True)
    tables_l1_html = format_abcd_tables_html(tables_l1, compact=True)
    notes = notes_grid_html(obra, pav, name)
    cheg, saida, alt = niveis.get("chegada_abs"), niveis.get("saida_abs"), niveis.get("altura_cm")
    tag_fix = (
        '<span class="tag fix">L1 corrigido — aprovar</span>'
        if fixes
        else '<span class="tag ok">sem auto-fix</span>'
    )

    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>{html_mod.escape(name)} — Interpretação ABCD + N3</title>
<style>{page_css()}
{css_pil_qa()}
</style>
<script>
document.addEventListener('DOMContentLoaded',function(){{
  function showPanel(id){{
    document.querySelectorAll('.n1-tab').forEach(function(b){{
      var on=b.getAttribute('data-n1tab')===id;
      b.classList.toggle('active',on);
      b.setAttribute('aria-selected',on?'true':'false');
    }});
    document.querySelectorAll('.n1-panel').forEach(function(p){{
      var on=p.getAttribute('data-n1panel')===id;
      p.classList.toggle('active',on);
      if(on) p.removeAttribute('hidden'); else p.setAttribute('hidden','');
      if(on){{
        // mesmo initPilPanZoom do N1: re-prepara SVG e home viewBox
        var el=p.querySelector('[data-pil-pz],.pil-panzoom');
        if(el&&el.id&&window.initPilPanZoom){{
          el.dataset.pzInit='0';
          var svg=el.querySelector('svg');
          if(svg){{
            if(window._prepPilSvg) window._prepPilSvg(svg);
            else {{
              svg.removeAttribute('width'); svg.removeAttribute('height');
              svg.style.width='100%'; svg.style.height='100%';
              if(!svg.getAttribute('viewBox')) svg.setAttribute('viewBox','0 0 900 640');
              svg.setAttribute('preserveAspectRatio','xMidYMid meet');
              if(!svg.dataset.homeVb) svg.dataset.homeVb=svg.getAttribute('viewBox')||'';
            }}
          }}
          window.initPilPanZoom(el.id);
          if(el._pzReset) el._pzReset();
        }}
      }}
    }});
    document.querySelectorAll('[data-ficha-panel]').forEach(function(fp){{
      var on=false;
      if(id==='near'||id==='far') on = fp.getAttribute('data-ficha-panel')==='interp';
      if(id.indexOf('n3-')===0) on = fp.getAttribute('data-ficha-panel')===id;
      fp.style.display=on?'block':'none';
    }});
  }}
  document.querySelectorAll('.n1-tab').forEach(function(btn){{
    btn.addEventListener('click',function(){{ showPanel(btn.getAttribute('data-n1tab')); }});
  }});
  showPanel('near');
}});
</script>
{js_pil_qa()}
</head><body>
{notes_store}
<h2>{html_mod.escape(name)}<span class="tag">{idx}/{total}</span>{tag_fix}</h2>
<div class="nav-bar">{''.join(nav)}</div>
<div class="sec"><div class="sec-title">Identidade</div><div class="sec-body">
<table class="meta">
<tr><td>Obra / Pav</td><td>{html_mod.escape(obra)} / {html_mod.escape(pav)}</td></tr>
<tr><td>Nível saída</td><td><b>{saida}cm</b></td></tr>
<tr><td>Nível chegada</td><td><b>{cheg}cm</b></td></tr>
<tr><td>Pé-direito</td><td><b>{alt}cm</b></td></tr>
</table></div></div>
{notes}
{fix_html}
<div class="sec"><div class="sec-title">Viewer — N1 + N3 partes</div>
<div class="sec-body">
<div class="n1-tabs" role="tablist">
  <button type="button" class="n1-tab active" data-n1tab="near">N1 próximo</button>
  <button type="button" class="n1-tab" data-n1tab="far">N1 distante</button>
  <button type="button" class="n1-tab" data-n1tab="n3-cima">N3 cima</button>
  <button type="button" class="n1-tab" data-n1tab="n3-abcd-para">N3 ABCD para</button>
  <button type="button" class="n1-tab" data-n1tab="n3-abcd-passa">N3 ABCD passa</button>
  <button type="button" class="n1-tab" data-n1tab="n3-grades-para">N3 grades para</button>
  <button type="button" class="n1-tab" data-n1tab="n3-grades-passa">N3 grades passa</button>
</div>
<div class="n1-panel active" data-n1panel="near">{near}</div>
<div class="n1-panel" data-n1panel="far" hidden>{far}</div>
<div class="n1-panel" data-n1panel="n3-cima" hidden>{n3_panel('cima')}</div>
<div class="n1-panel" data-n1panel="n3-abcd-para" hidden>{n3_panel('abcd_para')}</div>
<div class="n1-panel" data-n1panel="n3-abcd-passa" hidden>{n3_panel('abcd_passa')}</div>
<div class="n1-panel" data-n1panel="n3-grades-para" hidden>{n3_panel('grades_para')}</div>
<div class="n1-panel" data-n1panel="n3-grades-passa" hidden>{n3_panel('grades_passa')}</div>
</div></div>

<div class="sec" data-ficha-panel="interp"><div class="sec-title">Interpretação ABCD — SA (atual motor)</div>
<div class="sec-body">{tables_sa_html}</div></div>
<div class="sec" data-ficha-panel="interp"><div class="sec-title">Interpretação ABCD — proposta L1 (corrigida)</div>
<div class="sec-body">
<div class="l1-diff">Compare com SA acima. Aba <b>Ag. camada 1</b> no N1 mostra as tags desta proposta.</div>
{tables_l1_html}
</div></div>

<div class="sec" data-ficha-panel="n3-cima" style="display:none"><div class="sec-title">Ficha conversão N3 · CIMA</div>
<div class="sec-body">{n3_fields.get('cima','')}</div></div>
<div class="sec" data-ficha-panel="n3-abcd-para" style="display:none"><div class="sec-title">Ficha conversão N3 · ABCD PARA</div>
<div class="sec-body">{n3_fields.get('abcd_para') or n3_fields.get('abcd','')}</div></div>
<div class="sec" data-ficha-panel="n3-abcd-passa" style="display:none"><div class="sec-title">Ficha conversão N3 · ABCD PASSA</div>
<div class="sec-body">{n3_fields.get('abcd_passa') or n3_fields.get('abcd','')}</div></div>
<div class="sec" data-ficha-panel="n3-grades-para" style="display:none"><div class="sec-title">Ficha conversão N3 · GRADES PARA</div>
<div class="sec-body">{n3_fields.get('grades_para') or n3_fields.get('grades','')}</div></div>
<div class="sec" data-ficha-panel="n3-grades-passa" style="display:none"><div class="sec-title">Ficha conversão N3 · GRADES PASSA</div>
<div class="sec-body">{n3_fields.get('grades_passa') or n3_fields.get('grades','')}</div></div>
</body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True)
    ap.add_argument("--project-id", default="dd238e47-1dc6-4f63-a760-4e7ce19a7386")
    ap.add_argument("--db", default=str(ROOT.parent / "project_data.vision"))
    ap.add_argument("--obra", default="Obra_TREINO_1")
    ap.add_argument("--pav", default="13_PAV")
    ap.add_argument("--items", nargs="*", default=[])
    ap.add_argument("--skip-render", action="store_true", help="Não re-render L1 agentic SVG")
    ap.add_argument(
        "--n3-only",
        action="store_true",
        help="Só regenera HTML + N3 (forms/zoom); mantém L1 SVG/tables se existirem",
    )
    args = ap.parse_args()
    # --n3-only: não força skip_render se houver atenções a aplicar em L1
    # (L1 SVG precisa re-render com tabelas corrigidas)

    pack = Path(args.pack)
    if not pack.is_dir():
        print("[ERR] pack", pack)
        return 2

    import importlib.util

    ag_path = Path(__file__).resolve().parent / "pil_agentic_highlight_draw.py"
    spec = importlib.util.spec_from_file_location("pil_agentic_highlight_draw", ag_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)

    dxf_path, slab_h, slab_n, slab_pts, beams, pillars = mod.load_project(
        Path(args.db), args.project_id, args.obra, args.pav
    )
    niveis = get_pavimento_niveis_abs(args.obra, args.pav) or {
        "chegada_abs": 852.19,
        "saida_abs": 848.98,
        "altura_cm": 321.0,
    }
    nivel_v = f"{niveis.get('chegada_abs')}cm"
    prop = pack / "propostas"
    prop.mkdir(exist_ok=True)
    n3_dir = prop / "n3"
    n3_dir.mkdir(exist_ok=True)

    wanted = {x.upper() for x in args.items} if args.items else None
    batch = [p for p in pillars if not wanted or p["name"].upper() in wanted]
    # only pack html items if no filter
    pack_names = {p.stem for p in (pack / "pilares").glob("*.html")}
    if not wanted:
        batch = [p for p in pillars if p["name"] in pack_names]
    batch.sort(key=lambda p: _natural_key(p["name"]))
    names = [p["name"] for p in batch]

    report_items = []
    for i, pillar in enumerate(batch, 1):
        name = pillar["name"]
        print(f"[{i}/{len(batch)}] {name}…", flush=True)
        keys = pil_keys(args.obra, args.pav, name)
        notes_path = pack / "pilares" / f"{name}.notes.json"
        human = _read_human_note_pack(pack, name, keys)

        # geometria vinculada: reparar contorno truncado via GOLDEN se aplicável
        from src.core.pillar_geometry_fix import maybe_repair_pillar_points

        geom_rep = maybe_repair_pillar_points(
            pillar, obra=args.obra, pav=args.pav, repo_root=ROOT, apply=True
        )

        # orientação geométrica (não forçar vertical)
        pts = pillar.get("points") or []
        try:
            xs = [float(p[0]) for p in pts]
            ys = [float(p[1]) for p in pts]
            pillar["orientation"] = (
                "horizontal"
                if (max(xs) - min(xs)) >= (max(ys) - min(ys))
                else "vertical"
            )
        except Exception:
            pillar.setdefault("orientation", "vertical")

        # re-enriquecer face_beams se horizontal ou geometria reparada
        if geom_rep.get("repaired") or pillar.get("orientation") == "horizontal":
            try:
                from src.core.pillar_face_beams import enrich_pillar_report_with_beams

                report = {name: pillar}
                enrich_pillar_report_with_beams(report, beams)
                if isinstance(pillar.get("face_beams"), dict):
                    pass  # enrich mutates report entry
            except Exception as exc:
                print(f"  [WARN] enrich face_beams: {exc}", flush=True)

        tables_sa = build_abcd_tables_from_pillar(
            pillar,
            slab_height_map=slab_h,
            slab_nivel_map=slab_n,
            slab_points_map=slab_pts,
            beams=beams,
            nivel_viga_default=nivel_v,
        )
        # reusa L1 tables já aprovadas se existirem (--n3-only)
        tables_l1 = tables_sa
        fixes: list[str] = []
        l1_json = prop / f"{name}_qa_L1_tables.json"
        if args.n3_only and l1_json.is_file() and not human:
            try:
                prev = json.loads(l1_json.read_text(encoding="utf-8"))
                tables_l1 = prev.get("tables") or tables_sa
                fixes = list(prev.get("fixes") or [])
            except Exception:
                tables_l1, fixes = apply_human_corrections(
                    name, tables_sa, human, pillar=pillar
                )
        else:
            # com atenção humana: SEMPRE recompute L1 a partir do SA atual
            tables_l1, fixes = apply_human_corrections(
                name, tables_sa, human, pillar=pillar
            )
        is_vert = (tables_l1.get("orientation") or pillar.get("orientation")) != "horizontal"
        # coluna canto sempre preenchida (laje/passa/chega/interior)
        try:
            fill_cantos_all_rows(tables_sa.get("faces") or {}, vertical=is_vert)
            fill_cantos_all_rows(tables_l1.get("faces") or {}, vertical=is_vert)
        except Exception:
            pass

        # SVGs
        def _read_svg(fn: str) -> str:
            p = prop / fn
            return _strip_xml(p.read_text(encoding="utf-8")) if p.is_file() else ""

        sa_plain = _read_svg(f"{name}_sa_plain.svg")
        sa_tags = _read_svg(f"{name}_sa_motor.svg")

        # re-render SA+L1 quando geometria/orientação mudou (horizontal ou GOLDEN)
        l1_svg = ""
        need_sa_rerender = bool(
            geom_rep.get("repaired")
            or pillar.get("orientation") == "horizontal"
            or human
        )
        if not args.skip_render and dxf_path and dxf_path.is_file() and pillar.get("points"):
            try:
                pts_r = pillar.get("points") or []
                if need_sa_rerender:
                    # N1 plain: reusa process_item path via render sem tags
                    # (export _render_n1_svg não está aqui — plain = agentic sa com
                    #  tables vazias? melhor agentic sa + plain from full motor)
                    sa_tags = mod.render_agentic_svg(
                        dxf_path, pts_r, tables_sa, layer="sa"
                    )
                    (prop / f"{name}_sa_motor.svg").write_text(sa_tags, encoding="utf-8")
                    # plain: mesmo SVG base — sem tags extra = layer sa is with tags;
                    # keep previous plain if exists unless geometry repaired
                    if geom_rep.get("repaired") or not sa_plain:
                        # fallback: sa_tags also used as near plain reference
                        sa_plain = sa_tags
                        (prop / f"{name}_sa_plain.svg").write_text(
                            sa_plain, encoding="utf-8"
                        )
                l1_svg = mod.render_agentic_svg(
                    dxf_path, pts_r, tables_l1, layer="l1"
                )
                (prop / f"{name}_qa_L1.svg").write_text(l1_svg, encoding="utf-8")
                (prop / f"{name}_qa_proposta.svg").write_text(l1_svg, encoding="utf-8")
                (prop / f"{name}_qa_L1_tables.json").write_text(
                    json.dumps(
                        {
                            "item": name,
                            "fixes": fixes,
                            "human_note": human,
                            "tables": tables_l1,
                            "geometry_repair": geom_rep if geom_rep.get("repaired") else None,
                            "orientation": pillar.get("orientation"),
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                print(
                    f"  L1 SVG ok · orient={pillar.get('orientation')} "
                    f"geom_fix={geom_rep.get('repaired')} · fixes={fixes}",
                    flush=True,
                )
            except Exception as exc:
                print(f"  [ERR] L1 render: {exc}", flush=True)
                l1_svg = _read_svg(f"{name}_qa_L1.svg")
        else:
            l1_svg = _read_svg(f"{name}_qa_L1.svg")

        # N3 assets — ficha 2.0: CIMA + ABCD/GRADES × {para,passa}
        n3_paths = find_n3_artifacts(name, obra=args.obra, pav=args.pav)
        ficha_by_mode: dict[str, dict] = {}
        for mode in ("para", "passa"):
            key = f"ficha_{mode}"
            if key in n3_paths:
                try:
                    ficha_by_mode[mode] = json.loads(
                        n3_paths[key].read_text(encoding="utf-8")
                    )
                except Exception:
                    ficha_by_mode[mode] = {}
        ficha = {}
        if "ficha" in n3_paths:
            try:
                ficha = json.loads(n3_paths["ficha"].read_text(encoding="utf-8"))
            except Exception:
                ficha = {}
        if not ficha and ficha_by_mode:
            ficha = next(iter(ficha_by_mode.values()))

        n3_svgs: dict[str, str] = {}
        n3_fields: dict[str, str] = {}
        n3_parts = (
            "cima",
            "abcd_para",
            "abcd_passa",
            "grades_para",
            "grades_passa",
        )
        for part in n3_parts:
            form_part = "cima" if part == "cima" else part.split("_")[0]  # abcd|grades
            mode = "para" if part.endswith("_para") else (
                "passa" if part.endswith("_passa") else ""
            )
            ficha_use = ficha_by_mode.get(mode) or ficha
            n3_fields[part] = ficha_fields_html(
                ficha_use, form_part, item=name, tables_abcd=tables_l1 or tables_sa
            )
            # aliases legados
            if form_part in ("abcd", "grades") and form_part not in n3_fields:
                n3_fields[form_part] = n3_fields[part]
            if part == "cima":
                n3_fields["cima"] = n3_fields[part]

            out_svg = n3_dir / f"{name}_{part}.svg"
            src = n3_paths.get(part) or n3_paths.get(form_part)
            if src and Path(src).is_file():
                is_abcd = form_part == "abcd"
                y_up = 850.0 if is_abcd else 300.0
                z_out = 2.35 * 1.2 if is_abcd else 2.35
                dxf_to_svg(
                    Path(src),
                    out_svg,
                    zoom_out=z_out,
                    y_shift_up_cm=y_up,
                    line_scale=0.45,
                    soft_hatch=is_abcd,
                )
                if out_svg.is_file():
                    n3_svgs[part] = _strip_xml(out_svg.read_text(encoding="utf-8"))

        # notes: agent L1 invalidou previous, new proposal text
        agent_text = (
            f"[Camada 1 CORRIGIDA · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%MZ')}]\n"
            f"A partir da atenção humana.\n"
            f"Fixes: {'; '.join(fixes) if fixes else 'nenhum automático'}\n"
            f"Atenção: {human or '—'}\n\n"
            "Peço aprovação humana no destaque L1 (tags) + tabelas L1 abaixo. "
            "Após Validou L1, consolidamos no motor SA."
        )
        notes_updates = {
            keys["agent_l1"]: agent_text,
            keys["agent_verdict_l1"]: "invalidou" if fixes else "validou",
            keys["agent"]: agent_text,
            keys["agent_verdict"]: "invalidou" if fixes else "validou",
        }
        # merge notes
        notes_doc = {
            "version": 1,
            "page": name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "notes": {},
        }
        if notes_path.is_file():
            try:
                old = json.loads(notes_path.read_text(encoding="utf-8"))
                notes_doc["notes"] = dict(old.get("notes") or {})
            except Exception:
                pass
        notes_doc["notes"].update(notes_updates)
        # keep human keys
        notes_path.write_text(json.dumps(notes_doc, ensure_ascii=False, indent=2), encoding="utf-8")
        store = (
            f'<script type="application/json" id="pil-notes-store">\n'
            f"{json.dumps(notes_doc, ensure_ascii=False)}\n</script>"
        )

        html = build_page(
            name=name,
            idx=i,
            total=len(batch),
            names=names,
            obra=args.obra,
            pav=args.pav,
            niveis=niveis,
            tables_sa=tables_sa,
            tables_l1=tables_l1,
            fixes=fixes,
            human_note=human,
            sa_plain=sa_plain,
            sa_tags=sa_tags,
            l1_svg=l1_svg,
            n3_svgs=n3_svgs,
            n3_fields=n3_fields,
            notes_store=store,
        )
        (pack / "pilares" / f"{name}.html").write_text(html, encoding="utf-8")
        report_items.append(
            {
                "item": name,
                "human_note": human,
                "fixes": fixes,
                "n3": {k: str(v) for k, v in n3_paths.items()},
            }
        )

    rep = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "pack": str(pack),
        "items": report_items,
        "instrucao": (
            "Humano: abra cada P#, compare SA vs L1 (tabelas + aba Ag.camada1), "
            "marque Camada1 Validou se a proposta estiver correta. "
            "Abas N3 cima/ABCD/grades = conversão + desenho gerado."
        ),
    }
    (pack / "aten_l1_apply_report.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # index SEMPRE lista todos os HTML do pack (não só o batch --items)
    all_names = sorted(
        {p.stem for p in (pack / "pilares").glob("*.html")},
        key=_natural_key,
    )
    links = "".join(
        f'<li><a href="pilares/{n}.html">{n}</a></li>' for n in all_names
    )
    (pack / "index.html").write_text(
        f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>Pack ABCD + L1 + N3 — {len(all_names)} pilares</title>
<style>
body{{background:#111;color:#ccc;font:13px/1.45 Consolas,sans-serif;padding:20px;max-width:960px}}
a{{color:#7eb8f7;text-decoration:none}}a:hover{{text-decoration:underline}}
h2{{color:#7eb8f7;margin:0 0 10px}}.meta{{color:#888;margin:0 0 14px}}
.grid{{display:flex;flex-wrap:wrap;gap:8px;list-style:none;padding:0;margin:0}}
.grid li a{{display:inline-block;border:1px solid #333;padding:6px 12px;border-radius:4px;min-width:3.2em;text-align:center}}
.grid li a:hover{{border-color:#7eb8f7;background:#151515}}
.note{{background:#1a1208;border:1px solid #665500;border-radius:6px;padding:10px;margin:12px 0;font-size:12px}}
</style>
</head><body>
<h2>Pilares ABCD — atenção aplicada (L1) + N3</h2>
<p class="meta">{args.obra} / {args.pav} — <b>{len(all_names)}</b> itens
(processados nesta corrida: {len(names)})</p>
<div class="note"><b>Fluxo:</b> N1 SA vs L1 corrigido → aprovar L1 → depois motor.
N3: cima · ABCD para/passa · grades para/passa.</div>
<ul class="grid">{links}</ul>
</body></html>""",
        encoding="utf-8",
    )
    print(f"[OK] report {pack / 'aten_l1_apply_report.json'}")
    print(f"[OK] index {len(all_names)} pilares → {pack / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
