#!/usr/bin/env python3
"""Audit N1/N3 LAJ outputs against N2/N4 references for Obra_TREINO_1 13_PAV.

The script is intentionally conservative: it reports hashes, bbox deltas and
missing artifacts, and creates a JSON report. Visual contact sheets are best
effort and generated only when matplotlib/ezdxf drawing are available.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path | None) -> str | None:
    if not path or not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def bbox_from_coords(coords: list) -> list[float] | None:
    pts = [(float(p[0]), float(p[1])) for p in coords or [] if isinstance(p, (list, tuple)) and len(p) >= 2]
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return [min(xs), min(ys), max(xs), max(ys)]


def bbox_delta(a: list[float] | None, b: list[float] | None) -> list[float] | None:
    if not a or not b:
        return None
    return [round(a[i] - b[i], 3) for i in range(4)]


def find_file(root: Path, patterns: list[str]) -> Path | None:
    for pattern in patterns:
        matches = sorted(root.rglob(pattern)) if root.exists() else []
        if matches:
            return matches[0]
    return None


def audit(obra_path: Path, pavimento: str) -> dict[str, Any]:
    fase4_lajes = obra_path / "Fase-4_Sincronizacao" / "JSON_Lajes"
    fase6 = obra_path / "Fase-6_Execucao_CAD"
    n1_dir = obra_path / "Fase-3_N1_LAJ"
    n3_dir = obra_path / "Fase-3_N3_LAJ"
    n2_dir = obra_path / "Fase-2_Triagem"

    rows = []
    for n2_json in sorted(fase4_lajes.glob("L*.json")):
        lid = n2_json.stem.upper()
        n2 = load_json(n2_json)
        n1 = load_json(n1_dir / f"{lid}.json")
        bbox_n1 = bbox_from_coords(n1.get("coordenadas") or n1.get("points") or [])
        bbox_n2 = bbox_from_coords(n2.get("coordenadas") or [])
        n3_dxf = find_file(n3_dir, [f"LJ_preview_{lid}.dxf", "LJ_stog_quality.dxf"])
        n4_dxf = find_file(fase6, [f"LJ_preview_{lid}.dxf", "LJ_stog_quality.dxf"])
        n2_cut = find_file(n2_dir, [f"*{lid}*.dxf"])
        structural_clean = find_file(obra_path / "Fase-2_Triagem", ["*_clean*.dxf", "*.dxf"])
        delta = bbox_delta(bbox_n1, bbox_n2)
        canonical_ok = bool(n3_dxf and n4_dxf and bbox_n1 and bbox_n2 and max(abs(x) for x in (delta or [999])) <= 1.0)
        rows.append(
            {
                "laje": lid,
                "n2_aprovado_usado_como_professor": str(n2_json),
                "hash_estrutural_limpo": sha256(structural_clean),
                "hash_recorte_n2": sha256(n2_cut),
                "bbox_n1": bbox_n1,
                "bbox_n2": bbox_n2,
                "delta_contorno": delta,
                "n3_gerado": str(n3_dxf) if n3_dxf else None,
                "n4_publicado": str(n4_dxf) if n4_dxf else None,
                "veredito_canonico": "ok" if canonical_ok else "pendente",
                "veredito_visual": "nao_avaliado",
            }
        )
    return {"obra": str(obra_path), "pavimento": pavimento, "total": len(rows), "lajes": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit LAJ N1/N3 13_PAV")
    parser.add_argument("--obra", default="D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1")
    parser.add_argument("--pavimento", default="13_PAV")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    report = audit(Path(args.obra), args.pavimento)
    out = Path(args.out) if args.out else Path(args.obra) / "audit_laj_n1_n3_13pav.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Audit LAJ N1/N3: {report['total']} lajes -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
