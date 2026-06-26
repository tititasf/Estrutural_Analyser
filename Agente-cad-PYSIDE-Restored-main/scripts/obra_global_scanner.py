#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
obra_global_scanner.py — Sprint 2: Scanner global de DXFs limpos aprovados.

Varre todas as obras em DADOS-OBRAS, coleta metadados rápidos de cada DXF limpo
(Fase-2_Triagem/Estruturais_Pavimentos_Limpos/) e gera obra_global_context.json
com o contexto completo da obra (pavimentos, contagens de peças, torres etc.).

Saída padrão: data/obra_global_context.json  (relativo ao PROJECT_ROOT)
Também salva por obra: DADOS-OBRAS/{Obra_X}/obra_global_context.json

Uso:
    python scripts/obra_global_scanner.py                     # todas as obras
    python scripts/obra_global_scanner.py --obra Obra_TREINO_1  # só uma
    python scripts/obra_global_scanner.py --force              # força re-scan mesmo se recente
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Paths ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT  = Path("D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main")
DADOS_OBRAS   = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
DB_SQLITE     = Path("D:/Agente-cad-PYSIDE/project_data.vision")
OUTPUT_GLOBAL = PROJECT_ROOT / "data" / "obra_global_context.json"

SCANNER_VERSION = "1.1"

# ── Pavimento type inference ───────────────────────────────────────────────────

_PAV_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"FUND|FUNDA",      re.I), "fundacao"),
    (re.compile(r"SUBSOL|SUB-SOL",  re.I), "subsolo"),
    (re.compile(r"TERRE|TER\b|TER-",re.I), "terreo"),
    (re.compile(r"TIPO|TIP\b",      re.I), "tipo"),
    (re.compile(r"ÁTICO|ATICO|ATC", re.I), "atico"),
    (re.compile(r"COB|COV",         re.I), "cobertura"),
    (re.compile(r"DECK",            re.I), "deck"),
    (re.compile(r"BAR|BARR",        re.I), "barrilete"),
    (re.compile(r"CAIXA.AGUA",      re.I), "caixa_agua"),
    (re.compile(r"\bPAV\b|\bPV\b",  re.I), "pavimento"),
]


def _infer_pav_type(stem: str) -> str:
    for pat, label in _PAV_PATTERNS:
        if pat.search(stem):
            return label
    if re.search(r"\d", stem):
        return "pavimento"
    return "desconhecido"


# ── DXF quick scan ─────────────────────────────────────────────────────────────

def _scan_dxf(dxf_path: Path) -> dict:
    """Lê um DXF e retorna metadados leves (entity_count, layer_count, top_layers)."""
    try:
        import ezdxf
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()

        layer_counter: Counter = Counter()
        total = 0
        for ent in msp:
            total += 1
            try:
                layer_counter[ent.dxf.layer] += 1
            except Exception:
                pass

        top_layers = [lyr for lyr, _ in layer_counter.most_common(6)]
        layer_count = len(doc.layers)

        return {
            "entity_count": total,
            "layer_count":  layer_count,
            "top_layers":   top_layers,
            "scan_ok":      True,
        }
    except Exception as exc:
        return {
            "entity_count": 0,
            "layer_count":  0,
            "top_layers":   [],
            "scan_ok":      False,
            "scan_error":   str(exc)[:120],
        }


# ── Fase-3 counts ──────────────────────────────────────────────────────────────

def _read_fase3_counts(obra_path: Path) -> dict:
    """Lê ancoras_*.json da Fase-3 e retorna contagens pilar/viga/laje."""
    f3 = obra_path / "Fase-3_Interpretacao_Extracao"
    result = {
        "fase3_available": False,
        "pilar_count": 0,
        "viga_count":  0,
        "laje_count":  0,
    }
    if not f3.exists():
        return result

    def _count(fname: str) -> int:
        p = f3 / fname
        if not p.exists():
            return 0
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            return len(d) if isinstance(d, (dict, list)) else 0
        except Exception:
            return 0

    pc = _count("ancoras_pilares.json")
    vc = _count("ancoras_vigas.json")
    lc = _count("ancoras_lajes.json")

    if pc or vc or lc:
        result["fase3_available"] = True
        result["pilar_count"]     = pc
        result["viga_count"]      = vc
        result["laje_count"]      = lc

    return result


# ── obra_recortes summary ──────────────────────────────────────────────────────

def _read_recortes_summary(obra_name: str) -> dict:
    """Lê obra_recortes do SQLite para a obra, retorna resumo."""
    summary: dict = {"recortes_total": 0, "recortes_torres": 0, "recortes_detalhes": 0}
    try:
        conn = sqlite3.connect(str(DB_SQLITE))
        cur = conn.cursor()
        cur.execute(
            "SELECT recorte_type, COUNT(*) FROM obra_recortes "
            "WHERE obra_name=? GROUP BY recorte_type",
            (obra_name,)
        )
        for rtype, cnt in cur.fetchall():
            summary["recortes_total"] += cnt
            if rtype == "torre":
                summary["recortes_torres"] = cnt
            elif rtype == "detalhe":
                summary["recortes_detalhes"] = cnt
        conn.close()
    except Exception:
        pass
    return summary


# ── Scan de uma obra ────────────────────────────────────────────────────────────

def scan_obra(obra_name: str, verbose: bool = True) -> Optional[dict]:
    """Escaneia uma obra e retorna seu context dict."""
    obra_path = DADOS_OBRAS / obra_name
    if not obra_path.is_dir():
        if verbose:
            print(f"  [SKIP] {obra_name}: pasta não encontrada")
        return None

    limpos_dir = obra_path / "Fase-2_Triagem" / "Estruturais_Pavimentos_Limpos"
    if not limpos_dir.exists():
        if verbose:
            print(f"  [SKIP] {obra_name}: sem Fase-2 Limpos")
        return None

    dxf_files = sorted(limpos_dir.glob("*.dxf"))
    if not dxf_files:
        if verbose:
            print(f"  [SKIP] {obra_name}: 0 DXFs limpos")
        return None

    if verbose:
        print(f"  [{obra_name}] {len(dxf_files)} DXFs limpos ...", end=" ", flush=True)

    pavimentos: list[dict] = []
    total_entities = 0

    for dxf_path in dxf_files:
        meta = _scan_dxf(dxf_path)
        pav_type = _infer_pav_type(dxf_path.stem)
        total_entities += meta["entity_count"]
        pavimentos.append({
            "pav_name":     dxf_path.stem,
            "dxf_name":     dxf_path.name,
            "pav_type":     pav_type,
            "entity_count": meta["entity_count"],
            "layer_count":  meta["layer_count"],
            "top_layers":   meta["top_layers"],
            "scan_ok":      meta["scan_ok"],
            **({"scan_error": meta["scan_error"]} if not meta["scan_ok"] else {}),
        })

    fase3 = _read_fase3_counts(obra_path)
    recortes = _read_recortes_summary(obra_name)

    # Tipos de pavimento presentes
    pav_types_present = sorted(set(p["pav_type"] for p in pavimentos))

    ctx = {
        "obra_name":        obra_name,
        "scan_ts":          datetime.now(timezone.utc).isoformat(),
        "limpos_path":      str(limpos_dir),
        "total_pavimentos": len(pavimentos),
        "total_entities":   total_entities,
        "pav_types":        pav_types_present,
        "pavimentos":       pavimentos,
        **fase3,
        **recortes,
    }

    if verbose:
        print(f"OK ({total_entities} ent, pilares={fase3['pilar_count']}, vigas={fase3['viga_count']})")

    return ctx


# ── Scanner principal ───────────────────────────────────────────────────────────

def run_scanner(
    obras_filter: Optional[list[str]] = None,
    force: bool = False,
    verbose: bool = True,
) -> dict:
    """Escaneia todas as obras (ou as filtradas) e retorna o contexto global."""

    # Carrega contexto existente para merge incremental
    existing: dict = {}
    if OUTPUT_GLOBAL.exists() and not force:
        try:
            existing = json.loads(OUTPUT_GLOBAL.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    # Descobre obras
    if obras_filter:
        obra_names = obras_filter
    else:
        obra_names = sorted(d.name for d in DADOS_OBRAS.iterdir() if d.is_dir())

    if verbose:
        print(f"[obra_global_scanner] {len(obra_names)} obras a escanear")

    obras_dict: dict = existing.get("obras", {})
    scanned = 0
    skipped = 0

    for obra_name in obra_names:
        # Pula se já escaneado recentemente (menos de 1h) e não force
        if not force and obra_name in obras_dict:
            ts_str = obras_dict[obra_name].get("scan_ts", "")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str)
                    age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
                    if age_h < 1.0:
                        skipped += 1
                        continue
                except Exception:
                    pass

        ctx = scan_obra(obra_name, verbose=verbose)
        if ctx is not None:
            obras_dict[obra_name] = ctx
            scanned += 1

    obras_com_limpos = [n for n, v in obras_dict.items() if v.get("total_pavimentos", 0) > 0]
    total_pav = sum(v.get("total_pavimentos", 0) for v in obras_dict.values())
    total_ent = sum(v.get("total_entities", 0) for v in obras_dict.values())

    global_ctx = {
        "scanner_version":  SCANNER_VERSION,
        "generated_at":     datetime.now(timezone.utc).isoformat(),
        "total_obras":      len(obras_dict),
        "obras_com_limpos": len(obras_com_limpos),
        "total_pavimentos": total_pav,
        "total_entities":   total_ent,
        "obras":            obras_dict,
    }

    # Salva global
    OUTPUT_GLOBAL.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_GLOBAL.write_text(
        json.dumps(global_ctx, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    if verbose:
        print(f"\n[obra_global_scanner] DONE")
        print(f"  obras escaneadas : {scanned}  (skipped: {skipped})")
        print(f"  obras com limpos : {len(obras_com_limpos)}")
        print(f"  total pavimentos : {total_pav}")
        print(f"  total entidades  : {total_ent:,}")
        print(f"  saída            : {OUTPUT_GLOBAL}")

    return global_ctx


# ── API pública ────────────────────────────────────────────────────────────────

def get_global_context(obra_name: Optional[str] = None) -> dict:
    """
    Retorna o contexto global (ou de uma obra específica) do cache JSON.
    Se não existir, executa o scanner primeiro.
    """
    if not OUTPUT_GLOBAL.exists():
        run_scanner(verbose=False)

    ctx = json.loads(OUTPUT_GLOBAL.read_text(encoding="utf-8"))
    if obra_name:
        return ctx.get("obras", {}).get(obra_name, {})
    return ctx


def get_obra_pavimentos(obra_name: str) -> list[dict]:
    """Retorna lista de pavimentos de uma obra do cache global."""
    obra_ctx = get_global_context(obra_name)
    return obra_ctx.get("pavimentos", [])


def get_obra_pav_types(obra_name: str) -> list[str]:
    """Retorna tipos de pavimento presentes em uma obra (terreo, tipo, cobertura, etc.)."""
    obra_ctx = get_global_context(obra_name)
    return obra_ctx.get("pav_types", [])


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Obra Global Scanner — Sprint 2")
    ap.add_argument("--obra",  nargs="+", metavar="NOME", help="Escanear apenas obra(s) específica(s)")
    ap.add_argument("--force", action="store_true",       help="Força re-scan mesmo se recente")
    ap.add_argument("--query", metavar="OBRA_NAME",       help="Consulta contexto de uma obra (sem escanear)")
    ap.add_argument("--quiet", action="store_true",       help="Sem output verbose")
    args = ap.parse_args()

    if args.query:
        ctx = get_global_context(args.query)
        if ctx:
            print(json.dumps(ctx, ensure_ascii=False, indent=2))
        else:
            print(f"[WARN] Obra '{args.query}' não encontrada no contexto global.")
            print(f"       Execute o scanner primeiro: python scripts/obra_global_scanner.py")
        return

    run_scanner(
        obras_filter=args.obra,
        force=args.force,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
