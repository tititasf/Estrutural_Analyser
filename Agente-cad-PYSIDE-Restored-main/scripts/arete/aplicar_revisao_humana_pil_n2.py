"""Registra na ficha N2 as correções geométricas validadas no painel humano.

Este é um patch de dados, não uma regra do motor N4: o gerador continua lendo
somente ``campos_json``. Cada alteração é rastreada com a origem da revisão.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT.parent / "project_data.vision"
PAVIMENTO = "13_PAV"

# Coordenadas locais medidas no recorte N2. A altura é a faixa entre as juntas
# 195 e 260; a face C do P10 possui vazio integral entre 195 e 319.
CORRECOES = {
    # Pilar especial em L: o SCR combina a CIMA e usa apenas E/F nas elevações.
    # As quatro cotas vêm do recorte humano; G/H não existem nesta topologia.
    "P26": {
        "subtipo_pil": "L",
        "larg1_E": 240.0,
        "larg1_F": 210.0,
        "pilar_especial": {"tipo": "L", "secao_l": {"externa_x": 240.0, "interna_x": 210.0, "externa_y": 176.0, "interna_y": 153.0}},
    },
    "P27": {
        "subtipo_pil": "L",
        "larg1_E": 210.0,
        "larg1_F": 240.0,
        "pilar_especial": {"tipo": "L", "secao_l": {"externa_x": 240.0, "interna_x": 210.0, "externa_y": 176.0, "interna_y": 153.0}},
    },
    "P10": {
        "abertura_B": {"lado": "direito", "largura": 11.0, "y_rel": 195.0, "altura": 65.0},
        "abertura_C": {"lado": "meio", "x_offset": 0.0, "largura": 19.0, "y_rel": 195.0, "altura": 124.0},
        "vazio_laje_B": 59.0,
    },
    "P11": {
        "abertura_B": {"lado": "meio", "x_offset": 37.5, "largura": 27.0, "y_rel": 195.0, "altura": 65.0},
        "vazio_laje_B": 59.0,
        "paineis_intervals_B": [122.0, 73.0, 65.0],
    },
    "P17": {
        "abertura_B": {"lado": "meio", "x_offset": 57.5, "largura": 27.0, "y_rel": 195.0, "altura": 65.0},
        "vazio_laje_B": 59.0,
        "paineis_intervals_B": [122.0, 73.0, 65.0],
    },
    # A face B repete a composição da A: os três trechos finais são 21 + 15,
    # não três painéis artificiais de 5 + 10 + 5 cm.
    "P18": {
        "paineis_intervals_B": [122.0, 97.0, 21.0, 15.0],
    },
    # N2: duas aberturas laterais, laje de 12 cm entre elas e painel superior
    # de 7 cm. Esses valores pertencem às fichas; o motor apenas os desenha.
    "P28": {"rebaixo_laje_A": 7.0, "vazio_laje_A": 12.0, "rebaixo_laje_B": 7.0, "vazio_laje_B": 12.0},
    "P29": {"rebaixo_laje_A": 7.0, "vazio_laje_A": 12.0, "rebaixo_laje_B": 7.0, "vazio_laje_B": 12.0},
    "P30": {"rebaixo_laje_A": 7.0, "vazio_laje_A": 12.0, "rebaixo_laje_B": 7.0, "vazio_laje_B": 12.0},
    "P31": {"rebaixo_laje_A": 7.0, "vazio_laje_A": 12.0, "rebaixo_laje_B": 7.0, "vazio_laje_B": 12.0},
    "P32": {"rebaixo_laje_A": 7.0, "vazio_laje_A": 12.0, "rebaixo_laje_B": 7.0, "vazio_laje_B": 12.0},
}


def _load_row(connection: sqlite3.Connection, codigo: str) -> tuple[int, dict]:
    row = connection.execute(
        """
        SELECT id, campos_json
          FROM reverse_eng_fichas
         WHERE classe = 'PIL' AND elemento_id = ? AND pavimento = ?
        """,
        (codigo, PAVIMENTO),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Ficha PIL/{codigo}/{PAVIMENTO} não encontrada")
    return int(row[0]), json.loads(row[1])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--apply", action="store_true", help="persiste as correções")
    args = parser.parse_args()

    changes: list[tuple[int, str, dict]] = []
    with sqlite3.connect(args.db) as connection:
        for codigo, patch in CORRECOES.items():
            row_id, ficha = _load_row(connection, codigo)
            before = {key: deepcopy(ficha.get(key)) for key in patch}
            if before == patch:
                print(f"{codigo}: já está atualizado")
                continue
            ficha.update(deepcopy(patch))
            meta = ficha.setdefault("_er_meta", {})
            reviews = meta.setdefault("revisoes_humanas", [])
            reviews.append({
                "at": datetime.now(timezone.utc).isoformat(),
                "origem": "revisao_pil_vistas",
                "descricao": "Aberturas/vazios confirmados na comparação N2/N4.",
                "campos": sorted(patch),
            })
            print(f"{codigo}: {before} -> {patch}")
            changes.append((row_id, codigo, ficha))

        if not args.apply:
            print("Dry-run: execute novamente com --apply para persistir.")
            return 0

        for row_id, _codigo, ficha in changes:
            connection.execute(
                "UPDATE reverse_eng_fichas SET campos_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(ficha, ensure_ascii=False), row_id),
            )
        connection.commit()
    print(f"Persistidas {len(changes)} ficha(s) N2.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
