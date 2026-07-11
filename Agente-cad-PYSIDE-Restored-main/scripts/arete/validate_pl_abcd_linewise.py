#!/usr/bin/env python3
"""Validação visual RIGOROSA linha-a-linha: DXF manual × gerado (ABCD PIL).

Critério: CADA segmento do manual deve casar com exatamente um do gerado
(camada, orientação H/V, comprimento, endpoints). Nada de "parece igual".

Produz:
  1. Inventário 100% das linhas do manual com status MATCHED/MISSING
  2. Extras do gerado (não cobrem nenhuma linha do manual)
  3. Checklist estrutural por face (A/B/C/D)
  4. Prompt VISION criterioso (para o agente CLI ler PNG/DXF)
  5. JSON report + gates

Uso:
  py -3.12 scripts/arete/validate_pl_abcd_linewise.py
  py -3.12 scripts/arete/validate_pl_abcd_linewise.py --manual PATH --gen PATH
  py -3.12 scripts/arete/validate_pl_abcd_linewise.py --strict
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import ezdxf

DEFAULT_MANUAL = Path(
    r"D:\Agente-cad-PYSIDE\Desing-Visual-DXF\PL_ABCD_preview_P1_PARA_13PAV_OBRATREIN_1.dxf"
)
DEFAULT_GEN = Path(
    r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-6_Execucao_CAD\n3_variants\para\PL_ABCD_preview_P1.dxf"
)

LAYER_ALIASES = {
    "Painéis": {"Painéis", "Paineis"},
    "Paineis": {"Painéis", "Paineis"},
    "Sarrafo de Pressão": {"Sarrafo de Pressão", "SARRAFO DE PRESSAO"},
    "SARRAFO DE PRESSAO": {"Sarrafo de Pressão", "SARRAFO DE PRESSAO"},
}

# Layers estruturais que contam no match linewise (ignora legenda solta)
STRUCT_LAYERS = {
    "Painéis",
    "Paineis",
    "SARR_2.2x7",
    "Sarrafo de Pressão",
    "SARRAFO DE PRESSAO",
    "COTA",
    "Nível",
}


def layer_eq(a: str, b: str) -> bool:
    if a == b:
        return True
    return b in LAYER_ALIASES.get(a, set()) or a in LAYER_ALIASES.get(b, set())


def orient(s) -> str:
    if abs(s["x1"] - s["x2"]) < 0.6:
        return "V"
    if abs(s["y1"] - s["y2"]) < 0.6:
        return "H"
    return "D"


def face_of(x: float) -> str:
    if 70 <= x <= 190:
        return "A"
    if 300 <= x <= 430:
        return "B"
    if 520 <= x <= 600:
        return "C"
    if 660 <= x <= 760:
        return "D"
    return "?"


def role_of(s) -> str:
    """Classifica papel semântico da linha (para o prompt vision)."""
    layer = s["layer"]
    o = orient(s)
    L = s["L"]
    face = face_of((s["x1"] + s["x2"]) / 2)
    ymid = (s["y1"] + s["y2"]) / 2
    if layer in ("Nível",):
        return "nivel_global"
    if "Press" in layer or "PRESS" in layer:
        return f"pressao_{face}_{o}"
    if layer.startswith("SARR"):
        if L < 8:
            return f"sarr_L_canto_{face}"
        if o == "V" and L > 50:
            return f"sarr_vertical_marco_ou_abertura_{face}"
        if o == "H" and L <= 50:
            return f"sarr_travessa_ou_barra_{face}"
        return f"sarr_{face}_{o}"
    if layer in ("Painéis", "Paineis"):
        if o == "V" and L > 250:
            return f"painel_borda_full_{face}"
        if o == "V" and L > 150:
            return f"painel_borda_parcial_{face}"
        if o == "V" and 5 < L < 15:
            return f"painel_rebaixo_vertical_{face}"
        if o == "V":
            return f"painel_inner_abertura_{face}"
        if o == "H" and L > 70:
            return f"painel_H_full_ou_quase_{face}"
        if o == "H" and 40 <= L <= 55:
            return f"painel_H_miolo_marco_{face}"
        if o == "H" and L < 35:
            return f"painel_H_fundo_abertura_{face}"
        return f"painel_{face}_{o}"
    if layer == "COTA":
        if o == "V" and L > 50:
            return f"cota_contorno_vazio_{face}"
        if o == "H" and L < 40:
            return f"cota_stub_topo_{face}"
        if o == "D":
            return f"cota_leader_SP_{face}"
        return f"cota_{face}_{o}"
    return f"outro_{layer}_{face}"


def extract(path: Path):
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    segs = []
    dims = []
    texts = []
    hatches = []
    leaders = 0
    for e in msp:
        layer = e.dxf.layer if e.dxf.hasattr("layer") else "?"
        lt = e.dxf.linetype if e.dxf.hasattr("linetype") else "BYLAYER"
        if e.dxftype() == "LINE":
            x1, y1 = float(e.dxf.start.x), float(e.dxf.start.y)
            x2, y2 = float(e.dxf.end.x), float(e.dxf.end.y)
            L = math.hypot(x2 - x1, y2 - y1)
            if L < 0.05:
                continue
            segs.append(
                {
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "L": L,
                    "layer": layer,
                    "lt": lt,
                    "src": "LINE",
                }
            )
        elif e.dxftype() == "LWPOLYLINE":
            pts = [(float(p[0]), float(p[1])) for p in e.get_points("xy")]
            n = len(pts)
            closed = bool(e.closed)
            for i in range(n if closed else max(0, n - 1)):
                a = pts[i]
                b = pts[(i + 1) % n]
                L = math.hypot(b[0] - a[0], b[1] - a[1])
                if L < 0.05:
                    continue
                segs.append(
                    {
                        "x1": a[0],
                        "y1": a[1],
                        "x2": b[0],
                        "y2": b[1],
                        "L": L,
                        "layer": layer,
                        "lt": lt,
                        "src": "LWPOLY",
                    }
                )
        elif e.dxftype() == "DIMENSION":
            try:
                m = e.get_measurement()
            except Exception:
                m = None
            dims.append(
                {
                    "m": m,
                    "style": e.dxf.dimstyle if e.dxf.hasattr("dimstyle") else "?",
                    "layer": layer,
                }
            )
        elif e.dxftype() in ("TEXT", "MTEXT"):
            t = e.dxf.text if e.dxftype() == "TEXT" else e.text
            texts.append({"t": str(t), "layer": layer})
        elif e.dxftype() == "LEADER":
            leaders += 1
        elif e.dxftype() == "HATCH":
            paths = []
            for path in e.paths:
                verts = []
                if hasattr(path, "vertices") and path.vertices:
                    verts = [(float(v[0]), float(v[1])) for v in path.vertices]
                elif hasattr(path, "edges"):
                    for edge in path.edges:
                        if hasattr(edge, "start"):
                            verts.append((float(edge.start[0]), float(edge.start[1])))
                        if hasattr(edge, "end"):
                            verts.append((float(edge.end[0]), float(edge.end[1])))
                if verts:
                    xs = [v[0] for v in verts]
                    ys = [v[1] for v in verts]
                    paths.append(
                        {
                            "w": max(xs) - min(xs),
                            "h": max(ys) - min(ys),
                            "x0": min(xs),
                            "y0": min(ys),
                            "x1": max(xs),
                            "y1": max(ys),
                        }
                    )
            try:
                pscale = float(e.dxf.pattern_scale) if e.dxf.hasattr("pattern_scale") else None
            except Exception:
                pscale = None
            try:
                pangle = float(e.dxf.pattern_angle) if e.dxf.hasattr("pattern_angle") else None
            except Exception:
                pangle = None
            try:
                color = int(e.dxf.color) if e.dxf.hasattr("color") else None
            except Exception:
                color = None
            hatches.append(
                {
                    "layer": layer,
                    "pattern": e.dxf.pattern_name
                    if e.dxf.hasattr("pattern_name")
                    else "?",
                    "scale": pscale,
                    "angle": pangle,
                    "color": color,
                    "paths": paths,
                }
            )
    return {
        "segs": segs,
        "dims": dims,
        "texts": texts,
        "hatches": hatches,
        "leaders": leaders,
    }


def bbox_segs(segs):
    xs, ys = [], []
    for s in segs:
        xs += [s["x1"], s["x2"]]
        ys += [s["y1"], s["y2"]]
    return min(xs), min(ys), max(xs), max(ys)


def shift_segs(segs, dx, dy):
    out = []
    for s in segs:
        t = dict(s)
        t["x1"] += dx
        t["x2"] += dx
        t["y1"] += dy
        t["y2"] += dy
        out.append(t)
    return out


def endpoints_dist(m, g) -> float:
    """Menor soma de distâncias entre endpoints (respeita orientação)."""
    d_same = math.hypot(g["x1"] - m["x1"], g["y1"] - m["y1"]) + math.hypot(
        g["x2"] - m["x2"], g["y2"] - m["y2"]
    )
    d_flip = math.hypot(g["x1"] - m["x2"], g["y1"] - m["y2"]) + math.hypot(
        g["x2"] - m["x1"], g["y2"] - m["y1"]
    )
    return min(d_same, d_flip)


def center_dist(m, g) -> float:
    mx = (m["x1"] + m["x2"]) / 2
    my = (m["y1"] + m["y2"]) / 2
    gx = (g["x1"] + g["x2"]) / 2
    gy = (g["y1"] + g["y2"]) / 2
    return math.hypot(gx - mx, gy - my)


def covers_segment(m, g, tol=1.5) -> bool:
    """Gen cobre o segmento manual (mesma reta, gen >= manual).

    Útil p/ pressão HIDDEN desenhada contínua no gen mas partida no manual.
    """
    if orient(m) != orient(g):
        return False
    if not layer_eq(m["layer"], g["layer"]):
        return False
    o = orient(m)
    if o == "V":
        if abs(((g["x1"] + g["x2"]) / 2) - ((m["x1"] + m["x2"]) / 2)) > tol:
            return False
        g_lo, g_hi = sorted([g["y1"], g["y2"]])
        m_lo, m_hi = sorted([m["y1"], m["y2"]])
        return g_lo <= m_lo + tol and g_hi >= m_hi - tol
    if o == "H":
        if abs(((g["y1"] + g["y2"]) / 2) - ((m["y1"] + m["y2"]) / 2)) > tol:
            return False
        g_lo, g_hi = sorted([g["x1"], g["x2"]])
        m_lo, m_hi = sorted([m["x1"], m["x2"]])
        return g_lo <= m_lo + tol and g_hi >= m_hi - tol
    return False


def match_seg(
    m,
    pool,
    used,
    *,
    tol_pos=1.0,
    tol_len=1.0,
    require_layer=True,
    require_orient=True,
    allow_cover=False,
):
    """Casa 1:1. Exige layer + orientação + comprimento + endpoints.

    Se allow_cover=True, aceita gen mais longo na mesma reta (pressão partida).
    """
    best = None
    best_score = 1e18
    best_mode = "exact"
    mo = orient(m)
    for i, g in enumerate(pool):
        if i in used:
            continue
        if require_layer and not layer_eq(m["layer"], g["layer"]):
            continue
        if require_orient and orient(g) != mo:
            continue
        # exact length match
        len_ok = abs(g["L"] - m["L"]) <= tol_len
        cover_ok = allow_cover and covers_segment(m, g, tol=tol_pos)
        if not len_ok and not cover_ok:
            continue
        d_end = endpoints_dist(m, g)
        d_c = center_dist(m, g)
        if len_ok and d_end <= tol_pos * 2.0:
            score = d_end + 0.3 * d_c + abs(g["L"] - m["L"])
            mode = "exact"
        elif cover_ok:
            # penaliza cover (prefer exact)
            score = 50.0 + d_c + abs(g["L"] - m["L"]) * 0.1
            mode = "cover"
        else:
            continue
        if score < best_score:
            best_score = score
            best = i
            best_mode = mode
    return best, best_score, best_mode


def content_segs(segs):
    out = []
    for s in segs:
        if s["layer"] not in ("Painéis", "Paineis"):
            continue
        ys = (s["y1"], s["y2"])
        if min(ys) < -450 or max(ys) > -50:
            continue
        if s["L"] > 900:
            continue
        out.append(s)
    return out or [s for s in segs if s["L"] < 500]


def structural_checklist(matched_roles: set, missing_list, extra_list) -> list[tuple[str, bool, str]]:
    """Gates semânticos por face — o que o dono olha no desenho."""
    checks = []

    def has_role_prefix(prefix: str) -> bool:
        return any(r.startswith(prefix) or prefix in r for r in matched_roles)

    def missing_role(substr: str) -> int:
        return sum(1 for m in missing_list if substr in role_of(m))

    # Face A — abertura direita única (11cm)
    checks.append(
        (
            "A_pressao_esquerda_ate_topo",
            missing_role("pressao_A") == 0
            or any(
                abs(m["L"] - 124) < 2 and abs((m["x1"] + m["x2"]) / 2 - 87) < 2
                for m in missing_list
                if "Press" in m["layer"] or "PRESS" in m["layer"]
            )
            is False,
            "Pressão A em x≈87 deve cobrir corpo+abertura (178+124 ou 302)",
        )
    )
    # More concrete structural checks from inventory
    def need(desc, pred):
        checks.append((desc, pred, ""))

    # Count matched by face+layer key
    # Better: check critical geometry present in matched set
    return checks  # filled below in main with concrete geometry


def build_vision_prompt(
    *,
    manual_path: Path,
    gen_path: Path,
    inventory: list[dict],
    missing: list,
    extra: list,
    match_rate: float,
    dims_miss,
    dims_extra,
    hatch_miss,
    hatch_extra,
    texts_m,
    texts_g,
) -> str:
    """Prompt VISION criterioso: força varredura linha a linha, face a face."""
    lines_miss = []
    for m in sorted(missing, key=lambda s: (face_of((s["x1"] + s["x2"]) / 2), -s["L"])):
        o = orient(m)
        f = face_of((m["x1"] + m["x2"]) / 2)
        r = role_of(m)
        lines_miss.append(
            f"  - [{f}] {m['layer']:22} {o} L={m['L']:.1f} "
            f"({m['x1']:.1f},{m['y1']:.1f})→({m['x2']:.1f},{m['y2']:.1f})  role={r}"
        )
    lines_extra = []
    for g in sorted(extra, key=lambda s: (face_of((s["x1"] + s["x2"]) / 2), -s["L"])):
        o = orient(g)
        f = face_of((g["x1"] + g["x2"]) / 2)
        r = role_of(g)
        lines_extra.append(
            f"  - [{f}] {g['layer']:22} {o} L={g['L']:.1f} "
            f"({g['x1']:.1f},{g['y1']:.1f})→({g['x2']:.1f},{g['y2']:.1f})  role={r}"
        )

    inv_by_face = defaultdict(list)
    for row in inventory:
        inv_by_face[row["face"]].append(row)

    inv_blocks = []
    for face in ("A", "B", "C", "D", "?"):
        rows = inv_by_face.get(face, [])
        if not rows:
            continue
        inv_blocks.append(f"### FACE {face}  ({sum(1 for r in rows if r['status']=='MATCHED')}/{len(rows)} matched)")
        for r in rows:
            mark = "OK" if r["status"] == "MATCHED" else ("COVER" if r["status"] == "COVER" else "FAIL")
            inv_blocks.append(
                f"  [{mark:5}] #{r['idx']:02d} {r['layer']:22} {r['orient']} "
                f"L={r['L']:.1f} ({r['x1']:.1f},{r['y1']:.1f})→({r['x2']:.1f},{r['y2']:.1f}) "
                f"role={r['role']}"
                + (f"  via={r.get('mode','')}" if r["status"] != "MISSING" else "")
            )

    prompt = f"""# PROMPT VISION — PL ABCD linha-a-linha (criterioso)

Você é o validador visual do gerador N3 PIL/ABCD. Compare o **MANUAL (gabarito)** com o **GERADO**.
NÃO aprove por "gestalt" ou "parece similar". Cada linha do inventário abaixo DEVE existir no gerado.

## Arquivos
- MANUAL: `{manual_path}`
- GERADO: `{gen_path}`
- Alinhamento já aplicado no inventário (dx/dy do bbox Painéis).

## REGRA DE OURO (veto automático)
1. Percorra FACE A → B → C → D, camada a camada.
2. Para CADA linha do inventário com status FAIL/MISSING: verifique no desenho se realmente falta.
3. Para CADA EXTRA do gerado: diga se é lixo (deve remover) ou se cobre um MISSING (ajustar match).
4. PASS só se:
   - match_rate ≥ 90%
   - missing ≤ 8 e extra ≤ 12
   - TODAS as linhas estruturais críticas OK (lista abaixo)
   - cotas-chave presentes: 7, 11, 29, 48, 88, 120, 122, 182, 304
   - hatches path sizes = manual
   - textos PD/níveis/P1.A-D e 4× SP
5. Qualquer linha Painéis/SARR/Pressão MISSING em face com abertura = FAIL (severidade alta).
6. Diferença de estilo de cota (seta, dimstyle) NÃO libera ausência de geometria.

## Scorecard atual (numérico pré-visão)
- match_rate = {match_rate:.1%}
- missing = {len(missing)} | extra = {len(extra)}
- dims missing = {list(dims_miss)}
- dims extra = {list(dims_extra)}
- hatch missing = {list(hatch_miss)} | hatch extra = {list(hatch_extra)}
- texts manual = {texts_m}
- texts gen = {texts_g}

## Checklist estrutural OBRIGATÓRIO (marque true/false um a um)

### Face A (abertura DIREITA ~11cm, painel 88)
- [ ] Borda esquerda Painéis full altura ~304 (x≈80, y -380→-76)
- [ ] Borda direita Painéis só até fundo abertura ~180 (x≈168, y -380→-200)
- [ ] Inner vertical abertura Painéis ~124 (x≈157, y -200→-76)
- [ ] H mid painel parcial ~77 (80→157 em y≈-134) — NÃO full 88
- [ ] H topo painel parcial ~77 (80→157 em y≈-76) — NÃO full 88 sobre a abertura
- [ ] Pressão HIDDEN x≈87: corpo 178 (-378→-200) + trecho abertura 124 (-200→-76)  [pode ser 1 poly contínua]
- [ ] Pressão HIDDEN x≈161: só corpo 178 (-378→-200), PARA no fundo da abertura
- [ ] SARR L de abertura (para DENTRO do vazio, não para a parede):
      H7 (157→150 em y=-200) + V7 (150, -200→-207)
- [ ] SARR vertical marco/abertura x≈150 L=124 (-200→-76)
- [ ] SARR barra H11 em y≈-207 (150→161) ligando pé do L à pressão
- [ ] COTA contorno vazio: V124 em x=168 (-200→-76) + stubs H11 topo/fundo abertura
- [ ] Hatch 11×124 na faixa da abertura
- [ ] 2× SP (leaders ou mtext) na base

### Face B (aberturas DUPLA esq 11 + dir 29, miolo 48)
- [ ] Bordas Painéis param no fundo abertura (~180)
- [ ] Inners Painéis 334 e 382 sobem só até base vazio/rebaixo (~103, y -200→-97)
- [ ] H fundo aberturas PARCIAIS: 11 (323→334) e 29 (382→411) em y≈-200 — NÃO full 88
- [ ] H miolo 48 em y≈-134, -97, -76 (marco)
- [ ] Rebaixo laterais V7 em 334 e 382 (-83→-76)
- [ ] Pressão 330 e 404: só corpo 178 até y=-200 (NÃO sobe no vazio)
- [ ] SARR marco 341 e 375: V103 (-200→-97)
- [ ] SARR L cantos no fundo do marco (7+7 cada lado)
- [ ] SARR travessas H48 em y≈-83 (rebaixo) e y≈-97 (base vazio)
- [ ] SARR barras sob aberturas em y≈-207: H11 (330→341) e H29 (375→404)
- [ ] COTA outer V124 em 323 e 411; stubs topo 11 e 29; rebaixo COTA V7 se houver
- [ ] Hatch ÚNICO full-width 88×124 (não 11+29+14)
- [ ] 2× SP na base

### Face C e D (passantes estreitas ~19)
- [ ] Painéis retângulo completo (2V ~184 + 2H ~19)
- [ ] 2 SARR verticais centrais ~182 (C: 547/552; D: 695/700) — SEM DUPLICAR
- [ ] COTA laje acima: 2V ~120 + H19 no topo
- [ ] Hatch 19×120 no vazio de laje topo
- [ ] SEM pressão HIDDEN
- [ ] SEM SP

### Global
- [ ] 2 linhas Nível DASHED (topo e base do bloco)
- [ ] PD texto ≈ 3.04 (saída−chegada); níveis 855.25 / 852.19
- [ ] Labels P1.A P1.B P1.C P1.D
- [ ] Cotas-chave multiset presentes (7×N, 11, 29, 48, 88, 120, 122, 182, 304)

## INVENTÁRIO LINHA A LINHA (fonte da verdade)

{chr(10).join(inv_blocks)}

## MISSING (manual tem, gen não casou) — {len(missing)}
{chr(10).join(lines_miss) if lines_miss else "  (nenhum)"}

## EXTRA (gen tem, manual não casou) — {len(extra)}
{chr(10).join(lines_extra) if lines_extra else "  (nenhum)"}

## COMO RESPONDER (JSON obrigatório)
```json
{{
  "veredito": "PASS|FAIL|SUSPEITO",
  "confianca": 0.0,
  "match_rate_confirmado": 0.0,
  "checklist_por_face": {{
    "A": {{"ok": false, "faltas": ["..."], "extras_lixo": ["..."]}},
    "B": {{"ok": false, "faltas": [], "extras_lixo": []}},
    "C": {{"ok": false, "faltas": [], "extras_lixo": []}},
    "D": {{"ok": false, "faltas": [], "extras_lixo": []}}
  }},
  "linhas_criticas": [
    {{"face": "A", "role": "...", "status": "ok|missing|extra|divergente",
      "manual": "L=.. (x,y)->(x,y)", "gen": "...", "acao_motor": "o que corrigir no gerador"}}
  ],
  "vetos": ["lista de motivos que impedem PASS"],
  "resumo": "1-3 frases: o que falta para aprovação visual"
}}
```

REGRA DE VETO: se QUALQUER item do checklist estrutural A/B com abertura estiver false,
veredito = FAIL. Não invente PASS. Não ignore linhas curtas (L=7) — elas definem o L do sarrafo.
"""
    return prompt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manual", type=Path, default=DEFAULT_MANUAL)
    ap.add_argument("--gen", type=Path, default=DEFAULT_GEN)
    ap.add_argument("--tol-pos", type=float, default=1.0)
    ap.add_argument("--tol-len", type=float, default=1.0)
    # Padrão ESTRITO: ≥98% match, quase zero missing/extra estrutural
    ap.add_argument("--min-match", type=float, default=0.98)
    ap.add_argument("--max-missing", type=int, default=2)
    ap.add_argument("--max-extra", type=int, default=4)
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Modo máximo: tol 0.75, match 100%, missing/extra 0, cover off",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Pasta p/ JSON+prompt (default: scripts/arete/relatorios/pl_abcd_linewise/)",
    )
    args = ap.parse_args()

    if args.strict:
        args.tol_pos = 0.75
        args.tol_len = 0.75
        args.min_match = max(args.min_match, 1.0)
        args.max_missing = min(args.max_missing, 0)
        args.max_extra = min(args.max_extra, 0)
        allow_cover = False
    else:
        allow_cover = True  # pressão contínua cobre segmentos partidos do manual

    M = extract(args.manual)
    G = extract(args.gen)

    Mc = content_segs(M["segs"])
    Gc = content_segs(G["segs"])
    mbb = bbox_segs(Mc)
    gbb = bbox_segs(Gc)
    dx = mbb[0] - gbb[0]
    dy = mbb[3] - gbb[3]
    mh = mbb[3] - mbb[1]
    gh = gbb[3] - gbb[1]
    Gsegs = shift_segs(G["segs"], dx, dy)
    height_m, height_g = mh, gh

    print("=== ALIGN ===")
    print(f"manual bbox {tuple(round(v, 1) for v in mbb)}")
    print(f"gen bbox    {tuple(round(v, 1) for v in gbb)}")
    print(f"shift dx={dx:.2f} dy={dy:.2f}  heights M={mh:.1f} G={gh:.1f}")
    print(f"segs M={len(M['segs'])} G={len(Gsegs)}")
    print(f"tol_pos={args.tol_pos} tol_len={args.tol_len} allow_cover={allow_cover}")

    # Match: longer first, structural layers first
    order = sorted(
        enumerate(M["segs"]),
        key=lambda it: (
            0 if it[1]["layer"] in STRUCT_LAYERS else 1,
            -it[1]["L"],
            it[1]["layer"],
        ),
    )
    used = set()
    matched = []  # (m_idx, m, g, score, mode, layer_ok)
    missing = []
    inventory = []

    for m_idx, m in order:
        i, sc, mode = match_seg(
            m,
            Gsegs,
            used,
            tol_pos=args.tol_pos,
            tol_len=args.tol_len,
            require_layer=True,
            require_orient=True,
            allow_cover=allow_cover,
        )
        if i is None:
            # retry só com aliases de layer (NUNCA cruzar COTA↔Painéis↔SARR)
            i, sc, mode = match_seg(
                m,
                Gsegs,
                used,
                tol_pos=args.tol_pos + 0.5,
                tol_len=args.tol_len + 0.5,
                require_layer=True,
                require_orient=True,
                allow_cover=allow_cover,
            )
        face = face_of((m["x1"] + m["x2"]) / 2)
        row = {
            "idx": m_idx,
            "face": face,
            "layer": m["layer"],
            "orient": orient(m),
            "L": round(m["L"], 2),
            "x1": round(m["x1"], 2),
            "y1": round(m["y1"], 2),
            "x2": round(m["x2"], 2),
            "y2": round(m["y2"], 2),
            "role": role_of(m),
            "status": "MISSING",
            "mode": None,
            "layer_ok": False,
            "score": None,
        }
        if i is None:
            missing.append(m)
            inventory.append(row)
            continue
        # cover mode reuses same gen for multiple manual segments
        if mode != "cover":
            used.add(i)
        else:
            # cover can match multiple manuals to same gen; mark gen as used once
            used.add(i)
        g = Gsegs[i]
        lok = layer_eq(m["layer"], g["layer"])
        matched.append((m_idx, m, g, sc, mode, lok))
        row["status"] = "COVER" if mode == "cover" else "MATCHED"
        row["mode"] = mode
        row["layer_ok"] = lok
        row["score"] = round(sc, 3)
        row["gen"] = {
            "L": round(g["L"], 2),
            "x1": round(g["x1"], 2),
            "y1": round(g["y1"], 2),
            "x2": round(g["x2"], 2),
            "y2": round(g["y2"], 2),
            "layer": g["layer"],
        }
        inventory.append(row)

    # Cobertura por trechos: gen secciona sarrafo/pressão nas juntas de painel;
    # manual às vezes tem fuste contínuo. Se a união dos trechos gen cobre o manual,
    # marca MATCHED (mode=chain).
    def collinear_cover(m, gens, tol=1.5) -> list[int]:
        o = orient(m)
        if o not in ("H", "V"):
            return []
        idxs = []
        for i, g in enumerate(Gsegs):
            if i in used:
                continue
            if not layer_eq(m["layer"], g["layer"]):
                continue
            if orient(g) != o:
                continue
            if o == "V":
                if abs(((g["x1"] + g["x2"]) / 2) - ((m["x1"] + m["x2"]) / 2)) > tol:
                    continue
                g_lo, g_hi = sorted([g["y1"], g["y2"]])
                m_lo, m_hi = sorted([m["y1"], m["y2"]])
                # overlap real (não só toque na ponta — evita roubar trecho vizinho)
                ov = min(g_hi, m_hi) - max(g_lo, m_lo)
                if ov < 0.5:
                    continue
                idxs.append(i)
            else:
                if abs(((g["y1"] + g["y2"]) / 2) - ((m["y1"] + m["y2"]) / 2)) > tol:
                    continue
                g_lo, g_hi = sorted([g["x1"], g["x2"]])
                m_lo, m_hi = sorted([m["x1"], m["x2"]])
                ov = min(g_hi, m_hi) - max(g_lo, m_lo)
                if ov < 0.5:
                    continue
                idxs.append(i)
        if not idxs:
            return []
        # cobertura do intervalo manual
        m_lo, m_hi = (
            sorted([m["y1"], m["y2"]]) if o == "V" else sorted([m["x1"], m["x2"]])
        )
        spans = []
        for i in idxs:
            g = Gsegs[i]
            if o == "V":
                spans.append(sorted([g["y1"], g["y2"]]))
            else:
                spans.append(sorted([g["x1"], g["x2"]]))
        spans.sort()
        cur = m_lo
        for a, b in spans:
            if a > cur + tol:
                return []
            cur = max(cur, b)
        if cur < m_hi - tol:
            return []
        return idxs

    still_missing = []
    chained_keys = set()
    for m in missing:
        # só tenta chain em pressão/SARR longos
        if not (
            "Press" in m["layer"]
            or "PRESS" in m["layer"]
            or str(m["layer"]).startswith("SARR")
        ):
            still_missing.append(m)
            continue
        if m["L"] < 20:
            still_missing.append(m)
            continue
        chain = collinear_cover(m, Gsegs)
        if not chain:
            still_missing.append(m)
            continue
        for i in chain:
            used.add(i)
        g0 = Gsegs[chain[0]]
        matched.append((None, m, g0, 0.0, "chain", True))
        key = (
            round(m["x1"], 2),
            round(m["y1"], 2),
            round(m["x2"], 2),
            round(m["y2"], 2),
            m["layer"],
        )
        chained_keys.add(key)
        # atualiza inventário: MISSING → COVER
        for row in inventory:
            if row.get("status") != "MISSING":
                continue
            rkey = (
                round(row["x1"], 2),
                round(row["y1"], 2),
                round(row["x2"], 2),
                round(row["y2"], 2),
                row["layer"],
            )
            if rkey == key or (
                abs(row["L"] - m["L"]) < 0.2
                and row["layer"] == m["layer"]
                and abs(row["x1"] - m["x1"]) < 0.5
                and abs(row["y1"] - m["y1"]) < 0.5
            ):
                row["status"] = "COVER"
                row["mode"] = "chain"
                row["layer_ok"] = True
    missing = still_missing

    inventory.sort(key=lambda r: (r["face"], r["layer"], -r["L"]))
    extra_raw = [Gsegs[i] for i in range(len(Gsegs)) if i not in used]

    def is_sp_leader_extra(s) -> bool:
        """Leaders SP desenhados como LWPOLY diagonal em COTA — estilo, não geometria de painel."""
        if s["layer"] != "COTA":
            return False
        if orient(s) == "D":
            return True
        return False

    def is_noise_missing(s) -> bool:
        """Linha solta do manual fora do bloco ABCD (ex. Nível L=1010 em y≈-566)."""
        if s["layer"] == "Nível" and (s["L"] > 1005 or min(s["y1"], s["y2"]) < -500):
            return True
        return False

    # missing estrutural vs ruído
    missing_struct = [m for m in missing if not is_noise_missing(m)]
    missing_noise = [m for m in missing if is_noise_missing(m)]
    extra = [g for g in extra_raw if not is_sp_leader_extra(g)]
    extra_leaders = [g for g in extra_raw if is_sp_leader_extra(g)]
    match_rate = len(matched) / max(len(M["segs"]) - len(missing_noise), 1)
    layer_ok = sum(1 for *_, lok in matched if lok) / max(len(matched), 1)

    print(
        f"\n=== LINE MATCH {len(matched)}/{len(M['segs']) - len(missing_noise)} "
        f"({match_rate:.1%}) layer_ok={layer_ok:.1%} "
        f"missing={len(missing_struct)} (+noise {len(missing_noise)}) "
        f"extra={len(extra)} (+SP-leaders {len(extra_leaders)}) ==="
    )
    # gates usam missing_struct / extra filtrado
    missing = missing_struct

    # Full inventory print
    print("\n=== INVENTÁRIO LINHA A LINHA (manual) ===")
    for r in inventory:
        st = r["status"]
        tag = {"MATCHED": "OK   ", "COVER": "COVER", "MISSING": "FAIL "}.get(st, st)
        print(
            f"  [{tag}] F{r['face']} {r['layer']:22} {r['orient']} "
            f"L={r['L']:6.1f} ({r['x1']:7.1f},{r['y1']:7.1f})→"
            f"({r['x2']:7.1f},{r['y2']:7.1f})  {r['role']}"
        )

    print("\n--- MISSING (manual → gen) ---")
    by = defaultdict(list)
    for m in missing:
        mx = (m["x1"] + m["x2"]) / 2
        by[(face_of(mx), m["layer"], orient(m))].append(m)
    for k, v in sorted(by.items(), key=lambda x: -len(x[1])):
        print(f"  {k}: {len(v)}")
        for m in sorted(v, key=lambda s: -s["L"])[:12]:
            print(
                f"    L={m['L']:.1f} ({m['x1']:.1f},{m['y1']:.1f})->"
                f"({m['x2']:.1f},{m['y2']:.1f}) role={role_of(m)}"
            )

    print("\n--- EXTRA (gen only) ---")
    by = defaultdict(list)
    for g in extra:
        mx = (g["x1"] + g["x2"]) / 2
        by[(face_of(mx), g["layer"], orient(g))].append(g)
    for k, v in sorted(by.items(), key=lambda x: -len(x[1])):
        print(f"  {k}: {len(v)}")
        for g in sorted(v, key=lambda s: -s["L"])[:12]:
            print(
                f"    L={g['L']:.1f} ({g['x1']:.1f},{g['y1']:.1f})->"
                f"({g['x2']:.1f},{g['y2']:.1f}) role={role_of(g)}"
            )

    md = Counter(round(d["m"], 1) for d in M["dims"] if d["m"] is not None)
    gd = Counter(round(d["m"], 1) for d in G["dims"] if d["m"] is not None)
    dims_miss = sorted((md - gd).elements())
    dims_extra = sorted((gd - md).elements())
    print("\n--- DIMS missing in gen ---", dims_miss)
    print("--- DIMS extra in gen ---", dims_extra)

    m_txt = [t["t"] for t in M["texts"]]
    g_txt = [t["t"] for t in G["texts"]]
    print("\n--- TEXTS manual ---", m_txt)
    print("--- TEXTS gen ---", g_txt)
    print(f"LEADERS manual={M['leaders']} gen={G['leaders']}")

    def hatch_sig(hats):
        sig = []
        for h in hats:
            for p in h["paths"]:
                sig.append((round(p["w"], 0), round(p["h"], 0)))
        return Counter(sig)

    m_hatch, g_hatch = hatch_sig(M["hatches"]), hatch_sig(G["hatches"])
    hatch_miss = sorted((m_hatch - g_hatch).elements())
    hatch_extra = sorted((g_hatch - m_hatch).elements())
    print("\n--- HATCH path sizes manual ---", sorted(m_hatch.elements()))
    print("--- HATCH path sizes gen ---", sorted(g_hatch.elements()))
    print("hatch missing", hatch_miss)
    print("hatch extra", hatch_extra)

    def hatch_scales(hats):
        return [h.get("scale") for h in hats if h.get("scale") is not None]

    def hatch_patterns(hats):
        return [str(h.get("pattern") or "?") for h in hats]

    m_scales = hatch_scales(M["hatches"])
    g_scales = hatch_scales(G["hatches"])
    m_pats = hatch_patterns(M["hatches"])
    g_pats = hatch_patterns(G["hatches"])
    print("--- HATCH scale manual ---", m_scales)
    print("--- HATCH scale gen ---", g_scales)
    print("--- HATCH pattern manual ---", m_pats)
    print("--- HATCH pattern gen ---", g_pats)

    # ── Structural critical geometry gates ──
    def has_line(pool, *, layer_sub, face, o=None, L=None, x=None, y=None, tol=2.0):
        for s in pool:
            if face_of((s["x1"] + s["x2"]) / 2) != face:
                continue
            if layer_sub.lower() not in s["layer"].lower() and not (
                layer_sub == "Painéis" and s["layer"] in ("Painéis", "Paineis")
            ):
                if layer_sub == "Press" and ("Press" in s["layer"] or "PRESS" in s["layer"]):
                    pass
                elif layer_sub == "SARR" and s["layer"].startswith("SARR"):
                    pass
                elif layer_sub == "Painéis" and s["layer"] in ("Painéis", "Paineis"):
                    pass
                else:
                    continue
            if o and orient(s) != o:
                continue
            if L is not None and abs(s["L"] - L) > tol:
                continue
            if x is not None and abs((s["x1"] + s["x2"]) / 2 - x) > tol:
                continue
            if y is not None and abs((s["y1"] + s["y2"]) / 2 - y) > tol:
                continue
            return True
        return False

    # Gen pool aligned
    crit = []

    def gate_crit(name, ok, detail=""):
        crit.append((name, ok, detail))

    def span_cover_at_x(layer_sub, face, x, y0, y1, tol=2.0) -> bool:
        """União de trechos seccionados cobre [y0,y1] em x≈."""
        spans = []
        for s in Gsegs:
            if face_of((s["x1"] + s["x2"]) / 2) != face:
                continue
            if orient(s) != "V":
                continue
            if layer_sub == "SARR" and not s["layer"].startswith("SARR"):
                continue
            if layer_sub == "Press" and "Press" not in s["layer"] and "PRESS" not in s["layer"]:
                continue
            if abs((s["x1"] + s["x2"]) / 2 - x) > tol:
                continue
            spans.append(sorted([s["y1"], s["y2"]]))
        if not spans:
            return False
        spans.sort()
        lo, hi = min(y0, y1), max(y0, y1)
        cur = lo
        for a, b in spans:
            if a > cur + tol:
                return False
            cur = max(cur, b)
        return cur >= hi - tol

    # A SARR vertical x=150 (pode ser seccionado em 66+58)
    gate_crit(
        "A_sarr_vert_150",
        span_cover_at_x("SARR", "A", 150, -200, -76)
        or has_line(Gsegs, layer_sub="SARR", face="A", o="V", L=124, x=150, tol=3),
        "SARR V x≈150 cobre -200→-76 (seccionado ok)",
    )
    # A SARR L pieces
    gate_crit(
        "A_sarr_L_into_void",
        has_line(Gsegs, layer_sub="SARR", face="A", o="H", L=7, y=-200)
        and has_line(Gsegs, layer_sub="SARR", face="A", o="V", L=7),
        "L 7×7 do SARR A aponta para DENTRO do vazio (150, não 164)",
    )
    gate_crit(
        "A_sarr_barra_y207",
        has_line(Gsegs, layer_sub="SARR", face="A", o="H", L=11, y=-207),
        "barra H11 em y≈-207 (150→161)",
    )
    # A pressure left covers to top (seccionado nos painéis ok)
    gate_crit(
        "A_press_left_to_top",
        span_cover_at_x("Press", "A", 87, -378, -76, tol=3)
        or has_line(Gsegs, layer_sub="Press", face="A", o="V", x=87, L=302, tol=5),
        "pressão A x≈87 cobre corpo+topo (trechos seccionados ok)",
    )
    # A painel H77 partial
    gate_crit(
        "A_painel_H77_mid",
        has_line(Gsegs, layer_sub="Painéis", face="A", o="H", L=77, y=-134, tol=3),
        "Painéis H≈77 mid (não full 88 sobre abertura)",
    )
    gate_crit(
        "A_painel_H77_top",
        has_line(Gsegs, layer_sub="Painéis", face="A", o="H", L=77, y=-76, tol=3),
        "Painéis H≈77 topo parcial",
    )
    # B dual sarr bars y=-207
    gate_crit(
        "B_sarr_barra_11_y207",
        has_line(Gsegs, layer_sub="SARR", face="B", o="H", L=11, y=-207, tol=3),
        "B SARR H11 y≈-207 (330→341)",
    )
    gate_crit(
        "B_sarr_barra_29_y207",
        has_line(Gsegs, layer_sub="SARR", face="B", o="H", L=29, y=-207, tol=3),
        "B SARR H29 y≈-207 (375→404)",
    )
    gate_crit(
        "B_painel_H48_mid",
        has_line(Gsegs, layer_sub="Painéis", face="B", o="H", L=48, y=-134, tol=3),
        "B Painéis H48 mid y≈-134",
    )
    # Painel de 7cm ACIMA da laje (rebaixo) — laterais V7 no miolo B
    gate_crit(
        "B_rebaixo_V7_left",
        has_line(Gsegs, layer_sub="Painéis", face="B", o="V", L=7, x=334, tol=2)
        or has_line(Gsegs, layer_sub="Painéis", face="B", o="V", L=7, y=-79.5, tol=4),
        "Painéis V7 rebaixo miolo esq (painel acima da laje)",
    )
    gate_crit(
        "B_rebaixo_V7_right",
        has_line(Gsegs, layer_sub="Painéis", face="B", o="V", L=7, x=382, tol=2)
        or has_line(Gsegs, layer_sub="Painéis", face="B", o="V", L=7, y=-79.5, tol=4),
        "Painéis V7 rebaixo miolo dir (painel acima da laje)",
    )
    gate_crit(
        "B_rebaixo_SARR_H48_y83",
        has_line(Gsegs, layer_sub="SARR", face="B", o="H", L=48, y=-83, tol=2),
        "SARR H48 base do rebaixo y≈-83",
    )
    gate_crit(
        "B_void_base_H48_y97",
        has_line(Gsegs, layer_sub="Painéis", face="B", o="H", L=48, y=-97, tol=2),
        "Painéis H48 base do vazio laje y≈-97",
    )
    # C/D no duplicate SARR (count == 2)
    def count_sarr(face):
        n = 0
        for s in Gsegs:
            if face_of((s["x1"] + s["x2"]) / 2) != face:
                continue
            if not s["layer"].startswith("SARR"):
                continue
            if orient(s) == "V" and s["L"] > 100:
                n += 1
        return n

    gate_crit("C_sarr_count_2", count_sarr("C") == 2, f"C SARR V long count={count_sarr('C')} (want 2)")
    gate_crit("D_sarr_count_2", count_sarr("D") == 2, f"D SARR V long count={count_sarr('D')} (want 2)")

    # zero missing em layers estruturais (Painéis/SARR/Pressão) — veto forte
    struct_missing = [
        m
        for m in missing
        if m["layer"] in ("Painéis", "Paineis")
        or str(m["layer"]).startswith("SARR")
        or "Press" in m["layer"]
        or "PRESS" in m["layer"]
    ]
    gate_crit(
        "zero_struct_missing",
        len(struct_missing) == 0,
        f"struct_missing={len(struct_missing)} {[role_of(m) for m in struct_missing[:6]]}",
    )

    # Gates numeric
    gates = []

    def gate(name, ok, detail=""):
        gates.append((name, ok, detail))
        print(("PASS" if ok else "FAIL"), name, detail)

    print("\n=== GATES NUMÉRICOS ===")
    gate("match_rate", match_rate >= args.min_match, f"{match_rate:.1%} >= {args.min_match:.0%}")
    gate("layer_ok", layer_ok >= 0.99, f"{layer_ok:.1%} >= 99%")
    gate("missing", len(missing) <= args.max_missing, f"{len(missing)} <= {args.max_missing}")
    gate("extra", len(extra) <= args.max_extra, f"{len(extra)} <= {args.max_extra}")
    gate("height", abs(height_m - height_g) < 2, f"M={height_m:.1f} G={height_g:.1f}")
    for need in (7.0, 11.0, 14.0, 29.0, 37.0, 48.0, 58.0, 66.0, 88.0, 120.0, 122.0, 182.0, 304.0):
        gate(
            f"dim_{need:g}",
            gd.get(need, 0) >= 1 or any(abs(k - need) < 0.6 for k in gd),
            f"count={gd.get(need, 0)}",
        )
    gate(
        "leaders_sp",
        G["leaders"] >= 4 or sum(1 for t in g_txt if "SP" in t) >= 4,
        f"leaders={G['leaders']} sp_txt={sum(1 for t in g_txt if 'SP' in t)}",
    )
    gate(
        "hatch_11x124",
        any(abs(w - 11) < 1 and abs(h - 124) < 2 for w, h in g_hatch.elements()),
        str(list(g_hatch.elements())),
    )
    gate(
        "hatch_19x120",
        any(abs(w - 19) < 1 and abs(h - 120) < 2 for w, h in g_hatch.elements()),
        "",
    )
    # Face B dual: vazios corretos = abertura esq (~11×H) + dir (~29×H) + miolo vazio laje (~48×14)
    # NÃO full-width 88×124 (sobreporia painel sólido).
    g_h_list = list(g_hatch.elements())
    has_b_open_esq = any(abs(w - 11) < 1.5 and h > 50 for w, h in g_h_list)
    has_b_open_dir = any(abs(w - 29) < 2.0 and h > 50 for w, h in g_h_list)
    has_b_miolo_vazio = any(abs(w - 48) < 2.0 and 10 <= h <= 20 for w, h in g_h_list)
    has_b_full_wrong = any(abs(w - 88) < 2.0 and h > 50 for w, h in g_h_list)
    gate(
        "hatch_B_voids_only",
        (has_b_open_esq and has_b_open_dir and has_b_miolo_vazio and not has_b_full_wrong)
        or (not has_b_open_dir and any(abs(w - 88) < 2 and abs(h - 124) < 2 for w, h in g_h_list)),
        f"esq11={has_b_open_esq} dir29={has_b_open_dir} miolo14={has_b_miolo_vazio} "
        f"full88_wrong={has_b_full_wrong} paths={g_h_list}",
    )
    # exact vs manual: paths de B mudam (manual tinha 88 full errado p/ miolo);
    # exige A 11×124 e C/D 19×120; B validado em hatch_B_voids_only
    hatch_core_ok = (
        any(abs(w - 11) < 1 and abs(h - 124) < 2 for w, h in g_h_list)
        and any(abs(w - 19) < 1 and abs(h - 120) < 2 for w, h in g_h_list)
    )
    gate("hatch_core_ACD", hatch_core_ok, str(g_h_list))
    # escala visual do AR-CONC: faixa 0.04–0.08 (0.03 chapava; ≥0.5 ralo)
    def _scale_ok(scales, lo=0.035, hi=0.12):
        if not scales:
            return False
        return all(s is not None and lo <= float(s) <= hi for s in scales)

    gate(
        "hatch_scale_dense",
        _scale_ok(g_scales),
        f"gen_scales={g_scales} (manual≈{m_scales}; want ~0.05, faixa 0.035–0.12)",
    )
    gate(
        "hatch_pattern_ARCONC",
        any("AR-CONC" in p.upper() or "ARCONC" in p.upper() for p in g_pats) or any(
            "ANSI31" in p.upper() for p in g_pats
        ),
        f"patterns={g_pats}",
    )

    print("\n=== GATES ESTRUTURAIS (linha crítica) ===")
    for name, ok, detail in crit:
        gate(f"crit:{name}", ok, detail)
        # already appended via gate()

    passed = sum(1 for _, ok, _ in gates if ok)
    total = len(gates)
    print(f"\n=== RESULT {passed}/{total} ===")
    approved = passed == total
    if approved:
        print("VISUAL_VALIDATION: APPROVED")
        rc = 0
    else:
        print("VISUAL_VALIDATION: REJECTED")
        for name, ok, d in gates:
            if not ok:
                print("  fail:", name, d)
        rc = 1

    # Write artifacts
    out_dir = args.out_dir or (
        Path(__file__).resolve().parent / "relatorios" / "pl_abcd_linewise"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {
        "ts": ts,
        "manual": str(args.manual),
        "gen": str(args.gen),
        "align": {"dx": dx, "dy": dy, "height_m": height_m, "height_g": height_g},
        "match_rate": match_rate,
        "layer_ok": layer_ok,
        "missing_n": len(missing),
        "extra_n": len(extra),
        "inventory": inventory,
        "missing": [
            {
                "face": face_of((m["x1"] + m["x2"]) / 2),
                "layer": m["layer"],
                "orient": orient(m),
                "L": m["L"],
                "x1": m["x1"],
                "y1": m["y1"],
                "x2": m["x2"],
                "y2": m["y2"],
                "role": role_of(m),
            }
            for m in missing
        ],
        "extra": [
            {
                "face": face_of((g["x1"] + g["x2"]) / 2),
                "layer": g["layer"],
                "orient": orient(g),
                "L": g["L"],
                "x1": g["x1"],
                "y1": g["y1"],
                "x2": g["x2"],
                "y2": g["y2"],
                "role": role_of(g),
            }
            for g in extra
        ],
        "dims_miss": dims_miss,
        "dims_extra": dims_extra,
        "hatch_miss": hatch_miss,
        "hatch_extra": hatch_extra,
        "gates": [{"name": n, "ok": ok, "detail": d} for n, ok, d in gates],
        "veredito": "APPROVED" if approved else "REJECTED",
    }
    json_path = out_dir / f"linewise_{ts}.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    vision = build_vision_prompt(
        manual_path=args.manual,
        gen_path=args.gen,
        inventory=inventory,
        missing=missing,
        extra=extra,
        match_rate=match_rate,
        dims_miss=dims_miss,
        dims_extra=dims_extra,
        hatch_miss=hatch_miss,
        hatch_extra=hatch_extra,
        texts_m=m_txt,
        texts_g=g_txt,
    )
    prompt_path = out_dir / f"VISION_PROMPT_{ts}.md"
    prompt_path.write_text(vision, encoding="utf-8")
    # always refresh "latest" copies
    (out_dir / "VISION_PROMPT_LATEST.md").write_text(vision, encoding="utf-8")
    (out_dir / "linewise_LATEST.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\n=== ARTIFACTS ===")
    print(f"JSON:   {json_path}")
    print(f"PROMPT: {prompt_path}")
    print(f"LATEST: {out_dir / 'VISION_PROMPT_LATEST.md'}")

    return rc


if __name__ == "__main__":
    sys.exit(main())
