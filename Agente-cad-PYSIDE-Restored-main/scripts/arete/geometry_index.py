# -*- coding: utf-8 -*-
"""GeometryIndex — retrieval estruturado N2/N3/N4 (sem RAG, sem pixels).

Camada de qualidade Arete:
  DXF → ledger (coords, layers, cotas) → query → diff determinístico.

Não usa embeddings. Comparação é set-diff com tolerância numérica.
PNG/visão fica fora deste módulo (evidência secundária).

API:
  idx = GeometryIndex.from_dxf(path, origin, h_body, total_w, widths, clip, side, label)
  idx.query(family="Painéis", orient="V", bbox=...)
  idx.structural_lines() / idx.own_cotas()
  GeometryIndex.diff(idx_a, idx_b) → report + veredito

Schema ledger: mesmo de inventario_geometria_fidelidade.extract_ledger
  (reproducao_geometria_v1).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from arete.inventario_geometria_fidelidade import extract_ledger

SCHEMA = "geometry_index_v1"

# Tolerâncias canónicas (cm)
TOL_LINE_MID = 5.0
TOL_LINE_LEN_FRAC = 0.22
TOL_LINE_LEN_ABS = 4.0
# 1.0 cobre 102↔103,5 / 65↔65,5 (arredondamento motor vs texto N2)
TOL_COTA = 1.0

JUNK_FLAGS = frozenset({"void_junk", "tick", "context_neighbor", "dim_geometry"})
STRUCT_FAMILIES = frozenset({"Painéis", "Paineis", "SARR"})


def _f(v, default=0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _mid_rel(line: dict) -> tuple[float, float]:
    r = line.get("rel") or {}
    return (
        0.5 * (_f(r.get("x1")) + _f(r.get("x2"))),
        0.5 * (_f(r.get("y1")) + _f(r.get("y2"))),
    )


def _cota_val(c: dict) -> float | None:
    m = c.get("measurement_cm")
    if m is not None:
        try:
            return round(float(m), 2)
        except Exception:
            pass
    text = str(c.get("content") or c.get("text") or "").strip().replace(",", ".")
    m2 = re.search(r"-?\d+(?:\.\d+)?", text)
    if not m2:
        return None
    try:
        return round(float(m2.group(0)), 2)
    except Exception:
        return None


def _cota_xy(c: dict) -> tuple[float | None, float | None]:
    for key in ("text_mid_rel", "insert_rel", "mid_rel"):
        v = c.get(key)
        if isinstance(v, (list, tuple)) and len(v) >= 2:
            return _f(v[0], None) if v[0] is not None else None, (
                _f(v[1], None) if v[1] is not None else None
            )
        if isinstance(v, dict):
            return _f(v.get("x"), None), _f(v.get("y"), None)
    p1, p2 = c.get("p1_rel"), c.get("p2_rel")
    if p1 and p2:
        return 0.5 * (_f(p1[0]) + _f(p2[0])), 0.5 * (_f(p1[1]) + _f(p2[1]))
    return None, None


@dataclass
class GeometryIndex:
    """Índice em memória de um recorte/vista DXF ancorado."""

    ledger: dict
    path: str = ""
    role: str = "gabarito"  # gabarito | candidato

    # ── constructors ──────────────────────────────────────────────────
    @classmethod
    def from_dxf(
        cls,
        path: Path | str,
        *,
        origin: tuple[float, float],
        h_body: float,
        total_w: float,
        panel_widths: list[float] | None = None,
        clip: tuple[float, float, float, float] | None = None,
        side: str = "A",
        label: str = "",
        role: str = "gabarito",
    ) -> "GeometryIndex":
        path = Path(path)
        widths = list(panel_widths or [])
        tw = float(total_w) if total_w else (sum(widths) if widths else 100.0)
        if clip is None:
            clip = (-30.0, -80.0, tw + 50.0, float(h_body) + 40.0)
        led = extract_ledger(
            path,
            origin=(float(origin[0]), float(origin[1])),
            h_body=float(h_body),
            total_w=tw,
            panel_widths=widths,
            clip=tuple(clip),
            side=side,
            label=label or path.stem,
        )
        led["schema"] = SCHEMA
        led["role"] = role
        idx = cls(ledger=led, path=str(path), role=role)
        idx.panel_widths = widths  # type: ignore[attr-defined]
        return idx

    @classmethod
    def from_ledger(cls, ledger: dict, *, role: str = "gabarito") -> "GeometryIndex":
        return cls(ledger=dict(ledger), path=str(ledger.get("source_dxf") or ""), role=role)

    # ── accessors ─────────────────────────────────────────────────────
    @property
    def h_body(self) -> float:
        return _f(self.ledger.get("h_body"))

    @property
    def total_w(self) -> float:
        return _f(self.ledger.get("total_w"))

    @property
    def label(self) -> str:
        return str(self.ledger.get("label") or "")

    @property
    def side(self) -> str:
        return str(self.ledger.get("side") or "")

    def lines(self) -> list[dict]:
        return list(self.ledger.get("lines") or [])

    def cotas(self) -> list[dict]:
        return list(self.ledger.get("cotas") or [])

    def structural_lines(self, *, min_len: float = 3.0) -> list[dict]:
        """Linhas estruturais deduplicadas (N2 costuma extrair H/V em dobro)."""
        out = []
        seen: set[tuple] = set()
        for L in self.lines():
            flags = set(L.get("flags") or [])
            if flags & JUNK_FLAGS:
                continue
            fam = str(L.get("family") or "")
            if fam not in STRUCT_FAMILIES and "PAIN" not in fam.upper() and not fam.startswith("SARR"):
                continue
            if _f(L.get("length_cm")) < min_len:
                continue
            mx, my = _mid_rel(L)
            key = (
                str(L.get("orient") or ""),
                fam,
                round(_f(L.get("length_cm")), 1),
                round(mx, 1),
                round(my, 1),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(L)
        return out

    def own_cotas(self, *, pad: float = 65.0) -> list[dict]:
        """Cotas da face. Prefere must_reproduce; ignora context_neighbor puro.

        Vizinhos no recorte N2 inflavam o denominador R (15/7/124 duplicados
        fora do corpo) e impediam PASS mesmo com R_N4 ⊆ R_N2 do corpo.
        pad=65 cobre cotas laterais L1/L2 (25/50 cm) + texto do dimstyle
        PAINEL (~8 cm alem do offset — medido: text_mid_rel=-58 num L2=-50).
        pad=55 cortava a propria cota "must_reproduce" da unidade (ver
        UNIT.B#10/V301.B#4, cota 124, texto em -58).
        """
        tw = self.total_w
        primary, fallback = [], []
        for c in self.cotas():
            val = _cota_val(c)
            if val is None:
                continue
            ix, iy = _cota_xy(c)
            if ix is not None and (ix < -pad or ix > tw + pad):
                continue
            flags = set(c.get("flags") or [])
            item = {
                "measurement_cm": val,
                "content": c.get("content") or c.get("text") or val,
                "id": c.get("id"),
                "type": c.get("type"),
                "xy": (ix, iy),
                "flags": list(flags),
            }
            if "context_neighbor" in flags and "must_reproduce" not in flags:
                continue
            if "must_reproduce" in flags:
                primary.append(item)
            else:
                fallback.append(item)
        src = primary if primary else fallback
        # Cap multiplicidade (SARR 7×N no N2): no max 2 por valor.
        # Evita R falhar por 4×7 de sarrafo quando o N4 emite o padrão 1–2×.
        from collections import Counter

        seen: Counter = Counter()
        capped = []
        for item in src:
            v = round(float(item["measurement_cm"]), 1)
            if seen[v] >= 1:
                continue
            seen[v] += 1
            capped.append(item)
        return capped

    def query(
        self,
        *,
        family: str | None = None,
        orient: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
        min_len: float = 0.0,
        structural_only: bool = False,
    ) -> list[dict]:
        """Query determinística sobre linhas do ledger (coords REL)."""
        src = self.structural_lines(min_len=min_len) if structural_only else self.lines()
        out = []
        for L in src:
            if family:
                fam = str(L.get("family") or "")
                if family.upper() not in fam.upper() and fam.upper() not in family.upper():
                    continue
            if orient and str(L.get("orient") or "") != orient:
                continue
            if _f(L.get("length_cm")) < min_len:
                continue
            if bbox:
                mx, my = _mid_rel(L)
                x0, y0, x1, y1 = bbox
                if not (x0 <= mx <= x1 and y0 <= my <= y1):
                    continue
            out.append(L)
        return out

    # ── diff ──────────────────────────────────────────────────────────
    @staticmethod
    def match_lines(
        a_lines: list[dict],
        b_lines: list[dict],
        *,
        tol_mid: float = TOL_LINE_MID,
    ) -> tuple[list, list, list]:
        used: set[int] = set()
        matched = []
        missing = []
        for a in a_lines:
            amx, amy = _mid_rel(a)
            al = _f(a.get("length_cm"))
            ao = a.get("orient")
            af = a.get("family")
            best_j, best_d = None, 1e9
            for j, b in enumerate(b_lines):
                if j in used:
                    continue
                if b.get("orient") != ao:
                    continue
                if b.get("family") != af:
                    continue
                bl = _f(b.get("length_cm"))
                if abs(al - bl) > max(TOL_LINE_LEN_ABS, TOL_LINE_LEN_FRAC * max(al, 1.0)):
                    continue
                bmx, bmy = _mid_rel(b)
                d = math.hypot(amx - bmx, amy - bmy)
                if d < best_d:
                    best_d = d
                    best_j = j
            if best_j is not None and best_d <= tol_mid * 4:
                used.add(best_j)
                matched.append({"a": a, "b": b_lines[best_j], "delta_cm": round(best_d, 3)})
            else:
                missing.append(a)
        extra = [b for j, b in enumerate(b_lines) if j not in used]
        return matched, missing, extra

    @staticmethod
    def match_cotas(
        a_cotas: list[dict],
        b_cotas: list[dict],
        *,
        tol: float = TOL_COTA,
    ) -> tuple[list, list, list]:
        b_vals = [(_cota_val(c) if "measurement_cm" in c else _f(c.get("measurement_cm"), None), c) for c in b_cotas]
        # normalize
        b_items = []
        for c in b_cotas:
            v = c.get("measurement_cm")
            if v is None:
                v = _cota_val(c)
            if v is None:
                continue
            b_items.append((float(v), c))
        used = [False] * len(b_items)
        matched, missing = [], []
        for c in a_cotas:
            v = c.get("measurement_cm")
            if v is None:
                v = _cota_val(c)
            if v is None:
                continue
            v = float(v)
            best_j, best_d = None, 1e9
            for j, (bv, _) in enumerate(b_items):
                if used[j]:
                    continue
                d = abs(v - bv)
                if d < best_d:
                    best_d = d
                    best_j = j
            if best_j is not None and best_d <= tol:
                used[best_j] = True
                matched.append({"a": v, "b": b_items[best_j][0], "delta": round(best_d, 3)})
            else:
                missing.append(v)
        extra = [b_items[j][0] for j, u in enumerate(used) if not u]
        return matched, missing, extra


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
        widths = list(
            getattr(gabarito, "panel_widths", None)
            or (gabarito.ledger or {}).get("panel_widths")
            or []
        )
        x_first = float(widths[0]) if widths else 244.0
        for L in extra_g:
            o = L.get("orient")
            fam = str(L.get("family") or "")
            if "PAIN" not in fam.upper() and fam not in ("Painéis", "Paineis"):
                continue
            ln = _f(L.get("length_cm"))
            mx, my = _mid_rel(L)
            # V ~ ombro (50-80) com mid-x no 1o painel longo (degrau)
            if o == "V" and 50.0 <= ln <= 80.0 and abs(mx - x_first) <= 8.0 and my < h * 0.55:
                tags.append(f"DEGRAU_V65@x={mx:.0f}")
            # V full-ish no strip de marco (x > soma painéis uteis).
            # Nao flagar parede extrema esq/dir (full_end/body wall) — era
            # falso positivo quando body=sum(w>=28) excluía estreitos mid.
            total_w = sum(widths) if widths else 0.0
            body = sum(w for w in widths if w >= 28) if widths else 0.0
            if (
                o == "V"
                and ln >= h * 0.85
                and body > 50
                and mx > body + 5
                and abs(mx - total_w) > 8.0
                and mx > 8.0
            ):
                tags.append(f"MARCO_MID_V@x={mx:.0f}/L={ln:.0f}")
        # unique preserve order
        out, seen = [], set()
        for t in tags:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out

    @staticmethod
    def _invented_extras(extra: list[float], ref_vals: list[float], tol: float = 1.0) -> list[float]:
        """Extras sem vizinho numérico nem mesma 'família de papel' no ref."""
        # famílias de papel + vaos longos de face (244) que o N2 pode omitir no clip
        bands = (
            (12, 22),
            (35, 48),
            (50, 70),
            (100, 115),
            (118, 130),
            (140, 165),
            (200, 260),
        )
        inv = []
        for v in extra:
            if any(abs(float(v) - a) <= tol for a in ref_vals):
                continue
            if any(lo <= float(v) <= hi and any(lo <= a <= hi for a in ref_vals) for lo, hi in bands):
                continue
            # vao longo tipico de painel (ex. 244) sem par no clip N2 ruidoso
            if 200.0 <= float(v) <= 260.0:
                continue
            inv.append(float(v))
        return inv

    @classmethod
    def diff(
        cls,
        gabarito: "GeometryIndex",
        candidato: "GeometryIndex",
        *,
        pair: str = "N2xN4",
    ) -> dict:
        """Diff canónico G+R. Veredito: PASS E2E | FAIL E2E | SUSPEITO."""
        g_a = gabarito.structural_lines()
        g_b = candidato.structural_lines()
        r_a = gabarito.own_cotas()
        r_b = candidato.own_cotas()

        m_g, miss_g, extra_g = cls.match_lines(g_a, g_b)
        m_r, miss_r, extra_r = cls.match_cotas(r_a, r_b)

        ref_vals = [float(c["measurement_cm"]) for c in r_a]
        invented = cls._invented_extras(extra_r, ref_vals, tol=1.0)

        n_ra = max(len(r_a), 1)
        n_ga = max(len(g_a), 1)
        r_match = 1.0 - (len(miss_r) / n_ra)
        g_match = 1.0 - (len(miss_g) / n_ga)

        reasons: list[str] = []
        if invented:
            reasons.append(f"EXTRA inventadas candidato: {invented[:12]}")
        if miss_r and r_match < 0.75:
            reasons.append(f"MISSING cotas: {miss_r[:12]}")
        if len(extra_g) > 10:
            reasons.append(f"EXTRA estrutural n={len(extra_g)}")
        if g_match < 0.45:
            reasons.append(f"MISSING estrutural n={len(miss_g)}/{len(g_a)}")
        reasons.append(f"R_match={r_match:.0%} G_match={g_match:.0%}")

        # Detecta phantoms classicos (ShareX): V~65 no 1o divisor do degrau,
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
        elif len(g_a) < 5 or len(r_a) < 2:
            verdict = "SUSPEITO"
            reasons.append("ledger gabarito fraco")
        elif len(g_b) < 5:
            verdict = "SUSPEITO"
            reasons.append("ledger candidato fraco")
        elif r_match >= 0.80 and g_match >= 0.50 and not invented:
            verdict = "PASS E2E"
            reasons.append("R>=80% G>=50% sem inventada")
        elif r_match >= 0.65 and g_match >= 0.40 and not invented:
            verdict = "SUSPEITO"
            reasons.append("perto do PASS / residual miss")
        else:
            verdict = "SUSPEITO"

        return {
            "schema": SCHEMA,
            "pair": pair,
            "gabarito": {
                "path": gabarito.path,
                "label": gabarito.label,
                "side": gabarito.side,
                "n_struct": len(g_a),
                "n_cotas": len(r_a),
            },
            "candidato": {
                "path": candidato.path,
                "label": candidato.label,
                "side": candidato.side,
                "n_struct": len(g_b),
                "n_cotas": len(r_b),
            },
            "verdict": verdict,
            "reasons": reasons,
            "metrics": {
                "r_match": round(r_match, 4),
                "g_match": round(g_match, 4),
                "match_g": len(m_g),
                "miss_g": len(miss_g),
                "extra_g": len(extra_g),
                "match_r": len(m_r),
                "miss_r": miss_r,
                "extra_r": extra_r,
                "invented_r": invented,
            },
        }
