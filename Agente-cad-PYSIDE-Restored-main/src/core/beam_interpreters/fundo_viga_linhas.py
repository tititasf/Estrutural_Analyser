"""Gate FV: fundo de viga nao pode ter borda fora das linhas do estrutural.

Regra do dono (D-60, 2026-09-26): desenhar fora das linhas originais e'
alucinacao. Vale para FV o que ja' vale para LV (``fora_da_linha_estrutural``
em ``lateral_viga_cells.py``), mas aqui BLOQUEIA em vez de so' avisar:

1. mede quanto de cada borda longa do contorno cai sobre linha ESTRUTURAL do
   DXF (mesma separacao estrutural x cota e mesmo indice de bordas da LV —
   ``lv_beam_scene``; nunca por nome de layer);
2. borda abaixo de ``LINE_COVERAGE_MIN`` -> tenta reparar: par de linhas
   paralelas com a largura do proprio contorno, perto dele, cobrindo o vao;
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
ORTHO_TOL = 0.05             # cm: contorno precisa ser retangulo alinhado aos eixos
AREA_KEY_RE = re.compile(r"^viga_fundo_seg_(\d+)_area_segs$")
ANULADO_SLOT = "anulado_d60"

STATUS_REPARADO = "reparado"
STATUS_ANULADO = "anulado"
STATUS_VALIDADO_FORA = "validado_fora_da_linha"


def gate_frozen(item: Any) -> bool:
    """True se o gate ja' decidiu este contorno e o reparador deve respeitar."""
    gate = item.get("fv_line_gate") if isinstance(item, dict) else None
    return isinstance(gate, dict) and gate.get("status") in (STATUS_REPARADO, STATUS_ANULADO)


def _rect(points: Iterable[Any]):
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
    horizontal = (x1 - x0) >= (y1 - y0)
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

    def repair(self, horizontal: bool, a: tuple[float, float], t: tuple[float, float]):
        """Par de linhas paralelas com a largura do contorno, mais perto dele."""
        width = t[1] - t[0]
        center = (t[0] + t[1]) / 2.0
        radius = max(1.5 * width, 30.0)
        faces = sorted({
            round(tt, 2) for tt, x, y in self.edges.along(horizontal)
            if abs(tt - center) <= radius + width and min(a[1], y) - max(a[0], x) > 0
        })
        best = None
        for i, lo in enumerate(faces):
            for hi in faces[i + 1:]:
                if abs((hi - lo) - width) > WIDTH_TOL:
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


def audit_fv_lines_all(beams: list[dict], texts: list[dict], lines: list[dict]) -> dict[str, Any]:
    """Aplica o gate a todos os contornos FV. Retorna o relatorio da rodada."""
    index = _Lines(list(texts or []), list(lines or []))
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
                rect = _rect(item.get("points"))
                if rect is None:
                    if item.get("points"):
                        report["nao_auditavel"].append(f"{name} S{seg}")
                    continue
                horizontal, a, t = rect
                cov = (round(index.coverage(horizontal, t[0], a), 3),
                       round(index.coverage(horizontal, t[1], a), 3))
                if min(cov) >= LINE_COVERAGE_MIN:
                    report["ok"] += 1
                    continue
                gate: dict[str, Any] = {
                    "regra": "D-60 fundo sem linha fora do estrutural",
                    "cobertura_antes": list(cov),
                    "largura": round(t[1] - t[0], 2),
                    "antes": item.get("points"),
                }
                entry = {"viga": name, "seg": seg, "cobertura_antes": list(cov)}
                if item.get("validated"):
                    gate["status"] = STATUS_VALIDADO_FORA
                    gate["motivo"] = "contorno validado por humano fora da linha: revisar (nao alterado)"
                    item["fv_line_gate"] = gate
                    entry.update(antes=gate["antes"])
                    report[STATUS_VALIDADO_FORA].append(entry)
                    continue
                found = index.repair(horizontal, a, t)
                if found is not None:
                    _score, pair, cov_new, shift = found
                    item["points"] = _points(horizontal, a, pair)
                    gate.update({
                        "status": STATUS_REPARADO,
                        "cobertura_depois": [round(c, 3) for c in cov_new],
                        "deslocamento": round(shift, 2),
                        "motivo": "borda fora da linha; faixa movida para o par de linhas "
                                  "estruturais com a mesma largura",
                    })
                    entry.update(deslocamento=round(shift, 2), cobertura_depois=gate["cobertura_depois"])
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
    return report


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
        return ", ".join(f"{e['viga']} S{e['seg']}" for e in report.get(key) or []) or "-"
    return (
        f"ok {report.get('ok', 0)}; reparados [{names(STATUS_REPARADO)}]; "
        f"anulados [{names(STATUS_ANULADO)}]; validados fora [{names(STATUS_VALIDADO_FORA)}]; "
        f"nao auditaveis [{', '.join(report.get('nao_auditavel') or []) or '-'}]"
    )
