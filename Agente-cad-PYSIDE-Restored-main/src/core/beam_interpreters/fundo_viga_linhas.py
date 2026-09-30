"""Gate FV: fundo de viga nao pode ter borda fora das linhas do estrutural.

Regra do dono (D-60, 2026-09-26): desenhar fora das linhas originais e'
alucinacao. Vale para FV o que ja' vale para LV (``fora_da_linha_estrutural``
em ``lateral_viga_cells.py``), mas aqui BLOQUEIA em vez de so' avisar:

1. mede quanto de cada borda longa do contorno cai sobre linha ESTRUTURAL do
   DXF (mesma separacao estrutural x cota e mesmo indice de bordas da LV —
   ``lv_beam_scene``; nunca por nome de layer);
2. borda abaixo de ``LINE_COVERAGE_MIN`` -> tenta reparar: par de linhas
   paralelas com a largura do proprio contorno (fundo deslocado, V304) ou com
   a largura declarada da viga (fundo largo demais, V327/V331), perto dele,
   cobrindo o vao; sem par, apara o fundo ao trecho em que as duas bordas
   tem parede (fundo que passa do fim da viga, V302 S9);
   o reparo so' vale se passar pelo mesmo teste;
3. sem par que sirva -> anula: o item sai de ``contour`` e vai para o slot
   ``anulado_d60`` (pontos vazios, antes guardado no registro). Assim o
   contrato de area fechada (``sa_db_persistence.fv_area_errors``), o N3 e o
   reparador — que so' leem ``contour`` — nunca recebem geometria inventada.

Cada decisao fica em ``item["fv_line_gate"]`` (status, coberturas, antes,
depois, motivo) — e' o feedback para depurar o motor. Contorno validado por
humano nunca e' alterado: recebe so' o registro, para revisao (D-53).

A medicao e' independente da classificacao da viga (seg_side_*): usa todas as
linhas estruturais do DXF, porque o erro tipico (V304/V308 do 13_PAV) e' o
fundo nascer do lado de fora da parede, deslocado uma largura.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

LINE_COVERAGE_MIN = 0.5      # igual a LV (lateral_viga_cells.LINE_COVERAGE_MIN)
WIDTH_TOL = 1.5              # cm: largura do par de linhas x largura do contorno
TRIM_KEEP_MIN = 0.4          # aparo mantem >= 40% do vao (V302 S9 0.49 fica; V323 S1 0.10 anula)
ORTHO_TOL = 0.05             # cm: contorno precisa ser retangulo alinhado aos eixos
AREA_KEY_RE = re.compile(r"^viga_fundo_seg_(\d+)_area_segs$")
ANULADO_SLOT = "anulado_d60"
ANULADOS_KEY = "viga_fundo_anulados_d60"   # registro dos anulados apos compactar a numeracao
SEG_KEY_RE = re.compile(r"^viga_fundo_seg_(\d+)_(.+)$")

STATUS_REPARADO = "reparado"
STATUS_ANULADO = "anulado"
STATUS_VALIDADO_FORA = "validado_fora_da_linha"


def gate_frozen(item: Any) -> bool:
    """True se o gate ja' decidiu este contorno e o reparador deve respeitar."""
    gate = item.get("fv_line_gate") if isinstance(item, dict) else None
    return isinstance(gate, dict) and gate.get("status") in (STATUS_REPARADO, STATUS_ANULADO)


def _rect(points: Iterable[Any], horizontal_hint: bool | None = None):
    pts = []
    for p in points or []:
        try:
            pts.append((float(p[0]), float(p[1])))
        except (TypeError, ValueError, IndexError):
            continue
    if len(pts) < 4:
        return None
    x0, x1 = min(x for x, _ in pts), max(x for x, _ in pts)
    y0, y1 = min(y for _, y in pts), max(y for _, y in pts)
    if x1 - x0 <= ORTHO_TOL or y1 - y0 <= ORTHO_TOL:
        return None
    # Vertice no meio de uma aresta (ponto colinear) ainda e' retangulo; ponto
    # fora do contorno do retangulo e' diagonal/chanfro: fora deste gate.
    for x, y in pts:
        on_x = min(abs(x - x0), abs(x - x1)) <= ORTHO_TOL
        on_y = min(abs(y - y0), abs(y - y1)) <= ORTHO_TOL
        if not (on_x or on_y):
            return None
    for i in range(len(pts) - 1):
        (xa, ya), (xb, yb) = pts[i], pts[i + 1]
        if abs(xa - xb) > ORTHO_TOL and abs(ya - yb) > ORTHO_TOL:
            return None  # aresta obliqua
    # Comprimento pode ser menor que a largura (painel isolado de 1 cm).
    # O eixo estrutural vem da viga/trecho, nao do maior lado do retangulo.
    horizontal = horizontal_hint if horizontal_hint is not None else (x1 - x0) >= (y1 - y0)
    if horizontal:
        return horizontal, (x0, x1), (y0, y1)
    return horizontal, (y0, y1), (x0, x1)


def _points(horizontal: bool, a: tuple[float, float], t: tuple[float, float]) -> list[list[float]]:
    (a0, a1), (t0, t1) = a, t
    if horizontal:
        rect = [(a0, t0), (a1, t0), (a1, t1), (a0, t1)]
    else:
        rect = [(t0, a0), (t1, a0), (t1, a1), (t0, a1)]
    return [[round(x, 6), round(y, 6)] for x, y in rect + [rect[0]]]


class _Lines:
    """Bordas estruturais do DXF, pelo mesmo indice que a LV usa."""

    def __init__(self, texts: list[dict], lines: list[dict]) -> None:
        from src.core.lv_beam_scene import _EdgeIndex, _line_segments, split_dimension_lines

        structural, _dimension = split_dimension_lines(_line_segments(lines), texts)
        self.edges = _EdgeIndex(structural)

    def coverage(self, horizontal: bool, t: float, a: tuple[float, float]) -> float:
        lo, hi = a
        if hi - lo <= 0:
            return 0.0
        covered = sum(
            max(0.0, min(hi, y) - max(lo, x)) for x, y in self.edges.coverage(horizontal, t)
        )
        return covered / (hi - lo)

    def repair(self, horizontal: bool, a: tuple[float, float], t: tuple[float, float],
               declared: Iterable[float] = ()):
        """Par de linhas paralelas mais perto do contorno, com a largura dele ou
        a largura declarada da viga (cotas laterais do segmento / ``width``)."""
        width = t[1] - t[0]
        widths = [width] + [w for w in declared if w > 0 and abs(w - width) > WIDTH_TOL]
        center = (t[0] + t[1]) / 2.0
        radius = max(1.5 * width, 30.0)
        faces = sorted({
            round(tt, 2) for tt, x, y in self.edges.along(horizontal)
            if abs(tt - center) <= radius + width and min(a[1], y) - max(a[0], x) > 0
        })
        best = None
        for i, lo in enumerate(faces):
            for hi in faces[i + 1:]:
                if min(abs((hi - lo) - w) for w in widths) > WIDTH_TOL:
                    continue
                shift = abs((lo + hi) / 2.0 - center)
                if shift > radius:
                    continue
                c_lo, c_hi = self.coverage(horizontal, lo, a), self.coverage(horizontal, hi, a)
                if min(c_lo, c_hi) < LINE_COVERAGE_MIN:
                    continue
                score = shift + 2.0 * abs((hi - lo) - width)
                if best is None or score < best[0]:
                    best = (score, (lo, hi), (c_lo, c_hi), shift)
        return best

    def trim(self, horizontal: bool, a: tuple[float, float], t: tuple[float, float]):
        """Trecho do vao em que as DUAS bordas tem parede (fundo que passa do
        fim da viga, V302 S9). Vaos ate' uma largura (cruzamento de viga) nao
        cortam. Devolve o maior trecho, se guardar ``TRIM_KEEP_MIN`` do vao:
        sobrar so' um toco e' fundo no lugar errado (V323 S1), nao excesso."""
        width = t[1] - t[0]

        def covered(tt):
            spans = sorted((max(a[0], x), min(a[1], y)) for x, y in self.edges.coverage(horizontal, tt)
                           if min(a[1], y) > max(a[0], x))
            merged: list[list[float]] = []
            for lo, hi in spans:
                if merged and lo - merged[-1][1] <= width + WIDTH_TOL:
                    merged[-1][1] = max(merged[-1][1], hi)
                else:
                    merged.append([lo, hi])
            return merged

        best = None
        for lo0, hi0 in covered(t[0]):
            for lo1, hi1 in covered(t[1]):
                lo, hi = max(lo0, lo1), min(hi0, hi1)
                if hi - lo >= width and (best is None or hi - lo > best[1] - best[0]):
                    best = (lo, hi)
        if best is None:
            return None
        # Ponta do contorno a menos de uma largura da parede: e' o encontro
        # com o apoio/viga que cruza, nao alucinacao — nao encurta.
        lo = a[0] if best[0] - a[0] <= width + WIDTH_TOL else best[0]
        hi = a[1] if a[1] - best[1] <= width + WIDTH_TOL else best[1]
        cov = (self.coverage(horizontal, t[0], (lo, hi)), self.coverage(horizontal, t[1], (lo, hi)))
        if (min(cov) < LINE_COVERAGE_MIN or (hi - lo) >= (a[1] - a[0]) - 1e-6
                or (hi - lo) < TRIM_KEEP_MIN * (a[1] - a[0])):
            return None
        return (lo, hi), cov


_LATERAL_DIM_RE = re.compile(r"^viga_[ab]_seg_\d+_dim$")
_DIM_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*[/xX]")


def _dim_width(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if value > 0 else None
    match = _DIM_RE.match(str(value or ""))
    return float(match.group(1).replace(",", ".")) if match else None


def _declared_widths(beam: dict, seg: int) -> list[float]:
    """Larguras declaradas da viga: cotas laterais (o segmento primeiro, depois
    os demais — laterais e fundo nem sempre tem a mesma segmentacao, V331) e
    o ``width``. O reparo continua exigindo par real de paredes cobrindo o vao.

    ``viga_fundo_seg_N_dim`` fica de fora de proposito: quando o fundo nasce
    largo demais (V327/V331 do 13_PAV) esse texto costuma ser o de um vizinho
    associado errado, e confirmaria o proprio erro.
    """
    keys = [f"viga_a_seg_{seg}_dim", f"viga_b_seg_{seg}_dim"]
    keys += sorted(k for k in beam if _LATERAL_DIM_RE.match(str(k)) and k not in keys)
    out: list[float] = []
    for key in keys + ["width", "largura"]:
        w = _dim_width(beam.get(key))
        if w is not None and all(abs(w - o) > WIDTH_TOL for o in out):
            out.append(w)
    return out


def _own_walls(beam: dict, horizontal: bool, a: tuple[float, float]) -> list[float]:
    """Coordenadas transversais das laterais da PROPRIA viga (seg_side_a/b)
    paralelas ao fundo e cobrindo >= LINE_COVERAGE_MIN do vao dele.

    Caso V327 do 13_PAV: o fundo nasceu entre as paredes de outra viga (x 2040,
    cobertura 0.67 — passava no teste de linha), enquanto as laterais da V327
    estao em x 4387/4401. Linha do DXF sozinha nao prova que a faixa e' desta
    viga; as laterais da viga provam."""
    span = a[1] - a[0]
    out: list[float] = []
    for slots in (beam.get("links") or {}).values():
        if not isinstance(slots, dict):
            continue
        for slot in ("seg_side_a", "seg_side_b"):
            for it in slots.get(slot) or []:
                pts = it.get("points") if isinstance(it, dict) else None
                for p, q in zip(pts or [], (pts or [])[1:]):
                    try:
                        (px, py), (qx, qy) = (float(p[0]), float(p[1])), (float(q[0]), float(q[1]))
                    except (TypeError, ValueError, IndexError):
                        continue
                    if horizontal and abs(py - qy) <= ORTHO_TOL:
                        t, lo, hi = py, min(px, qx), max(px, qx)
                    elif not horizontal and abs(px - qx) <= ORTHO_TOL:
                        t, lo, hi = px, min(py, qy), max(py, qy)
                    else:
                        continue
                    if min(hi, a[1]) - max(lo, a[0]) >= LINE_COVERAGE_MIN * span and \
                            all(abs(t - o) > WIDTH_TOL for o in out):
                        out.append(t)
    return sorted(out)


def _own_pair(index: "_Lines", horizontal: bool, a: tuple[float, float],
              own: list[float], widths: list[float]):
    """Par de laterais da propria viga com largura aceita e linha no DXF."""
    best = None
    for i, t0 in enumerate(own):
        for t1 in own[i + 1:]:
            if not any(abs((t1 - t0) - w) <= WIDTH_TOL for w in widths):
                continue
            cov = (index.coverage(horizontal, t0, a), index.coverage(horizontal, t1, a))
            if min(cov) >= LINE_COVERAGE_MIN and (best is None or min(cov) > min(best[1])):
                best = ((t0, t1), cov)
    return best


def _scene_walls(runs: dict, name: str, horizontal: bool, a: tuple[float, float]) -> list[float]:
    """Paredes da viga pela CENA DO DXF (faixa medida a partir do rotulo dela —
    a mesma autoridade das celulas LV). Independe de vinculo lateral: no job o
    gate roda antes das celulas LV e o merge repoe laterais antigas (face
    errada), que anularam fundo certo (V301/V303/V309/V314, 27/09)."""
    from src.core.lv_beam_scene import _norm_name

    span = a[1] - a[0]
    out: list[float] = []
    for scene in runs.get(_norm_name(name)) or []:
        if scene.angle or scene.is_horizontal != horizontal:
            continue
        if min(scene.end, a[1]) - max(scene.start, a[0]) >= LINE_COVERAGE_MIN * span:
            out.extend(t for t in (scene.t_lo, scene.t_hi)
                       if all(abs(t - o) > WIDTH_TOL for o in out))
    return sorted(out)


def audit_fv_lines_all(beams: list[dict], texts: list[dict], lines: list[dict]) -> dict[str, Any]:
    """Aplica o gate a todos os contornos FV. Retorna o relatorio da rodada."""
    index = _Lines(list(texts or []), list(lines or []))
    try:
        from src.core.lv_beam_scene import build_scene_runs
        runs = build_scene_runs(
            list(beams or []), list(texts or []), list(lines or []), {}, None,
            allow_width_hint_fallback=True,
        )
    except Exception:  # cena indisponivel: cai no vinculo lateral (comportamento anterior)
        runs = {}
    report: dict[str, Any] = {"ok": 0, STATUS_REPARADO: [], STATUS_ANULADO: [],
                              STATUS_VALIDADO_FORA: [], "nao_auditavel": []}
    for beam in beams or []:
        if not isinstance(beam, dict):
            continue
        name = str(beam.get("name") or "")
        for key, slots in (beam.get("links") or {}).items():
            match = AREA_KEY_RE.match(str(key))
            if not match or not isinstance(slots, dict):
                continue
            seg = int(match.group(1))
            for item in list(slots.get("contour") or []):
                if not isinstance(item, dict) or gate_frozen(item):
                    continue
                item.pop("fv_line_gate", None)
                orientation = item.get("fv_axis_is_horizontal")
                if not isinstance(orientation, bool):
                    orientation = beam.get("fv_is_h", beam.get("is_h"))
                rect = _rect(item.get("points"), orientation if isinstance(orientation, bool) else None)
                if rect is None:
                    if item.get("points"):
                        report["nao_auditavel"].append(f"{name} S{seg}")
                    continue
                horizontal, a, t = rect
                cov = (round(index.coverage(horizontal, t[0], a), 3),
                       round(index.coverage(horizontal, t[1], a), 3))
                own = _scene_walls(runs, name, horizontal, a)
                # largura da faixa do DXF e' a largura da viga (mesma autoridade)
                own_widths = [round(own[j] - own[i], 2) for i in range(len(own))
                              for j in range(i + 1, len(own))]
                if not own:
                    own = _own_walls(beam, horizontal, a)
                alheio = bool(own) and not all(
                    any(abs(e - w) <= WIDTH_TOL for w in own) for e in t)
                if min(cov) >= LINE_COVERAGE_MIN and not alheio:
                    report["ok"] += 1
                    continue
                gate: dict[str, Any] = {
                    "regra": "D-60 fundo sem linha fora do estrutural",
                    "cobertura_antes": list(cov),
                    "largura": round(t[1] - t[0], 2),
                    "antes": item.get("points"),
                }
                entry = {"viga": name, "seg": seg, "cobertura_antes": list(cov)}
                entry["fora_laterais_proprias"] = alheio
                if item.get("validated"):
                    gate["status"] = STATUS_VALIDADO_FORA
                    gate["motivo"] = "contorno validado por humano fora da linha: revisar (nao alterado)"
                    item["fv_line_gate"] = gate
                    entry.update(antes=gate["antes"])
                    report[STATUS_VALIDADO_FORA].append(entry)
                    continue
                if alheio:
                    # Fundo fora das laterais da propria viga: so' o par dessas
                    # laterais serve (o reparo generico poderia achar outra viga).
                    gate["laterais_proprias"] = [round(w, 4) for w in own]
                    widths = [gate["largura"]] + own_widths + _declared_widths(beam, seg)
                    hit = _own_pair(index, horizontal, a, own, widths)
                    if hit is not None:
                        pair, cov_new = hit
                        item["points"] = _points(horizontal, a, pair)
                        gate.update({
                            "status": STATUS_REPARADO,
                            "largura_depois": round(pair[1] - pair[0], 2),
                            "cobertura_depois": [round(c, 3) for c in cov_new],
                            "deslocamento": round(abs(pair[0] - t[0]), 2),
                            "motivo": "fundo fora das laterais da propria viga (entre paredes "
                                      "de outra); movido para entre as laterais desta viga",
                        })
                        entry.update(deslocamento=gate["deslocamento"],
                                     cobertura_depois=gate["cobertura_depois"],
                                     largura_depois=gate["largura_depois"])
                    else:
                        item["points"] = []
                        slots["contour"] = [c for c in slots.get("contour") or [] if c is not item]
                        slots.setdefault(ANULADO_SLOT, []).append(item)
                        gate.update({
                            "status": STATUS_ANULADO,
                            "motivo": "fundo fora das laterais da propria viga e nenhum par "
                                      "dessas laterais com linha no estrutural: anulado, revisar",
                        })
                    item["fv_line_gate"] = gate
                    entry.update(antes=gate["antes"], depois=item.get("points") or [])
                    report[gate["status"]].append(entry)
                    continue
                found = index.repair(horizontal, a, t, _declared_widths(beam, seg))
                if found is not None:
                    _score, pair, cov_new, shift = found
                    item["points"] = _points(horizontal, a, pair)
                    largura_depois = round(pair[1] - pair[0], 2)
                    motivo = ("borda fora da linha; faixa movida para o par de linhas "
                              "estruturais com a mesma largura")
                    if abs(largura_depois - gate["largura"]) > WIDTH_TOL:
                        motivo = (f"fundo com {gate['largura']} cm entre paredes de "
                                  f"{largura_depois} cm (largura declarada da viga); "
                                  "faixa ajustada ao par de linhas estruturais")
                        dim = _dim_width(beam.get(f"viga_fundo_seg_{seg}_dim"))
                        if dim is not None and abs(dim - largura_depois) > WIDTH_TOL:
                            gate["dim_fundo_diverge"] = beam.get(f"viga_fundo_seg_{seg}_dim")
                    gate.update({
                        "largura_depois": largura_depois,
                        "status": STATUS_REPARADO,
                        "cobertura_depois": [round(c, 3) for c in cov_new],
                        "deslocamento": round(shift, 2),
                        "motivo": motivo,
                    })
                    entry.update(deslocamento=round(shift, 2), cobertura_depois=gate["cobertura_depois"],
                                 largura=gate["largura"], largura_depois=largura_depois)
                elif (cut := index.trim(horizontal, a, t)) is not None:
                    (lo, hi), cov_new = cut
                    item["points"] = _points(horizontal, (lo, hi), t)
                    gate.update({
                        "status": STATUS_REPARADO,
                        "cobertura_depois": [round(c, 3) for c in cov_new],
                        "deslocamento": 0.0,
                        "aparado": [round(lo - a[0], 2), round(a[1] - hi, 2)],
                        "motivo": "fundo passava do trecho com paredes; aparado ao vao "
                                  "em que as duas bordas tem linha do estrutural",
                    })
                    entry.update(deslocamento=0.0, cobertura_depois=gate["cobertura_depois"],
                                 aparado=gate["aparado"])
                else:
                    item["points"] = []
                    slots["contour"] = [c for c in slots.get("contour") or [] if c is not item]
                    slots.setdefault(ANULADO_SLOT, []).append(item)
                    gate.update({
                        "status": STATUS_ANULADO,
                        "motivo": "borda fora da linha e nenhum par de linhas estruturais "
                                  "com a largura do fundo perto dele: segmento anulado, revisar",
                    })
                item["fv_line_gate"] = gate
                entry.update(antes=gate["antes"], depois=item.get("points") or [])
                report[gate["status"]].append(entry)
        _compact_annulled_slots(beam)
    return report


def _compact_annulled_slots(beam: dict) -> bool:
    """Fecha o buraco que o anulado deixa na numeracao (S1 anulado -> serie S2..Sn).

    O slot sem nenhum contorno sai da serie; os seguintes sobem uma posicao, levando
    junto os campos ``viga_fundo_seg_N_*``. O registro do anulado vai para
    ``links[ANULADOS_KEY]`` com o numero original (``fv_line_gate.slot_original``).
    Viga com fundo validado por humano nao e' renumerada (rotulo ja' conferido).
    """
    links = beam.get("links")
    if not isinstance(links, dict):
        return False
    slots = sorted(
        (int(m.group(1)), key) for key in links
        if (m := AREA_KEY_RE.match(str(key))) and isinstance(links[key], dict)
    )
    live = [idx for idx, key in slots if links[key].get("contour")]
    if [idx for idx, _ in slots] == live:
        return False
    if any(isinstance(c, dict) and c.get("validated")
           for _, key in slots for c in links[key].get("contour") or []):
        return False
    remap = {old: new for new, old in enumerate(live, start=1)}
    record = links.setdefault(ANULADOS_KEY, {}).setdefault(ANULADO_SLOT, [])
    moved = {}
    for idx, key in slots:
        slot = links.pop(key)
        for item in slot.pop(ANULADO_SLOT, None) or []:
            if isinstance(item, dict) and isinstance(item.get("fv_line_gate"), dict):
                item["fv_line_gate"].setdefault("slot_original", idx)
            record.append(item)
        if idx in remap:
            moved[f"viga_fundo_seg_{remap[idx]}_area_segs"] = slot
    links.update(moved)
    for store in (beam.get("fields"), beam):
        if not isinstance(store, dict):
            continue
        keys = [(k, m) for k in list(store) if (m := SEG_KEY_RE.match(str(k)))]
        values = {k: store.pop(k) for k, _ in keys}
        for key, match in keys:
            new = remap.get(int(match.group(1)))
            if new is not None:
                store[f"viga_fundo_seg_{new}_{match.group(2)}"] = values[key]
    # listas paralelas aos slots (so' quando alinhadas 1:1 com eles)
    keep = [pos for pos, (idx, _) in enumerate(slots) if idx in remap]
    classified = (beam.get("geometry") or {}).get("classified")
    lists = [(classified, "merged_bottom_groups_coords"), (classified, "merged_bottom_lengths"),
             (links.get("viga_segs"), "seg_bottom")]
    for owner, name in lists:
        values = owner.get(name) if isinstance(owner, dict) else None
        if isinstance(values, list) and len(values) == len(slots):
            owner[name] = [values[pos] for pos in keep]
    return True


def gate_attention(item: Any) -> str:
    """Aviso curto para a ficha (vazio se o gate nao atuou)."""
    gate = item.get("fv_line_gate") if isinstance(item, dict) else None
    if not isinstance(gate, dict):
        return ""
    antes = gate.get("cobertura_antes") or [0, 0]
    base = f"cobertura das bordas {min(antes):.0%}"
    if gate.get("status") == STATUS_REPARADO:
        return f"SA: fundo fora da linha do estrutural ({base}) — reparado, deslocado {gate.get('deslocamento')} cm"
    if gate.get("status") == STATUS_ANULADO:
        return f"SA: fundo fora da linha do estrutural ({base}) — ANULADO, revisar"
    if gate.get("status") == STATUS_VALIDADO_FORA:
        return f"SA: fundo validado fora da linha do estrutural ({base}) — revisar"
    return ""


def report_summary(report: dict[str, Any]) -> str:
    """Uma linha de log com o que o gate fez (nomes, nao so' contagem)."""
    def names(key: str) -> str:
        return ", ".join(
            f"{e['viga']} S{e['seg']} cov={e.get('cobertura_antes')}"
            + (" alheio" if e.get("fora_laterais_proprias") else "")
            for e in report.get(key) or []
        ) or "-"
    return (
        f"ok {report.get('ok', 0)}; reparados [{names(STATUS_REPARADO)}]; "
        f"anulados [{names(STATUS_ANULADO)}]; validados fora [{names(STATUS_VALIDADO_FORA)}]; "
        f"nao auditaveis [{', '.join(report.get('nao_auditavel') or []) or '-'}]"
    )
