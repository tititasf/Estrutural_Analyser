# -*- coding: utf-8 -*-
"""Remove phantom V65@244 + paredes marco inventadas; gate FAIL se overdraw.

Problema: para inflar G→100% o motor reintroduziu:
  - V base→ombro no 1º divisor do degrau (x=244) → caixa fantasma na cota 65
  - stubs H no vão do degrau
  - multi-paredes de marco (V mid full, H corpo@y_marco, stubs em massa)

Arete 100% real = miss_g=0 AND extra_g=0 AND miss_r=0 AND inventadas=[].
"""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARETE = Path(__file__).resolve().parent


def patch_motor() -> None:
    p = ROOT / "gerar_lv_dxf_stog.py"
    t = p.read_text(encoding="utf-8")

    # Replace entire _draw_panel_frame_n2 with clean version
    m = re.search(
        r"def _draw_panel_frame_n2\(msp, x0, y0, h, panels, \*,\n"
        r"                          marco_laje_sup=False, laje_sup=0\.0\):",
        t,
    )
    if not m:
        raise SystemExit("frame def not found")
    start = m.start()
    m2 = re.search(r"\ndef _draw_degrau_step_verticals\(", t[start:])
    if not m2:
        raise SystemExit("end marker not found")
    end = start + m2.start()

    new_fn = '''def _draw_panel_frame_n2(msp, x0, y0, h, panels, *,
                          marco_laje_sup=False, laje_sup=0.0):
    """Contorno Painéis N2-fiel — SEM phantoms de degrau/marco.

    Anti-alucinação (ShareX / Arete):
    - 1º divisor do degrau (x=244): SO faixa alta (ombro→topo). NUNCA V
      base→ombro (inventava parede na cota 65 / vão vazio).
    - Divisores intermediarios do vão (272.7…): V base→ombro (N2 real).
    - Fim do degrau (294.5): V base→ombro (parede da cota 65).
    - SEM stubs H no miolo do degrau.
    - Marco: envelope minimo (parede final + topo marco), SEM multi-V mid
      full-height nem H de marco atravessando o corpo inteiro.
    """
    a = {'layer': 'Painéis'}
    if not panels:
        return
    comprimento = sum(float(p.get('width', 0) or 0) for p in panels)
    if comprimento <= 0:
        return
    y_top = y0 + h
    y_shoulder = _degrau_shoulder_y(y0, h, panels)
    degrau_end = _degrau_zone_end_x(x0, h, panels)
    has_degrau = y_shoulder is not None and degrau_end > x0 + 0.5
    small_x = _small_panel_start_x(x0, h, panels)
    marco_h = _marco_extension_cm(marco_laje_sup, laje_sup)
    y_marco = y_top + marco_h if marco_h > 0.5 else y_top

    if has_degrau:
        # N2: parede esquerda so na faixa alta (nao fecha o vao)
        msp.add_line((x0, y_shoulder), (x0, y_top), dxfattribs=a)
    else:
        msp.add_line((x0, y0), (x0, y_top), dxfattribs=a)

    body_end = float(small_x) if small_x is not None else float(x0 + comprimento)
    full_end = float(x0 + comprimento)

    x_cur = float(x0)
    for idx, panel in enumerate(panels):
        pw = float(panel.get('width', 0) or 0)
        x_right = x_cur + pw
        is_last = idx >= len(panels) - 1
        cur_deg = _is_degrau_panel(panel, h)
        next_deg = (not is_last) and _is_degrau_panel(panels[idx + 1], h)
        in_small = small_x is not None and x_cur >= small_x - 0.1

        if in_small:
            x_cur = x_right
            continue

        is_body_end = abs(x_right - body_end) < 0.15

        if is_body_end:
            # parede real do corpo + extensao marco (uma so)
            msp.add_line((x_right, y0), (x_right, y_marco), dxfattribs=a)
        elif has_degrau and cur_deg and next_deg:
            if idx == 0:
                # PHANTOM FIX: so faixa alta — NUNCA V65 inventada em x=244
                msp.add_line((x_right, y_shoulder), (x_right, y_top), dxfattribs=a)
            else:
                # intermediarios reais do N2 (ex. 272.7)
                msp.add_line((x_right, y0), (x_right, y_shoulder), dxfattribs=a)
        elif has_degrau and cur_deg and not next_deg:
            # fim do vao / parede da cota 65 (ex. 294.5)
            msp.add_line((x_right, y0), (x_right, y_shoulder), dxfattribs=a)
        elif has_degrau and (not cur_deg) and next_deg:
            msp.add_line((x_right, y0), (x_right, y_shoulder), dxfattribs=a)
        else:
            msp.add_line((x_right, y0), (x_right, y_top), dxfattribs=a)
        x_cur = x_right

    if has_degrau:
        msp.add_line((x0, y_shoulder), (degrau_end, y_shoulder), dxfattribs=a)

    msp.add_line((x0, y_top), (body_end, y_top), dxfattribs=a)
    if has_degrau and degrau_end < body_end - 0.5:
        msp.add_line((degrau_end, y0), (body_end, y0), dxfattribs=a)
    elif not has_degrau:
        msp.add_line((x0, y0), (body_end, y0), dxfattribs=a)

    # hatch marco em COTA (nao inventa H Painéis no corpo inteiro)
    if marco_h > 0.5:
        _draw_vazio_concreto(msp, x0, y_top, body_end, y_marco)

    # ── marco (estreitos finais): envelope minimo ────────────────────
    if small_x is not None and full_end > body_end + 0.5:
        x_scan = float(x0)
        marco_panels = []
        for panel in panels:
            pw = float(panel.get('width', 0) or 0)
            if x_scan >= body_end - 0.1:
                marco_panels.append((x_scan, x_scan + pw, pw))
            x_scan += pw
        # topo/base do strip + parede final (sem V mid full fantasma)
        msp.add_line((body_end, y0), (full_end, y0), dxfattribs=a)
        msp.add_line((body_end, y_top), (full_end, y_top), dxfattribs=a)
        if marco_h > 0.5:
            msp.add_line((body_end, y_marco), (full_end, y_marco), dxfattribs=a)
        msp.add_line((full_end, y0), (full_end, y_marco), dxfattribs=a)
        # V15 so no meio da 1a faixa estreita de marco (~19) — N2 A
        if 12.0 <= marco_h < 18.0 and marco_panels:
            x_l, x_r, pw = marco_panels[0]
            if 15.0 <= float(pw) <= 22.0:
                x_mid = 0.5 * (x_l + x_r)
                msp.add_line((x_mid, y_top), (x_mid, y_marco), dxfattribs=a)


'''
    t = t[:start] + new_fn + t[end:]
    tmp = p.with_suffix(".py.tmp_patch")
    tmp.write_text(t, encoding="utf-8")
    os.replace(str(tmp), str(p))
    print("motor frame cleaned")


def patch_gate() -> None:
    p = ARETE / "geometry_index.py"
    t = p.read_text(encoding="utf-8")

    old = '''        # FAIL so por inventadas claras (nao por MISSING — clip N2 pode ser ruidoso)
        # EXTRA estrutural so pune se o gabarito NAO esta 100% coberto.
        if invented:
            verdict = "FAIL E2E"
        elif r_match >= 0.999 and g_match >= 0.999 and not invented:
            verdict = "PASS E2E"
            reasons.append("cobertura TOTAL G+R do gabarito (Arete 100%)")
            if len(extra_g) > 0:
                reasons.append(f"N4 tem {len(extra_g)} linhas a mais (overdraw, gabarito coberto)")
        elif len(extra_g) > 14:
            verdict = "FAIL E2E"
            reasons.append("EXTRA estrutural excessivo")
'''
    new = '''        # Detecta phantoms classicos (ShareX): V~65 no 1o divisor do degrau,
        # paredes mid de marco full-height inventadas.
        phantoms = cls._detect_phantoms(extra_g, gabarito)
        if phantoms:
            reasons.append(f"PHANTOM N4: {phantoms[:8]}")

        # FAIL por inventadas de cota OU phantoms de silhueta OU overdraw em Arete.
        if invented:
            verdict = "FAIL E2E"
        elif phantoms:
            verdict = "FAIL E2E"
            reasons.append("linhas fantasma (degrau 65 / parede marco) — nao e Arete")
        elif r_match >= 0.999 and g_match >= 0.999 and not invented and len(extra_g) == 0:
            verdict = "PASS E2E"
            reasons.append("Arete 100%: G+R cobertos e zero EXTRA estrutural")
        elif r_match >= 0.999 and g_match >= 0.999 and not invented and len(extra_g) > 0:
            # cobertura do gabarito ok mas N4 desenha a mais → nao chamar 100%
            verdict = "SUSPEITO"
            reasons.append(
                f"OVERDRAW: gabarito coberto mas N4 tem {len(extra_g)} linhas extras"
            )
        elif len(extra_g) > 14:
            verdict = "FAIL E2E"
            reasons.append("EXTRA estrutural excessivo")
'''
    if old not in t:
        raise SystemExit("gate verdict block not found")
    t = t.replace(old, new, 1)

    # inject detector before _invented_extras or after match_cotas classmethods
    detector = '''
    @staticmethod
    def _detect_phantoms(extra_g: list, gabarito: "GeometryIndex") -> list[str]:
        """Reconhece overdraw classico que inflava G sem fidelidade visual.

        - PHANTOM_DEGRAU_V65: vertical ~65 no 1o vao (x~244) sob o ombro
        - PHANTOM_MARCO_MID_V: V full no meio de faixa de marco
        """
        tags: list[str] = []
        if not extra_g:
            return tags
        h = float(getattr(gabarito, "h_body", 0) or 0) or 100.0
        widths = list(getattr(gabarito, "panel_widths", None) or [])
        x_first = float(widths[0]) if widths else 244.0
        for L in extra_g:
            try:
                from arete.geometry_index import _mid_rel, _f
            except Exception:
                continue
            o = L.get("orient")
            fam = str(L.get("family") or "")
            if "PAIN" not in fam.upper() and fam not in ("Painéis", "Paineis"):
                continue
            ln = _f(L.get("length_cm"))
            mx, my = _mid_rel(L)
            # V ~ ombro (50-80) com mid-x no 1o painel longo (degrau)
            if o == "V" and 50.0 <= ln <= 80.0 and abs(mx - x_first) <= 8.0 and my < h * 0.55:
                tags.append(f"DEGRAU_V65@x={mx:.0f}")
            # V full-ish no strip de marco (x > soma painéis uteis)
            body = sum(w for w in widths if w >= 28) if widths else 0.0
            if o == "V" and ln >= h * 0.85 and body > 50 and mx > body + 5:
                tags.append(f"MARCO_MID_V@x={mx:.0f}/L={ln:.0f}")
        # unique preserve order
        out, seen = [], set()
        for t in tags:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out

'''
    # insert before _invented_extras
    anchor = "    @staticmethod\n    def _invented_extras("
    if "def _detect_phantoms" not in t:
        if anchor not in t:
            raise SystemExit("invented_extras anchor missing")
        t = t.replace(anchor, detector + anchor, 1)
        print("detector injected")
    else:
        print("detector already present")

    # store panel_widths/h_body on GeometryIndex if not already
    # from_dxf already has h_body and total_w - check GeometryIndex class
    if "self.panel_widths" not in t:
        # try attach in from_dxf
        old_from = "        idx = cls(\n"
        # simpler: set attributes after construction in from_dxf
        pass

    tmp = p.with_suffix(".py.tmp_patch")
    tmp.write_text(t, encoding="utf-8")
    os.replace(str(tmp), str(p))
    print("gate patched")


def patch_index_attrs() -> None:
    """Ensure GeometryIndex keeps panel_widths for phantom detector."""
    p = ARETE / "geometry_index.py"
    t = p.read_text(encoding="utf-8")
    if "self.panel_widths" in t:
        print("attrs ok")
        return
    # find from_dxf return / construction
    # look for dataclass or __init__
    if "class GeometryIndex" in t and "panel_widths" not in t.split("class GeometryIndex")[1][:800]:
        # after from_dxf creates object, set attrs
        # search typical pattern
        m = re.search(r"(idx\s*=\s*cls\([^)]+\)\s*\n)", t)
        if not m:
            # try GeometryIndex(
            print("warn: could not wire panel_widths attr automatically")
            return
    # Set on object after from_dxf
    old = None
    for pat in (
        "return idx\n",
        "return GeometryIndex(",
    ):
        if "return idx" in t and "panel_widths=panel_widths" not in t:
            t2 = t.replace(
                "return idx\n",
                "        idx.panel_widths = list(panel_widths or [])\n"
                "        idx.h_body = float(h_body)\n"
                "        return idx\n",
                1,
            )
            if t2 != t:
                t = t2
                print("from_dxf attrs set")
                break
    tmp = p.with_suffix(".py.tmp_patch")
    tmp.write_text(t, encoding="utf-8")
    os.replace(str(tmp), str(p))


if __name__ == "__main__":
    patch_motor()
    patch_gate()
    patch_index_attrs()
