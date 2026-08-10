"""Contorno do marco vermelho N2 (LAJ) — CE + audit visual (fonte única).

Prioridade:
1) Override gravado no DB (`_er_meta.n2_highlight_world`) — o loop de audit grava
2) Cálculo dinâmico: motor × faixa Painéis (linhas H/V) × nota de atenção
3) Fallback: extent Painéis / motor / polilinha fechada

Nunca: bbox de todo o crop (invadia viga/pilar).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")


def bb_size(pts: list) -> tuple[float, float]:
    xs = [float(p[0]) for p in pts]
    ys = [float(p[1]) for p in pts]
    return max(xs) - min(xs), max(ys) - min(ys)


def bb_box(pts: list) -> tuple[float, float, float, float]:
    xs = [float(p[0]) for p in pts]
    ys = [float(p[1]) for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def close_ring(pts: list) -> list:
    if not pts:
        return []
    out = [(float(p[0]), float(p[1])) for p in pts]
    if out[0] != out[-1]:
        out = out + [out[0]]
    return out


def open_ring(pts: list) -> list:
    if not pts:
        return []
    out = [(float(p[0]), float(p[1])) for p in pts]
    if len(out) > 1 and out[0] == out[-1]:
        out = out[:-1]
    return out


def rect_from_box(x0, y0, x1, y1) -> list:
    return close_ring([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def iou_aabb(a: list, b: list) -> float:
    if not a or not b or len(a) < 2 or len(b) < 2:
        return 0.0
    ax0, ay0, ax1, ay1 = bb_box(a)
    bx0, by0, bx1, by1 = bb_box(b)
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    aa = (ax1 - ax0) * (ay1 - ay0)
    ba = (bx1 - bx0) * (by1 - by0)
    union = aa + ba - inter
    return inter / union if union > 0 else 0.0


def coverage_a_in_b(a: list, b: list) -> float:
    if not a or not b:
        return 0.0
    ax0, ay0, ax1, ay1 = bb_box(a)
    bx0, by0, bx1, by1 = bb_box(b)
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    aa = max((ax1 - ax0) * (ay1 - ay0), 1e-9)
    return inter / aa


def n4_outline_world_from_ficha(ficha: dict | None) -> list:
    """Polígono mundo **idêntico** ao contorno que `gerar_lj_dxf_stog` usa no N4.

    Espelha a lógica de base position em gerar_lj_dxf_stog (coords + _stog_pose
    se origem local ≈ 0). Vermelho N2 e área N4 devem ser equivalentes.
    """
    if not isinstance(ficha, dict):
        return []
    coords = ficha.get("coordenadas") or []
    pose = ficha.get("_stog_pose") or {}
    ox = float(pose.get("x", 0) or 0) if pose else 0.0
    oy = float(pose.get("y", 0) or 0) if pose else 0.0

    if len(coords) >= 3:
        xs = [float(c[0]) for c in coords]
        ys = [float(c[1]) for c in coords]
        raw_x0, raw_y0 = min(xs), min(ys)
        # Mesma regra do gerador: pose só se coords estão em espaço local
        if pose and abs(raw_x0) <= 0.5 and abs(raw_y0) <= 0.5:
            off_x, off_y = ox, oy
        else:
            off_x = off_y = 0.0
        return close_ring([(x + off_x, y + off_y) for x, y in zip(xs, ys)])

    # Fallback retângulo comprimento×largura na pose (N4 também usa comp/larg)
    try:
        w = float(ficha.get("comprimento") or 0)
        h = float(ficha.get("largura") or 0)
    except (TypeError, ValueError):
        return []
    if w <= 0 or h <= 0:
        return []
    return rect_from_box(ox, oy, ox + w, oy + h)


def load_ficha_db(
    obra: str, item_id: str, pavimento: str = ""
) -> dict | None:
    """Ficha persistida por obra+item (+ pavimento se informado).

    Filtra pavimento para não cruzar 13_PAV com 14_PAV no mesmo elemento_id.
    """
    try:
        from src.core.n2_anchor import pav_key_to_db_pav
    except Exception:
        pav_key_to_db_pav = None  # type: ignore

    db_pav = ""
    if pavimento and pav_key_to_db_pav:
        try:
            db_pav = pav_key_to_db_pav(pavimento) or ""
        except Exception:
            db_pav = str(pavimento or "").strip()

    try:
        with sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True) as conn:
            rows = conn.execute(
                """
                SELECT obra_name, pavimento, campos_json FROM reverse_eng_fichas
                WHERE UPPER(elemento_id)=?
                ORDER BY updated_at DESC LIMIT 24
                """,
                (str(item_id).upper(),),
            ).fetchall()
        obra_n = (obra or "").strip().lower()
        pav_n = (db_pav or "").strip().upper()

        def _rank(r):
            on = (r[0] or "").strip().lower()
            pv = (r[1] or "").strip().upper()
            obra_ok = 0 if on == obra_n else (1 if obra_n and obra_n in on else 2)
            if pav_n:
                # 13_PAV vs 14_PAV; aceita match parcial "13" em pav tecnico
                pav_ok = 0 if pv == pav_n or pav_n in pv or pv in pav_n else 1
                if pav_n.replace("_", "") in pv.replace("_", ""):
                    pav_ok = min(pav_ok, 0)
            else:
                pav_ok = 0
            return (obra_ok, pav_ok)

        ordered = sorted(rows, key=_rank)
        for on, pv, campos_json in ordered:
            if obra_n and (on or "").strip().lower() != obra_n and obra_n not in (on or "").lower():
                continue
            if pav_n:
                pv_u = (pv or "").upper()
                if (
                    pv_u != pav_n
                    and pav_n not in pv_u
                    and pv_u not in pav_n
                    and pav_n.replace("_", "") not in pv_u.replace("_", "")
                ):
                    continue
            d = json.loads(campos_json or "{}")
            if isinstance(d, dict) and (
                d.get("coordenadas") or d.get("comprimento")
            ):
                return d
    except Exception:
        return None
    return None


def extract_ficha_live(
    dxf_path: Path | str, item_id: str, obra: str
) -> dict:
    """Motor reverso LAJ no recorte N2 atual (fonte dinâmica)."""
    try:
        from motor_reverso_laj import extrair_ficha_laje
    except ImportError:
        import sys

        scripts = Path(__file__).resolve().parents[2] / "scripts"
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        from motor_reverso_laj import extrair_ficha_laje

    ficha = extrair_ficha_laje(str(dxf_path), item_id, obra)
    return ficha if isinstance(ficha, dict) else {}


def motor_poly_from_recorte(
    dxf_path: Path | str,
    item_id: str,
    obra: str,
    *,
    pavimento: str = "",
    prefer_live: bool = True,
) -> tuple[list, dict]:
    """Contorno motor ≡ N4.

    prefer_live=True (default): extrai do recorte N2 atual — mesmo comportamento
    estável do 13_PAV (motor dinâmico). Fallback: ficha DB do pavimento.
    """
    path = Path(dxf_path) if dxf_path else None
    if prefer_live and path and path.exists():
        ficha = extract_ficha_live(path, item_id, obra)
        poly = n4_outline_world_from_ficha(ficha)
        if len(poly) >= 3:
            return poly, ficha

    ficha = load_ficha_db(obra, item_id, pavimento=pavimento)
    if ficha:
        poly = n4_outline_world_from_ficha(ficha)
        if len(poly) >= 3:
            return poly, ficha

    if path and path.exists() and not prefer_live:
        ficha = extract_ficha_live(path, item_id, obra)
        return n4_outline_world_from_ficha(ficha), ficha
    return [], {}


def paineis_band_poly(dxf_path: Path | str) -> list:
    """Envelope da laje pela grade Painéis (ignora cotas/setas do bbox total).

    Regra geométrica (inegociável):
    - **X** = extensão das linhas **horizontais** (guias H)
    - **Y** = extensão das linhas **verticais** (guias V)

    Usar Y das linhas H colapsa a faixa nas divisões internas (L409 virava
    20 cm). X das linhas V sozinhas também falha em lajes longas.
    """
    import ezdxf

    path = Path(dxf_path)
    if not path.exists():
        return []
    doc = ezdxf.readfile(str(path))
    h_xspan: list[tuple[float, float]] = []
    v_yspan: list[tuple[float, float]] = []
    for ent in doc.modelspace():
        try:
            ly = str(getattr(ent.dxf, "layer", "") or "").upper()
            if "PAIN" not in ly:
                continue
            if ent.dxftype() != "LINE":
                continue
            x1, y1 = float(ent.dxf.start.x), float(ent.dxf.start.y)
            x2, y2 = float(ent.dxf.end.x), float(ent.dxf.end.y)
            dx, dy = abs(x2 - x1), abs(y2 - y1)
            length = (dx * dx + dy * dy) ** 0.5
            if length < 15.0:
                continue
            if dy <= 1.5 and dx >= 20.0:
                h_xspan.append((min(x1, x2), max(x1, x2)))
            elif dx <= 1.5 and dy >= 15.0:
                v_yspan.append((min(y1, y2), max(y1, y2)))
        except Exception:
            continue

    if h_xspan and v_yspan:
        # Preferir guias longas (contorno/grade), não cotas curtas
        long_h = [s for s in h_xspan if (s[1] - s[0]) >= 40.0]
        long_v = [s for s in v_yspan if (s[1] - s[0]) >= 25.0]
        use_h = long_h or h_xspan
        use_v = long_v or v_yspan
        x0 = min(s[0] for s in use_h)
        x1 = max(s[1] for s in use_h)
        y0 = min(s[0] for s in use_v)
        y1 = max(s[1] for s in use_v)
        if x1 > x0 + 20 and y1 > y0 + 8:
            return rect_from_box(x0, y0, x1, y1)

    # fallback: todos os pontos Painéis com percentil
    return paineis_extent_poly(dxf_path, robust=True)


def paineis_extent_poly(dxf_path: Path | str, robust: bool = False) -> list:
    import ezdxf

    path = Path(dxf_path)
    if not path.exists():
        return []
    doc = ezdxf.readfile(str(path))
    xs: list[float] = []
    ys: list[float] = []
    for ent in doc.modelspace():
        try:
            ly = str(getattr(ent.dxf, "layer", "") or "").upper()
            if "PAIN" not in ly:
                continue
            t = ent.dxftype()
            if t == "LWPOLYLINE":
                for x, y, *_ in ent.get_points("xy"):
                    xs.append(float(x))
                    ys.append(float(y))
            elif t == "LINE":
                xs.extend([float(ent.dxf.start.x), float(ent.dxf.end.x)])
                ys.extend([float(ent.dxf.start.y), float(ent.dxf.end.y)])
        except Exception:
            continue
    if len(xs) < 4:
        return []
    if robust and len(xs) >= 20:
        xs_s, ys_s = sorted(xs), sorted(ys)
        def pct(vals, p):
            i = int(round((len(vals) - 1) * p))
            return vals[max(0, min(len(vals) - 1, i))]
        x0, x1 = pct(xs_s, 0.05), pct(xs_s, 0.95)
        y0, y1 = pct(ys_s, 0.05), pct(ys_s, 0.95)
    else:
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    if (x1 - x0) < 20.0 or (y1 - y0) < 10.0:
        return []
    return rect_from_box(x0, y0, x1, y1)


def pillar_boxes(dxf_path: Path | str) -> list[tuple[float, float, float, float]]:
    """AABBs de pilares (layer 7) no recorte.

    No DXF de recorte LAJ, pilares costumam vir como arestas soltas (LINE /
    LWPOLYLINE de 2 pts) na layer 7 — não como um único polígono fechado.
    Agrupa segmentos próximos em caixas compactas.
    """
    import ezdxf

    path = Path(dxf_path)
    if not path.exists():
        return []
    doc = ezdxf.readfile(str(path))
    segs: list[tuple[float, float, float, float]] = []
    closed: list[tuple[float, float, float, float]] = []
    for ent in doc.modelspace():
        try:
            ly = str(getattr(ent.dxf, "layer", "") or "").strip()
            if ly != "7":
                continue
            t = ent.dxftype()
            if t == "LINE":
                x1, y1 = float(ent.dxf.start.x), float(ent.dxf.start.y)
                x2, y2 = float(ent.dxf.end.x), float(ent.dxf.end.y)
                segs.append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
            elif t == "LWPOLYLINE":
                pts = [(float(x), float(y)) for x, y, *_ in ent.get_points("xy")]
                if len(pts) < 2:
                    continue
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                bb = (min(xs), min(ys), max(xs), max(ys))
                w, h = bb[2] - bb[0], bb[3] - bb[1]
                closed_poly = bool(getattr(ent, "closed", False)) or (
                    len(pts) >= 3 and abs(pts[0][0] - pts[-1][0]) < 0.5
                    and abs(pts[0][1] - pts[-1][1]) < 0.5
                )
                if closed_poly and w >= 5 and h >= 5 and not (w > 400 and h > 400):
                    closed.append(bb)
                else:
                    # arestas soltas → cluster depois
                    for a, b in zip(pts, pts[1:]):
                        segs.append(
                            (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
                        )
        except Exception:
            continue

    boxes = list(closed)
    if not segs:
        return boxes

    # Cluster por proximidade (gap tipico entre pilares >> 40cm)
    used = [False] * len(segs)
    gap = 40.0
    for i, s in enumerate(segs):
        if used[i]:
            continue
        x0, y0, x1, y1 = s
        used[i] = True
        changed = True
        while changed:
            changed = False
            for j, t in enumerate(segs):
                if used[j]:
                    continue
                # expand se toca ou quase toca o cluster
                if t[2] < x0 - gap or t[0] > x1 + gap or t[3] < y0 - gap or t[1] > y1 + gap:
                    continue
                x0, y0 = min(x0, t[0]), min(y0, t[1])
                x1, y1 = max(x1, t[2]), max(y1, t[3])
                used[j] = True
                changed = True
        w, h = x1 - x0, y1 - y0
        if w < 4 and h < 4:
            continue
        # pilares compactos (ou faixas estreitas de borda)
        if w > 450 and h > 450:
            continue
        if w * h > 120_000:  # laje inteira disfarçada
            continue
        boxes.append((x0, y0, x1, y1))
    return boxes


def shrink_rect_away_from_pillars(
    red: list, pillars: list[tuple[float, float, float, float]], note: str = ""
) -> tuple[list, str]:
    """Aperta o retângulo vermelho para não engolir pilares de borda.

    Em lajes-faixa (altura pequena) os pilares atravessam quase toda a altura —
    só recorta X. Em lajes altas, recorta o eixo em que o pilar está na borda.
    """
    if not red or not pillars:
        return red, "no_pillar_clip"
    note_l = (note or "").lower()
    # Clip quando nota fala invasão/pilar/viga/área n2 — motor também clipe no extract
    if not any(
        k in note_l
        for k in ("pilar", "pilares", "invad", "viga", "vigas", "area n2")
    ):
        return red, "no_note_pillar"
    x0, y0, x1, y1 = bb_box(red)
    rw, rh = x1 - x0, y1 - y0
    if rw < 30 or rh < 12:
        return red, "red_too_small"

    strip_like = rh <= 120.0 or (rw / max(rh, 1.0) >= 4.0)
    changed = False
    for px0, py0, px1, py1 in pillars:
        pw, ph = px1 - px0, py1 - py0
        ox0, oy0 = max(x0, px0), max(y0, py0)
        ox1, oy1 = min(x1, px1), min(y1, py1)
        if ox1 <= ox0 or oy1 <= oy0:
            continue
        inter = (ox1 - ox0) * (oy1 - oy0)
        if inter < 40.0:
            continue
        cx = (px0 + px1) / 2.0
        cy = (py0 + py1) / 2.0
        band_x = max(25.0, min(90.0, max(pw * 1.3, rw * 0.12)))
        band_y = max(15.0, min(70.0, max(ph * 1.2, rh * 0.12)))

        touches_left = ox0 <= x0 + 2.0 or (cx <= x0 + band_x and px0 <= x0 + band_x)
        touches_right = ox1 >= x1 - 2.0 or (cx >= x1 - band_x and px1 >= x1 - band_x)
        if touches_left and px1 < x1 - 30.0 and (px1 - x0) < rw * 0.40:
            x0 = max(x0, px1 + 1.0)
            changed = True
        elif touches_right and px0 > x0 + 30.0 and (x1 - px0) < rw * 0.40:
            x1 = min(x1, px0 - 1.0)
            changed = True

        if strip_like:
            continue
        touches_bottom = oy0 <= y0 + 2.0 or (cy <= y0 + band_y and py0 <= y0 + band_y)
        touches_top = oy1 >= y1 - 2.0 or (cy >= y1 - band_y and py1 >= y1 - band_y)
        if touches_bottom and py1 < y1 - 15.0 and (py1 - y0) < rh * 0.40:
            y0 = max(y0, py1 + 1.0)
            changed = True
        elif touches_top and py0 > y0 + 15.0 and (y1 - py0) < rh * 0.40:
            y1 = min(y1, py0 - 1.0)
            changed = True

    if not changed or x1 <= x0 + 10 or y1 <= y0 + 8:
        return red, "pillar_clip_noop"
    return rect_from_box(x0, y0, x1, y1), "pillar_edge_clip"


def shrink_rect_away_from_beams(
    red: list, motor: list, paineis: list, note: str = ""
) -> tuple[list, str]:
    """Quando a nota acusa invasão, aperta o vermelho para a interseção com
    a faixa Painéis — NUNCA expande para o bbox Painéis inteiro (engole pilar)."""
    if not red:
        return red, "no_beam_clip"
    note_l = (note or "").lower()
    invade = any(k in note_l for k in ("invad", "viga", "vigas", "area n2 errada"))
    if not invade:
        return red, "no_note_beam"
    if not paineis or len(paineis) < 3:
        return red, "no_paineis_beam"
    # interseção com painéis (e motor se existir) — só encolhe, nunca amplia
    base = intersect_aabb(red, paineis)
    if motor and len(motor) >= 3:
        base2 = intersect_aabb(base if base else red, motor)
        if base2 and len(base2) >= 3:
            bw, bh = bb_size(base2)
            if bw > 25 and bh > 8:
                base = base2
    if not base or len(base) < 3:
        return red, "beam_clip_noop"
    bw, bh = bb_size(base)
    if bw < 25 or bh < 8:
        return red, "beam_clip_noop"
    return base, "beam_clip_intersect"


def intersect_aabb(a: list, b: list) -> list:
    if not a or not b:
        return a or b or []
    ax0, ay0, ax1, ay1 = bb_box(a)
    bx0, by0, bx1, by1 = bb_box(b)
    x0, y0 = max(ax0, bx0), max(ay0, by0)
    x1, y1 = min(ax1, bx1), min(ay1, by1)
    if x1 <= x0 + 5 or y1 <= y0 + 5:
        return a
    return rect_from_box(x0, y0, x1, y1)


def pick_highlight(
    motor_pts: list,
    paineis_pts: list,
    note: str = "",
    *,
    strategy: str = "auto",
    pillars: list | None = None,
) -> tuple[list, str]:
    note_l = (note or "").lower()
    invade = any(k in note_l for k in ("invad", "viga", "pilar", "pilares", "vigas"))
    faltou = any(k in note_l for k in ("faltou", "falta", "topo", "pedaco", "pedaço"))

    if strategy == "motor" and motor_pts:
        red, tag = motor_pts, "force_motor"
    elif strategy == "paineis" and paineis_pts:
        red, tag = paineis_pts, "force_paineis"
    elif strategy == "intersect" and motor_pts and paineis_pts:
        red, tag = intersect_aabb(motor_pts, paineis_pts), "force_intersect"
    elif strategy == "tighter" and motor_pts and paineis_pts:
        mw, mh = bb_size(motor_pts)
        pw, ph = bb_size(paineis_pts)
        red, tag = (
            (motor_pts, "force_tighter_motor")
            if mw * mh <= pw * ph
            else (paineis_pts, "force_tighter_paineis")
        )
    elif strategy == "larger" and motor_pts and paineis_pts:
        mw, mh = bb_size(motor_pts)
        pw, ph = bb_size(paineis_pts)
        red, tag = (
            (paineis_pts, "force_larger_paineis")
            if pw * ph >= mw * mh
            else (motor_pts, "force_larger_motor")
        )
    else:
        # auto
        if not motor_pts and not paineis_pts:
            return [], "none"
        if motor_pts and not paineis_pts:
            red, tag = motor_pts, "motor_only"
        elif paineis_pts and not motor_pts:
            red, tag = paineis_pts, "paineis_only"
        else:
            mw, mh = bb_size(motor_pts)
            pw, ph = bb_size(paineis_pts)
            n_open = len(motor_pts) - (1 if motor_pts and motor_pts[0] == motor_pts[-1] else 0)

            if faltou:
                if (pw > mw * 1.03 or ph > mh * 1.03) and pw < mw * 1.40 and ph < mh * 1.40:
                    red, tag = paineis_pts, "faltou_paineis"
                else:
                    red, tag = motor_pts, "faltou_motor"
            elif invade:
                # Motor já deve vir da grade Painéis (fix structural layer).
                # Só aperta se a grade H/V for menor; NUNCA expande para painéis
                # mais largos (L422 engolia pilar à esquerda).
                inter = intersect_aabb(motor_pts, paineis_pts)
                iw, ih = bb_size(inter) if inter else (0.0, 0.0)
                if mw > pw * 1.03 or mh > ph * 1.03:
                    if iw > 30 and ih > 12:
                        red, tag = inter, "invade_intersect"
                    else:
                        red, tag = paineis_pts, "invade_paineis"
                elif iw > 30 and ih > 12 and (iw < mw * 0.98 or ih < mh * 0.98):
                    red, tag = inter, "invade_intersect"
                else:
                    # motor já justo — mantém (clip de pilar abaixo)
                    red, tag = motor_pts, "invade_motor"
            elif n_open >= 6:
                red, tag = motor_pts, "motor_complex"
            elif mw > pw * 1.08 or mh > ph * 1.08:
                red, tag = paineis_pts, "motor_inflated"
            elif pw > mw * 1.25 or ph > mh * 1.25:
                red, tag = motor_pts, "paineis_bloated"
            elif pw > mw * 1.05 or ph > mh * 1.05:
                red, tag = paineis_pts, "paineis_complete"
            else:
                red, tag = motor_pts, "motor_default"

    if red:
        red_b, beam_tag = shrink_rect_away_from_beams(red, motor_pts, paineis_pts, note)
        if beam_tag == "beam_clip_paineis" and red_b and len(red_b) >= 3:
            # só aplica se realmente apertou (mudança visível)
            if bb_size(red_b)[0] * bb_size(red_b)[1] < bb_size(red)[0] * bb_size(red)[1] * 0.98:
                red, tag = red_b, f"{tag}+{beam_tag}"
            elif red_b is not red:
                # mesmo assim, se reason invade e painéis disponível, força painéis
                note_l2 = (note or "").lower()
                if any(k in note_l2 for k in ("invad", "viga", "pilar")) and paineis_pts:
                    red, tag = red_b, f"{tag}+{beam_tag}"
    if pillars and red:
        red2, clip_tag = shrink_rect_away_from_pillars(red, pillars, note)
        if clip_tag == "pillar_edge_clip":
            return red2, f"{tag}+{clip_tag}"
    return red, tag


def load_highlight_override(obra: str, item_id: str) -> list | None:
    """Lê polígono mundo gravado pelo loop de audit."""
    try:
        with sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True) as conn:
            rows = conn.execute(
                """
                SELECT obra_name, campos_json FROM reverse_eng_fichas
                WHERE UPPER(elemento_id)=?
                ORDER BY updated_at DESC LIMIT 8
                """,
                (str(item_id).upper(),),
            ).fetchall()
        obra_n = (obra or "").strip().lower()
        ordered = sorted(
            rows,
            key=lambda r: (
                0
                if (r[0] or "").strip().lower() == obra_n
                else 1
                if obra_n and obra_n in (r[0] or "").lower()
                else 2
            ),
        )
        for _obra_name, campos_json in ordered:
            er = (json.loads(campos_json or "{}").get("_er_meta") or {})
            pts = er.get("n2_highlight_world")
            # aceita lista de pontos OU dict {points:[...]}
            if isinstance(pts, dict):
                pts = pts.get("points") or pts.get("poly") or []
            if isinstance(pts, list) and len(pts) >= 3:
                try:
                    return [(float(p[0]), float(p[1])) for p in pts]
                except Exception:
                    continue
    except Exception:
        return None
    return None


def save_highlight_override(
    obra: str,
    item_id: str,
    world_pts: list,
    *,
    reason: str,
    strategy: str,
    note: str = "",
) -> bool:
    """Persiste polígono do marco — o CE lê isto primeiro (mudança garantida na UI)."""
    now = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).isoformat(timespec="seconds")
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            row = conn.execute(
                """
                SELECT id, campos_json FROM reverse_eng_fichas
                WHERE obra_name=? AND UPPER(elemento_id)=?
                ORDER BY updated_at DESC LIMIT 1
                """,
                (obra, str(item_id).upper()),
            ).fetchone()
            if not row:
                return False
            campos = json.loads(row[1] or "{}")
            er = dict(campos.get("_er_meta") or {})
            er["n2_highlight_world"] = [
                [round(float(p[0]), 3), round(float(p[1]), 3)] for p in open_ring(world_pts)
            ]
            er["n2_marco_strategy"] = strategy
            er["n2_marco_reason"] = reason
            er["n2_marco_note"] = (note or "")[:200]
            er["n2_marco_loop_at"] = now
            campos["_er_meta"] = er
            conn.execute(
                "UPDATE reverse_eng_fichas SET campos_json=?, updated_at=? WHERE id=?",
                (json.dumps(campos, ensure_ascii=False), now, row[0]),
            )
            conn.commit()
        return True
    except Exception:
        return False


def resolve_highlight(
    dxf_path: Path | str,
    item_id: str,
    obra: str,
    note: str = "",
    *,
    strategy: str = "auto",
    use_override: bool = False,
    pavimento: str = "",
    prefer_live: bool = True,
) -> dict:
    """Marco vermelho.

    **auto (default / CE):** vermelho ≡ contorno N4 = motor live no recorte
    (comportamento do 13_PAV). `use_override` default False — overrides
    experimentais não devem desviar o contorno do gerador.

    Strategies experimentais (`intersect`, `paineis`, …) só para audit.
    """
    path = Path(dxf_path) if dxf_path else Path()
    motor, ficha = motor_poly_from_recorte(
        path,
        item_id,
        obra,
        pavimento=pavimento,
        prefer_live=prefer_live,
    )
    paineis = paineis_band_poly(path) if path.exists() else []
    pillars = pillar_boxes(path) if path.exists() else []

    if strategy in ("auto", "n4", "n4_equiv", "motor", "override", ""):
        if use_override and motor and len(motor) >= 3:
            ov = load_highlight_override(obra, item_id)
            if ov and len(ov) >= 3 and iou_aabb(ov, motor) >= 0.97:
                return {
                    "red": close_ring(ov),
                    "reason": "n4_equiv_override",
                    "motor": motor,
                    "paineis": paineis,
                    "ficha": ficha,
                    "strategy": "n4_equiv",
                    "pillars": pillars,
                }
        red = motor if motor and len(motor) >= 3 else []
        reason = "n4_equiv_live" if red else "none"
        if not red and paineis:
            red, reason = paineis, "n4_equiv_paineis_fallback"
        return {
            "red": red,
            "reason": reason,
            "motor": motor,
            "paineis": paineis,
            "ficha": ficha,
            "strategy": "n4_equiv",
            "pillars": pillars,
        }

    red, reason = pick_highlight(
        motor, paineis, note, strategy=strategy, pillars=pillars
    )
    if len(red) < 3:
        red = paineis_extent_poly(path, robust=True) if path.exists() else []
        reason = "extent_fallback" if red else "none"
    return {
        "red": red,
        "reason": reason,
        "motor": motor,
        "paineis": paineis,
        "ficha": ficha,
        "strategy": strategy,
        "pillars": pillars,
    }


def score_item(note: str, red: list, motor: list, paineis: list, pillars: list | None = None) -> dict:
    note_l = (note or "").lower()
    invade = any(k in note_l for k in ("invad", "viga", "pilar", "pilares", "vigas"))
    faltou = any(k in note_l for k in ("faltou", "falta", "topo", "pedaco", "pedaço"))
    fails: list[str] = []
    if not red or len(red) < 3:
        return {"pass": False, "fails": ["sem_contorno_vermelho"], "metrics": {}}

    rw, rh = bb_size(red)
    mw, mh = bb_size(motor) if motor else (0.0, 0.0)
    pw, ph = bb_size(paineis) if paineis else (0.0, 0.0)
    iou_m = iou_aabb(red, motor) if motor else 0.0
    iou_p = iou_aabb(red, paineis) if paineis else 0.0
    cov_p_in_red = coverage_a_in_b(paineis, red) if paineis else 0.0

    # Gate duro: vermelho não pode cobrir a maior parte de um pilar de borda
    if pillars and invade:
        rx0, ry0, rx1, ry1 = bb_box(red)
        for px0, py0, px1, py1 in pillars:
            ox0, oy0 = max(rx0, px0), max(ry0, py0)
            ox1, oy1 = min(rx1, px1), min(ry1, py1)
            if ox1 <= ox0 or oy1 <= oy0:
                continue
            inter = (ox1 - ox0) * (oy1 - oy0)
            p_area = max((px1 - px0) * (py1 - py0), 1e-9)
            # pilar quase todo dentro do red e compacto → invasão visual
            if inter / p_area > 0.85 and (px1 - px0) < rw * 0.4:
                # se o pilar está na borda (não no miolo), falha
                cx = (px0 + px1) / 2
                if abs(cx - rx0) < rw * 0.2 or abs(cx - rx1) < rw * 0.2:
                    fails.append("pilar_borda_dentro_do_vermelho")
                    break

    if invade:
        if paineis and (rw > pw * 1.08 or rh > ph * 1.08):
            fails.append("invade_red_maior_paineis")
        if motor and paineis and max(iou_m, iou_p) < 0.55:
            fails.append("invade_iou_baixo")
        # Gate de mudança real: se o vermelho ≈ motor, o usuário não vê ajuste
        if motor and mw > 0 and mh > 0:
            area_ratio = (rw * rh) / max(mw * mh, 1e-9)
            if iou_m >= 0.92 and area_ratio >= 0.92:
                fails.append("invade_sem_mudanca_vs_motor")
            # altura/largura ainda inchadas vs painéis
            if paineis and ph > 0 and rh > ph * 1.12:
                fails.append("invade_altura_ainda_inflada")
            if paineis and pw > 0 and rw > pw * 1.12:
                fails.append("invade_largura_ainda_inflada")

    if faltou:
        if paineis and cov_p_in_red < 0.90:
            fails.append(f"faltou_cobertura({cov_p_in_red:.2f})")
        if paineis and (rw < pw * 0.92 or rh < ph * 0.92):
            fails.append("faltou_red_menor_paineis")

    if not invade and not faltou and max(iou_m, iou_p) < 0.80:
        fails.append("iou_generico_baixo")

    return {
        "pass": len(fails) == 0,
        "fails": fails,
        "metrics": {
            "red_wh": [round(rw, 1), round(rh, 1)],
            "motor_wh": [round(mw, 1), round(mh, 1)],
            "paineis_wh": [round(pw, 1), round(ph, 1)],
            "iou_motor": round(iou_m, 3),
            "iou_paineis": round(iou_p, 3),
            "cov_paineis_in_red": round(cov_p_in_red, 3),
        },
    }


LOOP_STRATEGIES: tuple[str, ...] = (
    "auto",
    "intersect",
    "tighter",
    "paineis",
    "motor",
    "larger",
)


def best_strategy_for_item(
    dxf_path: Path | str, item_id: str, obra: str, note: str
) -> dict:
    best = None
    for strat in LOOP_STRATEGIES:
        res = resolve_highlight(
            dxf_path, item_id, obra, note, strategy=strat, use_override=False
        )
        sc = score_item(
            note, res["red"], res["motor"], res["paineis"], res.get("pillars")
        )
        entry = {**res, "score": sc, "strategy": strat}
        if sc["pass"]:
            return entry
        soft = max(
            sc["metrics"].get("iou_motor", 0),
            sc["metrics"].get("iou_paineis", 0),
            sc["metrics"].get("cov_paineis_in_red", 0),
        )
        # penaliza se ainda invade pilar
        if "pilar_borda_dentro_do_vermelho" in sc["fails"]:
            soft -= 0.3
        entry["soft"] = soft
        if best is None or soft > best.get("soft", -9):
            best = entry
    return best or {
        "red": [],
        "reason": "none",
        "score": {"pass": False, "fails": ["no_strategy"], "metrics": {}},
        "strategy": "auto",
    }
