"""Detalhes N4 de LV que usam campos explicitos por face_unit da ficha."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import ezdxf


def _load_motor(generator_path: Path):
    spec = importlib.util.spec_from_file_location(
        "lv_n4_details_generator", generator_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    original_key = module._face_unit_geom_key

    def occurrence_aware_key(unit):
        key = original_key(unit)
        if float(unit.get("painel_sup_alt", 0) or 0) > 0.5:
            bbox = unit.get("bbox") or {}
            return key + (tuple(
                round(float(bbox.get(name, 0) or 0), 1)
                for name in ("x_left", "y_bot", "x_right", "y_top")
            ),)
        return key

    module._face_unit_geom_key = occurrence_aware_key
    return module


def augment_face_unit_details(
    path: Path, entry: dict, view: str, generator_path: Path,
) -> None:
    """Desenha painel superior e normaliza cotas laterais por parede real."""
    view = str(view or "ALL").upper()
    if view not in {"ALL", "A", "B"}:
        return
    motor = _load_motor(Path(generator_path))
    layouts = motor.layout_lv_face_unit_bboxes(
        entry.get("face_units", []), x_origin=0.0, y_top=0.0, view=view,
    )
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    changed = False

    for layout in layouts:
        unit = layout.get("unit") or {}
        side = str(unit.get("side") or "").upper()
        if view in {"A", "B"} and side != view:
            continue
        crop = layout.get("bbox") or (0, 0, 0, 0)
        h = float(unit.get("h_body", unit.get("h_total", 0)) or 0)
        li = float(unit.get("laje_inf", 0) or 0)
        ls = float(unit.get("laje_sup", 0) or 0)
        x0 = float(crop[0]) + 25.0
        y0 = float(crop[1]) + li + motor.DIM_TOTAL_BELOW + 25.0
        panels = unit.get("panels") or unit.get("segments") or []
        widths = [float(p.get("width", p.get("largura_cm", 0)) or 0)
                  for p in panels]
        heights = [float(p.get("height1", 0) or 0) for p in panels]
        right = x0 + sum(widths)
        trailing_step = bool(
            len(heights) >= 2 and heights[0] >= h - 5.0
            and any(0 < ph < h - 5.0 for ph in heights[1:])
        )
        # A cota da laje (15/14) so existe no N2 quando a ocorrencia tem uma
        # faixa de marco real (painel estreito <28cm na ponta, leading ou
        # trailing) — sem faixa estreita em nenhuma ponta, o papel nao
        # anota essa altura mesmo com padrao de degrau (evidencia real:
        # V301.B#1/#2/#5, larguras [111,63,244] sem nenhum painel <28cm,
        # tem zero cotas 14/15 no N2). Mesmo criterio usado em
        # gerar_lv_dxf_stog.py::draw_lv_face para o laco espelhado.
        has_narrow_strip = bool(widths) and (
            widths[0] < 28.0 or widths[-1] < 28.0
        )

        # Cadeia com marcos estreitos nas duas pontas: os dois últimos não
        # pertencem à cotagem útil. Completa o prefixo antes do painel largo
        # (111 + 21,8 + 28,7 = 161,5) e remove o residual 46.
        lead = 0
        while lead < len(widths) and widths[lead] < 28.0:
            lead += 1
        tail = len(widths)
        if (
            tail - lead >= 3 and widths[-1] < 28.0 and widths[-2] < 28.0
            and widths[-1] + widths[-2] < 55.0
        ):
            tail -= 2
        trimmed_tail = tail < len(widths)
        useful = widths[lead:tail]
        wide_positions = [i for i, value in enumerate(useful) if value >= 150.0]
        if trimmed_tail and wide_positions and wide_positions[-1] > 0:
            prefix = round(sum(useful[:wide_positions[-1]]), 1)
            if prefix >= 55.0:
                residual = motor._fmt_dim_cm(sum(widths[tail:]))
                for ent in list(msp):
                    if (
                        ent.dxftype() == "DIMENSION" and ent.dxf.layer == "COTA"
                        and str(ent.dxf.get("text", "")) == residual
                        and x0 - 1.0 <= ent.dxf.defpoint2.x <= right + 1.0
                    ):
                        msp.delete_entity(ent)
                        changed = True
                motor.dim_panel_lv(
                    msp, x0, x0 + prefix, y0,
                    text_override=motor._fmt_dim_cm(prefix), level=1,
                )
                changed = True

        for ent in msp:
            if (
                ent.dxftype() == "DIMENSION" and ent.dxf.layer == "COTA"
                and str(ent.dxf.get("text", "")) == "64"
                and x0 - 1.0 <= ent.dxf.defpoint2.x <= right + 1.0
            ):
                ent.dxf.text = "65"
                changed = True

        if trailing_step and ls > 0.5 and has_narrow_strip:
            label = motor._fmt_dim_cm(15.0 if 17.5 <= ls <= 24.0 else ls)
            dims = [
                ent for ent in msp
                if ent.dxftype() == "DIMENSION" and ent.dxf.layer == "COTA"
                and str(ent.dxf.get("text", "")) == label
                and y0 + h - 1.0 <= ent.dxf.defpoint2.y <= y0 + h + ls + 1.0
            ]
            has_right_dim = any(
                abs(ent.dxf.defpoint2.x - right) < 0.5 for ent in dims
            )
            seen = set()
            for ent in dims:
                key = (
                    round(ent.dxf.defpoint2.x, 1), round(ent.dxf.defpoint2.y, 1),
                    round(ent.dxf.defpoint3.x, 1), round(ent.dxf.defpoint3.y, 1),
                )
                if key in seen:
                    msp.delete_entity(ent)
                    changed = True
                else:
                    seen.add(key)
            if not has_right_dim:
                d15 = msp.add_linear_dim(
                    base=(right + motor.DIM_H_RIGHT, y0 + h),
                    p1=(right, y0 + h), p2=(right, y0 + h + ls),
                    angle=90, dimstyle="PAINEL", dxfattribs={"layer": "COTA"},
                )
                d15.render()
                motor._apply_dim_text(
                    d15, label,
                    (right + motor.DIM_H_RIGHT + 4.0, y0 + h + ls / 2.0),
                )
                changed = True

        top_h = float(unit.get("painel_sup_alt", 0) or 0)
        top_w = float(unit.get("painel_sup_width", 0) or 0)
        top_off = float(unit.get("painel_sup_x_offset", 0) or 0)
        if top_h <= 0.5 or top_w <= 0.5:
            continue

        tx0 = x0 + top_off
        ty0 = y0 + h + ls
        tx1 = tx0 + top_w
        # O motor principal desenha o retangulo usando a mesma ocorrencia da
        # ficha. Aqui entram somente as cotas complementares de 7 cm e total.
        for vx, direction in ((tx0, -1.0), (tx1, 1.0)):
            base_x = vx + direction * motor.DIM_H_RIGHT
            dim = msp.add_linear_dim(
                base=(base_x, ty0), p1=(vx, ty0), p2=(vx, ty0 + top_h),
                angle=90, dimstyle="PAINEL", dxfattribs={"layer": "COTA"},
            )
            dim.render()
            motor._apply_dim_text(
                dim, motor._fmt_dim_cm(top_h),
                (base_x + direction * 4.0, ty0 + top_h / 2.0),
            )

        anchor = x0 if trailing_step else right
        direction = -1.0 if trailing_step else 1.0
        old_total = motor._fmt_dim_cm(h + li + ls)
        for ent in list(msp):
            if (ent.dxftype() == "DIMENSION" and ent.dxf.layer == "COTA"
                    and str(ent.dxf.get("text", "")) == old_total
                    and y0 - li - 1.0 <= ent.dxf.defpoint2.y <= y0 + 1.0
                    and abs(ent.dxf.defpoint2.x - anchor) < 0.5):
                msp.delete_entity(ent)
        total = h + li + ls + top_h
        total_text = motor._fmt_dim_cm(total)
        # O motor principal (gerar_lv_dxf_stog.py) ja desenha a cota total
        # (h + laje + marco + painel superior) na ancora real do corpo
        # (_body_end), quando ha marco. O `anchor` daqui e recalculado a
        # partir de largura bruta (sem parar na faixa de marco) e pode nao
        # coincidir com essa ancora real — desenhar sempre duplicava a
        # cota (ex. "124 extra" em V301.B). So completa quando o motor
        # principal nao desenhou nenhuma cota com esse valor nesta unidade.
        has_total_already = any(
            ent.dxftype() == "DIMENSION" and ent.dxf.layer == "COTA"
            and str(ent.dxf.get("text", "")) == total_text
            and x0 - 1.0 <= ent.dxf.defpoint2.x <= right + 1.0
            for ent in msp
        )
        if not has_total_already:
            dt = msp.add_linear_dim(
                base=(anchor + direction * 2.0 * motor.DIM_H_RIGHT, y0 - li),
                p1=(anchor, y0 - li), p2=(anchor, y0 + h + ls + top_h),
                angle=90, dimstyle="PAINEL", dxfattribs={"layer": "COTA"},
            )
            dt.render()
            motor._apply_dim_text(
                dt, motor._fmt_dim_cm(total),
                (anchor + direction * (2.0 * motor.DIM_H_RIGHT + 4.0),
                 y0 - li + total / 2.0),
            )
            changed = True

    if changed:
        doc.saveas(str(path))
