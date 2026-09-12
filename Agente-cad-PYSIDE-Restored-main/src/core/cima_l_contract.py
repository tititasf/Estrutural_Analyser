"""Contrato editável do CIMA L — grades, quadradinhos, parafusos, desvio.

Espelha os campos do legado SCR (globais L, par_a/par_e, detalhes de grade)
para o payload DXF e a ficha web. O desenho consome exatamente este contrato.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

from src.core.pillar_special_faces import secao_l_from_points

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def globais_pilar_especial_l(
    comp_1: float, comp_2: float, larg_1: float, larg_2: float,
) -> dict[str, float]:
    c1, c2 = float(comp_1), float(comp_2)
    l1, l2 = float(larg_1), float(larg_2)
    return {
        "pilar1_paia_tamanho": c1 + 22.0,
        "pilar1_paib_tamanho": c1 - l2 - 18.5 + 11.0 + 4.4,
        "pilar1_gradea_tamanho": c1 + 22.0,
        "pilar1_gradeb_tamanho": c1 - l2 - 18.5 + 11.0,
        "pilar1_parafuso_tamanho": c1 - l2 - 30.0 + 22.0,
        "pilar2_paia_tamanho": c2 + l1 + 11.0,
        "pilar2_paib_tamanho": c2 + 11.0,
        "pilar2_gradea_tamanho": c2 + l1 + 11.0,
        "pilar2_gradeb_tamanho": c2 + 11.0 - 18.5,
        "pilar2_parafuso_tamanho": c1 - l2 - 30.0 - 11.0,
        "pilar2_parafuso_posicao": 41.0,
        "comp_1": c1, "comp_2": c2, "larg_1": l1, "larg_2": l2,
    }


def _n1_base(pj: dict | None) -> dict:
    if not isinstance(pj, dict):
        return {}
    for key in ("n1_base",):
        nested = pj.get(key)
        if isinstance(nested, dict) and nested:
            return nested
    contract = pj.get("_sa_mode_contract")
    if isinstance(contract, dict):
        nested = contract.get("n1_base")
        if isinstance(nested, dict) and nested:
            return nested
    return {}


def secao_l_do_payload(pj: dict) -> dict[str, float] | None:
    blobs = [pj] if isinstance(pj, dict) else []
    nested = _n1_base(pj)
    if nested:
        blobs.append(nested)
    for blob in blobs:
        special = blob.get("pilar_especial") if isinstance(blob, dict) else None
        section = special.get("secao_l") if isinstance(special, dict) else None
        if isinstance(section, dict):
            try:
                ex = float(section.get("externa_x") or 0.0)
                ix = float(section.get("interna_x") or 0.0)
                ey = float(section.get("externa_y") or 0.0)
                iy = float(section.get("interna_y") or 0.0)
            except (TypeError, ValueError):
                ex = ix = ey = iy = 0.0
            if min(ex, ix, ey, iy) > 0.0 and ix < ex and iy < ey:
                return {"externa_x": ex, "interna_x": ix, "externa_y": ey, "interna_y": iy}
        found = secao_l_from_points(blob.get("geometry_points") if isinstance(blob, dict) else None)
        if found:
            return found
    return None


def is_cima_l(pj: dict | None) -> bool:
    if not isinstance(pj, dict):
        return False
    blobs = [pj, _n1_base(pj)]
    for blob in blobs:
        if not isinstance(blob, dict):
            continue
        if str(blob.get("subtipo_pil") or "").upper() == "L":
            return True
        special = blob.get("pilar_especial") or {}
        if str(special.get("tipo_pilar_especial") or "").upper() == "L":
            return True
    return False


def _floats(raw: Any, limit: int = 8) -> list[float]:
    if not isinstance(raw, (list, tuple)):
        return []
    out: list[float] = []
    for value in raw[:limit]:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number) and number > 0.0:
            out.append(number)
    return out


def _spacings(pj: dict, keys: list[str], fallback: list[float] | None = None) -> list[float]:
    found: list[float] = []
    saw = False
    for key in keys:
        try:
            value = float(pj.get(key) or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        if value > 0.0:
            saw = True
            found.append(value)
        elif saw:
            break
    if found:
        return found
    if fallback is None:
        return [45.0, 45.0]
    return list(fallback)


CIMA_L_GRADE_MODULES = (122.0, 120.0, 80.0, 70.0)
CIMA_L_GRID_CELL = 30.0
CIMA_L_MAX_GRADE = 122.0


def paineis_l_from_secao(secao: dict[str, float]) -> dict[str, float]:
    """Comprimentos de PAINEL das 4 faces longas, medidos no N2 CIMA.

    Haste externa = interno + 11 cm em cada ponta.
    Haste interna = (interno − espessura do ramo) + 11 cm só na ponta livre.
    Ramo externo  = interno + 11 cm só na ponta livre.
    Ramo interno  = (interno − espessura da haste) + 7 cm na ponta livre.
    """
    haste = float(secao["externa_y"])
    ramo = float(secao["externa_x"])
    thick = min(float(secao["interna_x"]), haste - float(secao["interna_y"]))
    return {
        "haste": haste,
        "ramo": ramo,
        "espessura": thick,
        "haste_ext": haste + 22.0,
        "haste_int": haste - thick + 11.0,
        "ramo_ext": ramo + 11.0,
        "ramo_int": ramo - thick + 7.0,
    }


def split_panel_grades(panel: float) -> tuple[list[float], list[float]]:
    """Parte um PAINEL em grades ≤ 122 cm (módulos 122/120/80/70 do N2)."""
    panel = float(panel)
    if panel <= CIMA_L_MAX_GRADE:
        return [round(panel, 4)], []
    best: tuple | None = None
    for a in CIMA_L_GRADE_MODULES:
        for b in CIMA_L_GRADE_MODULES:
            rest = panel - a - b
            if rest < -0.6:
                continue
            if abs(rest) < 0.6:
                gaps: list[float] = []
                score = (0, 0 if a == b else 1, 0.0, -(a + b))
            elif rest <= 16.0:
                gaps = [round(rest, 4)]
                score = (1, 0 if a == b else 1, rest, -(a + b))
            else:
                continue
            widths = [a, b] if a >= b else [b, a]
            cand = (score, widths, gaps)
            if best is None or cand[0] < best[0]:
                best = cand
    if best is not None:
        return [round(w, 4) for w in best[1]], best[2]
    n = max(2, int(math.ceil(panel / CIMA_L_MAX_GRADE)))
    gw = round(panel / n, 4)
    return [gw] * n, []


def _quadradinhos_for_grade(width: float, preferred: Any, bolt_offsets: list[float]) -> list[float]:
    from gerar_pl_dxf_stog import _div_segments, _integer_segments_with_avoidance

    width = float(width)
    pref = [float(v) for v in (preferred or []) if v]
    if pref and abs(sum(pref) - width) < 0.5:
        return [round(v, 4) for v in pref]
    whole = round(width)
    if (
        abs(width - whole) < 1e-4
        and 4 * CIMA_L_GRID_CELL <= whole <= CIMA_L_MAX_GRADE
    ):
        base, remainder = divmod(whole, 4)
        parts = [float(base)] * 4
        for position in ((1, 2) if remainder == 2 else (2,))[:remainder]:
            parts[position] += 1.0
        return parts
    fake = {"grade_1_div_a": preferred}
    try:
        return [round(v, 4) for v in _div_segments(fake, width, "grade_1_div_a", bolt_offsets=bolt_offsets)]
    except Exception:
        return [round(v, 4) for v in _integer_segments_with_avoidance(width, bolt_offsets)]


def _grade_starts_widths(widths: list[float], gaps: list[float]) -> list[float]:
    starts: list[float] = []
    cursor = 0.0
    for index, width in enumerate(widths):
        starts.append(cursor)
        cursor += width
        if index < len(gaps):
            cursor += gaps[index]
    return starts


def _face_divisions(
    pj: dict, widths: list[float], gaps: list[float],
    div_prefix: str, bolt_keys: list[str],
) -> list[list[float]]:
    spacings = _spacings(pj, bolt_keys, fallback=[])
    cursor = -1.0
    offsets: list[float] = []
    for spacing in spacings:
        cursor += spacing
        if cursor > 0:
            offsets.append(cursor)
    divisions: list[list[float]] = []
    for index, start in enumerate(_grade_starts_widths(widths, gaps)):
        gw = widths[index]
        local = [
            offset - start for offset in offsets
            if start - 3.0 <= offset <= start + gw + 3.0
        ]
        preferred = pj.get(f"{div_prefix}_{index + 1}_div_a")
        divisions.append(_quadradinhos_for_grade(gw, preferred, local))
    return divisions


def _face_contract(
    pj: dict, *, name: str, inner: float, panel: float,
    div_prefix: str, bolt_keys: list[str], bolt_start: float,
) -> dict[str, Any]:
    widths, gaps = split_panel_grades(panel)
    divs = _face_divisions(pj, widths, gaps, div_prefix, bolt_keys)
    spacings = _spacings(pj, bolt_keys, fallback=[])
    return {
        "id": name,
        "comprimento_interno": round(inner, 4),
        "grade_externa": round(panel, 4),
        "n_grades": len(widths),
        "grade_width": round(widths[0], 4) if widths else 0.0,
        "grade_widths": [round(w, 4) for w in widths],
        "gaps": [round(g, 4) for g in gaps],
        "quadradinhos": [[round(v, 4) for v in row] for row in divs],
        "parafusos": [round(v, 4) for v in spacings],
        "parafuso_inicio": round(bolt_start, 4),
        "div_prefix": div_prefix,
        "bolt_keys": bolt_keys,
    }


def _arm_contract(
    pj: dict, *, name: str, inner: float, grade_total: float,
    div_prefix: str, bolt_keys: list[str], bolt_start: float,
) -> dict[str, Any]:
    return _face_contract(
        pj, name=name, inner=inner, panel=grade_total,
        div_prefix=div_prefix, bolt_keys=bolt_keys, bolt_start=bolt_start,
    )


def build_cima_l_contract(pj: dict) -> dict[str, Any] | None:
    secao = secao_l_do_payload(pj)
    if not secao:
        return None
    thick = min(secao["interna_x"], secao["externa_y"] - secao["interna_y"])
    haste_len = secao["externa_y"]
    ramo_len = secao["externa_x"]
    globais = globais_pilar_especial_l(haste_len, ramo_len, thick, thick)
    saved = ((pj.get("pilar_especial") or {}).get("cima") or {}) if isinstance(pj, dict) else {}
    if not isinstance(saved, dict):
        saved = {}
    saved_arms = saved.get("arms") if isinstance(saved.get("arms"), dict) else {}
    haste_keys = [f"par_a_{i}" for i in range(1, 9)]
    ramo_keys = [f"par_e_{i}" for i in range(1, 9)]
    if not any(float(pj.get(k) or 0) for k in haste_keys):
        for i in range(1, 9):
            inherited = pj.get(f"par_{i}_{i + 1}")
            if inherited:
                pj[f"par_a_{i}"] = inherited
    # Preferência: campos flat do payload (legado) e depois o contrato salvo.
    if not any(float(pj.get(k) or 0) for k in haste_keys):
        for i, value in enumerate(_floats((saved_arms.get("haste") or {}).get("parafusos")), start=1):
            pj.setdefault(f"par_a_{i}", value)
    if not any(float(pj.get(k) or 0) for k in ramo_keys):
        for i, value in enumerate(_floats((saved_arms.get("ramo") or {}).get("parafusos")), start=1):
            pj.setdefault(f"par_e_{i}", value)
    paineis = paineis_l_from_secao(secao)
    specs = (
        ("haste_ext", paineis["haste"], paineis["haste_ext"], "grade_haste_ext", haste_keys, 0.0),
        ("haste_int", paineis["haste"] - thick, paineis["haste_int"], "grade_haste_int", haste_keys, 0.0),
        ("ramo_ext", paineis["ramo"], paineis["ramo_ext"], "grade_ramo_ext", ramo_keys, globais["pilar2_parafuso_posicao"]),
        ("ramo_int", paineis["ramo"] - thick, paineis["ramo_int"], "grade_ramo_int", ramo_keys, 0.0),
    )
    faces: dict[str, Any] = {}
    for name, inner, panel, prefix, keys, bolt_start in specs:
        alias = "haste" if name.startswith("haste") else "ramo"
        source = saved_arms.get(name) or saved_arms.get(alias) or {}
        face = _face_contract(
            pj, name=name, inner=inner, panel=panel,
            div_prefix=prefix, bolt_keys=keys, bolt_start=bolt_start,
        )
        if isinstance(source, dict) and source.get("quadradinhos"):
            face["quadradinhos"] = source["quadradinhos"]
        if isinstance(source, dict) and source.get("grade_widths"):
            face["grade_widths"] = source["grade_widths"]
            face["n_grades"] = len(source["grade_widths"])
            face["grade_width"] = source["grade_widths"][0]
        if isinstance(source, dict) and source.get("gaps") is not None:
            face["gaps"] = source["gaps"]
        faces[name] = face
    faces["haste"] = faces["haste_ext"]
    faces["ramo"] = faces["ramo_ext"]
    return {
        "schema": "pil.cima_l/v1",
        "secao": {**secao, "espessura": round(thick, 4)},
        "paineis": paineis,
        "globais": globais,
        "arms": faces,
    }


def flatten_cima_l_into_robot(pj: dict, contract: dict | None) -> dict:
    """Grava os campos editáveis no payload do robô (fonte do DXF)."""
    result = dict(pj or {})
    if not contract:
        return result
    special = dict(result.get("pilar_especial") or {})
    special["ativar_pilar_especial"] = True
    special["tipo_pilar_especial"] = "L"
    special["secao_l"] = dict(contract.get("secao") or {})
    special["cima"] = contract
    result["pilar_especial"] = special
    result["subtipo_pil"] = "L"
    arms = contract.get("arms") or {}
    haste = arms.get("haste") or {}
    ramo = arms.get("ramo") or {}
    result["grade_1"] = haste.get("grade_externa") or result.get("grade_1")
    result["grade_2"] = ramo.get("grade_externa") or 0.0
    for index, spacing in enumerate(haste.get("parafusos") or [], start=1):
        result[f"par_a_{index}"] = spacing
        if index <= 8:
            result[f"par_{index}_{index + 1}"] = spacing
    for index, spacing in enumerate(ramo.get("parafusos") or [], start=1):
        result[f"par_e_{index}"] = spacing
    for name, arm in arms.items():
        if name in {"haste", "ramo"}:
            continue
        prefix = arm.get("div_prefix") or f"grade_{name}"
        for index, row in enumerate(arm.get("quadradinhos") or [], start=1):
            result[f"{prefix}_{index}_div_a"] = list(row)
    for index, row in enumerate(haste.get("quadradinhos") or [], start=1):
        result[f"grade_haste_{index}_div_a"] = list(row)
        if index == 1:
            result["grade_1_div_a"] = list(row)
    for index, row in enumerate(ramo.get("quadradinhos") or [], start=1):
        result[f"grade_ramo_{index}_div_a"] = list(row)
    return result


def portal_cima_l_contract(robot: dict) -> dict[str, Any]:
    """Cima_contract da ficha web para pilar L."""
    contract = build_cima_l_contract(robot) or {}
    arms = contract.get("arms") or {}

    def fmt(value: float) -> str:
        return str(int(value)) if abs(value - round(value)) < 1e-6 else f"{value:.1f}"

    def label(values: list) -> str:
        nums = [float(v) for v in (values or []) if v]
        return " | ".join(fmt(v) for v in nums) if nums else "—"

    rows = [["formato", "L — 4 faces longas (haste ext/int + ramo ext/int)"]]
    fields_arms = {}
    titles = [
        ("haste_ext", "Haste externa"),
        ("haste_int", "Haste interna"),
        ("ramo_ext", "Ramo externo"),
        ("ramo_int", "Ramo interno"),
    ]
    if not any(arms.get(key) for key, _title in titles):
        titles = [("haste", "Haste"), ("ramo", "Ramo")]
    for key, title in titles:
        arm = arms.get(key)
        if not arm:
            continue
        widths = arm.get("grade_widths") or ([arm.get("grade_width")] if arm.get("grade_width") else [])
        rows.append([f"{title} comprimento interno", f"{fmt(arm.get('comprimento_interno') or 0)} cm"])
        rows.append([f"{title} PAINEL", f"{fmt(arm.get('grade_externa') or 0)} cm"])
        rows.append([f"{title} layout grades", (
            f"{arm.get('n_grades') or 0} grade(s): {label(widths)} cm; "
            f"gaps {label(arm.get('gaps'))}"
        )])
        rows.append([f"{title} parafusos", f"spacings: {label(arm.get('parafusos'))} cm; início {fmt(arm.get('parafuso_inicio') or 0)}"])
        rows.append([f"{title} quadradinhos", " ; ".join(
            f"G{i + 1}: {label(row)}" for i, row in enumerate(arm.get("quadradinhos") or [])
        )])
        fields_arms[key] = {
            "comprimento_interno": arm.get("comprimento_interno") or 0.0,
            "grade_externa": arm.get("grade_externa") or 0.0,
            "n_grades": arm.get("n_grades") or 0,
            "grade_width": arm.get("grade_width") or 0.0,
            "grade_widths": list(widths),
            "gaps": list(arm.get("gaps") or []),
            "parafusos": (list(arm.get("parafusos") or []) + [None] * 7)[:7],
            "parafuso_inicio": arm.get("parafuso_inicio") or 0.0,
            "quadradinhos": [
                (list(row) + [None] * 5)[:5] for row in (arm.get("quadradinhos") or [[]])[:3]
            ] or [[None] * 5],
        }
    secao = contract.get("secao") or {}
    return {
        "rows": rows,
        "fields": {
            "formato": "L",
            "comprimento_interno": secao.get("externa_y") or 0.0,
            "largura_interna": secao.get("externa_x") or 0.0,
            "espessura": secao.get("espessura") or secao.get("interna_x") or 0.0,
            "especial": fields_arms,
        },
    }
