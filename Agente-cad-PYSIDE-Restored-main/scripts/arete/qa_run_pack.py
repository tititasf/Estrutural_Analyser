#!/usr/bin/env python3
"""Executa uma rodada QA sincrona sobre um pack Arete (diagnostico/validacao)."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from portal.app.qa_jobs import contexto_item_pil, localizar_pack_pil
from scripts.arete.qa_cli_fallback import run_round


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--obra-pack", required=True)
    parser.add_argument("--pavimento", default="13_PAV")
    parser.add_argument("--items", nargs="+", required=True)
    parser.add_argument("--layer", choices=("L1", "L2", "L3"), default="L1")
    parser.add_argument(
        "--pack",
        type=Path,
        help="pack ABCD explicito; evita escolher um checkpoint historico por timestamp",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    items = list(dict.fromkeys(item.strip().upper() for item in args.items if item.strip()))
    pack = args.pack.resolve() if args.pack else localizar_pack_pil(
        REPO_ROOT, args.obra_pack, args.pavimento
    )
    if not (pack / "pilares").is_dir():
        parser.error(f"pack ABCD invalido: {pack}")
    result = run_round(
        round_id=uuid.uuid4().hex,
        items=items,
        layer=args.layer,
        cwd=REPO_ROOT,
        context_for_item=lambda item: contexto_item_pil(REPO_ROOT, pack, item, args.layer),
    )
    payload = result.to_dict()
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0 if all(item.status == "completed" for item in result.items) else 2


if __name__ == "__main__":
    raise SystemExit(main())
