"""Âncora N2: resolve recorte aprovado e rebind de ficha."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.core.n2_anchor import (
    list_n2_anchors,
    rebind_fichas_to_n2_anchors,
    resolve_n2_anchor,
)


def _seed(db: Path, recortes_dir: Path) -> Path:
    recortes_dir.mkdir(parents=True, exist_ok=True)
    approved = recortes_dir / "LAJ_L416_motor_999.dxf"
    stale = recortes_dir / "LAJ_L416_motor_111.dxf"
    approved.write_bytes(b"approved-dxf")
    stale.write_bytes(b"stale-dxf")

    with sqlite3.connect(str(db)) as conn:
        conn.executescript(
            """
            CREATE TABLE reverse_eng_recortes (
                id INTEGER PRIMARY KEY,
                ficha_id INTEGER,
                obra_name TEXT,
                elemento_id TEXT,
                recorte_path TEXT,
                bbox_json TEXT,
                entity_count INTEGER,
                created_at TEXT,
                projeto_id TEXT,
                classe TEXT,
                status TEXT,
                confidence REAL
            );
            CREATE TABLE reverse_eng_fichas (
                id INTEGER PRIMARY KEY,
                projeto_id INTEGER,
                obra_name TEXT,
                pavimento TEXT,
                classe TEXT,
                elemento_id TEXT,
                campos_json TEXT,
                recorte_path TEXT,
                confianca REAL,
                status TEXT,
                aprovado_at TEXT,
                rag_indexed INTEGER,
                created_at TEXT,
                updated_at TEXT
            );
            """
        )
        conn.execute(
            """
            INSERT INTO reverse_eng_recortes
                (obra_name, elemento_id, recorte_path, classe, status, confidence)
            VALUES (?, ?, ?, 'LAJ', 'aprovado', 90.0)
            """,
            ("Obra_A", "L416", str(approved)),
        )
        conn.execute(
            """
            INSERT INTO reverse_eng_fichas
                (obra_name, pavimento, classe, elemento_id, campos_json,
                 recorte_path, confianca, status)
            VALUES (?, '14_PAV', 'LAJ', 'L416', ?, ?, 0.5, 'draft')
            """,
            (
                "Obra_A",
                json.dumps({"comprimento": 1, "largura": 2}),
                str(stale),
            ),
        )
    return approved


def test_resolve_prefers_aprovado_recorte(tmp_path: Path):
    db = tmp_path / "t.vision"
    folder = tmp_path / "DADOS" / "ALIMONTI - PARAISO - 14° PAV.- LJ - R00"
    approved = _seed(db, folder)

    anc = resolve_n2_anchor("Obra_A", "LJ", "L416", "14_PAV", db_path=db)
    assert anc is not None
    assert Path(anc["recorte_path"]) == approved.resolve() or Path(anc["recorte_path"]) == approved
    assert anc["is_human_approved"] is True
    assert anc["source"] == "reverse_eng_recortes"


def test_list_anchors_14p(tmp_path: Path):
    db = tmp_path / "t.vision"
    folder = tmp_path / "DADOS" / "ALIMONTI - PARAISO - 14° PAV.- LJ - R00"
    _seed(db, folder)
    items = list_n2_anchors("Obra_A", "LAJ", "14_PAV", db_path=db)
    assert len(items) == 1
    assert items[0]["elemento_id"] == "L416"


def test_rebind_updates_ficha_path(tmp_path: Path, monkeypatch):
    db = tmp_path / "t.vision"
    folder = tmp_path / "DADOS" / "ALIMONTI - PARAISO - 14° PAV.- LJ - R00"
    approved = _seed(db, folder)

    # skip real motor extract
    result = rebind_fichas_to_n2_anchors(
        "Obra_A",
        "LAJ",
        "14_PAV",
        db_path=db,
        reextract=False,
        only_if_path_differs=True,
    )
    assert len(result["updated"]) == 1
    with sqlite3.connect(str(db)) as conn:
        path, campos = conn.execute(
            "SELECT recorte_path, campos_json FROM reverse_eng_fichas WHERE elemento_id='L416'"
        ).fetchone()
    assert Path(path).name == approved.name
    meta = json.loads(campos)["_er_meta"]
    assert meta["n2_anchor_status"] == "aprovado"
