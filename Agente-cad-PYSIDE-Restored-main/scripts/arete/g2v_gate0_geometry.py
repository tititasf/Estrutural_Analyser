# -*- coding: utf-8 -*-
"""
g2v_gate0_geometry.py — Portão 0 geométrico (FAIL-closed) para G2-V.

Antes de qualquer veredito visual de agente:
  - extrai segmentos LINE de camadas estruturais (Painéis / SARR*)
  - compara N2 (recorte) × N4 (gerado) com tolerância
  - FAIL se only_n4 (lixo do gerador) ou only_n2 estrutural

Não substitui vision: se gate0 FAIL, vision só explica; PASS visual com
gate0 FAIL é inválido (validar_veredito_cli).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import ezdxf

# Camadas estruturais — contorno e sarrafo. Cotas/texto ficam para vision.
STRUCT_PREFIXES = ("Painéis", "Paineis", "SARR")
DEFAULT_TOL_CM = 1.5
# Lixo típico de recorte N2 sob o vão do degrau (não exige espelho no N4)
JUNK_Y_MAX = -1.0


def _is_struct_layer(layer: str) -> bool:
    layer = str(layer or "")
    return any(layer == p or layer.startswith(p) for p in STRUCT_PREFIXES)


def _norm_layer(layer: str) -> str:
    s = str(layer or "")
    if s.startswith("SARR"):
        return "SARR"
    if "Pain" in s or s in {"Painéis", "Paineis"}:
        return "Painéis"
    return s


def extract_line_segments(
    dxf_path: Path,
    *,
    origin: tuple[float, float] = (0.0, 0.0),
    clip: tuple[float, float, float, float] | None = None,
) -> set[tuple]:
    """Segmentos normalizados (layer, x1, y1, x2, y2) relativos a origin."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    ox, oy = origin
    out: set[tuple] = set()
    for e in msp:
        if e.dxftype() != "LINE":
            continue
        if not _is_struct_layer(e.dxf.layer):
            continue
        a, b = e.dxf.start, e.dxf.end
        x1, y1 = a.x - ox, a.y - oy
        x2, y2 = b.x - ox, b.y - oy
        if clip is not None:
            xl, yb, xr, yt = clip
            def _ok(x, y):
                return xl - 2 <= x <= xr + 2 and yb - 5 <= y <= yt + 5
            if not (_ok(x1, y1) or _ok(x2, y2)):
                continue
        # Normalizar endpoints (sempre ponto "menor" primeiro) — evita falso
        # n2_only/n4_only só por sentido da LINE.
        (x1, y1), (x2, y2) = sorted([(x1, y1), (x2, y2)])
        out.add(
            (
                _norm_layer(e.dxf.layer),
                round(x1, 1),
                round(y1, 1),
                round(x2, 1),
                round(y2, 1),
            )
        )
    return out


def _fuzzy_in(seg: tuple, pool: Iterable[tuple], tol: float) -> bool:
    L, x1, y1, x2, y2 = seg
    for p in pool:
        if p[0] != L:
            continue
        if (
            abs(p[1] - x1) <= tol
            and abs(p[2] - y1) <= tol
            and abs(p[3] - x2) <= tol
            and abs(p[4] - y2) <= tol
        ):
            return True
    return False


def _is_junk_n2(seg: tuple) -> bool:
    """Artefato sob o piso da face (vão do degrau no recorte)."""
    _, x1, y1, x2, y2 = seg
    return max(y1, y2) < JUNK_Y_MAX


def compare_segments(
    n2_segs: set[tuple],
    n4_segs: set[tuple],
    *,
    tol_cm: float = DEFAULT_TOL_CM,
) -> dict:
    only_n2 = sorted(s for s in n2_segs if not _fuzzy_in(s, n4_segs, tol_cm))
    only_n4 = sorted(s for s in n4_segs if not _fuzzy_in(s, n2_segs, tol_cm))
    only_n2_struct = [s for s in only_n2 if not _is_junk_n2(s)]
    only_n4_struct = list(only_n4)  # qualquer extra no N4 é lixo do gerador

    status = "PASS"
    reasons: list[str] = []
    if only_n4_struct:
        status = "FAIL"
        reasons.append(f"n4_a_mais: {len(only_n4_struct)} segmento(s) só no N4")
    if only_n2_struct:
        status = "FAIL"
        reasons.append(f"n4_a_menos: {len(only_n2_struct)} segmento(s) estrutural só no N2")

    return {
        "schema": "arete.g2v_gate0_geometry/v1",
        "status": status,
        "tol_cm": tol_cm,
        "counts": {
            "n2": len(n2_segs),
            "n4": len(n4_segs),
            "only_n2": len(only_n2),
            "only_n4": len(only_n4),
            "only_n2_struct": len(only_n2_struct),
            "only_n4_struct": len(only_n4_struct),
            "only_n2_junk": len(only_n2) - len(only_n2_struct),
        },
        "only_n2_struct": only_n2_struct[:80],
        "only_n4_struct": only_n4_struct[:80],
        "reasons": reasons,
        "pass_allowed": status == "PASS",
    }


def gate0_n2_n4_files(
    n2_path: Path,
    n4_path: Path,
    *,
    n2_origin: tuple[float, float] = (0.0, 0.0),
    n4_origin: tuple[float, float] = (0.0, 0.0),
    clip: tuple[float, float, float, float] | None = None,
    tol_cm: float = DEFAULT_TOL_CM,
) -> dict:
    n2 = extract_line_segments(n2_path, origin=n2_origin, clip=clip)
    n4 = extract_line_segments(n4_path, origin=n4_origin, clip=clip)
    result = compare_segments(n2, n4, tol_cm=tol_cm)
    result["n2_path"] = str(n2_path)
    result["n4_path"] = str(n4_path)
    result["n2_origin"] = list(n2_origin)
    result["n4_origin"] = list(n4_origin)
    result["clip"] = list(clip) if clip else None
    return result


def write_gate0_report(result: dict, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path
