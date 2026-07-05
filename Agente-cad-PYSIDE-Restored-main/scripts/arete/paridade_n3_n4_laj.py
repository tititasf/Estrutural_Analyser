#!/usr/bin/env python3
"""Gate G5 LAJ: gera N3 de N1 bruto e compara canonicamente com N4."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
for path in (REPO_ROOT, REPO_ROOT / "scripts", SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from arete_config import DADOS_OBRAS  # noqa: E402
from conversao_n1_diff import DEFAULT_DB, load_raw_n1_slabs  # noqa: E402
from ficha_adapter import get_real_n4_path  # noqa: E402
from src.core.laj_n3_learning import (  # noqa: E402
    apply_learning_to_ficha,
    normalize_ficha_pose_coords,
)
from src.core.laj_n3_stog_runner import gerar_laj_n3_from_n1  # noqa: E402
from src.core.laje_n1_to_robot_ficha import (  # noqa: E402
    apply_n1_outline_anchor,
    n1_laje_to_robot_ficha,
)
from arete_lj_canonico import canonical, diff  # noqa: E402

DEFAULT_OUTPUT_ROOT = SCRIPT_DIR / "relatorios" / "paridade_n3_n4_laj"
BLOCKED_PREFIXES = ("n4_dxf:", "n2/n4:", "n2/n4_validated")


def gabarito_references(value: Any, path: str = "$") -> list[str]:
    """Lista referências proibidas presentes em qualquer ponto da ficha N3."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            found.extend(gabarito_references(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(gabarito_references(child, f"{path}[{index}]"))
    elif isinstance(value, str) and value.lower().startswith(BLOCKED_PREFIXES):
        found.append(f"{path}={value}")
    return found


def clean_n3_ficha(raw_n1: dict) -> dict:
    """Executa o caminho N1→Fase-4 com padrões de gabarito desabilitados."""
    ficha = n1_laje_to_robot_ficha(raw_n1)
    ficha["_sa_meta"] = {
        "source": "g5_raw_slabs",
        "n3_teacher": None,
        "gabarito_patterns_allowed": False,
    }
    ficha = apply_learning_to_ficha(
        ficha,
        teacher=None,
        record_teacher=False,
        allow_gabarito_patterns=False,
    )
    ficha = normalize_ficha_pose_coords(ficha)
    ficha = apply_n1_outline_anchor(ficha, raw_n1)
    return ficha


def _write_markdown(report: dict, path: Path) -> None:
    summary = report["resumo"]
    lines = [
        "# G5 — Paridade final N3×N4 de LAJ",
        "",
        f"- Obra/pavimento: `{report['obra']}` / `{report['pavimento']}`",
        f"- Resultado: **{summary['resultado']}**",
        f"- Itens: {summary['itens']} — PASS {summary['pass']} / FAIL {summary['fail']} / BLOCKED {summary['blocked']}",
        f"- Vazamentos detectados: {summary['vazamentos_gabarito']}",
        "",
        "| Item | G5 | Diffs canônicos |",
        "|---|---:|---|",
    ]
    for item in report["itens"]:
        fields = ", ".join((item.get("diff") or {}).get("diffs", {}).keys()) or "—"
        lines.append(f"| {item['item']} | {item['resultado']} | {fields} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    *,
    obra: str,
    pavimento: str,
    db_path: str | Path = DEFAULT_DB,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    project_id: str | None = None,
) -> tuple[dict, Path]:
    generated = datetime.now().astimezone()
    run_id = generated.strftime("%Y%m%d_%H%M%S")
    run_dir = Path(output_root) / obra / pavimento / run_id
    json_dir = run_dir / "n1_fase4_limpo"
    n3_dir = run_dir / "n3"
    json_dir.mkdir(parents=True, exist_ok=True)
    n3_dir.mkdir(parents=True, exist_ok=True)

    project, n1_slabs = load_raw_n1_slabs(
        db_path, obra, pavimento, project_id=project_id
    )
    obra_path = DADOS_OBRAS / obra
    items = []
    for name in sorted(
        n1_slabs,
        key=lambda value: int(value[1:]) if value[1:].isdigit() else value,
    ):
        ficha = clean_n3_ficha(n1_slabs[name])
        leaks = gabarito_references(ficha)
        json_path = json_dir / f"{name}.json"
        json_path.write_text(
            json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        n4_path = get_real_n4_path(obra, "LAJ", name)
        if leaks:
            items.append(
                {
                    "item": name,
                    "resultado": "FAIL",
                    "motivo": "vazamento de gabarito na ficha N3",
                    "vazamentos": leaks,
                    "n3_json": str(json_path),
                }
            )
            continue
        ok, n3_path = gerar_laj_n3_from_n1(
            obra_path,
            n1_json_dir=json_dir,
            out_dir=n3_dir,
            item=name,
        )
        if not ok or n3_path is None or not n4_path.is_file():
            items.append(
                {
                    "item": name,
                    "resultado": "BLOCKED",
                    "motivo": "DXF N3 ou N4 ausente",
                    "n3": str(n3_path) if n3_path else None,
                    "n4": str(n4_path),
                    "n3_json": str(json_path),
                }
            )
            continue
        comparison = diff(canonical(n3_path), canonical(n4_path))
        items.append(
            {
                "item": name,
                "resultado": "PASS" if comparison["pass"] else "FAIL",
                "vazamentos": [],
                "n3_json": str(json_path),
                "n3": str(n3_path),
                "n4": str(n4_path),
                "diff": comparison,
            }
        )

    counts = Counter(item["resultado"] for item in items)
    leak_count = sum(bool(item.get("vazamentos")) for item in items)
    report = {
        "schema_version": 1,
        "gate": "G5",
        "gerado_em": generated.isoformat(),
        "run_id": run_id,
        "obra": obra,
        "pavimento": pavimento,
        "fontes": {
            "project_id": project["id"],
            "n1_table": "slabs",
            "n1_forbidden_table": "slab_elements",
            "n4_dir": str((obra_path / "Fase-6_Execucao_CAD" / "n4").resolve()),
            "comparador": "scripts/arete_lj_canonico.py",
        },
        "resumo": {
            "resultado": "PASS" if counts["PASS"] == len(items) else "FAIL",
            "itens": len(items),
            "pass": counts["PASS"],
            "fail": counts["FAIL"],
            "blocked": counts["BLOCKED"],
            "vazamentos_gabarito": leak_count,
        },
        "itens": items,
    }
    report_path = run_dir / "g5_paridade_n3_n4_laj.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_markdown(report, run_dir / "RELATORIO.md")
    return report, run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="G5 LAJ: N3 limpo vs N4 canônico")
    parser.add_argument("--obra", default="Obra_TREINO_1")
    parser.add_argument("--pav", default="13_PAV")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()
    report, run_dir = run(
        obra=args.obra,
        pavimento=args.pav,
        db_path=args.db,
        output_root=args.output_root,
        project_id=args.project_id,
    )
    print(json.dumps(report["resumo"], ensure_ascii=False, indent=2))
    print(f"Relatório: {run_dir}")
    return 0 if report["resumo"]["resultado"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
