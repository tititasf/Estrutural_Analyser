# -*- coding: utf-8 -*-
"""
gerar_n4_item.py — Gera DXF N4 a partir de ficha N2 (DB) para 1 ou N itens.

Usa ficha_adapter.py para materializar campos_json → layout Fase-4,
depois chama o gerador STOG correspondente via subprocess.

Uso:
    python gerar_n4_item.py PIL P1
    python gerar_n4_item.py PIL --todos
    python gerar_n4_item.py PIL P1 P5 P12
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from arete_config import PAV_13, ESCOPO_13PAV
from ficha_adapter import (
    query_fichas, query_ficha_item,
    materializar_item, rodar_gerador, get_output_dxf_path,
)


def gerar_item(classe: str, elemento_id: str,
               pavimento: str = PAV_13,
               verbose: bool = True) -> dict:
    """
    Gera DXF N4 para 1 item. Retorna dict de resultado.

    Returns:
        {ok, classe, elemento_id, dxf_path, obra_dir, log, erro}
    """
    result = {
        "ok": False, "classe": classe, "elemento_id": elemento_id,
        "dxf_path": None, "obra_dir": None, "log": "", "erro": "",
    }

    # 1. Buscar ficha no DB
    row = query_ficha_item(classe, elemento_id, pavimento)
    if row is None:
        result["erro"] = f"Ficha não encontrada: {classe}/{elemento_id}/{pavimento}"
        return result

    if not row["campos_json"]:
        result["erro"] = "campos_json vazio"
        return result

    # 2. Materializar ficha → pasta temp
    obra_dir, json_path = materializar_item(row)
    result["obra_dir"] = str(obra_dir)

    if verbose:
        print(f"  Materializado: {json_path}")

    # 3. Rodar gerador
    ok_gen, log = rodar_gerador(obra_dir, classe, elemento_id)
    result["log"] = log

    if not ok_gen:
        result["erro"] = "Gerador falhou (rc≠0)"
        if verbose:
            tail = "\n".join(log.splitlines()[-8:])
            print(f"  [FAIL] gerador:\n{tail}")
        return result

    # 4. Verificar DXF
    dxf_path = get_output_dxf_path(Path(obra_dir), classe, elemento_id)
    if dxf_path.exists() and dxf_path.stat().st_size > 0:
        result["ok"] = True
        result["dxf_path"] = str(dxf_path)
        if verbose:
            kb = dxf_path.stat().st_size // 1024
            print(f"  [PASS] DXF: {dxf_path.name} ({kb} KB)")
    else:
        result["erro"] = f"DXF não gerado ou vazio: {dxf_path}"
        if verbose:
            print(f"  [FAIL] {result['erro']}")

    return result


def gerar_batch(classe: str, elemento_ids: list[str],
                pavimento: str = PAV_13) -> list[dict]:
    """Gera N4 para lista de elementos. Retorna lista de resultados."""
    resultados = []
    n = len(elemento_ids)
    for i, elem_id in enumerate(elemento_ids, 1):
        print(f"[{i}/{n}] {classe}/{elem_id} ...", end=" ", flush=True)
        r = gerar_item(classe, elem_id, pavimento, verbose=False)
        status = "PASS" if r["ok"] else f"FAIL — {r['erro']}"
        print(status)
        resultados.append(r)
    return resultados


def gerar_todos(classe: str, pavimento: str = PAV_13) -> list[dict]:
    """Gera N4 para todos os itens da classe/pavimento no DB."""
    rows  = query_fichas(classe, pavimento)
    ids   = [r["elemento_id"] for r in rows]
    print(f"\nGerando {len(ids)} itens de {classe}/{pavimento} ...")
    return gerar_batch(classe, ids, pavimento)


# ═════════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gerar DXF N4 — Arete AR-0.2")
    parser.add_argument("classe", help="PIL|LV|FV|LAJ")
    parser.add_argument("elementos", nargs="*",
                        help="IDs dos elementos (ex: P1 P5). Omitir com --todos.")
    parser.add_argument("--todos", action="store_true",
                        help="Gerar todos os itens da classe no DB")
    parser.add_argument("--pav", default=PAV_13, help=f"Pavimento (default: {PAV_13})")
    args = parser.parse_args()

    if args.todos:
        rs = gerar_todos(args.classe, args.pav)
    elif args.elementos:
        rs = gerar_batch(args.classe, args.elementos, args.pav)
    else:
        parser.error("Forneça elemento_ids ou use --todos")

    n_ok   = sum(1 for r in rs if r["ok"])
    n_fail = len(rs) - n_ok
    print(f"\n=== {n_ok}/{len(rs)} PASS | {n_fail} FAIL ===")
    if n_fail:
        for r in rs:
            if not r["ok"]:
                print(f"  FAIL {r['elemento_id']}: {r['erro']}")
