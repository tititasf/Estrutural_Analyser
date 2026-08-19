"""Tabelas de interpretação ABCD por face (laje / passa / chega / interior).

Contrato compartilhado entre:
- ficha HTML (pre_validation_dialog)
- portal web N1
- docs/INTERPRETACAO-PILARES-ABCD.md

Não remove regras legadas: só consolida a apresentação e a dualidade
AC/BC ↔ passa C (CA/CB), com nome + dim + nível + canto.
"""
from __future__ import annotations

import html
import re
from typing import Any, Optional


FACE_LABELS_VERTICAL = {
    "A": "A — esquerda (oeste) · face longa",
    "B": "B — direita (leste) · face longa",
    "C": "C — topo (norte) · face curta",
    "D": "D — base (sul) · face curta",
}

FACE_LABELS_HORIZONTAL = {
    "A": "A — base (sul) · face longa",
    "B": "B — topo (norte) · face longa",
    "C": "C — esquerda (oeste) · face curta",
    "D": "D — direita (leste) · face curta",
}

# Dualidade esquina C (pilar vertical): chega na longa ↔ passa na C
# AC ↔ CA (esq de C) · BC ↔ CB (dir de C)
C_DUAL = {
    "AC": ("A", "chega", "AC", "C", "passa", "CA"),
    "BC": ("B", "chega", "BC", "C", "passa", "CB"),
    "CA": ("C", "passa", "CA", "A", "chega", "AC"),
    "CB": ("C", "passa", "CB", "B", "chega", "BC"),
}


def _clean(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    if s in ("", "—", "?", "None", "null"):
        return ""
    return s


def _nivel_str(v: Any, default: str = "") -> str:
    s = _clean(v)
    if not s:
        return default
    if s.endswith("cm") or "⚠" in s:
        return s
    try:
        float(s.replace(",", "."))
        return f"{s}cm" if "cm" not in s else s
    except Exception:
        return s


def _parse_detail_line(text: str) -> dict[str, str]:
    """Extrai nome/dim/N/canto de uma linha 'Viga: X · dim: Y · N: Z · ...'."""
    out = {"nome": "", "dim": "", "nivel": "", "canto": "", "papel": "", "raw": text}
    if not text:
        return out
    m = re.search(r"Viga:\s*([^\s·]+)", text, re.I)
    if m:
        out["nome"] = m.group(1).strip()
    m = re.search(r"dim:\s*([^·\s]+)", text, re.I)
    if m:
        out["dim"] = m.group(1).strip()
    m = re.search(r"N:\s*([^·]+)", text, re.I)
    if m:
        out["nivel"] = m.group(1).strip()
    m = re.search(r"canto\s+([A-D]{2})", text, re.I)
    if m:
        out["canto"] = m.group(1).upper()
    # CA/CB em "passa CA" etc.
    m = re.search(r"\b(CA|CB|AC|AD|BC|BD|DA|DB)\b", text)
    if m and not out["canto"]:
        out["canto"] = m.group(1).upper()
    if "interior" in text.lower() or "limite interno" in text.lower() or "Caso 4" in text:
        out["papel"] = "interior"
    elif "chega" in text.lower() or "termina" in text.lower():
        out["papel"] = "chega"
    elif "passa" in text.lower() or "corre" in text.lower():
        out["papel"] = "passa"
    return out


def _fmt_dist(v: Any) -> str:
    """Formata distância em cm (sem .0 desnecessário)."""
    if v is None or v == "":
        return "—"
    if isinstance(v, str):
        s = v.strip()
        if s in ("", "—", "?"):
            return "—"
        try:
            v = float(s.replace("cm", "").replace(",", "."))
        except Exception:
            return s if s.endswith("cm") else f"{s}cm"
    try:
        f = float(v)
    except Exception:
        return "—"
    if f < 0:
        f = 0.0
    if abs(f - round(f)) < 1e-6:
        return f"{int(round(f))}cm"
    return f"{f:.1f}cm".replace(".0cm", "cm")


def _row(
    familia: str,
    nome: str = "",
    dim: str = "",
    nivel: str = "",
    canto: str = "",
    papel: str = "",
    raw: str = "",
    dist_esq: Any = "",
    dist_dir: Any = "",
) -> dict[str, str]:
    return {
        "familia": familia,
        "nome": _clean(nome) or "—",
        "dim": _clean(dim) or "—",
        "nivel": _nivel_str(nivel) or "—",
        "canto": _clean(canto).upper() or "—",
        "papel": _clean(papel) or "—",
        "raw": raw or "",
        "dist_esq": _fmt_dist(dist_esq),
        "dist_dir": _fmt_dist(dist_dir),
    }


def _beam_from_slot(beam: Optional[dict], default_canto: str = "", papel: str = "") -> Optional[dict]:
    if not isinstance(beam, dict):
        return None
    nome = _clean(beam.get("name") or beam.get("nome"))
    if not nome:
        return None
    return _row(
        familia="viga",
        nome=nome,
        dim=beam.get("dim") or beam.get("d") or "",
        nivel=beam.get("nivel") or beam.get("n") or beam.get("nivel_viga") or "",
        canto=beam.get("corner") or beam.get("canto") or default_canto,
        papel=papel or beam.get("behavior") or "",
        dist_esq=beam.get("dist_esq") or beam.get("d_esq") or "",
        dist_dir=beam.get("dist_dir") or beam.get("d_dir") or "",
    )


# Cantos esq/dir por face (pilar vertical) — INTERPRETACAO-ABCD / face_beams
_FACE_CORNERS_V = {
    "A": ("AC", "AD"),  # esq=topo, dir=base ao longo da face
    "B": ("BD", "BC"),
    "C": ("CA", "CB"),
    "D": ("DA", "DB"),
}


def _pillar_bbox(points) -> tuple[float, float, float, float] | None:
    if not points or len(points) < 2:
        return None
    try:
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
        return min(xs), min(ys), max(xs), max(ys)
    except Exception:
        return None


def _face_axis_span(
    fid: str,
    px0: float,
    py0: float,
    px1: float,
    py1: float,
    *,
    vertical: bool = True,
) -> tuple[str, float, float, float]:
    """Retorna (axis 'x'|'y', coord_esq, coord_dir, face_len).

    Parametrização da face de **esq → dir** (cantos FACE_CORNERS).
    """
    if vertical:
        # A oeste x=px0: esq=AC (y=py1), dir=AD (y=py0)
        # B leste x=px1: esq=BD (y=py0), dir=BC (y=py1)
        # C norte y=py1: esq=CA (x=px0), dir=CB (x=px1)
        # D sul   y=py0: esq=DA (x=px1), dir=DB (x=px0)  — FACE_CORNERS D=(DA,DB)
        if fid == "A":
            return "y", py1, py0, abs(py1 - py0)
        if fid == "B":
            return "y", py0, py1, abs(py1 - py0)
        if fid == "C":
            return "x", px0, px1, abs(px1 - px0)
        if fid == "D":
            return "x", px1, px0, abs(px1 - px0)
    else:
        # horizontal: A base, B topo, C esq, D dir — simplificado
        if fid == "A":
            return "x", px0, px1, abs(px1 - px0)
        if fid == "B":
            # norte E→W: esq=BC (oeste=px0), dir=BD (leste=px1) — alinhado FACE_CORNERS_H
            return "x", px0, px1, abs(px1 - px0)
        if fid == "C":
            return "y", py0, py1, abs(py1 - py0)
        if fid == "D":
            return "y", py1, py0, abs(py1 - py0)
    return "x", 0.0, 0.0, 0.0


def span_dists_on_face(
    fid: str,
    pillar_bb: tuple[float, float, float, float],
    elem_bb: tuple[float, float, float, float] | None,
    *,
    vertical: bool = True,
) -> tuple[Optional[float], Optional[float]]:
    """dist_esq / dist_dir (cm) do elemento na face, a partir dos cantos esq/dir.

    dist_esq = distância do canto esquerdo da face até o início do elemento
    dist_dir = distância do canto direito da face até o fim do elemento
    (cobertura total → 0 / 0; sem overlap → None, None)
    """
    if not elem_bb:
        return None, None
    px0, py0, px1, py1 = pillar_bb
    ex0, ey0, ex1, ey1 = elem_bb
    axis, c_esq, c_dir, face_len = _face_axis_span(
        fid, px0, py0, px1, py1, vertical=vertical
    )
    if face_len <= 1e-9:
        return None, None
    if axis == "y":
        e0, e1 = min(ey0, ey1), max(ey0, ey1)
        f0, f1 = min(py0, py1), max(py0, py1)
    else:
        e0, e1 = min(ex0, ex1), max(ex0, ex1)
        f0, f1 = min(px0, px1), max(px0, px1)
    # overlap com a face no eixo longitudinal
    o0, o1 = max(e0, f0), min(e1, f1)
    if o1 <= o0 + 1e-6:
        return None, None
    # parametriza de c_esq → c_dir (pode ser crescente ou decrescente)
    def to_s(coord: float) -> float:
        # s=0 no esq, s=face_len no dir
        if abs(c_dir - c_esq) < 1e-9:
            return 0.0
        return (coord - c_esq) / (c_dir - c_esq) * face_len

    s0, s1 = to_s(o0), to_s(o1)
    if s0 > s1:
        s0, s1 = s1, s0
    # clamp
    s0 = max(0.0, min(face_len, s0))
    s1 = max(0.0, min(face_len, s1))
    dist_esq = s0
    dist_dir = face_len - s1
    return dist_esq, dist_dir


def _bbox_from_points(pts) -> tuple[float, float, float, float] | None:
    if not pts:
        return None
    try:
        if isinstance(pts, str):
            import json as _json
            pts = _json.loads(pts)
        xs, ys = [], []
        for p in pts:
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                xs.append(float(p[0]))
                ys.append(float(p[1]))
        if len(xs) < 2:
            return None
        return min(xs), min(ys), max(xs), max(ys)
    except Exception:
        return None


def _bbox_near_pillar(
    ebb: tuple[float, float, float, float],
    pbb: tuple[float, float, float, float],
    *,
    pad: float = 30.0,
) -> bool:
    """True se o bbox toca a vizinhança do pilar (rejeita VF301 só no trecho de P1)."""
    ex0, ey0, ex1, ey1 = ebb
    px0, py0, px1, py1 = pbb
    return not (
        ex1 < px0 - pad
        or ex0 > px1 + pad
        or ey1 < py0 - pad
        or ey0 > py1 + pad
    )


def _dim_first_number(dim: Any) -> Optional[float]:
    m = re.match(r"(\d+(?:[.,]\d+)?)", str(dim or "").strip())
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except Exception:
        return None


def _dim_pair(dim: Any) -> tuple[Optional[float], Optional[float]]:
    """Parse '14/55' ou '14x55' → (14.0, 55.0)."""
    s = str(dim or "").strip().replace(",", ".")
    m = re.match(r"(\d+(?:\.\d+)?)\s*[/xX]\s*(\d+(?:\.\d+)?)", s)
    if not m:
        w = _dim_first_number(dim)
        return w, None
    try:
        return float(m.group(1)), float(m.group(2))
    except Exception:
        return None, None


def _fmt_dim_pair(a: float, b: Optional[float]) -> str:
    def _n(v: float) -> str:
        if abs(v - round(v)) < 1e-6:
            return str(int(round(v)))
        return f"{v:g}"

    if b is None:
        return _n(a)
    return f"{_n(a)}/{_n(b)}"


def _is_pillar_section_dim(
    dim: Any,
    pbb: tuple[float, float, float, float],
    *,
    tol: float = 1.6,
) -> bool:
    """True se dim parece seção do **pilar** (ex. 19/66 em pilar 19×66), não da viga.

    Padrão validado P2–P8: cota no nó CB colada na seção do pilar em vez da
    faixa da viga (14/55). Detectar dinamicamente via bbox do pilar — sem
    hardcode de item/nome.
    """
    a, b = _dim_pair(dim)
    if a is None or b is None:
        return False
    pw = abs(pbb[2] - pbb[0])
    ph = abs(pbb[3] - pbb[1])
    short, long = min(pw, ph), max(pw, ph)
    # ordem B/H típica: largura curta / altura longa
    if abs(a - short) <= tol and abs(b - long) <= tol:
        return True
    if abs(a - long) <= tol and abs(b - short) <= tol:
        return True
    return False


def _real_face_rows(tables: dict, fid: str, kind: str) -> list[dict]:
    out: list[dict] = []
    for r in (tables.get(fid) or {}).get(kind) or []:
        n = r.get("nome") or ""
        if n and n not in ("—", "nenhuma"):
            out.append(r)
    return out


def _has_real_laje(tables: dict, fid: str) -> bool:
    return bool(_real_face_rows(tables, fid, "lajes"))


def apply_top_dual_band_dims(
    tables: dict[str, dict[str, list[dict]]],
    pbb: tuple[float, float, float, float] | None,
    slab_points_map: Optional[dict] = None,
    beams: Optional[list] = None,
    *,
    vertical: bool = True,
) -> list[str]:
    """Alinha dim de dual topo (AC/CA/BC/CB) à faixa da viga — não à seção do pilar.

    Regras (pack P1–P8 validado, sem hardcode de nome):
    1. Preferir dim do par dual que NÃO é seção do pilar (ex. CA 14/55 vence CB 19/66).
    2. Se todas forem seção-pilar e houver top_band geométrica, reescrever
       ``{band}/{profundidade_viga}`` (profundidade via fundo canônico ou 2º nº).
    3. Propaga a mesma dim em chega A@AC / B@BC e passa C@CA/CB do mesmo nome.
    """
    notes: list[str] = []
    if not pbb or not vertical:
        return notes
    slab_points_map = slab_points_map or {}
    beams = beams or []
    top_band = _top_band_thickness_cm(
        tables, pbb, slab_points_map, vertical=vertical
    )

    pw = abs(pbb[2] - pbb[0])
    ph = abs(pbb[3] - pbb[1])
    long_side = max(pw, ph)
    short_side = min(pw, ph)

    # dims candidatas por nome: fundo canônico + dimension_texts + largura
    beam_dims: dict[str, list[str]] = {}
    beam_width: dict[str, float] = {}
    try:
        from src.core.pillar_face_beams import (
            canonical_fundo_section_dim,
            clean_beam_section_dim,
        )
    except Exception:
        canonical_fundo_section_dim = None  # type: ignore
        clean_beam_section_dim = lambda x: str(x or "").strip()  # type: ignore

    for b in beams:
        if not isinstance(b, dict):
            continue
        nm = str(b.get("name") or "").strip()
        if not nm:
            continue
        cands: list[str] = beam_dims.setdefault(nm, [])
        if canonical_fundo_section_dim:
            try:
                d = canonical_fundo_section_dim(b) or ""
                if d:
                    cands.append(d)
            except Exception:
                pass
        d0 = str(b.get("dim") or "").strip()
        if d0:
            cands.append(d0)
        for dt in b.get("dimension_texts") or []:
            if not isinstance(dt, dict):
                continue
            cleaned = clean_beam_section_dim(dt.get("text"))
            if cleaned and ("/" in cleaned or "x" in cleaned.lower()):
                cands.append(cleaned)
        for key in ("largura", "width"):
            try:
                w = float(b.get(key))
                if 2.0 <= w <= 80.0:
                    beam_width[nm] = w
            except Exception:
                pass

    dual_slots = (
        ("A", "chega", "AC"),
        ("B", "chega", "BC"),
        ("C", "passa", "CA"),
        ("C", "passa", "CB"),
    )
    by_name: dict[str, list[dict]] = {}
    for fid, kind, canto in dual_slots:
        for r in _real_face_rows(tables, fid, kind):
            c = (r.get("canto") or "").upper()
            if c != canto:
                continue
            nome = str(r.get("nome") or "").strip()
            by_name.setdefault(nome, []).append(r)

    def _depth_from_cands(cands: list[str]) -> Optional[float]:
        """Profundidade estrutural da viga (2º nº) — ignora altura do pilar."""
        depths: list[float] = []
        for d in cands:
            if _is_pillar_section_dim(d, pbb):
                continue
            _a, b = _dim_pair(d)
            if b is not None and abs(b - long_side) > 2.0:
                depths.append(b)
        if not depths:
            return None
        # moda simples
        return max(set(depths), key=depths.count)

    for nome, rows in by_name.items():
        if not rows:
            continue
        good: list[str] = []
        for r in rows:
            d = str(r.get("dim") or "").strip()
            if d and d != "—" and not _is_pillar_section_dim(d, pbb):
                # prefer dims cuja 1ª ≈ top_band (faixa), não largura do pilar
                if top_band is not None:
                    w = _dim_first_number(d)
                    if w is not None and abs(w - top_band) <= 1.6:
                        good.append(d)
                        continue
                    # 19/55 com top_band=14: 1º ≈ short do pilar → não é faixa
                    if w is not None and abs(w - short_side) <= 1.6:
                        continue
                good.append(d)
        for d in beam_dims.get(nome) or []:
            if d and not _is_pillar_section_dim(d, pbb):
                w = _dim_first_number(d)
                if top_band is not None and w is not None:
                    if abs(w - top_band) <= 1.6:
                        good.append(d)
                    elif abs(w - short_side) <= 1.6:
                        continue  # 19/55 residual
                    else:
                        good.append(d)
                else:
                    good.append(d)

        target = ""
        if good:
            if top_band is not None:
                scored = [
                    (abs(_dim_first_number(d) - top_band), d)
                    for d in good
                    if _dim_first_number(d) is not None
                ]
                if scored:
                    scored.sort(key=lambda t: t[0])
                    target = scored[0][1]
            if not target:
                target = good[0]
            # se target 1º nº ≠ band mas band conhecida, reescreve faixa
            if top_band is not None and target:
                tw = _dim_first_number(target)
                if tw is not None and abs(tw - top_band) > 1.6:
                    _a, depth = _dim_pair(target)
                    if depth is not None:
                        target = _fmt_dim_pair(top_band, depth)

        if not target and top_band is not None:
            depth = _depth_from_cands(beam_dims.get(nome) or [])
            if depth is None:
                depth = _depth_from_cands(
                    [str(r.get("dim") or "") for r in rows]
                )
            if depth is None and nome in beam_width:
                # sem profundidade textual: não inventa 2º nº
                depth = None
            if depth is not None:
                target = _fmt_dim_pair(top_band, depth)

        if not target:
            continue

        # Reescreve rows com dim vazia, seção-pilar, ou 1º nº = largura pilar
        # (ex. 19/55 com faixa real 14) — multi-seg real com 1º≈band mantém.
        changed = False
        for r in rows:
            old = str(r.get("dim") or "").strip()
            rewrite = old in ("", "—") or _is_pillar_section_dim(old, pbb)
            if not rewrite and top_band is not None:
                ow = _dim_first_number(old)
                if ow is not None and abs(ow - short_side) <= 1.6 and abs(
                    ow - top_band
                ) > 1.6:
                    rewrite = True
            if rewrite and old != target:
                r["dim"] = target
                changed = True
        if changed:
            notes.append(f"dual-topo {nome}: dim→{target} (faixa viga, não seção pilar)")
    return notes


def prune_phantom_top_dual(
    tables: dict[str, dict[str, list[dict]]],
    pbb: tuple[float, float, float, float] | None,
    *,
    vertical: bool = True,
) -> list[str]:
    """Remove dual topo fantasma no lado sem laje quando dim é seção do pilar.

    Padrão P1 validado: pilar na borda (só laje em B) — motor inventava AC/CA
    com 19/66 (seção do pilar). Mantém só o lado com laje adjacente (BC/CB).

    Não remove se o lado “vazio” tiver dim de viga real (não seção-pilar).
    """
    notes: list[str] = []
    if not pbb or not vertical:
        return notes
    la_a, la_b = _has_real_laje(tables, "A"), _has_real_laje(tables, "B")
    if la_a == la_b:
        return notes  # ambos ou nenhum — não podar por assimetria

    def _drop(fid: str, kind: str, canto: str) -> int:
        rows = (tables.get(fid) or {}).get(kind) or []
        keep = []
        n = 0
        for r in rows:
            c = (r.get("canto") or "").upper()
            nome = r.get("nome") or ""
            if (
                c == canto
                and nome not in ("", "—", "nenhuma")
                and _is_pillar_section_dim(r.get("dim"), pbb)
            ):
                n += 1
                continue
            keep.append(r)
        if n:
            tables[fid][kind] = keep
        return n

    if la_b and not la_a:
        n1 = _drop("A", "chega", "AC")
        n2 = _drop("C", "passa", "CA")
        if n1 or n2:
            notes.append(
                f"poda dual fantasma AC/CA (sem laje em A; dim seção-pilar) n={n1 + n2}"
            )
    elif la_a and not la_b:
        n1 = _drop("B", "chega", "BC")
        n2 = _drop("C", "passa", "CB")
        if n1 or n2:
            notes.append(
                f"poda dual fantasma BC/CB (sem laje em B; dim seção-pilar) n={n1 + n2}"
            )
    return notes


def _top_band_thickness_cm(
    tables: dict,
    pbb: tuple[float, float, float, float],
    slab_points_map: dict,
    *,
    vertical: bool = True,
) -> Optional[float]:
    """Espessura N–S da faixa de viga no topo (ao longo das faces longas A/B).

    Na planta P2: topo laje Y=3193, face C Y=3207 → banda 14 cm.
    A dim 19/66 no nó (CB) é seção no eixo da viga E–W (largura ~pilar),
    **não** a ocupação ao longo de B; usar a banda geométrica ou a cota 14/55 (CA).
    """
    if not vertical:
        return None
    px0, py0, px1, py1 = pbb
    face_c_y = py1
    # 1) Geometria: face C − topo das lajes adjacentes a A/B
    tops: list[float] = []
    for fid in ("A", "B"):
        for r in tables.get(fid, {}).get("lajes") or []:
            nome = r.get("nome") or ""
            if nome in ("", "—", "nenhuma"):
                continue
            bb = _bbox_from_points(slab_points_map.get(nome))
            if bb:
                tops.append(bb[3])  # max y
    if tops:
        band = face_c_y - max(tops)
        if 2.0 <= band <= 80.0:
            return band
    # 2) Segmento CA em C (cota de faixa, ex. 14/55 → 14)
    for r in tables.get("C", {}).get("passa") or []:
        if (r.get("canto") or "").upper() == "CA":
            w = _dim_first_number(r.get("dim"))
            if w and 2.0 <= w <= 80.0:
                return w
    # 3) Menor 1º número entre passa de C que seja "faixa" típica (< face longa/2)
    face_len = abs(py1 - py0)
    cands = []
    for r in tables.get("C", {}).get("passa") or []:
        w = _dim_first_number(r.get("dim"))
        if w and 2.0 <= w <= face_len * 0.5:
            cands.append(w)
    if cands:
        return min(cands)
    return None


def _chega_dists_from_corner(
    fid: str,
    canto: str,
    width_cm: float,
    pbb: tuple[float, float, float, float],
    *,
    vertical: bool = True,
) -> tuple[Optional[float], Optional[float]]:
    """Chegada no canto: ocupa ``width_cm`` ao longo da face a partir do canto.

    d.esq / d.dir relativos aos cantos esq/dir (A: AC/AD, B: BD/BC, …).
    Face A L=66, canto AC, w=14 → (0, 52).
    """
    if width_cm <= 0:
        return None, None
    px0, py0, px1, py1 = pbb
    _axis, _c_esq, _c_dir, face_len = _face_axis_span(
        fid, px0, py0, px1, py1, vertical=vertical
    )
    if face_len <= 1e-9:
        return None, None
    w = min(float(width_cm), face_len)
    canto = (canto or "").upper()
    table = {
        ("A", "AC"): (0.0, face_len - w),
        ("A", "AD"): (face_len - w, 0.0),
        ("B", "BC"): (face_len - w, 0.0),  # esq=BD, dir=BC
        ("B", "BD"): (0.0, face_len - w),
        ("C", "CA"): (0.0, face_len - w),
        ("C", "CB"): (face_len - w, 0.0),
        ("D", "DA"): (0.0, face_len - w),
        ("D", "DB"): (face_len - w, 0.0),
    }
    return table.get((fid, canto), (None, None))


def _beam_bbox_for_name(beams: list, name: str) -> tuple[float, float, float, float] | None:
    if not name or not beams:
        return None
    try:
        from src.core.pillar_face_beams import beam_bbox_from_entity
    except Exception:
        beam_bbox_from_entity = None
    for b in beams:
        if not isinstance(b, dict):
            continue
        if str(b.get("name") or "").strip() != name:
            continue
        if beam_bbox_from_entity:
            bb = beam_bbox_from_entity(b)
            if bb:
                return bb
        pts = b.get("points")
        bb = _bbox_from_points(pts)
        if bb:
            return bb
    return None


def _interior_names(tables: dict) -> set[str]:
    names: set[str] = set()
    for fid in ("C", "D"):
        for r in (tables.get(fid) or {}).get("interior") or []:
            n = r.get("nome") or ""
            if n and n not in ("—", "nenhuma"):
                names.add(n)
    return names


def apply_c_dualidade(tables: dict[str, dict[str, list[dict]]]) -> dict[str, dict[str, list[dict]]]:
    """Garante dualidade: chega A@AC ↔ passa C@CA e chega B@BC ↔ passa C@CB.

    Não propaga vigas de **interior** (Caso 4 em D/C) — essas não são chegadas
    de topo nem passantes de C.
    """

    interior = _interior_names(tables)

    def _has(rows: list, nome: str, canto: str = "") -> bool:
        for r in rows:
            if r.get("nome") != nome:
                continue
            if not canto or r.get("canto") in (canto, "—", ""):
                return True
        return False

    # C passa → A/B chega (exceto se for viga de interior)
    for idx, r in enumerate(list(tables.get("C", {}).get("passa") or [])):
        nome = r.get("nome") or ""
        if not nome or nome in ("—", "nenhuma") or nome in interior:
            continue
        canto = (r.get("canto") or "").upper()
        if canto == "CA":
            target_canto, face = "AC", "A"
        elif canto == "CB":
            target_canto, face = "BC", "B"
        else:
            r["canto"] = "CA" if idx == 0 else "CB"
            if r["canto"] == "CA":
                target_canto, face = "AC", "A"
            else:
                target_canto, face = "BC", "B"
        chega = tables.setdefault(face, {}).setdefault("chega", [])
        # remove chega espúria da viga de interior no mesmo canto
        if not _has(chega, nome, target_canto):
            chega.append(
                _row(
                    "viga",
                    nome=nome,
                    dim=r.get("dim"),
                    nivel=r.get("nivel"),
                    canto=target_canto,
                    papel="chega",
                    raw=r.get("raw"),
                )
            )

    # A/B chega com AC/BC → C passa CA/CB (exceto interior)
    for face, src_canto, c_canto in (("A", "AC", "CA"), ("B", "BC", "CB")):
        for r in list(tables.get(face, {}).get("chega") or []):
            nome = r.get("nome") or ""
            if not nome or nome in ("—", "nenhuma") or nome in interior:
                continue
            canto = (r.get("canto") or "").upper()
            if canto in ("", "—"):
                r["canto"] = src_canto
                canto = src_canto
            if canto != src_canto:
                continue
            passa = tables.setdefault("C", {}).setdefault("passa", [])
            found = False
            for p in passa:
                if p.get("nome") == nome and p.get("canto") in ("—", "", c_canto):
                    p["canto"] = c_canto
                    if p.get("dim") in ("—", "") and r.get("dim") not in ("—", ""):
                        p["dim"] = r["dim"]
                    if p.get("nivel") in ("—", "") and r.get("nivel") not in ("—", ""):
                        p["nivel"] = r["nivel"]
                    found = True
                    break
            if not found and not _has(passa, nome, c_canto):
                passa.append(
                    _row(
                        "viga",
                        nome=nome,
                        dim=r.get("dim"),
                        nivel=r.get("nivel"),
                        canto=c_canto,
                        papel="passa",
                        raw=r.get("raw"),
                    )
                )
    return tables


def apply_c_interior_suppress_top_dual(
    tables: dict[str, dict[str, list[dict]]],
) -> list[str]:
    """Se C tem interior real, não dualiza chega AC/BC → passa CA/CB.

    Padrão validado (P23/P24/P28…): face C é **só interior**; AC/BC nas longas
    são **passa** (não chega) e CA/CB não existem.
    """
    notes: list[str] = []
    c_int = [
        r
        for r in (tables.get("C") or {}).get("interior") or []
        if (r.get("nome") or "") not in ("", "—", "nenhuma")
    ]
    if not c_int:
        return notes

    # remove passa CA/CB em C (dual topo inválido quando há interior C)
    before = len(_real_face_rows(tables, "C", "passa"))
    tables.setdefault("C", {})["passa"] = [
        r
        for r in (tables.get("C") or {}).get("passa") or []
        if (r.get("nome") or "") in ("", "—", "nenhuma")
        or (r.get("canto") or "").upper() not in ("CA", "CB")
    ]
    after = len(_real_face_rows(tables, "C", "passa"))
    if before != after:
        notes.append("C.interior presente → removidos passa CA/CB (sem dual topo)")

    # chega AC/BC → passa AC/BC nas longas
    for face, canto in (("A", "AC"), ("B", "BC")):
        chega = tables.setdefault(face, {}).setdefault("chega", [])
        passa = tables.setdefault(face, {}).setdefault("passa", [])
        keep_chega = []
        moved = 0
        for r in chega:
            c = (r.get("canto") or "").upper()
            nome = r.get("nome") or ""
            if c == canto and nome not in ("", "—", "nenhuma"):
                # já tem passa mesmo nome+canto?
                if not any(
                    p.get("nome") == nome and (p.get("canto") or "").upper() == canto
                    for p in passa
                ):
                    nr = dict(r)
                    nr["papel"] = "passa"
                    nr["canto"] = canto
                    nr["dist_esq"] = "—"
                    nr["dist_dir"] = "—"
                    passa.append(nr)
                    moved += 1
                continue
            keep_chega.append(r)
        tables[face]["chega"] = keep_chega
        if moved:
            notes.append(f"{face}.chega@{canto}→passa@{canto} (C interior, sem dual)")
    return notes


def apply_interior_d_as_passa_ab(tables: dict[str, dict[str, list[dict]]]) -> dict:
    """Interior em C/D materializa os cantos correspondentes nas faces longas.

    Uma viga axial que engloba a tampa C ocupa AC+BC; na tampa D ocupa AD+BD.
    O vínculo é por ``nome+canto``: encontrar o mesmo nome em um extremo não pode
    apagar o segundo extremo da mesma face longa.
    """
    for short_face in ("C", "D"):
        for r in list(tables.get(short_face, {}).get("interior") or []):
            nome = r.get("nome") or ""
            if not nome or nome == "—":
                continue
            for face in ("A", "B"):
                canto = f"{face}{short_face}"
                passa = tables.setdefault(face, {}).setdefault("passa", [])
                if any(
                    p.get("nome") == nome
                    and str(p.get("canto") or "").upper() == canto
                    for p in passa
                ):
                    continue
                passa.append(
                    _row(
                        "viga",
                        nome=nome,
                        dim=r.get("dim"),
                        nivel=r.get("nivel"),
                        canto=canto,
                        papel="passa",
                        raw=r.get("raw"),
                    )
                )
    return tables


def apply_axial_bilateral_short_faces(
    tables: dict[str, dict[str, list[dict]]],
) -> list[str]:
    """Consolida uma viga axial observada nas duas tampas curtas.

    A mesma identidade em C e D prova que a viga percorre o eixo longo do
    pilar: C/D são interiores e A/B recebem os dois cantos. A regra usa apenas
    topologia e identidade, sem nomes de obra, pilar ou viga. Também elimina a
    dualidade falsa ``passa+chega`` criada pela leitura isolada de um extremo.
    """
    short_rows: dict[str, dict[str, dict]] = {"C": {}, "D": {}}
    for face in ("C", "D"):
        for role in ("passa", "chega", "interior"):
            for row in _real_face_rows(tables, face, role):
                name = str(row.get("nome") or "").strip()
                if name:
                    short_rows[face].setdefault(name, row)

    notes: list[str] = []
    for name in sorted(set(short_rows["C"]) & set(short_rows["D"])):
        source = short_rows["C"].get(name) or short_rows["D"][name]
        for face in ("C", "D"):
            for role in ("passa", "chega", "interior"):
                tables.setdefault(face, {}).setdefault(role, [])
                tables[face][role] = [
                    row
                    for row in tables[face][role]
                    if str(row.get("nome") or "").strip() != name
                ]
            tables[face]["interior"].append(
                _row(
                    "viga", nome=name, dim=source.get("dim"),
                    nivel=source.get("nivel"), canto=f"{face}{face}",
                    papel="interior", raw=source.get("raw"),
                )
            )

        for face, corners in (("A", ("AC", "AD")), ("B", ("BC", "BD"))):
            bucket = tables.setdefault(face, {})
            bucket.setdefault("passa", [])
            bucket.setdefault("chega", [])
            bucket["chega"] = [
                row for row in bucket["chega"]
                if str(row.get("nome") or "").strip() != name
            ]
            for corner in corners:
                if any(
                    str(row.get("nome") or "").strip() == name
                    and str(row.get("canto") or "").upper() == corner
                    for row in bucket["passa"]
                ):
                    continue
                bucket["passa"].append(
                    _row(
                        "viga", nome=name, dim=source.get("dim"),
                        nivel=source.get("nivel"), canto=corner,
                        papel="passa", raw=source.get("raw"),
                    )
                )
        notes.append(f"{name}: axial bilateral C/D consolidada")
    return notes


def build_abcd_tables_from_pillar(
    pillar: dict,
    *,
    slab_height_map: Optional[dict] = None,
    slab_nivel_map: Optional[dict] = None,
    slab_points_map: Optional[dict] = None,
    beams: Optional[list] = None,
    nivel_viga_default: str = "",
    face_interp_lines: Optional[dict] = None,
) -> dict[str, Any]:
    """Monta as 4 tabelas a partir de pillar['face_beams'] + lajes (+ linhas opcionais).

    ``dist_esq`` / ``dist_dir``: só para **lajes**, **chegam** e **interior**
    (passantes = "—"). Medidas ao longo da face a partir dos cantos esq/dir.

    Retorno::
        {
          "faces": {
            "A": {"label": "...", "lajes":[row], "passa":[row], "chega":[row], "interior":[row]},
            ...
          },
          "orientation": "vertical"|"horizontal"
        }
    """
    slab_height_map = slab_height_map or {}
    slab_nivel_map = slab_nivel_map or {}
    slab_points_map = slab_points_map or {}
    beams = beams or []
    nivel_viga_default = _nivel_str(nivel_viga_default)

    pts = pillar.get("points") or pillar.get("points_json") or []
    if isinstance(pts, str):
        try:
            import json as _json

            pts = _json.loads(pts)
        except Exception:
            pts = []
    raw_orientation = str(pillar.get("orientation") or "").strip().lower()
    if "horizontal" in raw_orientation:
        orientation = "horizontal"
    elif "vertical" in raw_orientation:
        orientation = "vertical"
    else:
        orientation = ""
    if not orientation and pts:
        try:
            xs = [float(p[0]) for p in pts]
            ys = [float(p[1]) for p in pts]
            orientation = "vertical" if (max(ys) - min(ys)) > (max(xs) - min(xs)) else "horizontal"
        except Exception:
            orientation = "vertical"
    if orientation not in ("vertical", "horizontal"):
        orientation = "vertical"

    labels = (
        FACE_LABELS_HORIZONTAL
        if orientation == "horizontal"
        else FACE_LABELS_VERTICAL
    )

    tables: dict[str, dict[str, list[dict]]] = {
        fid: {"lajes": [], "passa": [], "chega": [], "interior": []} for fid in "ABCD"
    }

    # 1) Lajes de pillar['lajes'] / lajes_adjacentes
    lajes_list = list(pillar.get("lajes") or [])
    if not lajes_list and pillar.get("lajes_adjacentes"):
        lajes_list = list(pillar.get("lajes_adjacentes") or [])
    for e in lajes_list:
        if not isinstance(e, dict):
            continue
        side = str(e.get("side") or "").strip().upper()
        if side not in tables:
            continue
        ct = (e.get("content_type") or "laje").lower()
        if ct in ("laje", "both") and e.get("laje"):
            ln = str(e["laje"]).strip()
            tables[side]["lajes"].append(
                _row(
                    "laje",
                    nome=ln,
                    dim=(slab_height_map.get(ln) or e.get("h") or e.get("esp") or ""),
                    nivel=(slab_nivel_map.get(ln) or e.get("nivel") or e.get("n") or ""),
                    papel="laje",
                )
            )
        # content_type viga em lajes_adjacentes é dica; face_beams manda no papel
            # (passa/chega/interior). Não duplicar aqui.

    # 2) face_beams canônico
    fb = pillar.get("face_beams") or {}
    interior_names: set[str] = set()
    if isinstance(fb, dict):
        for fid in "ABCD":
            data = fb.get(fid) or {}
            if not isinstance(data, dict):
                continue
            for beam in data.get("interior") or []:
                if isinstance(beam, dict) and beam.get("name"):
                    interior_names.add(str(beam["name"]).strip())

        for fid in "ABCD":
            data = fb.get(fid) or {}
            if not isinstance(data, dict):
                continue
            c_esq = str(data.get("corner_esq") or "").upper()
            c_dir = str(data.get("corner_dir") or "").upper()
            for slot, default_c in (("passa_esq", c_esq), ("passa_dir", c_dir)):
                beam_raw = data.get(slot) or {}
                br = _beam_from_slot(beam_raw, default_canto=default_c, papel="passa")
                if not br:
                    continue
                nome = br["nome"]
                behavior = str(beam_raw.get("behavior") or "").lower()
                # Viga de interior (Caso 4) nos slots A/B → sempre PASSA nas longas
                # (mesmo se behavior=para no payload topológico).
                is_interior_beam = nome in interior_names
                if (
                    behavior == "para"
                    and fid in ("A", "B")
                    and not is_interior_beam
                    and default_c in ("AC", "BC", "CA", "CB")
                ):
                    # Chegada de topo nos cantos AC/BC (não misturar com AD/BD da viga de baixo)
                    br["papel"] = "chega"
                    br["canto"] = default_c if default_c in ("AC", "BC") else (
                        "AC" if fid == "A" else "BC"
                    )
                    if not br["nivel"] or br["nivel"] == "—":
                        br["nivel"] = nivel_viga_default or "—"
                    tables[fid]["chega"].append(br)
                else:
                    if fid == "C":
                        br["canto"] = "CA" if slot == "passa_esq" else "CB"
                    # Interior (Caso 4) nas longas = passa; MANTER canto do slot
                    # (AC/AD/BC/BD). Limpar canto→"—" gerava AA/BB e perdia
                    # multi-passa validado (P10: V309A@AC + V309@AD).
                    if is_interior_beam and fid in ("A", "B"):
                        br["papel"] = "passa"
                        # se slot não trouxe canto, usa default_c do corner_esq/dir
                        if (br.get("canto") or "") in ("", "—"):
                            br["canto"] = default_c or "—"
                    if not br["nivel"] or br["nivel"] == "—":
                        br["nivel"] = nivel_viga_default or "—"
                    tables[fid]["passa"].append(br)
            for beam in data.get("para") or []:
                br = _beam_from_slot(beam, papel="chega")
                if not br:
                    continue
                canto_b = (br.get("canto") or str(beam.get("corner") or "")).upper()
                # Corner central em para[] depende da família da face. Em A/B
                # (faces longas), a viga perpendicular termina no meio da face:
                # é uma chegada central. Em C/D (faces curtas), o slot central
                # continua representando o eixo longitudinal interior (Caso 4).
                if canto_b in ("CC", "DD", "AA", "BB"):
                    br["canto"] = canto_b
                    if not br["nivel"] or br["nivel"] == "—":
                        br["nivel"] = nivel_viga_default or "—"
                    target_kind = "chega" if fid in ("A", "B") else "interior"
                    br["papel"] = target_kind
                    if not any(
                        x.get("nome") == br["nome"]
                        for x in tables[fid][target_kind]
                    ):
                        tables[fid][target_kind].append(br)
                    continue
                if br["nome"] in interior_names:
                    continue  # interior de D/C não vira chega em A/B
                if not br["nivel"] or br["nivel"] == "—":
                    br["nivel"] = nivel_viga_default or "—"
                tables[fid]["chega"].append(br)
            for beam in data.get("interior") or []:
                br = _beam_from_slot(beam, papel="interior")
                if br:
                    if not br["nivel"] or br["nivel"] == "—":
                        br["nivel"] = nivel_viga_default or "—"
                    tables[fid]["interior"].append(br)
                    # D/C: não listar a mesma viga como passa na face curta interior
                    tables[fid]["passa"] = [
                        p for p in tables[fid]["passa"] if p.get("nome") != br["nome"]
                    ]

    # 3) Linhas já interpretadas (ficha dinâmica) — complementam sem apagar
    if isinstance(face_interp_lines, dict):
        for fid in "ABCD":
            data = face_interp_lines.get(fid) or {}
            for kind in ("lajes", "passa", "chega", "interior"):
                for line in data.get(kind) or []:
                    if kind == "lajes":
                        m = re.search(r"Laje:\s*([^\s·]+)", str(line))
                        nome = m.group(1) if m else ""
                        if not nome:
                            continue
                        if any(r.get("nome") == nome for r in tables[fid]["lajes"]):
                            continue
                        m_esp = re.search(r"esp:\s*([^·\s]+)", str(line))
                        m_n = re.search(r"N:\s*([^·]+)", str(line))
                        tables[fid]["lajes"].append(
                            _row(
                                "laje",
                                nome=nome,
                                dim=(m_esp.group(1) if m_esp else slab_height_map.get(nome, "")),
                                nivel=(m_n.group(1).strip() if m_n else slab_nivel_map.get(nome, "")),
                                papel="laje",
                                raw=str(line),
                            )
                        )
                    else:
                        parsed = _parse_detail_line(str(line))
                        if not parsed.get("nome"):
                            continue
                        bucket = kind
                        if any(
                            r.get("nome") == parsed["nome"] and r.get("dim") == (parsed["dim"] or r.get("dim"))
                            for r in tables[fid][bucket]
                        ):
                            continue
                        if not parsed.get("nivel"):
                            parsed["nivel"] = nivel_viga_default
                        if kind == "passa" and fid == "C" and parsed.get("canto") in ("", "—"):
                            # preenche CA/CB por ordem
                            n_exist = len(tables[fid]["passa"])
                            parsed["canto"] = "CA" if n_exist == 0 else "CB"
                        tables[fid][bucket].append(
                            _row(
                                "viga",
                                nome=parsed["nome"],
                                dim=parsed["dim"],
                                nivel=parsed["nivel"],
                                canto=parsed["canto"],
                                papel=parsed["papel"] or kind,
                                raw=parsed["raw"],
                            )
                        )

    # 4) Regras de consolidação
    apply_axial_bilateral_short_faces(tables)
    apply_interior_d_as_passa_ab(tables)
    apply_c_dualidade(tables)

    # Default nível viga se ainda vazio
    if nivel_viga_default:
        for fid in "ABCD":
            for kind in ("passa", "chega", "interior"):
                for r in tables[fid][kind]:
                    if r.get("nivel") in ("", "—"):
                        r["nivel"] = nivel_viga_default

    # ── dist_esq / dist_dir (lajes, chega, interior; passa fica "—") ─────────
    pbb = _pillar_bbox(pts)
    is_vertical = orientation == "vertical"

    # 4b) Poda fantasma (com dim ainda "seção-pilar") → unifica dim dual topo.
    #     Ordem importa: se reescrever dim antes, a poda deixa de ver 19/66.
    #     P1: remove AC/CA inventados; P2–P8: BC/CB 19/66 → 14/55.
    if pbb and is_vertical:
        prune_phantom_top_dual(tables, pbb, vertical=is_vertical)
        apply_c_dualidade(tables)  # re-sincroniza só o lado real restante
        apply_top_dual_band_dims(
            tables,
            pbb,
            slab_points_map,
            beams,
            vertical=is_vertical,
        )
    # 4c) Interior em C anula dual topo (CA/CB + chega AC/BC → passa AC/BC)
    apply_c_interior_suppress_top_dual(tables)

    if pbb:
        for fid in "ABCD":
            # lajes
            for r in tables[fid]["lajes"]:
                nome = r.get("nome") or ""
                if nome in ("", "—", "nenhuma"):
                    r["dist_esq"] = r["dist_dir"] = "—"
                    continue
                ebb = _bbox_from_points(slab_points_map.get(nome))
                de, dd = span_dists_on_face(fid, pbb, ebb, vertical=is_vertical)
                r["dist_esq"] = _fmt_dist(de)
                r["dist_dir"] = _fmt_dist(dd)
            # passa: sem distâncias posicionais
            for r in tables[fid]["passa"]:
                r["dist_esq"] = "—"
                r["dist_dir"] = "—"
            # Espessura da faixa de topo (compartilhada A@AC e B@BC)
            top_band = _top_band_thickness_cm(
                tables, pbb, slab_points_map, vertical=is_vertical
            )

            # chega + interior
            for kind in ("chega", "interior"):
                for r in tables[fid][kind]:
                    nome = r.get("nome") or ""
                    if nome in ("", "—", "nenhuma"):
                        r["dist_esq"] = r["dist_dir"] = "—"
                        continue
                    if r.get("dist_esq") not in ("", "—") and r.get("dist_dir") not in ("", "—"):
                        continue

                    de = dd = None
                    canto = (r.get("canto") or "").upper()
                    w = _dim_first_number(r.get("dim"))

                    # CHEGA nos cantos de TOPO das longas (AC/BC): ocupação ao
                    # longo da face = espessura N–S da faixa E–W (14 cm no P2),
                    # NÃO o 1º nº de 19/66 (largura no eixo da viga ≈ pilar).
                    # Assim A e B ficam simétricos: 0/52 e 52/0 (não 0/52 e 47/0).
                    if kind == "chega" and canto in ("AC", "BC", "CA", "CB"):
                        w_use = top_band if top_band is not None else w
                        # se dim local for faixa típica (< metade da face longa), ok
                        if w_use is None and w is not None:
                            w_use = w
                        if w_use is not None and canto:
                            # mapear CA→AC, CB→BC quando a row estiver em A/B
                            c_use = canto
                            if fid == "A" and canto == "CA":
                                c_use = "AC"
                            if fid == "B" and canto == "CB":
                                c_use = "BC"
                            de, dd = _chega_dists_from_corner(
                                fid, c_use, w_use, pbb, vertical=is_vertical
                            )
                    elif kind == "chega" and w and canto:
                        de, dd = _chega_dists_from_corner(
                            fid, canto, w, pbb, vertical=is_vertical
                        )

                    if de is None:
                        ebb = _beam_bbox_for_name(beams, nome)
                        if ebb and _bbox_near_pillar(ebb, pbb, pad=30.0):
                            de, dd = span_dists_on_face(
                                fid, pbb, ebb, vertical=is_vertical
                            )
                        elif kind == "interior" and w:
                            de, dd = span_dists_on_face(
                                fid, pbb, pbb, vertical=is_vertical
                            )

                    r["dist_esq"] = _fmt_dist(de)
                    r["dist_dir"] = _fmt_dist(dd)

    faces_out = {}
    for fid in "ABCD":
        faces_out[fid] = {
            "label": labels.get(fid, fid),
            "lajes": tables[fid]["lajes"] or [_row("laje", nome="nenhuma", papel="—")],
            "passa": tables[fid]["passa"] or [_row("viga", nome="nenhuma", papel="passa")],
            "chega": tables[fid]["chega"] or [_row("viga", nome="nenhuma", papel="chega")],
            "interior": tables[fid]["interior"] or [_row("viga", nome="nenhuma", papel="interior")],
        }
        # garante chaves dist em todas as rows
        for kind in ("lajes", "passa", "chega", "interior"):
            for r in faces_out[fid][kind]:
                r.setdefault("dist_esq", "—")
                r.setdefault("dist_dir", "—")
                if kind == "passa":
                    r["dist_esq"] = r["dist_dir"] = "—"

    fill_cantos_all_rows(faces_out, vertical=is_vertical)
    return {"faces": faces_out, "orientation": orientation, "schema": "pil.abcd_tables.v2"}


def _parse_dist_cm(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip().replace("cm", "").replace(",", ".")
    if s in ("", "—", "-", "None"):
        return None
    try:
        return float(s)
    except Exception:
        return None


def _canto_from_dists(
    fid: str,
    dist_esq: Any,
    dist_dir: Any,
    *,
    vertical: bool = True,
    kind: str = "lajes",
) -> str:
    """Resolve marca de canto a partir de d.esq/d.dir e família.

    - Laje/interior de lado a lado (ambos ~0 ou sem dist) → AA/BB/CC/DD
    - Distância 0 só em um lado → canto daquela esquina (AC/AD/BC/BD/…)
    - Chega: AC/BC/… canônicos se vazio
    - Passa: mantém dual CA/CB ou mid AA… se vazio
    """
    mid = {"A": "AA", "B": "BB", "C": "CC", "D": "DD"}.get(fid, "AA")
    corners = _FACE_CORNERS_V if vertical else {
        "A": ("AD", "AC"),
        "B": ("BC", "BD"),
        "C": ("CA", "CB"),
        "D": ("DA", "DB"),
    }
    c_esq, c_dir = corners.get(fid, ("AA", "AA"))
    de = _parse_dist_cm(dist_esq)
    dd = _parse_dist_cm(dist_dir)
    tol = 0.6  # cm — “0” prático

    if kind == "interior":
        return mid

    if kind == "chega":
        # chega quase sempre na esquina de topo das longas
        default_chega = {"A": "AC", "B": "BC", "C": "CA", "D": "DA"}.get(fid, mid)
        if de is not None and dd is not None:
            if de <= tol and dd > tol:
                return c_esq
            if dd <= tol and de > tol:
                return c_dir
            if de <= tol and dd <= tol:
                return mid
        return default_chega

    if kind == "passa":
        # dual C já vem CA/CB; longas sem canto → meio da face (AA/BB)
        if fid in ("C", "D"):
            # sem dist em passa; caller deve setar CA/CB; fallback mid
            return mid if fid == "D" else "CA"
        return mid

    # lajes (e genérico)
    if de is not None and dd is not None:
        if de <= tol and dd <= tol:
            return mid  # de lado a lado / cobre a face
        if de <= tol and dd > tol:
            return c_esq  # encosta no canto esquerdo
        if dd <= tol and de > tol:
            return c_dir  # encosta no canto direito
        # parcial no meio da face
        return mid
    if de is not None and de <= tol:
        return c_esq
    if dd is not None and dd <= tol:
        return c_dir
    return mid


def fill_cantos_all_rows(faces: dict, *, vertical: bool = True) -> None:
    """Garante coluna ``canto`` preenchida em laje/passa/chega/interior (nunca — se real).

    Regras (dono):
    - interior → AA/BB/CC/DD
    - laje lado a lado → AA/BB/CC/DD; d=0 só num lado → AC/AD/BC/BD/…
    - passa: mantém CA/CB se já setado; senão mid AA/BB (longas) ou CA/CB por ordem em C
    - chega: AC/BC se vazio
    - linha ``nenhuma`` permanece —
    """
    # multi-seg C: atribui CA, CB na ordem se vazios
    c_passa = [
        r
        for r in (faces.get("C") or {}).get("passa") or []
        if (r.get("nome") or "") not in ("", "—", "nenhuma")
    ]
    empty_c = [
        r
        for r in c_passa
        if str(r.get("canto") or "").strip().upper() in ("", "—", "NONE", "N/A", "CC")
    ]
    if len(c_passa) >= 1 and empty_c:
        slots = ["CA", "CB", "CC"]
        used = {
            str(r.get("canto") or "").upper()
            for r in c_passa
            if str(r.get("canto") or "").upper() in ("CA", "CB")
        }
        free = [s for s in slots if s not in used]
        for r in empty_c:
            r["canto"] = free.pop(0) if free else "CA"

    for fid in "ABCD":
        data = faces.get(fid) or {}
        for kind in ("lajes", "passa", "chega", "interior"):
            for r in data.get(kind) or []:
                nome = str(r.get("nome") or "").strip()
                if nome in ("", "—", "nenhuma"):
                    r["canto"] = "—"
                    continue
                cur = str(r.get("canto") or "").strip().upper()
                if cur in ("", "—", "NONE", "N/A"):
                    cur = ""
                if kind == "interior":
                    r["canto"] = {"A": "AA", "B": "BB", "C": "CC", "D": "DD"}[fid]
                    continue
                if cur in (
                    "AC", "AD", "BC", "BD", "CA", "CB", "DA", "DB",
                    "AA", "BB", "CC", "DD",
                ):
                    r["canto"] = cur
                    continue
                r["canto"] = _canto_from_dists(
                    fid,
                    r.get("dist_esq"),
                    r.get("dist_dir"),
                    vertical=vertical,
                    kind=kind if kind != "lajes" else "lajes",
                )


def _face_rows_unified(data: dict) -> list[tuple[str, dict]]:
    """Uma linha por vínculo: (rótulo família, row). Evita 4 mini-tabelas."""
    fams = (
        ("Lajes", data.get("lajes") or []),
        ("Passam", data.get("passa") or []),
        ("Chegam", data.get("chega") or []),
        ("Interior", data.get("interior") or []),
    )
    out: list[tuple[str, dict]] = []
    for fam, rows in fams:
        real = [r for r in rows if (r.get("nome") or "") not in ("", "—", "nenhuma")]
        if real:
            for r in real:
                out.append((fam, r))
        else:
            out.append((fam, {"nome": "nenhuma", "dim": "—", "nivel": "—", "canto": "—"}))
    return out


def format_abcd_tables_html(tables_payload: dict, *, compact: bool = False) -> str:
    """HTML: 1 tabela por face (Família|Nome|Dim|Nível|Canto|d.esq|d.dir)."""
    faces = (tables_payload or {}).get("faces") or {}
    # compact ainda legível (fichas SA); não-compact um pouco maior
    fs = "13px" if compact else "14px"
    title_fs = "14px" if compact else "15px"
    table_fs = "13px" if compact else "14px"
    pad = "5px 7px" if compact else "6px 8px"
    cards = []
    colors = {"A": "#4fc3a1", "B": "#7eb8f7", "C": "#c47ef7", "D": "#f0b840"}
    head = (
        "<tr><th>Família</th><th>Nome</th><th>Dim</th><th>Nível</th>"
        "<th>Canto</th><th>d.esq</th><th>d.dir</th></tr>"
    )
    for fid in "ABCD":
        data = faces.get(fid) or {}
        label = data.get("label") or fid
        color = colors[fid]
        body = []
        for fam, r in _face_rows_unified(data):
            body.append(
                "<tr>"
                f"<td class=\"abcd-fam-cell\">{html.escape(fam)}</td>"
                f"<td>{html.escape(str(r.get('nome') or '—'))}</td>"
                f"<td>{html.escape(str(r.get('dim') or '—'))}</td>"
                f"<td>{html.escape(str(r.get('nivel') or '—'))}</td>"
                f"<td>{html.escape(str(r.get('canto') or '—'))}</td>"
                f"<td>{html.escape(str(r.get('dist_esq') or '—'))}</td>"
                f"<td>{html.escape(str(r.get('dist_dir') or '—'))}</td>"
                "</tr>"
            )
        cards.append(
            f'<div class="abcd-face-card" style="border-left:3px solid {color}">'
            f'<div class="abcd-face-title" style="color:{color}">{html.escape(label)}</div>'
            f'<table class="abcd-mini">{head}{"".join(body)}</table>'
            f"</div>"
        )
    style = f"""
<style>
.abcd-grid{{display:grid;grid-template-columns:repeat(2,minmax(320px,1fr));gap:12px;margin:8px 0}}
.abcd-face-card{{background:#101010;border:1px solid #2a2a2a;border-radius:4px;padding:10px;font-size:{fs}}}
.abcd-face-title{{font-weight:bold;margin-bottom:8px;font-size:{title_fs}}}
.abcd-mini{{width:100%;border-collapse:collapse;font-size:{table_fs}}}
.abcd-mini th{{text-align:left;color:#888;border-bottom:1px solid #333;padding:{pad};font-weight:600}}
.abcd-mini td{{padding:{pad};color:#ddd;border-bottom:1px solid #1a1a1a;vertical-align:top}}
.abcd-mini .abcd-fam-cell{{color:#9aa;font-weight:600;white-space:nowrap}}
.abcd-mini tr:last-child td{{border-bottom:none}}
</style>
"""
    return style + f'<div class="abcd-grid">{"".join(cards)}</div>'


def format_abcd_tables_portal_html(tables_payload: dict) -> str:
    """HTML claro portal N1: 1 tabela por face + d.esq/d.dir."""
    faces = (tables_payload or {}).get("faces") or {}
    cards = []
    colors = {"A": "#0d7a5f", "B": "#2b6cb0", "C": "#6b46c1", "D": "#c05621"}
    head = (
        "<tr><th>Família</th><th>Nome</th><th>Dim</th><th>Nível</th>"
        "<th>Canto</th><th>d.esq</th><th>d.dir</th></tr>"
    )
    for fid in "ABCD":
        data = faces.get(fid) or {}
        label = data.get("label") or fid
        color = colors[fid]
        body = []
        for fam, r in _face_rows_unified(data):
            body.append(
                "<tr>"
                f"<td class=\"abcd-p-fam-cell\">{html.escape(fam)}</td>"
                f"<td>{html.escape(str(r.get('nome') or '—'))}</td>"
                f"<td>{html.escape(str(r.get('dim') or '—'))}</td>"
                f"<td>{html.escape(str(r.get('nivel') or '—'))}</td>"
                f"<td>{html.escape(str(r.get('canto') or '—'))}</td>"
                f"<td>{html.escape(str(r.get('dist_esq') or '—'))}</td>"
                f"<td>{html.escape(str(r.get('dist_dir') or '—'))}</td>"
                "</tr>"
            )
        cards.append(
            f'<div class="abcd-p-card" style="border-left:4px solid {color}">'
            f'<div class="abcd-p-title" style="color:{color}">{html.escape(label)}</div>'
            f'<table class="abcd-p-tbl">{head}{"".join(body)}</table>'
            f"</div>"
        )
    style = """
<style>
.abcd-p-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;margin:10px 0}
.abcd-p-card{background:#fff;border:1px solid #e2e8f0;border-radius:6px;padding:10px;box-shadow:0 1px 2px rgba(0,0,0,.04)}
.abcd-p-title{font-weight:700;font-size:13px;margin-bottom:8px}
.abcd-p-tbl{width:100%;border-collapse:collapse;font-size:12px}
.abcd-p-tbl th{text-align:left;color:#64748b;border-bottom:1px solid #cbd5e1;padding:4px 6px;font-weight:600;background:#f8fafc}
.abcd-p-tbl td{padding:4px 6px;border-bottom:1px solid #f1f5f9;color:#1e293b}
.abcd-p-tbl .abcd-p-fam-cell{color:#64748b;font-weight:600;white-space:nowrap}
.abcd-p-tbl tr:last-child td{border-bottom:none}
</style>
"""
    return (
        style
        + '<div class="abcd-p-wrap"><div style="font-size:12px;font-weight:700;margin:6px 0;color:#334155">'
        "Interpretação ABCD por face "
        "<span style=\"font-weight:500;color:#94a3b8\">(d.esq/d.dir = dist. dos cantos esq/dir da face; "
        "passantes = —)</span></div>"
        f'<div class="abcd-p-grid">{"".join(cards)}</div></div>'
    )


def lines_from_tables(tables_payload: dict) -> dict[str, dict[str, list[str]]]:
    """Converte tabelas em linhas texto compatíveis com _dynamic_face_interpretation."""
    out: dict[str, dict[str, list[str]]] = {}
    for fid, data in ((tables_payload or {}).get("faces") or {}).items():
        out[fid] = {"lajes": [], "passa": [], "chega": [], "interior": []}
        for r in data.get("lajes") or []:
            if (r.get("nome") or "") in ("", "—", "nenhuma"):
                continue
            bits = [f"Laje: {r['nome']}"]
            if r.get("dim") not in ("", "—"):
                bits.append(f"esp: {r['dim']}cm" if "cm" not in str(r["dim"]) else f"esp: {r['dim']}")
            if r.get("nivel") not in ("", "—"):
                bits.append(f"N: {r['nivel']}")
            out[fid]["lajes"].append("  ·  ".join(bits))
        for kind in ("passa", "chega", "interior"):
            for r in data.get(kind) or []:
                if (r.get("nome") or "") in ("", "—", "nenhuma"):
                    continue
                bits = [f"Viga: {r['nome']}"]
                if r.get("dim") not in ("", "—"):
                    bits.append(f"dim: {r['dim']}")
                if r.get("nivel") not in ("", "—"):
                    bits.append(f"N: {r['nivel']}")
                if kind == "passa":
                    canto = r.get("canto") or ""
                    if canto not in ("", "—"):
                        bits.append(f"passa {canto}")
                    else:
                        bits.append(f"corre ao longo da face {fid}")
                elif kind == "chega":
                    canto = r.get("canto") or ""
                    if canto not in ("", "—"):
                        bits.append(f"chega no canto {canto}")
                    else:
                        bits.append(f"chega na face {fid}")
                else:
                    bits.append(f"face {fid} é limite interno (Caso 4)")
                out[fid][kind].append("  ·  ".join(bits))
    return out
