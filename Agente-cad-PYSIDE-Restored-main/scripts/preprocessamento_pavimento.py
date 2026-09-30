"""CLI seguro para construir a camada interna de pré-processamento.

Entrega parcial: inventário verificável e leituras conservadoras de convenções,
níveis e pilares. Cortes, consolidação e consumo SA seguem desabilitados.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from portal.app.preprocessamento.runner import RunnerError, run_inventory  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pré-processamento isolado por pavimento")
    parser.add_argument("--obra-id", required=True)
    parser.add_argument("--pavimento", required=True)
    parser.add_argument("--recorte-id", action="append", default=[])
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--preview", action="store_true", help="valida e mostra sem escrever")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_inventory(
            input_manifest=args.manifest,
            output_dir=args.output_dir,
            obra_id=args.obra_id,
            pavimento_id=args.pavimento,
            selected_source_ids=set(args.recorte_id) or None,
            preview=args.preview,
        )
    except RunnerError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"ok": True, **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
