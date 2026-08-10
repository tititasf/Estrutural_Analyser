#!/usr/bin/env python3
"""Registra veredito visual padronizado no relatorio.json do g2v_harness.

Mesmo schema para PIL/LAJ/FV/LV. Usa validar_veredito_cli do harness.
Gera pacote de dossiê com paths absolutos (não sela Arete sozinho).

Exemplos:
  python scripts/arete/qa_g2v_record_verdict.py \\
    --relatorio scripts/arete/relatorios/g2v/20260716_150103/relatorio.json \\
    --item V327 --veredito PASS --confianca 0.85 \\
    --checklist-all-true --resumo \"par N1xN2 coerente\"

  python scripts/arete/qa_g2v_record_verdict.py --relatorio ... --from-json verdict.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.arete.g2v_harness import validar_veredito_cli  # noqa: E402

SCHEMA = "arete.g2v_recorded_verdict/v1"
CHECKLIST_KEYS = (
    "fonte_atual_confirmada",
    "recorte_alvo_preciso",
    "contorno_area_interna",
    "cotas_valores",
    "cotas_posicao_legibilidade",
    "linhas_paineis",
    "hlaz",
    "hachuras_apoio",
    "sem_contaminacao_vizinha",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_relatorio(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def find_item(relatorio: dict, item: str) -> dict | None:
    for row in relatorio.get("itens") or []:
        if str(row.get("elemento_id") or "").upper() == item.upper():
            return row
    return None


def build_verdict_payload(
    *,
    veredito: str,
    confianca: float,
    resumo: str,
    checklist: dict[str, bool | None],
    achados: list[dict],
    agent: str,
    svgs: list[str],
    manifesto: str | None,
) -> dict:
    payload = {
        "_backend": "cli",
        "aguardando_agente": False,
        "recorded_at": utc_now(),
        "recorded_by": agent,
        "svgs_lidos": list(svgs),
        "manifesto_svg": manifesto,
        "veredito": veredito.upper(),
        "confianca": confianca,
        "checklist_visual": checklist,
        "achados": achados,
        "resumo": resumo,
        "schema": SCHEMA,
    }
    ok, reason = validar_veredito_cli(payload)
    if not ok:
        raise ValueError(reason or "veredito inválido")
    return payload


def record_item(
    relatorio_path: Path,
    *,
    item: str,
    payload: dict,
    backend: str = "cli",
    dossie_dir: Path | None = None,
) -> dict:
    relatorio = load_relatorio(relatorio_path)
    row = find_item(relatorio, item)
    if row is None:
        raise SystemExit(f"item {item} ausente em {relatorio_path}")
    if row.get("erro"):
        raise SystemExit(f"item {item} bloqueado no harness: {row['erro']}")
    vereditos = row.setdefault("vereditos", {})
    existing = vereditos.get(backend) or {}
    # preserve svgs list from stub if present
    if not payload.get("svgs_lidos") and existing.get("svgs_para_ler"):
        payload["svgs_lidos"] = list(existing["svgs_para_ler"])
    if not payload.get("manifesto_svg"):
        payload["manifesto_svg"] = existing.get("manifesto_svg") or row.get("svg_manifest_path")
    vereditos[backend] = payload
    relatorio_path.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")

    pack_dir = dossie_dir or (relatorio_path.parent / "vereditos_registrados")
    pack_dir.mkdir(parents=True, exist_ok=True)
    pack = {
        "schema": SCHEMA,
        "relatorio": str(relatorio_path.resolve()),
        "classe": row.get("classe"),
        "item": row.get("elemento_id"),
        "par": row.get("par") or relatorio.get("par"),
        "pavimento": row.get("pavimento") or relatorio.get("pavimento"),
        "backend": backend,
        "veredito": payload.get("veredito"),
        "confianca": payload.get("confianca"),
        "recorded_at": payload.get("recorded_at"),
        "svg_paths": row.get("svg_paths") or payload.get("svgs_lidos") or [],
        "svg_manifest_path": row.get("svg_manifest_path"),
        "html_path": row.get("html_path"),
        "payload": payload,
        "anti_superselo": (
            "PASS visual registrado ≠ selagem Arete completa; "
            "ainda exige gates de classe e apply explícito quando couber."
        ),
    }
    out = pack_dir / f"{row.get('classe')}_{row.get('elemento_id')}_{backend}.json"
    out.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    md = pack_dir / f"{row.get('classe')}_{row.get('elemento_id')}_{backend}.md"
    md.write_text(
        "\n".join([
            f"# Veredito visual {row.get('classe')} {row.get('elemento_id')}",
            "",
            f"- Veredito: **{payload.get('veredito')}** (confiança {payload.get('confianca')})",
            f"- Par: `{pack.get('par')}`",
            f"- Relatório: `{pack['relatorio']}`",
            f"- Pacote: `{out.resolve()}`",
            f"- Resumo: {payload.get('resumo')}",
            "",
            "## SVGs lidos",
            "",
            *[f"- `{p}`" for p in (pack.get("svg_paths") or [])[:40]],
            "",
            pack["anti_superselo"],
            "",
        ]),
        encoding="utf-8",
    )
    return {"relatorio": str(relatorio_path.resolve()), "pack": str(out.resolve()), "md": str(md.resolve()), "veredito": payload.get("veredito")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--relatorio", type=Path, required=True)
    parser.add_argument("--item", required=True)
    parser.add_argument("--backend", default="cli")
    parser.add_argument("--from-json", type=Path, help="JSON com veredito/checklist/achados")
    parser.add_argument("--veredito", choices=("PASS", "FAIL", "SUSPEITO"))
    parser.add_argument("--confianca", type=float, default=0.8)
    parser.add_argument("--resumo", default="")
    parser.add_argument("--checklist-all-true", action="store_true")
    parser.add_argument("--achado", action="append", default=[], help="JSON object string")
    parser.add_argument("--agent", default="qa-global-evidencias")
    parser.add_argument("--dossie-dir", type=Path)
    args = parser.parse_args()

    if args.from_json:
        raw = json.loads(args.from_json.read_text(encoding="utf-8"))
        veredito = str(raw.get("veredito") or "").upper()
        confianca = float(raw.get("confianca") or 0.0)
        resumo = str(raw.get("resumo") or "")
        checklist = raw.get("checklist_visual") or {}
        achados = raw.get("achados") or []
        agent = str(raw.get("recorded_by") or args.agent)
    else:
        if not args.veredito:
            parser.error("informe --veredito ou --from-json")
        veredito = args.veredito
        confianca = args.confianca
        resumo = args.resumo
        if args.checklist_all_true:
            checklist = {k: True for k in CHECKLIST_KEYS}
        else:
            checklist = {k: None for k in CHECKLIST_KEYS}
        achados = [json.loads(a) for a in args.achado]
        agent = args.agent

    rel = load_relatorio(args.relatorio)
    row = find_item(rel, args.item)
    if row is None:
        raise SystemExit(f"item {args.item} não encontrado")
    stub = (row.get("vereditos") or {}).get(args.backend) or {}
    payload = build_verdict_payload(
        veredito=veredito,
        confianca=confianca,
        resumo=resumo,
        checklist=checklist,
        achados=achados,
        agent=agent,
        svgs=list(stub.get("svgs_para_ler") or row.get("svg_paths") or []),
        manifesto=stub.get("manifesto_svg") or row.get("svg_manifest_path"),
    )
    result = record_item(
        args.relatorio.resolve(),
        item=args.item,
        payload=payload,
        backend=args.backend,
        dossie_dir=args.dossie_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
