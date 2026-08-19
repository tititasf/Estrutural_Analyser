#!/usr/bin/env python
"""Cria uma revisao ABCD sem sobrescrever o checkpoint historico.

Atualiza apenas as bases SA/N1 de pilares cuja geometria foi recuperada no
microciclo headless. As camadas L1/L2/L3 seguem preservadas como evidencia
historica, para nova decisao humana contra a base corrigida.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _tables_from_n1(page: Path) -> dict:
    """Le as tabelas ABCD que o headless acabou de produzir.

    A ficha headless e a autoridade desta sincronizacao: nao reutilizamos as
    tabelas historicas do pack agentico porque elas pertencem a geometria
    rejeitada.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
    faces: dict[str, dict] = {}
    family_keys = {
        "lajes": ("lajes", "laje", "laje"),
        "passam": ("passa", "viga", "passa"),
        "chegam": ("chega", "viga", "chega"),
        "interior": ("interior", "viga", "interior"),
    }
    for card in soup.select(".abcd-face-card"):
        title = card.select_one(".abcd-face-title")
        if title is None:
            continue
        label = title.get_text(" ", strip=True)
        face = label[:1].upper()
        if face not in "ABCDEFGH":
            continue
        face_data = {"label": label, "lajes": [], "passa": [], "chega": [], "interior": []}
        for row in card.select("table.abcd-mini tr"):
            cells = [cell.get_text(" ", strip=True) for cell in row.select("td")]
            if len(cells) < 7:
                continue
            family_label = cells[0].strip().lower()
            family = family_keys.get(family_label)
            if family is None:
                continue
            key, element_family, role = family
            face_data[key].append(
                {
                    "familia": element_family,
                    "nome": cells[1],
                    "dim": cells[2],
                    "nivel": cells[3],
                    "canto": cells[4],
                    "papel": role,
                    "raw": "",
                    "dist_esq": cells[5],
                    "dist_dir": cells[6],
                }
            )
        faces[face] = face_data
    if not faces:
        raise ValueError(f"Tabelas ABCD nao encontradas em {page}")
    label_a = str((faces.get("A") or {}).get("label") or "").lower()
    orientation = "vertical" if "face longa" in label_a else "horizontal"
    return {"faces": faces, "orientation": orientation, "schema": "pil.abcd_tables.v2"}


def _recovered_pillar_points(
    *, db: Path, project_id: str, dxf: Path, items: list[str]
) -> tuple[dict[str, list], list[dict]]:
    """Reaplica a regra universal do SA sem persistir o banco."""
    from src.core.dxf_loader import DXFLoader
    from src.core.pillar_geometry_recovery import repair_truncated_named_pillars_from_dxf

    wanted = {item.strip().upper() for item in items}
    report: dict[str, dict] = {}
    with sqlite3.connect(str(db)) as conn:
        for name, points_json in conn.execute(
            "SELECT name, points_json FROM pillars WHERE project_id=?", (project_id,)
        ):
            normalized = str(name or "").strip().upper()
            if normalized in wanted:
                report[normalized] = {
                    "name": normalized,
                    "points": json.loads(points_json or "[]"),
                }
    missing = sorted(wanted - set(report))
    if missing:
        raise ValueError(f"Pilares ausentes no DB: {', '.join(missing)}")
    dxf_data = DXFLoader.load_dxf(str(dxf)) or {}
    repaired = repair_truncated_named_pillars_from_dxf(
        report,
        polylines=dxf_data.get("polylines") or [],
        texts=dxf_data.get("texts") or [],
    )
    return {name: data["points"] for name, data in report.items()}, repaired


def _svgs_from_n1(page: Path) -> tuple[str, str]:
    html = page.read_text(encoding="utf-8")
    svgs = re.findall(r"(?s)(<svg\b.*?</svg>)", html)
    if len(svgs) < 2:
        raise ValueError(f"N1 sem os SVGs proximo/distante: {page}")
    return svgs[0], svgs[1]


def _replace_layer(html: str, item: str, layer: str, svg: str) -> str:
    pattern = (
        rf'(?s)(<div class="pil-layer[^>]*data-layer="{layer}"[^>]*>'
        rf'<div class="n1-svg">).*?(</svg>)'
    )
    updated, count = re.subn(pattern, lambda match: match.group(1) + svg, html, count=1)
    if count != 1:
        raise ValueError(f"Camada {layer} nao encontrada em {item}")
    return updated


def _replace_far(html: str, item: str, svg: str) -> str:
    pattern = (
        rf'(?s)(<div id="pil-n1-far-{re.escape(item)}".*?'
        rf'<div class="n1-svg">).*?(</svg>)'
    )
    updated, count = re.subn(pattern, lambda match: match.group(1) + svg, html, count=1)
    if count != 1:
        raise ValueError(f"Viewer N1 distante nao encontrado em {item}")
    return updated


def _replace_sa_tables(html: str, item: str, tables: dict) -> str:
    from src.core.pillar_abcd_tables import format_abcd_tables_html

    rendered = format_abcd_tables_html(tables, compact=True)
    replacement = (
        '<div class="sec" data-ficha-panel="interp">'
        '<div class="sec-title">Interpretação ABCD — SA (atual motor)</div>'
        f'<div class="sec-body">{rendered}</div></div>\n'
    )
    pattern = (
        r'(?s)<div class="sec" data-ficha-panel="interp">'
        r'<div class="sec-title">Interpretação ABCD — SA \(atual motor\)</div>.*?'
        r'(?=<div class="sec" data-ficha-panel="interp">'
        r'<div class="sec-title">Interpretação ABCD — proposta)'
    )
    updated, count = re.subn(pattern, lambda _match: replacement, html, count=1)
    if count != 1:
        raise ValueError(f"Tabela SA nao encontrada em {item}")
    return updated


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-pack", type=Path, required=True)
    ap.add_argument("--n1-pack", type=Path, required=True)
    ap.add_argument("--output-pack", type=Path, required=True)
    ap.add_argument("--items", nargs="+", default=["P12", "P13", "P14"])
    ap.add_argument("--db", type=Path)
    ap.add_argument("--project-id")
    ap.add_argument("--dxf", type=Path)
    args = ap.parse_args()

    tag_args = (args.db, args.project_id, args.dxf)
    if any(tag_args) and not all(tag_args):
        raise SystemExit("Para sincronizar tags, informe --db, --project-id e --dxf juntos")

    if args.output_pack.exists():
        raise SystemExit(f"Saida ja existe: {args.output_pack}")
    shutil.copytree(args.source_pack, args.output_pack)

    points_by_item: dict[str, list] = {}
    repaired: list[dict] = []
    if all(tag_args):
        points_by_item, repaired = _recovered_pillar_points(
            db=args.db,
            project_id=args.project_id,
            dxf=args.dxf,
            items=args.items,
        )
        repaired_names = {str(entry.get("item") or "").upper() for entry in repaired}
        not_repaired = sorted({item.upper() for item in args.items} - repaired_names)
        if not_repaired:
            raise ValueError(
                "A geometria universal nao confirmou recuperacao para: "
                + ", ".join(not_repaired)
            )

        import importlib.util

        draw_path = Path(__file__).resolve().parent / "pil_agentic_highlight_draw.py"
        spec = importlib.util.spec_from_file_location("pil_agentic_highlight_draw", draw_path)
        draw_module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(draw_module)
        render_tagged = draw_module.render_agentic_svg
    else:
        render_tagged = None

    for item in args.items:
        n1_page = args.n1_pack / "pilares" / "INDETERMINADO" / f"{item}.html"
        near_svg, far_svg = _svgs_from_n1(n1_page)
        tagged_svg = near_svg
        if render_tagged is not None:
            tables = _tables_from_n1(n1_page)
            tagged_svg = render_tagged(
                args.dxf,
                points_by_item[item.upper()],
                tables,
                layer="sa",
            )
        page = args.output_pack / "pilares" / f"{item}.html"
        html = page.read_text(encoding="utf-8")
        html = _replace_layer(html, item, "sa_plain", near_svg)
        html = _replace_layer(html, item, "sa", tagged_svg)
        html = _replace_far(html, item, far_svg)
        if render_tagged is not None:
            html = _replace_sa_tables(html, item, tables)
        proposals = args.output_pack / "propostas"
        proposals.mkdir(parents=True, exist_ok=True)
        (proposals / f"{item}_sa_plain.svg").write_text(near_svg, encoding="utf-8")
        (proposals / f"{item}_sa_motor.svg").write_text(tagged_svg, encoding="utf-8")
        html = html.replace(
            "GEOMETRIA REPARADA (GOLDEN)",
            "GEOMETRIA RECUPERADA (DXF HOMONIMO)",
        )
        html = html.replace(
            "retangulo GOLDEN aplicado",
            "retangulo completo homonimo do DXF aplicado",
        )
        banner = (
            '<div class="pil-geometry-reanalysis"><b>Revisao DXF aplicada:</b> '
            'SA/N1 recuperado pelo retangulo completo de mesmo nome no DXF (19x98). '
            'As abas L1/L2/L3 sao evidencia historica e devem ser reavaliadas contra esta base.</div>'
        )
        if banner not in html:
            html = html.replace('<div class="pil-agent-tab-wrap">', banner + '<div class="pil-agent-tab-wrap">', 1)
        page.write_text(html, encoding="utf-8")
    if repaired:
        print("tags SA recompostas das tabelas headless: " + ", ".join(args.items))
    print(args.output_pack)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
