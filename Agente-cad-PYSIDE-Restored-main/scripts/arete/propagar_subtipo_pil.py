#!/usr/bin/env python3
"""
propagar_subtipo_pil.py — Injeta `subtipo_pil` nos JSONs da Fase-4.

Para cada obra em DADOS-OBRAS/, lê todos os P*.json em
Fase-4_Sincronizacao/JSON_Pilares/ e escreve/atualiza o campo
`subtipo_pil` (RETANGULAR | U | ESPECIAL) com base em SUBTIPO_PIL
de arete_config.py.

Uso:
    python scripts/arete/propagar_subtipo_pil.py
    python scripts/arete/propagar_subtipo_pil.py --dry-run
    python scripts/arete/propagar_subtipo_pil.py --obra Obra_TREINO_1
"""
import sys, json, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from arete_config import DADOS_OBRAS, get_subtipo_pil


def propagar(obra_path: Path, dry_run: bool) -> dict[str, int]:
    json_dir = obra_path / "Fase-4_Sincronizacao" / "JSON_Pilares"
    if not json_dir.is_dir():
        return {"obras": 0, "arquivos": 0, "atualizados": 0, "ja_ok": 0}

    counts = {"arquivos": 0, "atualizados": 0, "ja_ok": 0}
    for pf in sorted(json_dir.glob("P*.json")):
        try:
            pj = json.loads(pf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        elem_id = pj.get("nome", pf.stem)
        subtipo = get_subtipo_pil(elem_id)
        counts["arquivos"] += 1

        if pj.get("subtipo_pil") == subtipo:
            counts["ja_ok"] += 1
            continue

        pj["subtipo_pil"] = subtipo
        if not dry_run:
            pf.write_text(json.dumps(pj, ensure_ascii=False, indent=2), encoding="utf-8")
        counts["atualizados"] += 1
        tag = "[DRY] " if dry_run else ""
        print(f"  {tag}{pf.stem}: subtipo_pil = {subtipo}")

    return counts


def main():
    parser = argparse.ArgumentParser(description="Propaga subtipo_pil nos JSONs Fase-4")
    parser.add_argument("--dry-run", action="store_true",
                        help="Mostra o que seria alterado sem escrever")
    parser.add_argument("--obra", type=str, default=None,
                        help="Processar só esta obra (ex: Obra_TREINO_1)")
    args = parser.parse_args()

    if args.obra:
        obras = [DADOS_OBRAS / args.obra]
    else:
        obras = [p for p in DADOS_OBRAS.iterdir() if p.is_dir()]

    total = {"arquivos": 0, "atualizados": 0, "ja_ok": 0}
    for obra in sorted(obras):
        json_dir = obra / "Fase-4_Sincronizacao" / "JSON_Pilares"
        if not json_dir.is_dir():
            continue
        print(f"\n{obra.name}:")
        c = propagar(obra, args.dry_run)
        for k in total:
            total[k] += c[k]

    print(f"\n{'[DRY-RUN] ' if args.dry_run else ''}Concluído: "
          f"{total['arquivos']} arquivos, "
          f"{total['atualizados']} atualizados, "
          f"{total['ja_ok']} já corretos.")


if __name__ == "__main__":
    main()
