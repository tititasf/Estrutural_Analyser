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
        # bbox[1] (y_bot do layout) inclui o painel de fechamento no vao de
        # baixo quando ele existe — sem somar de volta, y0 saia 7cm abaixo
        # do real (achado ponto-a-ponto em V301.B, 2026-08-29: a cota do
        # painel de fechamento saia duplicada 7cm mais baixo que a certa).
        _top_h_for_y0 = float(unit.get("painel_sup_alt", 0) or 0)
        x0 = float(crop[0]) + 25.0
        y0 = float(crop[1]) + li + motor.DIM_TOTAL_BELOW + 25.0 + _top_h_for_y0
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
                motor.emitir_cota(
                    msp, origem="augment:laje_dir",
                    base=(right + motor.DIM_H_RIGHT, y0 + h),
                    p1=(right, y0 + h), p2=(right, y0 + h + ls),
                    angle=90,
                    texto=label,
                    texto_pos=(right + motor.DIM_H_RIGHT + 4.0,
                               y0 + h + ls / 2.0),
                )
                changed = True

        top_h = float(unit.get("painel_sup_alt", 0) or 0)
        top_w = float(unit.get("painel_sup_width", 0) or 0)
        top_off = float(unit.get("painel_sup_x_offset", 0) or 0)
        if top_h <= 0.5 or top_w <= 0.5:
            continue

        tx0 = x0 + top_off
        tx1 = tx0 + top_w
        # ANCORA NO DESENHO, nao na aritmetica propria. Este modulo recompoe
        # y0 a partir do crop (`crop[1] + li + DIM_TOTAL_BELOW + 25 + top_h`)
        # e isso diverge do frame do gerador: medido na V302.B, o painel de
        # fechamento e a cota total saiam 4 cm abaixo do topo real da laje —
        # a cota "3" flutuando no meio da faixa e a "59" parando antes do
        # topo, que foi o que o dono leu como "patinhas da cota fora de
        # posicao" (SEGMENTO 1B, P1/P2). O topo da laje ja' esta' desenhado:
        # usa-lo elimina a conta e a divergencia.
        # ESCOPO: so' em unidade com DEGRAU DE LAJE, que e' onde o topo plano
        # passou a ser desenhado e onde a divergencia aparece. Sem o escopo,
        # as unidades da V301 (sem trechos) mudavam: la' o N2 mostra a laje de
        # 15 e NENHUMA faixa de 7 acima dela — o "7" e' outra coisa — e a
        # ancora pela hachura punha a cota dentro da laje, expondo uma
        # duplicata que ate' entao ficava empilhada no mesmo y.
        _tem_degrau_laje = bool([
            t for t in (unit.get("laje_sup_trechos") or [])
            if float(t.get("altura", 0) or 0) > 0
        ])
        _topo_laje = None
        _fundo_laje = None
        for _ht in (msp if _tem_degrau_laje else ()):
            if _ht.dxftype() != "HATCH" or _ht.dxf.pattern_name != "AR-CONC":
                continue
            _pts = []
            for _path in _ht.paths:
                for _v in getattr(_path, "vertices", []) or []:
                    _pts.append((_v[0], _v[1]))
            if not _pts:
                continue
            _xs = [q[0] for q in _pts]
            if min(_xs) > right + 1.0 or max(_xs) < x0 - 1.0:
                continue
            _ys = [q[1] for q in _pts]
            _topo_laje = max(_topo_laje or -1e9, max(_ys))
            _fundo_laje = min(_fundo_laje if _fundo_laje is not None else 1e9,
                              min(_ys))
        ty0 = (float(_topo_laje) - top_h if _topo_laje is not None
               else y0 + h + ls)
        # O FUNDO da laje e' o topo do corpo; o fundo do corpo esta' `h`
        # abaixo dele. Ancorar so' o topo no desenho e deixar o pe' em
        # `y0 - li` fazia a cota total medir 62,6 com o texto dizendo 59
        # (V302.B). O dono apontou exatamente isso: "deveria medir de p3 a
        # p4", sendo p3 o topo da laje e p4 o fundo do corpo.
        _fundo_corpo = (float(_fundo_laje) - h if _fundo_laje is not None
                        else y0 - li)
        # O motor principal (draw_lv_face, bloco `d7`) ja desenha essa mesma
        # cota de 7cm do painel de fechamento nos dois lados, na mesma
        # ancora (vx, ty0). Sem este guard duplicava (achado ponto-a-ponto
        # em V301.B, 2026-08-29 — "cota de 7 duplicada"), igual ao guard
        # `has_total_already` logo abaixo para a cota total.
        top_h_text = motor._fmt_dim_cm(top_h)
        # Mesma regra do gerador (bloco `d7`): UMA cota, na ponta do painel
        # que encosta na borda da face. Medido no N2 da V13 — face A, painel
        # a esquerda: "3" em x=2.0; face B, painel a direita: "3" em x=436.6.
        # Sem isto, o gerador emitia na ponta certa e este modulo preenchia a
        # outra, mantendo 2 por face (apontamento do dono P1-P4, 2026-09-13).
        # So' quando o painel NAO cobre a face inteira — cobrindo tudo, as duas
        # pontas encostam na borda e nao ha' evidencia de qual e' a certa
        # (V301.B: 8 unidades com painel de 7 sobre os 418 da face).
        # ESCOPO: so' em unidade com DEGRAU DE LAJE — mesmo motivo do gerador.
        _pontas = [(tx0, -1.0), (tx1, 1.0)]
        if [t for t in (unit.get("laje_sup_trechos") or [])
                if float(t.get("altura", 0) or 0) > 0]:
            _tol = 2.0
            _enc_esq = abs(tx0 - x0) <= _tol
            _enc_dir = abs(tx1 - right) <= _tol
            if _enc_esq and not _enc_dir:
                _pontas = [(tx0, -1.0)]
            elif _enc_dir and not _enc_esq:
                _pontas = [(tx1, 1.0)]
        for vx, direction in _pontas:
            # A guarda NAO pode exigir y exato. O gerador ancora a cota em
            # `y0 + h + _marco_extension_cm(...)` e aqui a ancora e'
            # `y0 + h + ls` (laje_sup da unidade) — os dois valores divergem
            # (V13: 12 contra ~16), o `abs(... - ty0) < 0.5` nunca casava e a
            # cota saia DUPLICADA: 4 por face, com o N2 tendo uma so'
            # (medido na V13 face A: unico "3" em x=2.0). Apontado pelo dono
            # em 2026-09-13 (P1-P4).
            #
            # Mesmo texto, mesmo x e dentro da faixa da laje = e' a mesma
            # cota, venha de qual emissor vier.
            _y_lo = y0 + h - 1.0
            _y_hi = y0 + h + ls + top_h + 12.0
            has_top_h_already = any(
                ent.dxftype() == "DIMENSION" and ent.dxf.layer == "COTA"
                and str(ent.dxf.get("text", "")) == top_h_text
                and abs(ent.dxf.defpoint2.x - vx) < 0.5
                and _y_lo <= ent.dxf.defpoint2.y <= _y_hi
                for ent in msp
            )
            if has_top_h_already:
                continue
            base_x = vx + direction * motor.DIM_H_RIGHT
            motor.emitir_cota(
                msp, origem="augment:painel_topo_h",
                base=(base_x, ty0), p1=(vx, ty0), p2=(vx, ty0 + top_h),
                angle=90,
                texto=top_h_text,
                texto_pos=(base_x + direction * 4.0, ty0 + top_h / 2.0),
            )
            changed = True

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
            motor.emitir_cota(
                msp, origem="augment:total",
                base=(anchor + direction * 2.0 * motor.DIM_H_RIGHT,
                      _fundo_corpo),
                # Mesma ancora do painel de fechamento: o topo REAL do
                # desenho, nao `y0 + h + ls + top_h`. Na V302.B a diferenca
                # era de 4 cm e a cota total parava antes do topo da laje.
                p1=(anchor, _fundo_corpo),
                p2=(anchor, (float(_topo_laje) if _topo_laje is not None
                             else y0 + h + ls + top_h)),
                angle=90,
                texto=motor._fmt_dim_cm(total),
                texto_pos=(anchor + direction * (2.0 * motor.DIM_H_RIGHT + 4.0),
                           y0 - li + total / 2.0),
            )
            changed = True

    if changed:
        doc.saveas(str(path))
