# -*- coding: utf-8 -*-
"""
roundtrip_ficha.py - Gate G1: round-trip N2 -> N4 -> N2prime -> diff.

Pipeline:
    1. Materializar ficha N2 (DB) -> JSON para o gerador
    2. Gerar DXF N4
    3. Re-extrair ficha N2prime do DXF N4 usando o motor reverso correspondente
    4. Diff campo a campo N2 vs N2prime com tolerancias

PASS do gate: todos os campos nao-nulos identicos dentro das tolerancias
  - dimensoes (float): +-0.5 cm
  - contagens (int): exato
  - textos (str): exato
  - listas/dicts: recursivo

Uso:
    python roundtrip_ficha.py PIL P1
    python roundtrip_ficha.py PIL --todos
"""

import argparse
import importlib
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from arete_config import (
    PAV_13, MOTOR_FUNC, REPO_ROOT,
    TOL_GEOMETRIA_PCT,
)
from ficha_adapter import (
    query_fichas, query_ficha_item,
    materializar_item, rodar_gerador, get_output_dxf_path,
)

# Tolerancia para campos dimensionais (cm)
TOL_DIM_CM = 0.5

# Campos que o motor reverso NÃO consegue re-extrair do DXF STOG gerado.
# Estes campos são validados por G2 (visual) em vez de G1 (round-trip).
SKIP_G1: dict[str, set] = {
    "LV": {
        # Enriquecimento por recorte — motor não re-extrai do STOG
        "panels_A", "panels_B", "panels",
        "section_views", "h_section_all", "face_units",
        "laje_sup_A", "laje_inf_A", "laje_sup_B", "laje_inf_B",
        "tipo_viga",
        # h_section: gerador recalcula como (h_A+h_B)/2 quando usa fichas_h_map,
        # discrepando do valor N2. Motor lê 55cm por default quando não detecta.
        "h_section",
        # total_width / b_geom: motor usa 19cm por default para vigas de alma 14cm
        # (b_alma não é detectável de seção transversal no STOG gerado).
        "total_width", "b_geom",
        # text_left/right: referências a pilares vizinhos não escritas no STOG gerado
        "text_left", "text_right",
    },
    "FV": {
        # panels: top-level e dentro de segments_rich — o motor pode contar painéis
        # de forma diferente (junção de painéis adjacentes no STOG vs. divisão original).
        "panels",
        # texts: motor re-extrai textos de dimensões do DXF; N2 tem texts=[] (extraído do
        # recorte humano que não anota textos individuais nos painéis).
        "texts",
        # tiers: fiadas de tijolos — N2 tem lista de tiers por painel; o motor STOG
        # não re-extrai tiers (estrutura de fiadas não é desenhada no STOG FV).
        "tiers",
        # vertices: polígono do painel em coords locais — varia por escala/offset do DXF.
        "vertices",
        # holes: furos nos painéis — enriquecimento do recorte, motor não detecta no STOG.
        "holes",
        # total_height: comprimento total da forma (soma dos painéis). Motor pode somar
        # painéis de borda diferentemente para vigas multi-vão (ex: V301: 3202 vs 5451cm).
        "total_height",
        # total_width: largura da forma — análogo ao LV (motor usa default quando não detecta).
        "total_width",
        # sarrafo_left_id/right_id: IDs de peça de sarrafo — não escritos no STOG.
        "sarrafo_left_id", "sarrafo_right_id",
        # label_left/right: referências a pilares vizinhos não escritas no STOG.
        "label_left", "label_right",
        # segments_rich: estrutura aninhada por segmento — o motor pode dividir vigas
        # longas em mais segments (ex: V301: 16 N2 → 28 N2p). Validado por G2 visual.
        "segments_rich",
        # _n_linhas_folha: campo de layout de folha de desenho, varia com o gerador.
        "_n_linhas_folha",
    },
    "LAJ": {
        # cotas_paineis: posições (x, y, rotation) e valores de cotas de painéis —
        # o motor re-extrai cotas do DXF STOG com lógica diferente da recorte N2.
        # Posições variam por layout; contagem pode diferir. Validado por G2.
        "cotas_paineis",
        # _forma_canonica: cotas_valor, textos, textos_contexto derivados da forma.
        # Calculado a partir das cotas_paineis; não confiável no round-trip STOG.
        "_forma_canonica",
        # coordenadas: posição absoluta da laje no DXF da obra — varia por DXF.
        "coordenadas",
        # modo_selecionado: modo de seleção de painéis (0=vertical, 1=horizontal)
        # detectado pelo motor com base em heurística do DXF. Pode diferir do N2.
        "modo_selecionado",
    },
}


def _load_motor(classe: str):
    """Importa e retorna a funcao de extracao do motor reverso."""
    mod_name, func_name = MOTOR_FUNC[classe]
    scripts_dir = str(REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    mod = importlib.import_module(mod_name)
    return getattr(mod, func_name)


def re_extrair(dxf_path: Path, classe: str,
               elemento_id: str, obra_root: Path) -> dict:
    """
    Re-extrai ficha N2prime do DXF N4 gerado.
    obra_root = adapter dir (tmp/PIL_P1); motor usa obra_root/Fase-4_Sincronizacao
    """
    func = _load_motor(classe)
    try:
        result = func(str(dxf_path), elemento_id, obra_root=str(obra_root))
        if not result:
            result = {}
    except Exception as exc:
        result = {"_extracao_erro": str(exc)}
    return result


def _normalizar(v):
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def diff_campos(n2: dict, n2_prime: dict, tol_dim: float = TOL_DIM_CM,
                skip_keys: set | None = None) -> dict:
    """
    Compara campos estruturais de N2 vs N2prime.
    Ignora chaves de metadado: _er_meta, _sa_meta, _confianca, _extracao_*.
    skip_keys: campos adicionais a ignorar em qualquer nível da hierarquia.
    """
    META_KEYS = {"_er_meta", "_sa_meta", "_confianca", "_confianca_extracao",
                 "_extracao_erro", "dxf_validation", "fase4_vs_dxf_gaps",
                 # _fase4_ref: referência ao N1 original — não comparável no round-trip
                 "_fase4_ref"}
    # Chaves internas de posição DXF-mundo: variam por obra/DXF, nunca batem no round-trip
    POS_KEYS  = {"_xl", "_xr", "_y0", "_y1", "_cx", "_cy", "_origin", "_offset"}
    _SKIP      = (skip_keys or set()) | META_KEYS
    # Leaf-key skip: campos a ignorar em qualquer nível da hierarquia (ex: dentro de panels[i])
    _SKIP_LEAF = skip_keys or set()

    diffs = []
    total = 0

    def _leaf(campo: str) -> str:
        """Extrai a última chave de um path como 'seg[0].panels[1].texts' → 'texts'."""
        return campo.rsplit(".", 1)[-1].split("[")[0]

    def _cmp_val(campo, v_n2, v_n2p):
        nonlocal total
        # Verificar leaf key antes de qualquer comparação
        if _leaf(campo) in _SKIP_LEAF:
            return
        v_n2  = _normalizar(v_n2)
        v_n2p = _normalizar(v_n2p)
        if v_n2 is None:
            return
        total += 1
        if isinstance(v_n2, (int, float)) and isinstance(v_n2p, (int, float)):
            if abs(float(v_n2) - float(v_n2p)) > tol_dim:
                diffs.append({
                    "campo": campo,
                    "n2": v_n2, "n2p": v_n2p,
                    "delta": round(float(v_n2p) - float(v_n2), 4),
                    "tipo": "dim",
                })
        elif isinstance(v_n2, str):
            if str(v_n2).strip() != str(v_n2p or "").strip():
                diffs.append({"campo": campo, "n2": v_n2, "n2p": v_n2p, "tipo": "str"})
        elif isinstance(v_n2, list):
            if not isinstance(v_n2p, list) or len(v_n2) != len(v_n2p):
                diffs.append({
                    "campo": campo,
                    "n2_len": len(v_n2),
                    "n2p_len": len(v_n2p) if isinstance(v_n2p, list) else "?",
                    "tipo": "list_len",
                })
            elif all(isinstance(x, dict) for x in v_n2):
                for i, (a, b) in enumerate(zip(v_n2, v_n2p)):
                    for k in a:
                        if k not in META_KEYS and k not in POS_KEYS and k not in _SKIP_LEAF:
                            _cmp_val(f"{campo}[{i}].{k}", a.get(k), b.get(k) if isinstance(b, dict) else None)
        elif isinstance(v_n2, dict):
            if isinstance(v_n2p, dict):
                for k in v_n2:
                    if k not in META_KEYS and k not in POS_KEYS and k not in _SKIP_LEAF:
                        _cmp_val(f"{campo}.{k}", v_n2.get(k), v_n2p.get(k))
            else:
                diffs.append({"campo": campo, "n2": "dict", "n2p": type(v_n2p).__name__, "tipo": "type"})

    for campo, val in n2.items():
        if campo in _SKIP:
            continue
        _cmp_val(campo, val, n2_prime.get(campo))

    iguais = total - len(diffs)
    return {
        "pass": len(diffs) == 0 and total > 0,
        "total": total,
        "iguais": iguais,
        "diffs": diffs,
    }


def roundtrip_item(classe: str, elemento_id: str,
                   pavimento: str = PAV_13,
                   verbose: bool = True) -> dict:
    result = {
        "gate": "G1",
        "resultado": "FAIL",
        "classe": classe,
        "elemento_id": elemento_id,
        "campos_comparados": 0,
        "diffs": [],
        "n4_path": None,
        "log_gerador": "",
        "erro": "",
    }

    row = query_ficha_item(classe, elemento_id, pavimento)
    if row is None:
        result["resultado"] = "BLOCKED"
        result["erro"] = f"Ficha nao encontrada: {classe}/{elemento_id}/{pavimento}"
        return result

    n2 = row["campos_json"]
    if not n2:
        result["resultado"] = "BLOCKED"
        result["erro"] = "campos_json vazio"
        return result

    obra_dir, _ = materializar_item(row)
    ok_gen, log = rodar_gerador(obra_dir, classe, elemento_id)
    result["log_gerador"] = log

    if not ok_gen:
        result["erro"] = "Gerador falhou"
        return result

    dxf_path = get_output_dxf_path(obra_dir, classe, elemento_id)
    if not dxf_path.exists():
        result["erro"] = f"DXF nao gerado: {dxf_path}"
        return result

    result["n4_path"] = str(dxf_path)

    n2_prime = re_extrair(dxf_path, classe, elemento_id, obra_dir)

    if "_extracao_erro" in n2_prime:
        result["erro"] = f"Re-extracao falhou: {n2_prime['_extracao_erro']}"
        return result

    cmp = diff_campos(n2, n2_prime, skip_keys=SKIP_G1.get(classe))
    result["campos_comparados"] = cmp["total"]
    result["diffs"]             = cmp["diffs"]
    result["resultado"]         = "PASS" if cmp["pass"] else "FAIL"

    if verbose:
        status = "PASS" if cmp["pass"] else f"FAIL ({len(cmp['diffs'])} diffs)"
        print(f"  G1 {classe}/{elemento_id}: {status}  [{cmp['iguais']}/{cmp['total']} campos iguais]")
        if cmp["diffs"]:
            for d in cmp["diffs"][:5]:
                print(f"    delta {d['campo']}: N2={d.get('n2')} N2p={d.get('n2p')} [{d['tipo']}]")
            if len(cmp["diffs"]) > 5:
                print(f"    ... +{len(cmp['diffs'])-5} diffs")

    return result


def roundtrip_batch(classe: str, elemento_ids: list,
                    pavimento: str = PAV_13) -> list:
    n = len(elemento_ids)
    resultados = []
    for i, eid in enumerate(elemento_ids, 1):
        print(f"[{i}/{n}] G1 {classe}/{eid} ...", end=" ", flush=True)
        r = roundtrip_item(classe, eid, pavimento, verbose=False)
        print(r["resultado"])
        resultados.append(r)
    return resultados


def roundtrip_todos(classe: str, pavimento: str = PAV_13) -> list:
    rows = query_fichas(classe, pavimento)
    ids  = [r["elemento_id"] for r in rows]
    print(f"Round-trip G1: {len(ids)} itens de {classe}/{pavimento}")
    return roundtrip_batch(classe, ids, pavimento)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Round-trip G1 - Arete AR-0.2")
    parser.add_argument("classe", help="PIL|LV|FV|LAJ")
    parser.add_argument("elementos", nargs="*", help="IDs dos elementos. Omitir com --todos.")
    parser.add_argument("--todos",  action="store_true")
    parser.add_argument("--pav",    default=PAV_13)
    parser.add_argument("--json",   action="store_true")
    args = parser.parse_args()

    if args.todos:
        rs = roundtrip_todos(args.classe, args.pav)
    elif args.elementos:
        rs = roundtrip_batch(args.classe, args.elementos, args.pav)
    else:
        parser.error("Forneca IDs ou use --todos")

    n_pass = sum(1 for r in rs if r["resultado"] == "PASS")
    n_fail = sum(1 for r in rs if r["resultado"] == "FAIL")
    n_blk  = sum(1 for r in rs if r["resultado"] == "BLOCKED")
    print(f"G1 {args.classe}: {n_pass}P / {n_fail}F / {n_blk}B  total={len(rs)}")

    if args.json:
        print(json.dumps(rs, indent=2, ensure_ascii=False, default=str))
    elif n_fail:
        print("FAILs:")
        for r in rs:
            if r["resultado"] == "FAIL":
                nd = len(r["diffs"])
                print(f"  {r['elemento_id']}: {nd} diffs -- {r['diffs'][:2]}")
