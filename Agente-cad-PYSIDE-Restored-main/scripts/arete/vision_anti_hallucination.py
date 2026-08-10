# -*- coding: utf-8 -*-
"""Camada de VISÃO anti-alucinação N2×N4.

Problema: GeometryIndex pode dar R/G=100% com miss=0/extra=0 enquanto o olho
humano vê paredes/cotas inventadas (phantom degrau 65, marco, overdraw).

Esta camada:
1. Render full-layers DXF → PNG (modo agente)
2. Diff pixel: tinta N4 sem vizinho em N2 → EXTRA visual
3. Diff estrutural estrito + phantoms (V65@244, marco mid)
4. **VETA Arete 100%** se houver EXTRA visual ou phantom

Uso:
  from arete.vision_anti_hallucination import vision_gate_unit
  rep = vision_gate_unit(n2_path, n4_path, a2, a4, label='V301.A', out_dir=...)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

# ── render ─────────────────────────────────────────────────────────────

def render_dxf_png(
    dxf_path: Path,
    out_png: Path,
    *,
    clip: tuple[float, float, float, float] | None,
    title: str = "",
    width_px: int = 900,
    height_px: int = 480,
    dpi: int = 140,
) -> bool:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import ezdxf
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        fig = plt.figure(figsize=(width_px / dpi, height_px / dpi), dpi=dpi)
        ax = fig.add_axes([0.01, 0.02, 0.98, 0.92])
        ax.set_facecolor("#0a0a12")
        ctx = RenderContext(doc)
        Frontend(ctx, MatplotlibBackend(ax)).draw_layout(msp, finalize=True)
        if clip is not None:
            xmin, ymin, xmax, ymax = clip
            dx = max(4.0, (xmax - xmin) * 0.02)
            dy = max(4.0, (ymax - ymin) * 0.02)
            ax.set_xlim(xmin - dx, xmax + dx)
            ax.set_ylim(ymin - dy, ymax + dy)
        ax.set_aspect("equal", adjustable="box")
        if title:
            ax.set_title(title, fontsize=8, color="#e2e8f0", pad=2)
        ax.tick_params(labelsize=5, colors="#64748b")
        fig.savefig(out_png, dpi=dpi, facecolor="#0a0a12", bbox_inches="tight")
        plt.close(fig)
        return out_png.is_file()
    except Exception as ex:
        import traceback
        print(f"[vision] render fail {dxf_path.name}: {ex}")
        traceback.print_exc()
        try:
            plt.close("all")
        except Exception:
            pass
        return False


def _ink_mask(png_path: Path, size: tuple[int, int] = (640, 360)) -> np.ndarray | None:
    """True = tinta (não fundo)."""
    try:
        from PIL import Image

        im = Image.open(png_path).convert("RGB").resize(size, Image.Resampling.BILINEAR)
        arr = np.asarray(im, dtype=np.float32) / 255.0
        gray = arr.mean(axis=2)
        return gray > 0.14
    except Exception:
        pass
    try:
        import matplotlib.image as mpimg

        arr = mpimg.imread(str(png_path))
        if arr.ndim == 3:
            gray = arr[..., :3].mean(axis=2)
            if float(np.max(gray)) <= 1.0 + 1e-6:
                ink = gray > 0.12
            else:
                ink = gray > 30
        else:
            ink = arr > 0.12
        ys = np.linspace(0, ink.shape[0] - 1, size[1]).astype(int)
        xs = np.linspace(0, ink.shape[1] - 1, size[0]).astype(int)
        return ink[ys][:, xs]
    except Exception as ex:
        print(f"[vision] ink_mask fail: {ex}")
        return None


def _dilate(mask: np.ndarray, r: int = 2) -> np.ndarray:
    """Dilatação binária barata (max-pool)."""
    if r <= 0:
        return mask
    m = mask.astype(bool)
    out = m.copy()
    h, w = m.shape
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy > r * r:
                continue
            ys = slice(max(0, dy), h + min(0, dy))
            xs = slice(max(0, dx), w + min(0, dx))
            y2 = slice(max(0, -dy), h - max(0, dy))
            x2 = slice(max(0, -dx), w - max(0, dx))
            out[ys, xs] |= m[y2, x2]
    return out


def pixel_extra_ratio(
    n2_png: Path,
    n4_png: Path,
    *,
    dilate_n2: int = 1,
    dilate_n4: int = 1,
    size: tuple[int, int] = (640, 360),
    save_extra_map: Path | None = None,
) -> dict[str, Any]:
    """Diff visual simétrico: EXTRA (só N4) e MISS (só N2).

    EXTRA = tinta N4 sem vizinho em N2 (alucinação).
    MISS  = tinta N2 sem vizinho em N4 (incompleto).
    density_delta = (n2-n4)/n2 — N4 pobre demais falha Arete 100.
    """
    m2 = _ink_mask(n2_png, size=size)
    m4 = _ink_mask(n4_png, size=size)
    if m2 is None or m4 is None:
        return {"ok": False, "error": "ink_mask_failed"}
    n2d = _dilate(m2, dilate_n2)
    n4d = _dilate(m4, dilate_n4)
    extra = m4 & ~n2d
    miss = m2 & ~n4d
    n4_ink = int(m4.sum())
    n2_ink = int(m2.sum())
    extra_n = int(extra.sum())
    miss_n = int(miss.sum())
    ratio = (extra_n / n4_ink) if n4_ink > 0 else 0.0
    miss_ratio = (miss_n / n2_ink) if n2_ink > 0 else 0.0
    dens = ((n2_ink - n4_ink) / n2_ink) if n2_ink > 0 else 0.0
    row_dense = int((extra.sum(axis=1) > size[0] * 0.015).sum())
    if save_extra_map is not None:
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            rgb = np.zeros((*extra.shape, 3), dtype=np.float32)
            rgb[m2 & m4] = (0.2, 0.7, 0.3)  # match green
            rgb[extra] = (1.0, 0.2, 0.2)  # EXTRA red
            rgb[miss] = (1.0, 0.85, 0.1)  # MISS yellow
            fig, ax = plt.subplots(figsize=(8, 4.5), dpi=120)
            ax.imshow(rgb, origin="upper")
            ax.set_title("VISION map: green=match · red=EXTRA N4 · yellow=MISS N2", fontsize=8)
            ax.axis("off")
            fig.tight_layout()
            fig.savefig(save_extra_map, dpi=120, facecolor="#111")
            plt.close(fig)
        except Exception as ex:
            print(f"[vision] extra map fail: {ex}")
    return {
        "ok": True,
        "n2_ink": n2_ink,
        "n4_ink": n4_ink,
        "extra_pixels": extra_n,
        "extra_ratio": round(ratio, 4),
        "miss_pixels": miss_n,
        "miss_ratio": round(miss_ratio, 4),
        "density_delta": round(dens, 4),
        "extra_row_bands": row_dense,
    }


# ── gate unit ──────────────────────────────────────────────────────────

def abs_clip(origin: tuple[float, float], clip_rel: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    ox, oy = origin
    return (ox + clip_rel[0], oy + clip_rel[1], ox + clip_rel[2], oy + clip_rel[3])


def vision_gate_unit(
    n2_path: Path,
    n4_path: Path,
    anchor_n2: dict,
    anchor_n4: dict,
    *,
    label: str,
    out_dir: Path,
    # limiares (falha se EXTRA visual)
    max_extra_ratio: float = 0.08,
    max_extra_pixels: int = 2500,
    max_struct_extra: int = 0,
    require_pixel: bool = True,
) -> dict[str, Any]:
    """Gate visão por unidade. FAIL se alucinação visual ou EXTRA estrutural.

    Arete 100% só é elegível se vision_verdict == PASS_VISION.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = "".join(c if c.isalnum() or c in "._-" else "_" for c in label)[:60]

    # Clip largo (humano/dims) + clip estrutural (Arete: sem margem de cotas)
    c2 = abs_clip(anchor_n2["origin"], anchor_n2["clip"])
    c4 = abs_clip(anchor_n4["origin"], anchor_n4["clip"])
    h2 = float(anchor_n2.get("h_body") or 100)
    tw2 = float(anchor_n2.get("total_w") or 100)
    h4 = float(anchor_n4.get("h_body") or h2)
    tw4 = float(anchor_n4.get("total_w") or tw2)
    # corpo + marco ~25, sem L1/L2 de cota
    c2s = abs_clip(anchor_n2["origin"], (-8.0, -12.0, tw2 + 12.0, h2 + 28.0))
    c4s = abs_clip(anchor_n4["origin"], (-8.0, -12.0, tw4 + 12.0, h4 + 28.0))

    p2 = out_dir / f"{stem}_N2.png"
    p4 = out_dir / f"{stem}_N4.png"
    p2s = out_dir / f"{stem}_N2_struct.png"
    p4s = out_dir / f"{stem}_N4_struct.png"
    ok2 = render_dxf_png(n2_path, p2, clip=c2, title=f"N2 {label}")
    ok4 = render_dxf_png(n4_path, p4, clip=c4, title=f"N4 {label}")
    ok2s = render_dxf_png(n2_path, p2s, clip=c2s, title=f"N2 {label} struct")
    ok4s = render_dxf_png(n4_path, p4s, clip=c4s, title=f"N4 {label} struct")

    reasons: list[str] = []
    pixel = {"ok": False}
    map_path = out_dir / f"{stem}_EXTRA_MAP.png"
    # Arete usa clip estrutural (evita MISS por cotas externas do N2)
    if ok2s and ok4s:
        # dilate_n4=2: hachura ANSI31 N2/N4 nao alinham pixel-a-pixel
        pixel = pixel_extra_ratio(
            p2s, p4s, dilate_n2=1, dilate_n4=2, save_extra_map=map_path
        )
    elif ok2 and ok4:
        pixel = pixel_extra_ratio(
            p2, p4, dilate_n2=1, dilate_n4=2, save_extra_map=map_path
        )
        if pixel.get("ok"):
            reasons.append(
                f"pixel_extra={pixel['extra_pixels']}({pixel['extra_ratio']:.1%}) "
                f"miss={pixel.get('miss_pixels')}({float(pixel.get('miss_ratio') or 0):.1%}) "
                f"densΔ={float(pixel.get('density_delta') or 0):.1%}"
            )
    else:
        reasons.append("render PNG incompleto")

    # GeometryIndex estrito (já com phantoms)
    from arete.geometry_index import GeometryIndex

    idx2 = GeometryIndex.from_dxf(
        n2_path,
        origin=anchor_n2["origin"],
        h_body=anchor_n2["h_body"],
        total_w=anchor_n2["total_w"],
        panel_widths=anchor_n2.get("panel_widths"),
        clip=anchor_n2["clip"],
        side="N2",
        label=label,
        role="gabarito",
    )
    idx4 = GeometryIndex.from_dxf(
        n4_path,
        origin=anchor_n4["origin"],
        h_body=anchor_n4["h_body"],
        total_w=anchor_n4["total_w"],
        panel_widths=anchor_n4.get("panel_widths") or anchor_n2.get("panel_widths"),
        clip=anchor_n4["clip"],
        side="N4",
        label=label,
        role="candidato",
    )
    geo = GeometryIndex.diff(idx2, idx4, pair="VISION")
    m = geo.get("metrics") or {}
    extra_g = int(m.get("extra_g") or 0)
    miss_g = int(m.get("miss_g") or 0)
    invented = list(m.get("invented_r") or [])
    phantoms = GeometryIndex._detect_phantoms(
        # recompute extra list from match
        GeometryIndex.match_lines(idx2.structural_lines(), idx4.structural_lines())[2],
        idx2,
    )

    fail = False
    if invented:
        fail = True
        reasons.append(f"inventadas R: {invented[:8]}")
    if phantoms:
        fail = True
        reasons.append(f"PHANTOM: {phantoms[:6]}")
    if extra_g > max_struct_extra:
        fail = True
        reasons.append(f"EXTRA estrutural n={extra_g} (limite {max_struct_extra})")
    if require_pixel and pixel.get("ok"):
        er = float(pixel.get("extra_ratio") if pixel.get("extra_ratio") is not None else 1.0)
        ep = int(pixel.get("extra_pixels") if pixel.get("extra_pixels") is not None else 10**9)
        mr = float(pixel.get("miss_ratio") if pixel.get("miss_ratio") is not None else 1.0)
        dens = float(pixel.get("density_delta") if pixel.get("density_delta") is not None else 1.0)
        if er > max_extra_ratio:
            fail = True
            reasons.append(f"EXTRA pixel ratio {er:.1%} > {max_extra_ratio:.0%}")
        if ep > max_extra_pixels:
            fail = True
            reasons.append(f"EXTRA pixels {ep} > {max_extra_pixels}")
        # incompleto forte também invalida (N4 ralo demais)
        if mr > 0.25:
            fail = True
            reasons.append(f"MISS pixel ratio {mr:.1%} > 25% (N4 incompleto)")
        if dens > 0.22:
            fail = True
            reasons.append(f"densidade N4 {dens:.1%} abaixo do N2 (Δ>22%)")
    if not ok2 or not ok4:
        fail = True

    r_match = float(m.get("r_match") or 0)
    g_match = float(m.get("g_match") or 0)

    # Cotas hard (sem faixas moles) — 20.6 vs 15 conta como inventada visual
    hard_inv = []
    ref = [float(c["measurement_cm"]) for c in idx2.own_cotas()]
    for c in idx4.own_cotas():
        v = float(c["measurement_cm"])
        if not any(abs(v - a) <= 1.0 for a in ref):
            hard_inv.append(v)
    if hard_inv:
        reasons.append(f"cotas hard-extra (tol1 sem banda): {hard_inv[:8]}")

    # Arete 100% só se visão limpa + cobertura total + zero extra
    pix_ok = bool(pixel.get("ok"))
    pix_ratio = (
        float(pixel["extra_ratio"])
        if pix_ok and pixel.get("extra_ratio") is not None
        else 1.0
    )
    pix_extra_n = (
        int(pixel["extra_pixels"])
        if pix_ok and pixel.get("extra_pixels") is not None
        else 10**9
    )
    pix_miss_r = (
        float(pixel["miss_ratio"])
        if pix_ok and pixel.get("miss_ratio") is not None
        else 1.0
    )
    pix_dens = (
        float(pixel["density_delta"])
        if pix_ok and pixel.get("density_delta") is not None
        else 1.0
    )
    arete_100 = (
        not fail
        and r_match >= 0.999
        and g_match >= 0.999
        and extra_g == 0
        and miss_g == 0
        and not invented
        and not phantoms
        and not hard_inv
        and (
            not require_pixel
            or (
                pix_ok
                and pix_ratio <= 0.03
                and pix_extra_n <= max_extra_pixels
                # clip estrutural: miss/dens por hachura residual, nao cotas externas
                and pix_miss_r <= 0.08
                and abs(pix_dens) <= 0.12
            )
        )
    )

    if fail:
        vision_verdict = "FAIL_VISION"
    elif arete_100:
        vision_verdict = "PASS_VISION_ARETE100"
        reasons.append("visão+geo: Arete 100% elegível (zero EXTRA pixel/estrutural)")
    elif r_match >= 0.8 and g_match >= 0.5 and not invented and not phantoms and not fail:
        vision_verdict = "PASS_VISION"
        reasons.append("visão ok sem Arete 100% (miss residual ou pixel residual)")
    else:
        vision_verdict = "SUSPEITO_VISION"

    report = {
        "schema": "vision_anti_hallucination_v1",
        "label": label,
        "vision_verdict": vision_verdict,
        "arete_100_eligible": arete_100,
        "reasons": reasons,
        "geometry": {
            "verdict": geo.get("verdict"),
            "r_match": r_match,
            "g_match": g_match,
            "miss_g": miss_g,
            "extra_g": extra_g,
            "invented_r": invented,
            "phantoms": phantoms,
        },
        "pixel": pixel,
        "png_n2": str(p2.name) if ok2 else None,
        "png_n4": str(p4.name) if ok4 else None,
        "png_extra_map": str(map_path.name) if map_path.is_file() else None,
        "hard_invented_cotas": hard_inv,
        "limits": {
            "max_extra_ratio": max_extra_ratio,
            "max_extra_pixels": max_extra_pixels,
            "max_struct_extra": max_struct_extra,
        },
    }
    (out_dir / f"{stem}_VISION.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def merge_arete_verdict(geo_verdict: str, vision_report: dict | None) -> str:
    """Combina gate geométrico + visão. Visão tem veto sobre Arete 100%."""
    if not vision_report:
        return geo_verdict
    vv = vision_report.get("vision_verdict") or ""
    if vv == "FAIL_VISION":
        return "FAIL E2E"
    if "Arete 100%" in (geo_verdict or "") or "cobertura TOTAL" in str(
        vision_report.get("geometry", {})
    ):
        # se geo disse 100% mas visão não elege → rebaixa
        if not vision_report.get("arete_100_eligible"):
            if vv.startswith("PASS"):
                return "PASS E2E"  # pass normal, sem 100%
            return "SUSPEITO"
    if vv == "PASS_VISION_ARETE100":
        return "PASS E2E"
    return geo_verdict
