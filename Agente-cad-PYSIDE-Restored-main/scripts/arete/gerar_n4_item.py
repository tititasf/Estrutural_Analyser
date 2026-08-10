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
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from arete_config import DADOS_OBRAS, GERADORES, PAV_13, REPO_ROOT, get_subtipo_pil
from ficha_adapter import (
    query_fichas, query_ficha_item,
    materializar_item, rodar_gerador, get_output_dxf_path,
)


_PIL_ZONES = ("cima", "abcd", "grades")
_LV_VIEWS = ("CORTE", "A", "B")


def _publicar_splits_pil_n4(
    obra_dir: Path,
    obra_name: str,
    elemento_id: str,
) -> tuple[bool, dict[str, str], str]:
    """Gera e publica os tres splits PIL usados pelas fichas HTML N4.

    O DXF N4 combinado continua sendo a fonte do G1/G2. Os splits sao gerados
    pelo mesmo motor e pela mesma ficha materializada, somente com ``--zone``;
    assim o card N4 nunca cai no fallback da raiz, que pertence ao N3.
    GRADES e publicado mesmo sem comparador automatico no 13_PAV.
    """
    gerador = GERADORES["PIL"]
    temp_out = obra_dir / "Fase-6_Execucao_CAD"
    real_out = (
        DADOS_OBRAS
        / obra_name
        / "Fase-6_Execucao_CAD"
        / "n4"
    )
    real_out.mkdir(parents=True, exist_ok=True)

    published: dict[str, str] = {}
    logs: list[str] = []
    zones = _PIL_ZONES + (("efgh",) if get_subtipo_pil(elemento_id) in {"L", "U"} else ())
    for zone in zones:
        cmd = [
            sys.executable,
            str(gerador),
            "--obra",
            str(obra_dir),
            "--item",
            elemento_id,
            "--max",
            "1",
            "--zone",
            zone,
        ]
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(REPO_ROOT),
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return False, published, f"split PIL {zone}: {exc}"

        zone_log = (completed.stdout or "") + (completed.stderr or "")
        logs.append(zone_log)
        if completed.returncode != 0:
            return (
                False,
                published,
                f"split PIL {zone} falhou (rc={completed.returncode})\n{zone_log}",
            )

        filename = f"PL_{zone.upper()}_preview_{elemento_id}.dxf"
        source = temp_out / filename
        if not source.exists() or source.stat().st_size == 0:
            return False, published, f"split PIL {zone} ausente ou vazio: {source}"

        destination = real_out / filename
        shutil.copy2(source, destination)
        published[zone.upper()] = str(destination)

    return True, published, "".join(logs)


def _publicar_splits_lv_n4(
    obra_dir: Path,
    obra_name: str,
    elemento_id: str,
    pavimento: str | None = None,
) -> tuple[bool, dict[str, str], str]:
    """Gera e publica os trÃªs viewers LV N4 da mesma ficha N2 materializada.

    O adaptador enriquece o item a partir do seu recorte antes de escrever a
    pasta temporÃ¡ria. Os viewers, portanto, nÃ£o leem o fichas_lv_v2 global da
    obra (que pode estar velho) nem reutilizam a geometria de outra viga.
    """
    gerador = GERADORES["LV"]
    temp_out = obra_dir / "Fase-6_Execucao_CAD"
    real_out = DADOS_OBRAS / obra_name / "Fase-6_Execucao_CAD" / "n4"
    real_out.mkdir(parents=True, exist_ok=True)
    published: dict[str, str] = {}
    logs: list[str] = []
    for view in _LV_VIEWS:
        cmd = [
            sys.executable, str(gerador), "--obra", str(obra_dir),
            "--item", elemento_id, "--max", "1", "--view", view,
            "--stog-obra-hint", obra_name,
        ]
        if pavimento:
            cmd += ["--stog-pav-hint", pavimento]
        try:
            completed = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120,
                cwd=str(REPO_ROOT),
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return False, published, f"split LV {view}: {exc}"
        view_log = (completed.stdout or "") + (completed.stderr or "")
        logs.append(view_log)
        if completed.returncode != 0:
            return False, published, f"split LV {view} falhou (rc={completed.returncode})\n{view_log}"
        suffix = "CORTE" if view == "CORTE" else f"VIEW_{view}"
        source = temp_out / f"LV_preview_{elemento_id}_{suffix}.dxf"
        if not source.exists() or source.stat().st_size == 0:
            return False, published, f"split LV {view} ausente ou vazio: {source}"
        destination = real_out / source.name
        shutil.copy2(source, destination)
        published[view] = str(destination)
    return True, published, "".join(logs)


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
        "split_paths": {},
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
    ok_gen, log = rodar_gerador(obra_dir, classe, elemento_id,
                                real_obra_name=row.get("obra_name"),
                                real_pavimento=row.get("pavimento"))
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
        result["dxf_path"] = str(dxf_path)
        if classe == "PIL":
            canonical_n4 = (
                DADOS_OBRAS
                / row["obra_name"]
                / "Fase-6_Execucao_CAD"
                / "n4"
                / dxf_path.name
            )
            canonical_n4.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dxf_path, canonical_n4)
            result["dxf_path"] = str(canonical_n4)

            splits_ok, split_paths, split_log = _publicar_splits_pil_n4(
                Path(obra_dir), row["obra_name"], elemento_id
            )
            result["split_paths"] = split_paths
            result["log"] += split_log
            if not splits_ok:
                result["erro"] = split_log
                if verbose:
                    print(f"  [FAIL] {split_log}")
                return result

        elif classe == "LV":
            splits_ok, split_paths, split_log = _publicar_splits_lv_n4(
                Path(obra_dir), row["obra_name"], elemento_id,
                pavimento=row.get("pavimento"),
            )
            result["split_paths"] = split_paths
            result["log"] += split_log
            if not splits_ok:
                result["erro"] = split_log
                if verbose:
                    print(f"  [FAIL] {split_log}")
                return result

        result["ok"] = True
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
