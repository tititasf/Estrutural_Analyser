"""Preenche campos SA de P1–P3 (13_PAV) a partir dos contratos N3 derivados.

Não é hardcode de regra de interpretação: só projeta o que o SA já publicou em
`n3_variants/{para,passa}/*.json` (fontes_n1 + aberturas) nos slots do DetailCard
(`p_s*_l1_*` / `p_s*_v_int_*`) para a UI e o CE ficarem legíveis agora.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

DB = Path(r"D:/Agente-cad-PYSIDE/project_data.vision")
VARIANTS = Path(
    r"D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD/n3_variants"
)
PROJECT_ID = "dd238e47-1dc6-4f63-a760-4e7ce19a7386"
ITEMS = ("P1", "P2", "P3")
_EMPTY = {"", "N/A", "N.A.", "NONE", "—", "NULO", "SEM LAJE", "VAZIO (X)"}


def _parse_viga(text: str) -> tuple[str, str]:
    """'Viga: V309  ·  dim: 19/120  ·  ...' -> (V309, 19/120)"""
    name, dim = "", ""
    m = re.search(r"Viga:\s*([^·]+)", text or "", flags=re.I)
    if m:
        name = m.group(1).strip()
    m = re.search(r"dim:\s*([^·]+)", text or "", flags=re.I)
    if m:
        dim = m.group(1).strip()
    return name, dim


def _parse_laje(text: str) -> tuple[str, str]:
    """'Laje: L301 · esp: 12cm · N: 852.12'"""
    name, h = "", ""
    m = re.search(r"Laje:\s*([^·]+)", text or "", flags=re.I)
    if m:
        name = m.group(1).strip()
    m = re.search(r"esp:\s*([0-9]+(?:[.,][0-9]+)?)", text or "", flags=re.I)
    if m:
        h = m.group(1).replace(",", ".")
    return name, h


def _best_contract(item: str) -> dict:
    """Prefere PARA (tem aberturas/chegadas) e cai para PASSA se necessário."""
    for mode in ("para", "passa"):
        path = VARIANTS / mode / f"{item}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        contract = data.get("_sa_mode_contract") or {}
        if contract.get("faces"):
            return contract
    return {}


def _face_fields_from_contract(contract: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for fid, face in (contract.get("faces") or {}).items():
        sources = (face or {}).get("fontes_n1") or {}
        # Laje
        for raw in sources.get("lajes") or []:
            name, h = _parse_laje(str(raw))
            if name:
                out[f"p_s{fid}_l1_n"] = name
                if h:
                    out[f"p_s{fid}_l1_h"] = h
                break
        # Viga: passa > interior > chega (nome para o slot v_int)
        for kind in ("passa", "interior", "chega"):
            for raw in sources.get(kind) or []:
                name, dim = _parse_viga(str(raw))
                if name:
                    out[f"p_s{fid}_v_int_n"] = name
                    if dim:
                        out[f"p_s{fid}_v_int_d"] = dim
                    break
            if f"p_s{fid}_v_int_n" in out:
                break
        # Se ainda vazio e há abertura ativa, usa a viga da abertura
        if f"p_s{fid}_v_int_n" not in out:
            for op in (face.get("aberturas_vigas_que_param") or []) + (
                face.get("aberturas_vigas_que_chegam") or []
            ):
                if op.get("estado") not in (None, "ativa", "neutralizada"):
                    continue
                name = str(op.get("nome") or "").strip()
                if not name:
                    continue
                out[f"p_s{fid}_v_int_n"] = name
                depth = op.get("profundidade")
                if depth is not None:
                    # profundidade sozinha não é seção; tenta largura se houver
                    w = op.get("largura")
                    if w is not None:
                        out[f"p_s{fid}_v_int_d"] = f"{w}/{depth}"
                break
    return out


def _is_empty(val) -> bool:
    return str(val or "").strip().upper() in {x.upper() for x in _EMPTY}


def main() -> None:
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    updated = 0
    for item in ITEMS:
        row = cur.execute(
            "SELECT id, extra_data_json, sides_data_json FROM pillars "
            "WHERE project_id=? AND name=?",
            (PROJECT_ID, item),
        ).fetchone()
        if not row:
            print(f"{item}: not in DB project {PROJECT_ID}")
            continue
        contract = _best_contract(item)
        if not contract:
            print(f"{item}: no contract")
            continue
        fields = _face_fields_from_contract(contract)
        extra = json.loads(row["extra_data_json"] or "{}")
        sides = json.loads(row["sides_data_json"] or "{}")
        changed = []
        for key, val in fields.items():
            if not val:
                continue
            if _is_empty(extra.get(key)):
                extra[key] = val
                changed.append(key)
            # sides_data mirror
            m = re.match(r"p_s([A-D])_(.+)", key)
            if m:
                fid, rest = m.group(1), m.group(2)
                face = sides.setdefault(fid, {})
                if isinstance(face, dict) and _is_empty(face.get(rest)):
                    face[rest] = val
        if not changed:
            print(f"{item}: nothing to fill (already set or no empty slots)")
            continue
        cur.execute(
            "UPDATE pillars SET extra_data_json=?, sides_data_json=? WHERE id=?",
            (
                json.dumps(extra, ensure_ascii=False),
                json.dumps(sides, ensure_ascii=False),
                row["id"],
            ),
        )
        updated += 1
        print(f"{item}: filled {changed}")
    conn.commit()
    conn.close()
    print(f"DONE updated_items={updated}")


if __name__ == "__main__":
    main()
