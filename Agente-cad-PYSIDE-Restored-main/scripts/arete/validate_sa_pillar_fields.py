"""Valida população SA de pilares: face_beams, passa_esq/dir, chegadas, lajes, HTML N1."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

HTML_ROOT = ROOT / "scripts" / "arete" / "html_fichas" / "Obra_TREINO_1"
DADOS = Path(r"D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1")


def latest_pack() -> Path | None:
    if not HTML_ROOT.is_dir():
        return None
    packs = sorted(
        [p for p in HTML_ROOT.iterdir() if p.is_dir() and "13P" in p.name],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return packs[0] if packs else None


def load_estado() -> dict | None:
    for name in ("estado_13_PAV.json", "estado_TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA.json"):
        p = DADOS / name
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    # search
    for p in DADOS.glob("estado_*.json"):
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def analyze_pillars_from_enrich(estado: dict) -> dict:
    from src.core.pillar_face_beams import enrich_pillar_report_with_beams

    pillars = estado.get("pilares") or estado.get("pillars") or []
    beams = estado.get("vigas") or estado.get("beams") or []
    # normalize report dict
    report = {}
    for p in pillars:
        if not isinstance(p, dict):
            continue
        nm = str(p.get("name") or p.get("key") or "").strip()
        if not nm:
            continue
        report[nm] = {
            "name": nm,
            "points": p.get("points") or [],
            "lajes": list(p.get("lajes") or p.get("lajes_adjacentes") or []),
        }
    # beams list
    blist = []
    for b in beams:
        if isinstance(b, dict):
            blist.append(b)
    enrich_pillar_report_with_beams(report, blist)
    return report


def scan_html_pack(pack: Path) -> dict:
    stats = {
        "n_html": 0,
        "has_passa_esquina": 0,
        "has_contorno": 0,
        "has_chegada": 0,
        "sample": [],
    }
    for html in pack.rglob("P*.html"):
        if "n3" in str(html).lower() and "variants" in str(html).lower():
            continue
        text = html.read_text(encoding="utf-8", errors="ignore")
        stats["n_html"] += 1
        if "Esquina" in text or "passa_esq" in text or "Passam — Esquina" in text:
            stats["has_passa_esquina"] += 1
        if "Contorno Esquerda" in text or "Contorno Direita" in text:
            stats["has_contorno"] += 1
        if "Chegada" in text or "v_ch1" in text:
            stats["has_chegada"] += 1
        if len(stats["sample"]) < 5 and ("P1" in html.name or "P2" in html.name):
            # extract face lines
            faces = re.findall(
                r'(Lado [ABCD]|Esquina [A-D]{2}|Passam|Chegada|Laje)[^<]{0,80}',
                text,
            )
            stats["sample"].append({"file": str(html.relative_to(pack)), "hits": faces[:12]})
    return stats


def summarize_report(report: dict) -> dict:
    n = len(report)
    n_with_fb = 0
    n_passa = 0
    n_para = 0
    n_laje = 0
    corners = Counter()
    empty_faces = 0
    samples = []
    for nm, entry in sorted(report.items(), key=lambda x: x[0]):
        fb = entry.get("face_beams") or {}
        if fb:
            n_with_fb += 1
        has_any_passa = False
        has_any_para = False
        for fid, data in fb.items():
            pe = data.get("passa_esq")
            pd = data.get("passa_dir")
            if pe:
                n_passa += 1
                has_any_passa = True
                corners[data.get("corner_esq") or f"{fid}_esq"] += 1
            if pd:
                n_passa += 1
                has_any_passa = True
                corners[data.get("corner_dir") or f"{fid}_dir"] += 1
            if data.get("para"):
                n_para += len(data["para"])
                has_any_para = True
            if not pe and not pd and not data.get("para"):
                empty_faces += 1
        lajes = entry.get("lajes") or []
        if any(le.get("laje") for le in lajes if isinstance(le, dict)):
            n_laje += 1
        if nm in ("P1", "P2", "P3", "P10", "P18") or (len(samples) < 8 and (has_any_passa or has_any_para)):
            samples.append({
                "name": nm,
                "passa": {
                    f: {
                        "esq": (fb.get(f) or {}).get("passa_esq"),
                        "dir": (fb.get(f) or {}).get("passa_dir"),
                        "para": (fb.get(f) or {}).get("para"),
                    }
                    for f in "ABCD"
                    if fb.get(f)
                },
                "lajes": [
                    {"side": le.get("side"), "laje": le.get("laje"), "ct": le.get("content_type")}
                    for le in lajes if isinstance(le, dict)
                ][:8],
                "viga_que_passa": entry.get("viga_que_passa"),
                "viga_que_para": entry.get("viga_que_para"),
            })
    return {
        "n_pillars": n,
        "n_with_face_beams": n_with_fb,
        "n_passa_slots_filled": n_passa,
        "n_para_entries": n_para,
        "n_with_laje": n_laje,
        "empty_faces": empty_faces,
        "corners": dict(corners),
        "samples": samples,
    }


def main() -> None:
    pack = latest_pack()
    print("=== PACK HTML ===")
    print("latest:", pack)
    if pack:
        hs = scan_html_pack(pack)
        print(json.dumps(hs, ensure_ascii=False, indent=2))

    print("\n=== ESTADO + ENRICH (motor atual) ===")
    estado = load_estado()
    if not estado:
        # try analysis state in html pack
        if pack:
            for p in pack.rglob("analysis_state*.json"):
                estado = json.loads(p.read_text(encoding="utf-8"))
                print("estado from", p)
                break
            for p in pack.rglob("estado*.json"):
                estado = json.loads(p.read_text(encoding="utf-8"))
                print("estado from", p)
                break
    if not estado:
        print("NO ESTADO — tentando pillars from pack meta")
        # build from n3 contracts?
        sys.exit(2)

    # detect structure
    print("estado keys", list(estado.keys())[:30])
    report = analyze_pillars_from_enrich(estado)
    summary = summarize_report(report)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))

    # quality gates
    ok = True
    if summary["n_pillars"] < 1:
        print("FAIL: zero pillars")
        ok = False
    if summary["n_with_face_beams"] < summary["n_pillars"] * 0.5:
        print("WARN: menos de 50% com face_beams")
    if summary["n_passa_slots_filled"] < 1 and summary["n_para_entries"] < 1:
        print("FAIL: nenhum passa/para preenchido")
        ok = False
    print("\nRESULT:", "PASS" if ok else "NEEDS_REVIEW")
    out = ROOT / "scripts" / "arete" / "relatorios" / "sa_pillar_validation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {"pack": str(pack), "summary": summary, "ok": ok},
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print("wrote", out)


if __name__ == "__main__":
    main()
