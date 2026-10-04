"""Build a VPS knowledge-search snapshot while preserving VPS-owned decisions.

Reads the downloaded VPS DECISOES-DO-DONO.md as an explicit input. The result is a
new SQLite file; neither production data nor the normal local KB is overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from kb_build import _chunk, _linhas_de_tabela, chunks_globais, gravar
from kb_comum import GLOBAL_DB


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vps-decisions", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    source = args.vps_decisions.resolve(strict=True)
    output = args.output.resolve()
    if output.exists():
        ap.error("output exists: use a new snapshot path")
    if not GLOBAL_DB.exists():
        ap.error("local KB missing: run kb_build.py first")
    if "| D-08 |" not in source.read_text(encoding="utf-8"):
        ap.error("VPS decisions snapshot lacks Jev decision D-08")

    chunks, n_sources = chunks_globais()
    own = [c for c in chunks if c["path"].endswith("/docs/CONHECIMENTO/DECISOES-DO-DONO.md")]
    if not own:
        ap.error("local decisions were not indexed")
    normal_path = own[0]["path"]
    template = own[0]
    chunks = [c for c in chunks if c["path"] != normal_path]
    remote_text = source.read_text(encoding="utf-8")
    remote_chunks = []
    for order, (section, header, line) in enumerate(_linhas_de_tabela(remote_text)):
        text = f"{header}\n{line}" if header else line
        remote_chunks.append(_chunk("global", "decisao", normal_path,
                                    template["titulo"], section, template["status"],
                                    "T1", template["data"], order, text))
    chunks.extend(remote_chunks)

    # SQLite's backup API takes a consistent snapshot of the local vector cache.
    output.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(f"file:{GLOBAL_DB.as_posix()}?mode=ro", uri=True)) as src:
        with closing(sqlite3.connect(output)) as dst:
            src.backup(dst)
    gravar(output, chunks, "nim", "global", {"n_fontes": n_sources,
           "vps_decisions_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
           "snapshot_kind": "vps_source_overlay"})
    with closing(sqlite3.connect(f"file:{output.as_posix()}?mode=ro", uri=True)) as con:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        count = con.execute("SELECT count(*) FROM chunks").fetchone()[0]
        jev = con.execute("SELECT count(*) FROM chunks WHERE texto LIKE '%Jev%'").fetchone()[0]
        remote_lines = {line for _, _, line in _linhas_de_tabela(remote_text)}
        indexed_lines = {c["texto"].splitlines()[-1] for c in remote_chunks}
        if integrity != "ok" or count != len(chunks) or not jev or remote_lines != indexed_lines:
            raise RuntimeError(f"snapshot validation failed: {integrity=}, {count=}, {jev=}")
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                "db_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "vps_decisions_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "chunks": count, "jev_chunks": jev, "integrity_check": integrity,
                "source_policy": "local indexed docs + downloaded VPS decisions"}
    output.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
