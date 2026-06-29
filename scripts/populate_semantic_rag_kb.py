#!/usr/bin/env python3
"""
populate_semantic_rag_kb.py - Bridge SQLite para regras semanticas.

Espelha `domain_knowledge` (LanceDB) doc_type=field_semantics em
`project_data.vision.semantic_rag_kb`.

Importante: este script popula REGRA, nao INSTANCIA. Ele nao toca fichas F5/F7,
nao gera embeddings e nao indexa dados em desenvolvimento.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

DEFAULT_LANCEDB_PATH = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/stog_rag_db")
DEFAULT_SQLITE_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DOMAIN_TABLE = "domain_knowledge"
BRIDGE_TABLE = "semantic_rag_kb"
BRIDGE_CONTEXT = "domain_knowledge:field_semantics"


@dataclass(frozen=True)
class SemanticBridgeRow:
    classe: str
    regra_semantica: str
    obra_contexto: str
    confianca: float


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def infer_classes(record: dict[str, Any]) -> list[str]:
    """Infere classes estruturais pelo metadata/texto existente, sem inventar regra."""
    source_doc = _as_str(record.get("source_doc")).lower()
    if "pilar" in source_doc:
        return ["PIL"]
    if "laje" in source_doc:
        return ["LAJ"]
    if "viga" in source_doc or "vigas" in source_doc:
        return ["LV", "FV"]

    haystack = " ".join(
        _as_str(record.get(key))
        for key in ("source_doc", "section", "tags", "text")
    ).lower()

    classes: list[str] = []
    if any(token in haystack for token in ("pilar", " pil ", " pl ")):
        classes.append("PIL")
    if any(token in haystack for token in ("laje", " laj ", " lj ", "slab")):
        classes.append("LAJ")

    mentions_viga = any(token in haystack for token in ("viga", "beam", " vig "))
    mentions_fundo = any(token in haystack for token in ("fundo", "bottom", "fv"))
    mentions_lateral = any(token in haystack for token in ("lateral", " lv "))

    if mentions_fundo:
        classes.append("FV")
    if mentions_lateral:
        classes.append("LV")
    if mentions_viga and not (mentions_fundo or mentions_lateral):
        classes.extend(["LV", "FV"])

    if not classes:
        classes.append("GLOBAL")

    deduped: list[str] = []
    for cls in classes:
        if cls not in deduped:
            deduped.append(cls)
    return deduped


def confidence_for(record: dict[str, Any]) -> float:
    if bool(record.get("sprint_validated")):
        return 1.0
    if record.get("doc_type") == "field_semantics":
        return 0.95
    return 0.85


def build_rule_payload(record: dict[str, Any]) -> str:
    payload = {
        "source": "domain_knowledge",
        "source_doc": _as_str(record.get("source_doc")),
        "doc_type": _as_str(record.get("doc_type")),
        "section": _as_str(record.get("section")),
        "source_path": _as_str(record.get("source_path")),
        "tags": _as_str(record.get("tags")),
        "sprint_validated": bool(record.get("sprint_validated")),
        "text": _as_str(record.get("text")),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def records_to_bridge_rows(records: Iterable[dict[str, Any]]) -> list[SemanticBridgeRow]:
    rows: list[SemanticBridgeRow] = []
    for record in records:
        if record.get("doc_type") != "field_semantics":
            continue
        payload = build_rule_payload(record)
        confidence = confidence_for(record)
        for cls in infer_classes(record):
            rows.append(
                SemanticBridgeRow(
                    classe=cls,
                    regra_semantica=payload,
                    obra_contexto=BRIDGE_CONTEXT,
                    confianca=confidence,
                )
            )
    return rows


def load_domain_records(lancedb_path: Path = DEFAULT_LANCEDB_PATH) -> list[dict[str, Any]]:
    import lancedb

    db = lancedb.connect(str(lancedb_path))
    listed = db.list_tables()
    table_names = listed.tables if hasattr(listed, "tables") else listed
    if DOMAIN_TABLE not in table_names:
        raise RuntimeError(f"Tabela {DOMAIN_TABLE!r} nao encontrada em {lancedb_path}")

    tbl = db.open_table(DOMAIN_TABLE)
    df = tbl.to_pandas()
    columns = ["text", "source_doc", "doc_type", "section", "source_path", "tags", "sprint_validated"]
    available = [col for col in columns if col in df.columns]
    return df[available].to_dict(orient="records")


def ensure_bridge_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {BRIDGE_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            classe TEXT NOT NULL,
            regra_semantica TEXT NOT NULL,
            obra_contexto TEXT,
            confianca REAL DEFAULT 1.0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def count_bridge_rows(conn: sqlite3.Connection, context: str = BRIDGE_CONTEXT) -> int:
    ensure_bridge_table(conn)
    row = conn.execute(
        f"SELECT COUNT(*) FROM {BRIDGE_TABLE} WHERE obra_contexto=?",
        (context,),
    ).fetchone()
    return int(row[0])


def apply_rows(
    rows: list[SemanticBridgeRow],
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    *,
    replace: bool = True,
) -> int:
    with sqlite3.connect(sqlite_path) as conn:
        ensure_bridge_table(conn)
        if replace:
            conn.execute(
                f"DELETE FROM {BRIDGE_TABLE} WHERE obra_contexto=?",
                (BRIDGE_CONTEXT,),
            )
        conn.executemany(
            f"""
            INSERT INTO {BRIDGE_TABLE}
                (classe, regra_semantica, obra_contexto, confianca)
            VALUES (?, ?, ?, ?)
            """,
            [(r.classe, r.regra_semantica, r.obra_contexto, r.confianca) for r in rows],
        )
        conn.commit()
        return count_bridge_rows(conn)


def summarize(rows: list[SemanticBridgeRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.classe] = counts.get(row.classe, 0) + 1
    return dict(sorted(counts.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Popula semantic_rag_kb a partir de domain_knowledge")
    parser.add_argument("--lancedb", default=str(DEFAULT_LANCEDB_PATH), help="Path do stog_rag_db")
    parser.add_argument("--sqlite", default=str(DEFAULT_SQLITE_PATH), help="Path do project_data.vision")
    parser.add_argument("--apply", action="store_true", help="Grava no SQLite; sem isto e dry-run")
    parser.add_argument("--dry-run", action="store_true", help="Audita sem gravar (comportamento padrao)")
    parser.add_argument("--no-replace", action="store_true", help="Nao remover linhas anteriores do mesmo contexto")
    parser.add_argument("--sample", type=int, default=3, help="Numero de exemplos no dry-run")
    args = parser.parse_args()

    records = load_domain_records(Path(args.lancedb))
    rows = records_to_bridge_rows(records)
    summary = summarize(rows)

    print(f"[domain_knowledge] records={len(records)}")
    print(f"[semantic_rag_kb] candidate_rows={len(rows)} by_class={summary}")

    if not args.apply:
        print("[dry-run] Nenhuma escrita realizada. Use --apply para popular o SQLite.")
        for row in rows[: max(args.sample, 0)]:
            payload = json.loads(row.regra_semantica)
            print(
                f"  - {row.classe} conf={row.confianca:.2f} "
                f"{payload.get('source_doc')} :: {payload.get('section')}"
            )
        return

    total = apply_rows(
        rows,
        Path(args.sqlite),
        replace=not args.no_replace,
    )
    print(f"[OK] semantic_rag_kb rows for {BRIDGE_CONTEXT}: {total}")


if __name__ == "__main__":
    main()
