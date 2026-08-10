#!/usr/bin/env python3
"""Monta mosaico PNG por item (N1 local + N1 contextual + N2) a partir de relatorio g2v.

Uso:
  python scripts/arete/g2v_batch_mosaic.py \\
    --relatorio scripts/arete/relatorios/g2v/20260716_HHMMSS/relatorio.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def svg_to_png(svg_path: Path, out_path: Path) -> bool:
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM
    except ImportError:
        return False
    drawing = svg2rlg(str(svg_path))
    if drawing is None:
        return False
    renderPM.drawToFile(drawing, str(out_path), fmt="PNG")
    return out_path.exists()


def load_font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def trim_svgs_for_mosaic(svg_paths: list[Path], max_panels: int | None) -> list[Path]:
    """Reduz painéis em itens com dezenas de cartões N1 (ex. V301)."""
    if not max_panels or len(svg_paths) <= max_panels:
        return svg_paths
    if max_panels < 2:
        return svg_paths[:max_panels]
    n2 = [p for p in svg_paths if "_N2" in p.name]
    n3 = [p for p in svg_paths if "_N3" in p.name]
    n4 = [p for p in svg_paths if "_N4" in p.name]
    context = n2 or n3 or n4
    head = [p for p in svg_paths if p not in context]
    if not head:
        return svg_paths[:max_panels]
    tail = context[-1:] if context else []
    budget = max_panels - len(tail)
    return head[: max(1, budget)] + tail


def stage_label(path: Path) -> str:
    name = path.name
    m = re.search(r"_(N1|N2|N3|N4)(?:_|\.svg)", name)
    if m:
        return m.group(1)
    if "_01_" in name or "local" in name.lower():
        return "N1-local"
    if "_02_" in name:
        return "N1-ctx"
    return path.stem


def compose_row(images: list[tuple[str, Image.Image]], gap: int = 8, pad: int = 6) -> Image.Image:
    font = load_font(14)
    labeled: list[Image.Image] = []
    for label, img in images:
        banner_h = 22
        w, h = img.size
        canvas = Image.new("RGB", (w, h + banner_h), (20, 20, 20))
        canvas.paste(img, (0, banner_h))
        draw = ImageDraw.Draw(canvas)
        draw.text((pad, 2), label, fill=(200, 220, 255), font=font)
        labeled.append(canvas)
    total_w = sum(im.size[0] for im in labeled) + gap * (len(labeled) - 1)
    max_h = max(im.size[1] for im in labeled)
    row = Image.new("RGB", (total_w, max_h), (12, 12, 12))
    x = 0
    for im in labeled:
        row.paste(im, (x, 0))
        x += im.size[0] + gap
    return row


def resize_keep(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    w, h = img.size
    scale = min(max_w / w, max_h / h, 1.0)
    if scale >= 1.0:
        return img
    return img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)


def build_item_mosaic(svg_paths: list[Path], tmp_dir: Path, item_id: str,
                      max_panel_w: int, max_panel_h: int) -> Path | None:
    panels: list[tuple[str, Image.Image]] = []
    for svg in svg_paths:
        png = tmp_dir / f"{svg.stem}.png"
        if not png.exists() and not svg_to_png(svg, png):
            continue
        img = Image.open(png).convert("RGB")
        img = resize_keep(img, max_panel_w, max_panel_h)
        panels.append((stage_label(svg), img))
    if not panels:
        return None
    row = compose_row(panels)
    font = load_font(18)
    title_h = 28
    out = Image.new("RGB", (row.size[0], row.size[1] + title_h), (8, 8, 8))
    out.paste(row, (0, title_h))
    draw = ImageDraw.Draw(out)
    draw.text((8, 4), item_id, fill=(80, 220, 180), font=font)
    out_path = tmp_dir / f"mosaic_{item_id}.png"
    out.save(out_path)
    return out_path


def build_pack_mosaic(item_mosaics: list[Path], out_path: Path, gap: int = 12) -> Path:
    imgs = [Image.open(p).convert("RGB") for p in item_mosaics]
    max_w = max(im.size[0] for im in imgs)
    padded = []
    for im in imgs:
        if im.size[0] < max_w:
            canvas = Image.new("RGB", (max_w, im.size[1]), (8, 8, 8))
            canvas.paste(im, (0, 0))
            padded.append(canvas)
        else:
            padded.append(im)
    total_h = sum(im.size[1] for im in padded) + gap * (len(padded) - 1)
    sheet = Image.new("RGB", (max_w, total_h), (6, 6, 6))
    y = 0
    for im in padded:
        sheet.paste(im, (0, y))
        y += im.size[1] + gap
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    return out_path


def extract_n1_svgs_from_html(html_path: Path, tmp_dir: Path, item_id: str) -> list[Path]:
    """Extrai cartões N1 (local + contextual) embutidos na ficha HTML."""
    text = html_path.read_text(encoding="utf-8", errors="ignore")
    blocks = re.findall(
        r'N1 / SA (local|contextual)</b>.*?(?:<\?xml[^>]*\?>\s*)?(<svg[\s\S]*?</svg>)',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    blocks = [(f"N1 / SA {label}", svg) for label, svg in blocks]
    out: list[Path] = []
    for index, (label, svg_raw) in enumerate(blocks[:2], start=1):
        slug = re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_").lower()
        target = tmp_dir / f"{item_id}_html_{index:02d}_{slug}.svg"
        body = svg_raw.strip()
        if not body.startswith("<?xml"):
            body = '<?xml version="1.0" encoding="utf-8"?>\n' + body
        target.write_text(body, encoding="utf-8")
        out.append(target)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--relatorio", type=Path, default=None)
    parser.add_argument("--html-pack", type=Path, default=None,
                        help="Pasta do pack HTML (fundos_viga/) para itens sem N2")
    parser.add_argument("--html-items", nargs="+", default=[],
                        help="Itens adicionais só-N1 a incluir no mosaico")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--max-panel-w", type=int, default=520)
    parser.add_argument("--max-panel-h", type=int, default=360)
    parser.add_argument(
        "--max-panels", type=int, default=None,
        help="Limita SVGs por item (ex. 4 = 3×N1 + N2) para packs pesados",
    )
    args = parser.parse_args()
    if not args.relatorio and not args.html_pack:
        parser.error("informe --relatorio e/ou --html-pack")

    base = (args.relatorio or args.html_pack).parent
    tmp = base / "_mosaic_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    item_paths: list[Path] = []
    seen: set[str] = set()

    if args.relatorio and args.relatorio.exists():
        rel = json.loads(args.relatorio.read_text(encoding="utf-8"))
        base = args.relatorio.parent
        for row in rel.get("itens") or []:
            item_id = str(row.get("elemento_id") or "")
            svgs = [Path(p) for p in (row.get("svg_paths") or []) if Path(p).exists()]
            svgs = trim_svgs_for_mosaic(svgs, args.max_panels)
            if not svgs:
                continue
            mosaic = build_item_mosaic(svgs, tmp, item_id, args.max_panel_w, args.max_panel_h)
            if mosaic:
                item_paths.append(mosaic)
                seen.add(item_id)
                print(f"  {item_id}: {mosaic}")

    if args.html_pack:
        pack_dir = args.html_pack
        if (pack_dir / "fundos_viga").is_dir():
            pack_dir = pack_dir / "fundos_viga"
        for item_id in args.html_items:
            if item_id in seen:
                continue
            html = pack_dir / f"{item_id}.html"
            if not html.exists():
                print(f"  [WARN] HTML ausente: {html}")
                continue
            svgs = extract_n1_svgs_from_html(html, tmp, item_id)
            if not svgs:
                print(f"  [WARN] sem SVG N1 em {html.name}")
                continue
            mosaic = build_item_mosaic(svgs, tmp, f"{item_id}_N1only", args.max_panel_w, args.max_panel_h)
            if mosaic:
                item_paths.append(mosaic)
                print(f"  {item_id} (N1-only): {mosaic}")

    if not item_paths:
        print("[ERRO] nenhum mosaico gerado")
        return 1
    pack_out = args.out or (base / "PACK_MOSAIC_N1xN2.png")
    build_pack_mosaic(item_paths, pack_out)
    manifest = {
        "relatorio": str(args.relatorio.resolve()) if args.relatorio else None,
        "html_pack": str(args.html_pack.resolve()) if args.html_pack else None,
        "pack_mosaic": str(pack_out.resolve()),
        "itens": [p.name for p in item_paths],
        "panels_per_item": "SVGs N1 local + contextual + N2 quando existir",
    }
    (base / "mosaic_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Pack: {pack_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())