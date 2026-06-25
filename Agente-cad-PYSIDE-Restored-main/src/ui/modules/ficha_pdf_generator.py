"""Gerador de fichas PDF por classe (PIL/LV/FV/LAJ) usando reportlab 4.x."""
from __future__ import annotations

import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_LOGO = Path(__file__).parent.parent.parent.parent / "assets" / "logo.jpg"

_COR_HEADER   = colors.HexColor("#1a2340")
_COR_SUBHDR   = colors.HexColor("#2d3f6e")
_COR_ACENTO   = colors.HexColor("#cf8a4a")
_COR_LINHA    = colors.HexColor("#3a4a6e")
_COR_ALT      = colors.HexColor("#e8ecf4")
_COR_BRANCO   = colors.white
_COR_TEXTO    = colors.HexColor("#1a1a2e")

_CLASSE_NOME = {"PIL": "Pilares", "LV": "Vigas Laterais", "FV": "Fundos de Vigas", "LAJ": "Lajes"}
_CLASSE_COR  = {
    "PIL": colors.HexColor("#4a90d9"),
    "LV":  colors.HexColor("#5cb85c"),
    "FV":  colors.HexColor("#cf8a4a"),
    "LAJ": colors.HexColor("#9b59b6"),
}


def _fmt(v: Any, decimals: int = 2) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{decimals}f}" if v != int(v) else str(int(v))
    return str(v)


def _styles():
    s = getSampleStyleSheet()
    base = dict(fontName="Helvetica", fontSize=9, leading=12, textColor=_COR_TEXTO)
    return {
        "title": ParagraphStyle("title", **{**base, "fontSize": 16, "fontName": "Helvetica-Bold",
                                             "textColor": _COR_BRANCO, "alignment": TA_CENTER}),
        "subtitle": ParagraphStyle("sub", **{**base, "fontSize": 11, "fontName": "Helvetica-Bold",
                                              "textColor": _COR_BRANCO, "alignment": TA_CENTER}),
        "empresa": ParagraphStyle("emp", **{**base, "fontSize": 8, "textColor": colors.HexColor("#ccccdd"),
                                             "alignment": TA_CENTER}),
        "section": ParagraphStyle("sec", **{**base, "fontSize": 10, "fontName": "Helvetica-Bold",
                                             "textColor": _COR_BRANCO}),
        "cell_hdr": ParagraphStyle("ch", **{**base, "fontSize": 8, "fontName": "Helvetica-Bold",
                                             "textColor": _COR_BRANCO, "alignment": TA_CENTER}),
        "cell": ParagraphStyle("c", **{**base, "fontSize": 8, "alignment": TA_CENTER}),
        "cell_l": ParagraphStyle("cl", **{**base, "fontSize": 8, "alignment": TA_LEFT}),
        "label": ParagraphStyle("lbl", **{**base, "fontSize": 8, "fontName": "Helvetica-Bold",
                                           "textColor": _COR_SUBHDR}),
        "value": ParagraphStyle("val", **{**base, "fontSize": 8}),
        "obs": ParagraphStyle("obs", **{**base, "fontSize": 7, "textColor": colors.gray}),
        "date": ParagraphStyle("dt", **{**base, "fontSize": 7, "textColor": colors.HexColor("#ccccdd"),
                                         "alignment": TA_RIGHT}),
    }


def _tbl_style(header_rows: int = 1, alt: bool = True):
    cmds = [
        ("BACKGROUND", (0, 0), (-1, header_rows - 1), _COR_SUBHDR),
        ("TEXTCOLOR",  (0, 0), (-1, header_rows - 1), _COR_BRANCO),
        ("FONTNAME",   (0, 0), (-1, header_rows - 1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",       (0, 0), (-1, -1), 0.4, _COR_LINHA),
        ("ROWBACKGROUNDS", (0, header_rows), (-1, -1), [_COR_BRANCO, _COR_ALT] if alt else [_COR_BRANCO]),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
    ]
    return TableStyle(cmds)


def _section_hdr(text: str, classe: str, st: dict):
    cor = _CLASSE_COR.get(classe, _COR_SUBHDR)
    tbl = Table([[Paragraph(text, st["section"])]], colWidths=["100%"])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    return tbl


def _info_block(pairs: list[tuple[str, str]], st: dict, page_w: float):
    """Pares label/valor em grade de 2 colunas."""
    rows = []
    for i in range(0, len(pairs), 2):
        row = []
        for j in range(2):
            if i + j < len(pairs):
                lbl, val = pairs[i + j]
                row.append(Paragraph(f"<b>{lbl}:</b>  {val}", st["cell_l"]))
            else:
                row.append("")
        rows.append(row)
    if not rows:
        return Spacer(1, 2 * mm)
    cw = page_w / 2
    tbl = Table(rows, colWidths=[cw, cw])
    tbl.setStyle(TableStyle([
        ("GRID",            (0, 0), (-1, -1), 0.3, colors.HexColor("#ccccdd")),
        ("BACKGROUND",      (0, 0), (-1, -1), _COR_ALT),
        ("TOPPADDING",      (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",   (0, 0), (-1, -1), 3),
        ("LEFTPADDING",     (0, 0), (-1, -1), 6),
    ]))
    return tbl


# ─── Cabeçalho da ficha ───────────────────────────────────────────────────────

def _build_header(item_id: str, classe: str, obra: str, pav: str,
                  page_w: float, st: dict) -> list:
    cor_classe = _CLASSE_COR.get(classe, _COR_SUBHDR)
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    logo_cell: Any = ""
    if _LOGO.exists():
        try:
            logo_cell = Image(str(_LOGO), width=2.0 * cm, height=2.0 * cm)
        except Exception:
            pass

    title_cell = [
        Paragraph("TSF PROJETOS", st["title"]),
        Paragraph("Estrutural Analyzer — Ficha Técnica", st["empresa"]),
        Spacer(1, 2 * mm),
        Paragraph(f"{_CLASSE_NOME.get(classe, classe)}  ·  {item_id}", st["subtitle"]),
    ]
    date_cell = Paragraph(now, st["date"])

    hdr_tbl = Table(
        [[logo_cell, title_cell, date_cell]],
        colWidths=[2.4 * cm, page_w - 4.8 * cm, 2.4 * cm],
    )
    hdr_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), _COR_HEADER),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    bar = Table([[""]],
                colWidths=[page_w], rowHeights=[3])
    bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), cor_classe)]))

    info = [
        ("Elemento", item_id),
        ("Classe", f"{classe}  —  {_CLASSE_NOME.get(classe, '')}"),
        ("Obra", obra or "—"),
        ("Pavimento", pav or "—"),
    ]
    return [hdr_tbl, bar, Spacer(1, 3 * mm), _info_block(info, st, page_w), Spacer(1, 4 * mm)]


# ─── PIL ──────────────────────────────────────────────────────────────────────

def _build_pil(ficha: dict, st: dict, page_w: float, classe: str) -> list:
    elems = []
    elems.append(_section_hdr("ESPECIFICAÇÕES GERAIS", classe, st))
    elems.append(Spacer(1, 1 * mm))

    specs = [
        ("Comprimento", f"{_fmt(ficha.get('comprimento'))} cm"),
        ("Largura",     f"{_fmt(ficha.get('largura'))} cm"),
        ("Altura total", f"{_fmt(ficha.get('altura'))} cm"),
        ("Nível chegada", f"{_fmt(ficha.get('nivel_chegada'))} cm"),
        ("Nível saída",   f"{_fmt(ficha.get('nivel_saida'))} cm"),
        ("Pavimento", ficha.get("pavimento", "—")),
        ("Distribuição", ficha.get("modo_distribuicao", "—")),
    ]
    grade2 = ficha.get("grade_2")
    grade3 = ficha.get("grade_3")
    if grade2:
        specs.append(("Grade 2", f"{_fmt(grade2)} cm"))
    if grade3:
        specs.append(("Grade 3", f"{_fmt(grade3)} cm"))
    d1 = ficha.get("distancia_1")
    d2 = ficha.get("distancia_2")
    if d1:
        specs.append(("Distância 1", f"{_fmt(d1)} cm"))
    if d2:
        specs.append(("Distância 2", f"{_fmt(d2)} cm"))

    elems.append(_info_block(specs, st, page_w))
    elems.append(Spacer(1, 4 * mm))

    # Faces
    faces = [f for f in ["A", "B", "C", "D", "E", "F", "G", "H"]
             if ficha.get(f"h1_{f}") is not None]
    if faces:
        elems.append(_section_hdr("FACES — PAINÉIS E ALTURAS", classe, st))
        elems.append(Spacer(1, 1 * mm))

        hdr = ["Face", "H1", "H2", "H3", "H4", "H5", "Larg1", "Larg2", "Larg3", "Laje", "Pos. Laje"]
        rows = [hdr]
        for f in faces:
            rows.append([
                f,
                _fmt(ficha.get(f"h1_{f}")),
                _fmt(ficha.get(f"h2_{f}")),
                _fmt(ficha.get(f"h3_{f}")),
                _fmt(ficha.get(f"h4_{f}")),
                _fmt(ficha.get(f"h5_{f}")),
                _fmt(ficha.get(f"larg1_{f}")),
                _fmt(ficha.get(f"larg2_{f}")),
                _fmt(ficha.get(f"larg3_{f}")),
                _fmt(ficha.get(f"laje_{f}")),
                str(ficha.get(f"posicao_laje_{f}") or "—"),
            ])

        col_w = page_w / len(hdr)
        tbl = Table(rows, colWidths=[col_w] * len(hdr))
        tbl.setStyle(_tbl_style())
        elems.append(tbl)

    return elems


# ─── FV ───────────────────────────────────────────────────────────────────────

def _build_fv(ficha: dict, st: dict, page_w: float, classe: str) -> list:
    elems = []
    elems.append(_section_hdr("ESPECIFICAÇÕES GERAIS", classe, st))
    elems.append(Spacer(1, 1 * mm))

    specs = [
        ("Elemento",          ficha.get("name") or "—"),
        ("Pavimento",         ficha.get("floor") or "—"),
        ("Comprimento total", f"{_fmt(ficha.get('total_height'))} mm"),
        ("Espessura (h)",     f"{_fmt(ficha.get('total_width'))} cm"),
        ("Pilar esquerdo",    str(ficha.get("pillar_left") or "—")),
        ("Pilar direito",     str(ficha.get("pillar_right") or "—")),
        ("Label esquerdo",    str(ficha.get("label_left") or "—")),
        ("Label direito",     str(ficha.get("label_right") or "—")),
        ("Sarrafo esq.",      str(ficha.get("sarrafo_left_id") or "—")),
        ("Sarrafo dir.",      str(ficha.get("sarrafo_right_id") or "—")),
    ]
    elems.append(_info_block(specs, st, page_w))
    elems.append(Spacer(1, 4 * mm))

    # Painéis
    panels = ficha.get("panels") or []
    if panels:
        elems.append(_section_hdr("PAINÉIS", classe, st))
        elems.append(Spacer(1, 1 * mm))
        hdr = ["Nº", "Largura (mm)", "Altura1 (cm)", "Altura2 (cm)", "Grade H1", "Grade H2"]
        rows = [hdr]
        for i, p in enumerate(panels, 1):
            rows.append([
                str(i),
                _fmt(p.get("width")),
                _fmt(p.get("height1")),
                _fmt(p.get("height2")),
                str(p.get("grade_h1") or "—"),
                str(p.get("grade_h2") or "—"),
            ])
        cws = [page_w * f for f in [0.07, 0.23, 0.18, 0.18, 0.17, 0.17]]
        tbl = Table(rows, colWidths=cws)
        tbl.setStyle(_tbl_style())
        elems.append(tbl)
        elems.append(Spacer(1, 4 * mm))

    # Buracos / aberturas
    holes = ficha.get("holes") or []
    if holes:
        elems.append(_section_hdr("ABERTURAS / FUROS", classe, st))
        elems.append(Spacer(1, 1 * mm))
        hdr = ["Nº", "Largura", "Posição rel.", "Texto"]
        rows = [hdr]
        for i, h in enumerate(holes, 1):
            if isinstance(h, (list, tuple)) and len(h) >= 2:
                rows.append([str(i), _fmt(h[0]), _fmt(h[1]), str(h[2]) if len(h) > 2 else "—"])
            elif isinstance(h, dict):
                rows.append([str(i), _fmt(h.get("width")), _fmt(h.get("position")), str(h.get("text") or "—")])
        cws = [page_w * f for f in [0.07, 0.25, 0.25, 0.43]]
        tbl = Table(rows, colWidths=cws)
        tbl.setStyle(_tbl_style())
        elems.append(tbl)

    # Segments_rich (detalhamento por trecho)
    segs = ficha.get("segments_rich") or []
    if segs:
        elems.append(Spacer(1, 4 * mm))
        elems.append(_section_hdr("TRECHOS DETALHADOS", classe, st))
        elems.append(Spacer(1, 1 * mm))
        for i, seg in enumerate(segs, 1):
            seg_w = _fmt(seg.get("total_width"))
            sub_panels = seg.get("panels") or []
            hdr_seg = [f"Trecho {i}  (larg. total: {seg_w} mm)"]
            tbl_hdr = Table([[Paragraph(hdr_seg[0], st["cell_hdr"])]],
                            colWidths=[page_w])
            tbl_hdr.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), _COR_LINHA),
                ("TOPPADDING",    (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ]))
            elems.append(tbl_hdr)
            if sub_panels:
                hdr2 = ["Sub-painel", "Largura (mm)", "Texto(s)"]
                rows2 = [hdr2]
                for j, sp in enumerate(sub_panels, 1):
                    txts = ", ".join(sp.get("texts") or []) or "—"
                    rows2.append([str(j), _fmt(sp.get("width")), txts])
                cws2 = [page_w * f for f in [0.12, 0.28, 0.60]]
                tbl2 = Table(rows2, colWidths=cws2)
                tbl2.setStyle(_tbl_style())
                elems.append(tbl2)
            elems.append(Spacer(1, 2 * mm))

    return elems


# ─── LV ───────────────────────────────────────────────────────────────────────

def _build_lv(ficha: dict, st: dict, page_w: float, classe: str) -> list:
    elems = []
    elems.append(_section_hdr("ESPECIFICAÇÕES GERAIS", classe, st))
    elems.append(Spacer(1, 1 * mm))

    specs = [
        ("Elemento", ficha.get("name") or "—"),
        ("Pavimento", ficha.get("floor") or "—"),
        ("Comprimento total", f"{_fmt(ficha.get('total_width'))} mm" if ficha.get("total_width") else "—"),
        ("Altura total",      f"{_fmt(ficha.get('total_height'))} mm" if ficha.get("total_height") else "—"),
        ("Pilar esquerdo",    str(ficha.get("pillar_left") or "—")),
        ("Pilar direito",     str(ficha.get("pillar_right") or "—")),
    ]
    elems.append(_info_block(specs, st, page_w))
    elems.append(Spacer(1, 4 * mm))

    # face_units
    face_units = ficha.get("face_units") or []
    if face_units:
        elems.append(_section_hdr("FACES — UNIDADES VISUAIS", classe, st))
        elems.append(Spacer(1, 1 * mm))
        for fu in face_units:
            lbl   = fu.get("label") or fu.get("side") or "?"
            side  = fu.get("side") or "?"
            h_tot = _fmt(fu.get("h_total"))
            fu_panels = fu.get("panels") or []
            sub_hdr = f"Face {lbl}  (lado: {side}  |  h_total: {h_tot} mm)"
            bar = Table([[Paragraph(sub_hdr, st["cell_hdr"])]],
                        colWidths=[page_w])
            bar.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), _COR_LINHA),
                ("TOPPADDING",    (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ]))
            elems.append(bar)
            if fu_panels:
                hdr = ["Nº", "Largura", "Altura", "Tipo"]
                rows = [hdr]
                for k, fp in enumerate(fu_panels, 1):
                    rows.append([
                        str(k),
                        _fmt(fp.get("width") or fp.get("w")),
                        _fmt(fp.get("height") or fp.get("h")),
                        str(fp.get("tipo") or fp.get("type") or "painel"),
                    ])
                cws = [page_w * f for f in [0.10, 0.30, 0.30, 0.30]]
                tbl = Table(rows, colWidths=cws)
                tbl.setStyle(_tbl_style())
                elems.append(tbl)
            elems.append(Spacer(1, 2 * mm))

    # section_views
    svs = ficha.get("section_views") or []
    if svs:
        elems.append(Spacer(1, 3 * mm))
        elems.append(_section_hdr("SEÇÕES TRANSVERSAIS", classe, st))
        elems.append(Spacer(1, 1 * mm))
        all_keys = sorted({k for sv in svs for k in sv if not k.startswith("_")})
        hdr = ["Nº"] + all_keys[:10]
        rows = [hdr]
        for i, sv in enumerate(svs, 1):
            rows.append([str(i)] + [_fmt(sv.get(k)) for k in all_keys[:10]])
        col_n = len(hdr)
        cws = [page_w / col_n] * col_n
        tbl = Table(rows, colWidths=cws)
        tbl.setStyle(_tbl_style())
        elems.append(tbl)

    # panels_A / panels_B
    for side_key, side_lbl in [("panels_A", "Painéis Face A"), ("panels_B", "Painéis Face B")]:
        pnls = ficha.get(side_key) or []
        if not pnls:
            continue
        elems.append(Spacer(1, 4 * mm))
        elems.append(_section_hdr(side_lbl, classe, st))
        elems.append(Spacer(1, 1 * mm))
        all_seg_keys = sorted({k for seg in pnls for k in (seg.keys() if isinstance(seg, dict) else []) if not k.startswith("_")})
        if all_seg_keys:
            hdr = ["Nº"] + all_seg_keys[:8]
            rows = [hdr]
            for i, seg in enumerate(pnls, 1):
                if isinstance(seg, dict):
                    rows.append([str(i)] + [_fmt(seg.get(k)) for k in all_seg_keys[:8]])
            cws = [page_w / len(hdr)] * len(hdr)
            tbl = Table(rows, colWidths=cws)
            tbl.setStyle(_tbl_style())
            elems.append(tbl)

    return elems


# ─── LAJ ──────────────────────────────────────────────────────────────────────

def _build_laj(ficha: dict, st: dict, page_w: float, classe: str) -> list:
    elems = []
    elems.append(_section_hdr("ESPECIFICAÇÕES GERAIS", classe, st))
    elems.append(Spacer(1, 1 * mm))

    area = ficha.get("area_cm2")
    specs = [
        ("Elemento",    ficha.get("nome") or ficha.get("name") or "—"),
        ("Pavimento",   ficha.get("pavimento") or ficha.get("floor") or "—"),
        ("Comprimento", f"{_fmt(ficha.get('comprimento') or ficha.get('total_width'))} cm"),
        ("Largura",     f"{_fmt(ficha.get('largura') or ficha.get('total_height'))} cm"),
        ("Área",        f"{_fmt(area)} cm²" if area else "—"),
        ("Modo",        ficha.get("modo_selecionado") or "—"),
    ]
    elems.append(_info_block(specs, st, page_w))
    elems.append(Spacer(1, 4 * mm))

    # Linhas verticais
    lv_list = ficha.get("linhas_verticais") or []
    if lv_list:
        elems.append(_section_hdr("LINHAS VERTICAIS (DIVISÓRIAS)", classe, st))
        elems.append(Spacer(1, 1 * mm))
        hdr = ["Nº", "Valor (cm)", "União"]
        rows = [hdr]
        for i, lv in enumerate(lv_list, 1):
            if isinstance(lv, dict):
                rows.append([str(i), _fmt(lv.get("value")), "Sim" if lv.get("is_union") else "Não"])
            else:
                rows.append([str(i), _fmt(lv), "—"])
        cws = [page_w * f for f in [0.10, 0.45, 0.45]]
        tbl = Table(rows, colWidths=cws)
        tbl.setStyle(_tbl_style())
        elems.append(tbl)
        elems.append(Spacer(1, 4 * mm))

    # Linhas horizontais
    lh_list = ficha.get("linhas_horizontais") or []
    if lh_list:
        elems.append(_section_hdr("LINHAS HORIZONTAIS (DIVISÓRIAS)", classe, st))
        elems.append(Spacer(1, 1 * mm))
        hdr = ["Nº", "Valor (cm)", "União"]
        rows = [hdr]
        for i, lh in enumerate(lh_list, 1):
            if isinstance(lh, dict):
                rows.append([str(i), _fmt(lh.get("value")), "Sim" if lh.get("is_union") else "Não"])
            else:
                rows.append([str(i), _fmt(lh), "—"])
        cws = [page_w * f for f in [0.10, 0.45, 0.45]]
        tbl = Table(rows, colWidths=cws)
        tbl.setStyle(_tbl_style())
        elems.append(tbl)
        elems.append(Spacer(1, 4 * mm))

    # Cotas painéis
    cp = ficha.get("cotas_paineis") or []
    if cp:
        elems.append(_section_hdr("COTAS DE PAINÉIS", classe, st))
        elems.append(Spacer(1, 1 * mm))
        all_keys = sorted({k for c in cp for k in (c.keys() if isinstance(c, dict) else [])})
        if all_keys:
            hdr = ["Nº"] + all_keys[:8]
            rows = [hdr]
            for i, c in enumerate(cp, 1):
                rows.append([str(i)] + [_fmt(c.get(k)) for k in all_keys[:8]])
            cws = [page_w / len(hdr)] * len(hdr)
            tbl = Table(rows, colWidths=cws)
            tbl.setStyle(_tbl_style())
            elems.append(tbl)
            elems.append(Spacer(1, 4 * mm))

    # Pontaletes
    pont = ficha.get("pontaletes") or []
    if pont:
        elems.append(_section_hdr("PONTALETES", classe, st))
        elems.append(Spacer(1, 1 * mm))
        all_keys = sorted({k for p in pont for k in (p.keys() if isinstance(p, dict) else [])})
        if all_keys:
            hdr = ["Nº"] + all_keys[:6]
            rows = [hdr]
            for i, p in enumerate(pont, 1):
                rows.append([str(i)] + [_fmt(p.get(k)) for k in all_keys[:6]])
            cws = [page_w / len(hdr)] * len(hdr)
            tbl = Table(rows, colWidths=cws)
            tbl.setStyle(_tbl_style())
            elems.append(tbl)
            elems.append(Spacer(1, 4 * mm))

    # Obstáculos
    obst = ficha.get("obstaculos") or []
    if obst:
        elems.append(_section_hdr("OBSTÁCULOS / ABERTURAS", classe, st))
        elems.append(Spacer(1, 1 * mm))
        all_keys = sorted({k for o in obst for k in (o.keys() if isinstance(o, dict) else [])})
        if all_keys:
            hdr = ["Nº"] + all_keys[:6]
            rows = [hdr]
            for i, o in enumerate(obst, 1):
                rows.append([str(i)] + [_fmt(o.get(k)) for k in all_keys[:6]])
            cws = [page_w / len(hdr)] * len(hdr)
            tbl = Table(rows, colWidths=cws)
            tbl.setStyle(_tbl_style())
            elems.append(tbl)

    obs = ficha.get("observacoes")
    if obs:
        elems.append(Spacer(1, 4 * mm))
        elems.append(Paragraph(f"Observações: {obs}", st["obs"]))

    return elems


# ─── DXF preview ──────────────────────────────────────────────────────────────

def _try_dxf_preview(dxf_path: "Path | None", max_w: float, max_h: float) -> "Image | None":
    if not dxf_path or not Path(dxf_path).exists():
        return None
    try:
        import ezdxf
        from ezdxf.addons.drawing import Frontend, RenderContext
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        fig = plt.figure(figsize=(8, 5))
        ax  = fig.add_axes([0, 0, 1, 1])
        ctx = RenderContext(doc)
        backend = MatplotlibBackend(ax)
        Frontend(ctx, backend).draw_layout(msp)
        ax.set_facecolor("#f5f7fa")
        fig.patch.set_facecolor("#f5f7fa")

        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        fig.savefig(tmp.name, dpi=120, bbox_inches="tight",
                    facecolor="#f5f7fa", pad_inches=0.05)
        plt.close(fig)
        tmp.close()
        img = Image(tmp.name, width=max_w, height=max_h, kind="proportional")
        img._tmp_path = tmp.name
        return img
    except Exception:
        return None


# ─── Entry point público ──────────────────────────────────────────────────────

def gerar_ficha_pdf(
    ficha:   dict,
    classe:  str,
    item_id: str,
    obra:    str,
    pav:     str,
    out_dir: "Path | str | None" = None,
    dxf_path: "Path | None" = None,
) -> Path:
    """Gera o PDF da ficha e retorna o path do arquivo gerado."""
    if out_dir is None:
        out_dir = Path(tempfile.gettempdir()) / "fichas_pdf"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_id  = item_id.replace("/", "-").replace("\\", "-")
    safe_pav = (pav or "").replace("/", "-").replace(" ", "_")
    fname = f"Ficha_{classe}_{safe_id}_{safe_pav}.pdf"
    out_path = out_dir / fname

    PAGE_W, PAGE_H = A4
    margin = 1.2 * cm
    usable_w = PAGE_W - 2 * margin

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin,
        title=f"Ficha {classe} — {item_id}",
        author="TSF PROJETOS — Estrutural Analyzer",
    )

    st = _styles()

    story: list = []
    story += _build_header(item_id, classe, obra, pav, usable_w, st)

    cls_upper = classe.upper()
    if cls_upper == "PIL":
        story += _build_pil(ficha, st, usable_w, cls_upper)
    elif cls_upper == "FV":
        story += _build_fv(ficha, st, usable_w, cls_upper)
    elif cls_upper == "LV":
        story += _build_lv(ficha, st, usable_w, cls_upper)
    elif cls_upper in ("LAJ", "LJ"):
        story += _build_laj(ficha, st, usable_w, cls_upper)

    # DXF preview (opcional)
    preview = _try_dxf_preview(dxf_path, usable_w, 10 * cm)
    if preview:
        story.append(Spacer(1, 5 * mm))
        story.append(_section_hdr("PRÉVIA DO DXF (N3)", cls_upper, st))
        story.append(Spacer(1, 2 * mm))
        story.append(preview)

    # Rodapé
    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_COR_LINHA))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        f"TSF PROJETOS  ·  Estrutural Analyzer  ·  Gerado em "
        f"{datetime.now().strftime('%d/%m/%Y %H:%M')}",
        st["obs"],
    ))

    doc.build(story)

    # Limpa PNG temporário do preview
    if preview and hasattr(preview, "_tmp_path"):
        try:
            os.unlink(preview._tmp_path)
        except Exception:
            pass

    return out_path


def abrir_pdf(path: Path) -> None:
    """Abre o PDF no visualizador padrão do sistema."""
    import platform
    if platform.system() == "Windows":
        os.startfile(str(path))
    elif platform.system() == "Darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)
