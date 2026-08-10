#!/usr/bin/env python3
"""Índice de sessão do QA Global N1 — camadas B2 (snapshot) e B3 (fonte CAD).

Plano: docs/MASTERPLAN-MINIRAG-QA-N1.md (fases D0/D1).
Conceito e governança: docs/PROPOSTA-MINIRAG-SESSAO-N1.md.

B2 = projeção read-only do snapshot N1 (slabs/pillars/beams) de um project-id,
com grafo cross-classe derivado dos links persistidos. B3 = índice espacial das
entidades do DXF limpo do pavimento (Fase-1), consultável por coordenada, tipo e
conteúdo de texto — nome de layer é metadado descritivo, nunca filtro.

Consultivo por contrato: nenhuma resposta daqui confirma campo/ficha; a prova
continua sendo re-derivação do adaptador + gate visual + veredito humano.
Toda consulta é registrada em session_index_consultas.jsonl com o hash do
manifest; fontes alteradas após o build tornam o índice stale e a consulta
falha fechado exigindo rebuild.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BUILDER_VERSION = "0.2.0-d2"
DEFAULT_DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DEFAULT_GRID_CELL = 100.0
# Fontes N2/engenharia reversa jamais entram no índice N1 (anti-leakage).
FORBIDDEN_PATH_TOKENS = ("fase-2", "recortes_reversos", "recortes", "reverse_eng")

# B1: mesmo modelo local usado em obra_rag_utils.py/domain_knowledge_ingestor.py
# (paraphrase-multilingual-mpnet-base-v2), CPU, sem NVIDIA/API — "Sem API
# externa" é regra inegociável da proposta (docs/PROPOSTA-MINIRAG-SESSAO-N1.md).
LOCAL_EMBED_MODEL = "paraphrase-multilingual-mpnet-base-v2"
B1_TEXT_MAX_CHARS = 2000

CLASS_TABLES = {"LAJ": "slabs", "PIL": "pillars", "FV": "beams", "LV": "beams"}
B2_COLUMNS = {
    "slabs": ["id", "project_id", "name", "id_item", "is_validated", "type", "area",
              "points_json", "links_json", "validated_fields_json",
              "validated_link_classes_json", "na_fields_json", "issues_json"],
    "pillars": ["id", "project_id", "name", "id_item", "is_validated", "type", "area",
                "points_json", "sides_data_json", "links_json", "validated_fields_json",
                "validated_link_classes_json", "na_fields_json", "issues_json"],
    "beams": ["id", "project_id", "name", "id_item", "is_validated",
              "data_json", "sides_data_json", "links_json", "validated_fields_json",
              "validated_link_classes_json", "na_fields_json", "issues_json"],
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_dxf_path_allowed(dxf_path: Path) -> None:
    low = str(dxf_path).replace("\\", "/").lower()
    for token in FORBIDDEN_PATH_TOKENS:
        if token in low:
            raise ValueError(
                f"anti-leakage: path de fonte proibida para índice N1 ({token!r}): {dxf_path}"
            )
    if dxf_path.suffix.lower() == ".pkl":
        raise ValueError(f"TRUE_GEOMETRY.pkl é legado; B3 lê apenas DXF: {dxf_path}")
    if dxf_path.suffix.lower() != ".dxf":
        raise ValueError(f"B3 aceita somente .dxf: {dxf_path}")


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _fetch_n1_rows(con: sqlite3.Connection, project_id: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for table, cols in B2_COLUMNS.items():
        rows = con.execute(
            f"SELECT {', '.join(cols)} FROM {table} WHERE project_id=? ORDER BY id",
            (project_id,),
        ).fetchall()
        out[table] = [dict(r) for r in rows]
    return out


def _n1_fingerprint(rows_by_table: dict[str, list[dict]]) -> str:
    payload = json.dumps(rows_by_table, sort_keys=True, ensure_ascii=False,
                         default=str).encode("utf-8")
    return _sha256_bytes(payload)


def _extract_edges(rows_by_table: dict[str, list[dict]]) -> list[dict]:
    """Grafo cross-classe derivado apenas do que os links persistidos declaram."""
    known_names: dict[str, str] = {}
    for table, classe in (("slabs", "LAJ"), ("pillars", "PIL"), ("beams", "VIGA")):
        for row in rows_by_table[table]:
            if row.get("name"):
                known_names[str(row["name"])] = classe

    edges: list[dict] = []

    def _walk(node: object, path: str, src: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("pillar_name", "source_slab", "beam_name", "viga_name") and \
                        isinstance(value, str) and value in known_names and value != src:
                    edges.append({
                        "src": src, "dst": value,
                        "dst_classe": known_names[value],
                        "via": path or key, "declared_key": key,
                    })
                _walk(value, f"{path}.{key}" if path else key, src)
        elif isinstance(node, list):
            for item in node:
                _walk(item, path, src)

    for table in ("slabs", "pillars", "beams"):
        for row in rows_by_table[table]:
            src = str(row.get("name") or f"{table}:{row['id']}")
            links_raw = row.get("links_json")
            if not links_raw:
                continue
            try:
                links = json.loads(links_raw)
            except (TypeError, json.JSONDecodeError):
                continue
            _walk(links, "", src)

    seen: set[tuple] = set()
    unique: list[dict] = []
    for edge in edges:
        key = (edge["src"], edge["dst"], edge["via"], edge["declared_key"])
        if key not in seen:
            seen.add(key)
            unique.append(edge)
    return unique


def _entity_geometry(entity) -> tuple[list[list[float]], str | None]:
    etype = entity.dxftype()
    points: list[list[float]] = []
    text: str | None = None
    dxf = entity.dxf
    try:
        if etype == "LINE":
            points = [[dxf.start.x, dxf.start.y], [dxf.end.x, dxf.end.y]]
        elif etype == "LWPOLYLINE":
            points = [[p[0], p[1]] for p in entity.get_points("xy")]
        elif etype in ("TEXT", "MTEXT"):
            ins = dxf.insert if etype == "TEXT" else dxf.insert
            points = [[ins.x, ins.y]]
            text = entity.plain_text() if etype == "MTEXT" else dxf.text
        elif etype == "CIRCLE":
            c, r = dxf.center, float(dxf.radius)
            points = [[c.x - r, c.y - r], [c.x + r, c.y + r]]
        elif etype == "ARC":
            c, r = dxf.center, float(dxf.radius)
            points = [[c.x - r, c.y - r], [c.x + r, c.y + r]]
        elif etype == "SOLID":
            points = [[getattr(dxf, name).x, getattr(dxf, name).y]
                      for name in ("vtx0", "vtx1", "vtx2", "vtx3")
                      if hasattr(dxf, name)]
        elif etype == "POINT":
            points = [[dxf.location.x, dxf.location.y]]
        elif hasattr(dxf, "insert"):
            ins = dxf.insert
            points = [[ins.x, ins.y]]
    except Exception:
        points = []
    return points, text


def _b1_row_text_semantic_rag_kb(row: dict) -> str:
    """Duas formas conhecidas em semantic_rag_kb (2026-07-18, 117 linhas reais):
    doc_type='field_semantics' (109, tem 'text' em prosa) e
    kind='qa_groundtruth_item_field' (8, candidato T1 promovido — confirmação
    de campo por lote de itens, sem prosa). Dumpar o JSON cru do segundo tipo
    poluiria o embedding com IDs/hashes sem sinal semântico; resumimos em
    frase legível em vez disso.
    """
    try:
        regra = json.loads(row.get("regra_semantica") or "{}")
    except (TypeError, json.JSONDecodeError):
        regra = {}
    if not isinstance(regra, dict):
        regra = {}
    if regra.get("kind") == "qa_groundtruth_item_field":
        items = regra.get("items")
        n_items = len(items) if isinstance(items, (dict, list)) else 0
        body = (
            f"Confirmação {regra.get('tier') or ''} do campo "
            f"'{regra.get('field_id') or '?'}' aprovada por "
            f"{regra.get('approved_by') or 'humano'} para {n_items} itens "
            f"(run {regra.get('source_run') or '?'})"
        )
        header = f"[{row.get('classe')}] confirmacao_campo"
        return f"{header}\n{body}"[:B1_TEXT_MAX_CHARS]
    body = regra.get("text") or regra.get("regra_proposta") \
        or json.dumps(regra, ensure_ascii=False)
    header = f"[{row.get('classe')}] {regra.get('section') or ''}".strip()
    return f"{header}\n{body}"[:B1_TEXT_MAX_CHARS]


def _b1_row_text_human_event_logs(row: dict) -> str:
    """MR-1 (2026-07-19) achou este resumo fino demais: dizia "aprovado" sem
    dar ao leitor como localizar o pacote completo. log_id de aprovações em
    lote tem a forma "qa-rag-approval-<candidate_id>" — extraímos o
    candidate_id pra virar chave de busca em semantic_rag_kb.regra_semantica
    (onde vivem os decision_ids/items completos), em vez de só apontar que
    "existe" aprovação.
    """
    log_id = str(row.get("log_id") or "")
    candidate_id = log_id.split("qa-rag-approval-", 1)[-1] if "qa-rag-approval-" in log_id else None
    approval = ""
    if row.get("status") == "APPROVED":
        approval = (
            f"; aprovado por {row.get('approved_by') or '?'} em "
            f"{row.get('approved_at') or '?'}"
            + (f"; candidate_id={candidate_id} (buscar em semantic_rag_kb.regra_semantica)"
               if candidate_id else "")
        )
    text = (
        f"[{row.get('classe')}] item {row.get('item_id')} — "
        f"{row.get('user_reason') or '(sem motivo registrado)'} "
        f"(campos alterados: {row.get('campos_alterados') or '[]'}; "
        f"status {row.get('status')}{approval})"
    )
    return text[:B1_TEXT_MAX_CHARS]


def _fetch_b1_corpus(con: sqlite3.Connection) -> list[dict]:
    """B1 = conhecimento consultivo: regras curadas + decisões/ensino humano.

    Nunca inclui achado sem tier como confirmação — tier é propagado cru para
    quem consulta decidir (contrato QA↔RAG §4-5; T1/T2 confirmam, T3/None não).
    """
    entries: list[dict] = []
    tables = {row[0] for row in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}

    if "semantic_rag_kb" in tables:
        cols = {row[1] for row in con.execute("PRAGMA table_info(semantic_rag_kb)")}
        select_cols = [c for c in (
            "id", "classe", "regra_semantica", "obra_contexto", "confianca",
            "created_at", "tier", "field_id", "familia", "pavimento") if c in cols]
        for row in con.execute(
                f"SELECT {', '.join(select_cols)} FROM semantic_rag_kb"):
            d = dict(row)
            entries.append({
                "source_table": "semantic_rag_kb", "source_id": d["id"],
                "classe": d.get("classe"), "familia": d.get("familia"),
                "field": d.get("field_id"), "tier": d.get("tier"),
                "obra": d.get("obra_contexto"), "pav": d.get("pavimento"),
                "item": None, "confianca": d.get("confianca"),
                "created_at": d.get("created_at"),
                "text": _b1_row_text_semantic_rag_kb(d),
            })

    if "human_event_logs" in tables:
        cols = {row[1] for row in con.execute("PRAGMA table_info(human_event_logs)")}
        select_cols = [c for c in (
            "log_id", "timestamp", "obra_id", "classe", "item_id",
            "campos_alterados", "event_kind", "status", "tier",
            "user_reason", "approved_by", "approved_at") if c in cols]
        for row in con.execute(
                f"SELECT {', '.join(select_cols)} FROM human_event_logs "
                "WHERE (user_reason IS NOT NULL AND user_reason != '') "
                "OR status='APPROVED'"):
            d = dict(row)
            entries.append({
                "source_table": "human_event_logs", "source_id": d["log_id"],
                "classe": d.get("classe"), "familia": None, "field": None,
                "tier": d.get("tier"), "obra": d.get("obra_id"), "pav": None,
                "item": d.get("item_id"), "confianca": None,
                "created_at": d.get("timestamp"),
                "text": _b1_row_text_human_event_logs(d),
            })

    entries.sort(key=lambda e: (e["source_table"], e["source_id"]))
    return entries


def _b1_fingerprint(entries: list[dict]) -> str:
    payload = json.dumps(entries, sort_keys=True, ensure_ascii=False,
                         default=str).encode("utf-8")
    return _sha256_bytes(payload)


_EMBEDDER = None


def _local_embedder():
    """Modelo local lazy; nunca chama API externa (regra 5 da proposta)."""
    global _EMBEDDER
    if _EMBEDDER is None:
        from sentence_transformers import SentenceTransformer
        _EMBEDDER = SentenceTransformer(LOCAL_EMBED_MODEL)
    return _EMBEDDER


def _try_embed(texts: list[str]):
    """None = degradado; builder/query caem para filtro exato sem quebrar sessão."""
    if not texts:
        return None
    try:
        import numpy as np
        model = _local_embedder()
        vecs = model.encode(texts, show_progress_bar=False, batch_size=32,
                            normalize_embeddings=True)
        return np.asarray(vecs, dtype="float32")
    except Exception as exc:  # noqa: BLE001 — degradação deliberada, nunca bloqueia
        print(f"[qa_session_index] B1 degradado (embedder indisponível): {exc}",
             file=sys.stderr)
        return None


def build_index(project_id: str, out_dir: Path, *, db_path: Path = DEFAULT_DB,
                pav_dxf: Path | None = None,
                grid_cell: float = DEFAULT_GRID_CELL,
                include_b1: bool = True) -> dict:
    t_start = time.time()
    out_dir.mkdir(parents=True, exist_ok=True)
    idx_path = out_dir / "session_index.sqlite"
    if idx_path.exists():
        idx_path.unlink()

    con_src = _connect_ro(db_path)
    project = con_src.execute(
        "SELECT id, name, work_name FROM projects WHERE id=?", (project_id,)
    ).fetchone()
    if project is None:
        raise SystemExit(f"project-id não encontrado: {project_id}")
    rows_by_table = _fetch_n1_rows(con_src, project_id)
    con_src.close()
    n1_fp = _n1_fingerprint(rows_by_table)
    edges = _extract_edges(rows_by_table)

    idx = sqlite3.connect(idx_path)
    idx.executescript(
        """
        CREATE TABLE b2_items (
            classe TEXT, source_table TEXT, row_id INTEGER, name TEXT,
            id_item INTEGER, is_validated INTEGER, payload_json TEXT
        );
        CREATE INDEX ix_b2_name ON b2_items(name);
        CREATE TABLE b2_edges (
            src TEXT, dst TEXT, dst_classe TEXT, via TEXT, declared_key TEXT
        );
        CREATE INDEX ix_b2_edges_src ON b2_edges(src);
        CREATE INDEX ix_b2_edges_dst ON b2_edges(dst);
        CREATE TABLE b3_entities (
            eid INTEGER PRIMARY KEY, handle TEXT, etype TEXT, layer_meta TEXT,
            minx REAL, miny REAL, maxx REAL, maxy REAL,
            text_content TEXT, points_json TEXT
        );
        CREATE TABLE b3_grid (cell_x INTEGER, cell_y INTEGER, eid INTEGER);
        CREATE INDEX ix_b3_grid ON b3_grid(cell_x, cell_y);
        CREATE TABLE b1_entries (
            id INTEGER PRIMARY KEY, source_table TEXT, source_id INTEGER,
            classe TEXT, familia TEXT, field TEXT, tier TEXT, obra TEXT,
            pav TEXT, item TEXT, confianca REAL, created_at TEXT, text TEXT,
            embedding BLOB
        );
        CREATE INDEX ix_b1_classe ON b1_entries(classe);
        CREATE INDEX ix_b1_tier ON b1_entries(tier);
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        """
    )
    table_to_classe = {"slabs": "LAJ", "pillars": "PIL", "beams": "VIGA"}
    for table, rows in rows_by_table.items():
        for row in rows:
            idx.execute(
                "INSERT INTO b2_items VALUES (?,?,?,?,?,?,?)",
                (table_to_classe[table], table, row["id"], row.get("name"),
                 row.get("id_item"), row.get("is_validated"),
                 json.dumps(row, ensure_ascii=False, default=str)),
            )
    idx.executemany(
        "INSERT INTO b2_edges VALUES (?,?,?,?,?)",
        [(e["src"], e["dst"], e["dst_classe"], e["via"], e["declared_key"])
         for e in edges],
    )

    b3_stats: dict = {"enabled": False}
    dxf_hash = None
    if pav_dxf is not None:
        pav_dxf = Path(pav_dxf)
        _check_dxf_path_allowed(pav_dxf)
        import ezdxf
        doc = ezdxf.readfile(str(pav_dxf))
        msp = doc.modelspace()
        n_ent = 0
        for eid, entity in enumerate(msp):
            points, text = _entity_geometry(entity)
            if not points:
                continue
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            minx, miny, maxx, maxy = min(xs), min(ys), max(xs), max(ys)
            idx.execute(
                "INSERT INTO b3_entities VALUES (?,?,?,?,?,?,?,?,?,?)",
                (eid, entity.dxf.handle, entity.dxftype(),
                 getattr(entity.dxf, "layer", None),
                 minx, miny, maxx, maxy, text,
                 json.dumps(points)),
            )
            cells = set()
            for cx in range(int(minx // grid_cell), int(maxx // grid_cell) + 1):
                for cy in range(int(miny // grid_cell), int(maxy // grid_cell) + 1):
                    cells.add((cx, cy))
            idx.executemany(
                "INSERT INTO b3_grid VALUES (?,?,?)",
                [(cx, cy, eid) for cx, cy in cells],
            )
            n_ent += 1
        dxf_hash = _sha256_file(pav_dxf)
        b3_stats = {"enabled": True, "entities_indexed": n_ent,
                    "grid_cell": grid_cell, "dxf": str(pav_dxf)}

    b1_stats: dict = {"enabled": False}
    b1_fp = None
    if include_b1:
        con_b1 = _connect_ro(db_path)
        b1_entries = _fetch_b1_corpus(con_b1)
        con_b1.close()
        b1_fp = _b1_fingerprint(b1_entries)
        texts = [e["text"] for e in b1_entries]
        vectors = _try_embed(texts)
        for i, entry in enumerate(b1_entries):
            emb_blob = vectors[i].tobytes() if vectors is not None else None
            idx.execute(
                "INSERT INTO b1_entries (source_table, source_id, classe, familia, "
                "field, tier, obra, pav, item, confianca, created_at, text, "
                "embedding) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (entry["source_table"], entry["source_id"], entry["classe"],
                 entry["familia"], entry["field"], entry["tier"], entry["obra"],
                 entry["pav"], entry["item"], entry["confianca"],
                 entry["created_at"], entry["text"], emb_blob),
            )
        b1_stats = {
            "enabled": True, "entries": len(b1_entries),
            "degraded": vectors is None,
            "embed_model": LOCAL_EMBED_MODEL if vectors is not None else None,
            "sources": sorted({e["source_table"] for e in b1_entries}),
        }

    manifest = {
        "builder_version": BUILDER_VERSION,
        "built_at": _utc_now(),
        "project_id": project_id,
        "project_name": project["name"],
        "work_name": project["work_name"],
        "db_path": str(db_path),
        "n1_fingerprint_sha256": n1_fp,
        "n1_row_counts": {t: len(r) for t, r in rows_by_table.items()},
        "b2_edges": len(edges),
        "b3": b3_stats,
        "b1": b1_stats,
        "b1_fingerprint_sha256": b1_fp,
        "dxf_sha256": dxf_hash,
        "grid_cell": grid_cell,
        "authority": ("consultative_only; nenhuma resposta confirma campo/ficha; "
                      "prova = re-derivacao do adaptador + gate visual + humano"),
        "build_seconds": round(time.time() - t_start, 2),
    }
    manifest_json = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
    manifest["manifest_sha256"] = _sha256_bytes(manifest_json.encode("utf-8"))
    for key, value in manifest.items():
        idx.execute("INSERT OR REPLACE INTO meta VALUES (?,?)",
                    (key, json.dumps(value, ensure_ascii=False)))
    idx.commit()
    idx.close()
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    return manifest


class SessionIndex:
    """Consulta com verificação de staleness em toda chamada (falha fechado)."""

    def __init__(self, index_dir: Path, *, skip_stale_check: bool = False):
        self.dir = Path(index_dir)
        manifest_path = self.dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"manifest.json não encontrado em {self.dir}")
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self._log_path = self.dir / "session_index_consultas.jsonl"
        if not skip_stale_check:
            self._assert_fresh()
        self.con = sqlite3.connect(
            f"file:{(self.dir / 'session_index.sqlite').as_posix()}?mode=ro", uri=True)
        self.con.row_factory = sqlite3.Row

    def _assert_fresh(self) -> None:
        con_src = _connect_ro(Path(self.manifest["db_path"]))
        rows = _fetch_n1_rows(con_src, self.manifest["project_id"])
        con_src.close()
        if _n1_fingerprint(rows) != self.manifest["n1_fingerprint_sha256"]:
            raise RuntimeError(
                "índice STALE: snapshot N1 mudou desde o build — rebuild obrigatório "
                "(qa_session_index.py build)")
        if self.manifest.get("dxf_sha256"):
            dxf_path = Path(self.manifest["b3"]["dxf"])
            if not dxf_path.exists() or _sha256_file(dxf_path) != self.manifest["dxf_sha256"]:
                raise RuntimeError(
                    "índice STALE: DXF do pavimento mudou desde o build — rebuild obrigatório")
        if self.manifest.get("b1", {}).get("enabled"):
            con_b1 = _connect_ro(Path(self.manifest["db_path"]))
            entries = _fetch_b1_corpus(con_b1)
            con_b1.close()
            if _b1_fingerprint(entries) != self.manifest.get("b1_fingerprint_sha256"):
                raise RuntimeError(
                    "índice STALE: corpus B1 (regras/decisões humanas) mudou desde "
                    "o build — rebuild obrigatório")

    def _log(self, kind: str, query: dict, n_results: int) -> None:
        entry = {
            "ts": _utc_now(), "kind": kind, "query": query,
            "n_results": n_results,
            "manifest_sha256": self.manifest.get("manifest_sha256"),
            "n1_fingerprint": self.manifest["n1_fingerprint_sha256"],
        }
        with self._log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ── B1 (consultivo; filtro exato de partição, depois similaridade) ──
    def b1_query(self, text: str = "", *, classe: str | None = None,
                familia: str | None = None, field: str | None = None,
                tier: list[str] | None = None, obra: str | None = None,
                pav: str | None = None, item: str | None = None,
                top_k: int = 5) -> list[dict]:
        where, params = [], []
        if classe:
            where.append("upper(classe)=upper(?)")
            params.append(classe)
        if familia:
            where.append("familia=?")
            params.append(familia)
        if field:
            where.append("field=?")
            params.append(field)
        if tier:
            placeholders = ",".join("?" for _ in tier)
            where.append(f"upper(tier) IN ({placeholders})")
            params.extend(t.upper() for t in tier)
        sql = "SELECT * FROM b1_entries" + (
            " WHERE " + " AND ".join(where) if where else "")
        rows = [dict(r) for r in self.con.execute(sql, params)]

        b1_manifest = self.manifest.get("b1", {})
        degraded = (not b1_manifest.get("enabled")) or b1_manifest.get("degraded")
        method = "exact_partition_only"
        if not degraded and text:
            qvec = _try_embed([text])
            if qvec is None:
                method = "exact_partition_only_query_embed_failed"
            else:
                import numpy as np
                qv = qvec[0]
                scored = []
                for row in rows:
                    if not row.get("embedding"):
                        continue
                    vec = np.frombuffer(row["embedding"], dtype="float32")
                    scored.append((float(np.dot(qv, vec)), row))
                scored.sort(key=lambda pair: pair[0], reverse=True)
                rows = [row for _, row in scored]
                method = "semantic_within_partition"
        if method != "semantic_within_partition":
            rows = sorted(rows, key=lambda r: r.get("created_at") or "", reverse=True)
        rows = rows[:top_k]

        results = []
        for row in rows:
            row = dict(row)
            row.pop("embedding", None)
            same_origin = bool(
                (obra and row.get("obra") and str(row["obra"]) == str(obra))
                or (item and row.get("item") and str(row["item"]) == str(item))
            )
            row["same_origin"] = same_origin
            row["retrieval_method"] = method
            row["authority"] = (
                "consultative_only; same_origin=True nunca conta como reforço "
                "confirmatório; requires human-approved tier before confirmation")
            results.append(row)

        self._log("b1", {"op": "query", "text": text, "classe": classe,
                         "familia": familia, "field": field, "tier": tier,
                         "obra": obra, "pav": pav, "item": item,
                         "method": method}, len(results))
        return results

    # ── B2 ──────────────────────────────────────────────────────────────
    def b2_item(self, name: str) -> list[dict]:
        rows = self.con.execute(
            "SELECT classe, source_table, row_id, name, id_item, is_validated, "
            "payload_json FROM b2_items WHERE name=?", (name,)).fetchall()
        out = [dict(r) for r in rows]
        for r in out:
            r["payload"] = json.loads(r.pop("payload_json"))
        self._log("b2", {"op": "item", "name": name}, len(out))
        return out

    def b2_neighbors(self, name: str) -> dict:
        outgoing = [dict(r) for r in self.con.execute(
            "SELECT * FROM b2_edges WHERE src=?", (name,))]
        incoming = [dict(r) for r in self.con.execute(
            "SELECT * FROM b2_edges WHERE dst=?", (name,))]
        result = {"item": name, "outgoing": outgoing, "incoming": incoming}
        self._log("b2", {"op": "neighbors", "name": name},
                  len(outgoing) + len(incoming))
        return result

    def b2_list(self, classe: str | None = None) -> list[dict]:
        sql = ("SELECT classe, name, id_item, is_validated FROM b2_items"
               + (" WHERE classe=?" if classe else "") + " ORDER BY name")
        rows = self.con.execute(sql, (classe,) if classe else ()).fetchall()
        out = [dict(r) for r in rows]
        self._log("b2", {"op": "list", "classe": classe}, len(out))
        return out

    # ── B3 (sem filtro por layer, por contrato) ─────────────────────────
    def b3_entities_near(self, x: float, y: float, radius: float,
                         types: list[str] | None = None) -> list[dict]:
        cell = self.manifest["grid_cell"]
        cx0, cx1 = int((x - radius) // cell), int((x + radius) // cell)
        cy0, cy1 = int((y - radius) // cell), int((y + radius) // cell)
        eids = {r[0] for r in self.con.execute(
            "SELECT DISTINCT eid FROM b3_grid WHERE cell_x BETWEEN ? AND ? "
            "AND cell_y BETWEEN ? AND ?", (cx0, cx1, cy0, cy1))}
        out = []
        for eid in eids:
            row = self.con.execute(
                "SELECT * FROM b3_entities WHERE eid=?", (eid,)).fetchone()
            if types and row["etype"] not in types:
                continue
            dx = max(row["minx"] - x, 0, x - row["maxx"])
            dy = max(row["miny"] - y, 0, y - row["maxy"])
            dist = (dx * dx + dy * dy) ** 0.5
            if dist <= radius:
                d = dict(row)
                d["distance"] = round(dist, 3)
                d["points"] = json.loads(d.pop("points_json"))
                out.append(d)
        out.sort(key=lambda d: d["distance"])
        self._log("b3", {"op": "entities_near", "x": x, "y": y,
                         "radius": radius, "types": types}, len(out))
        return out

    def b3_texts_in_bbox(self, minx: float, miny: float, maxx: float,
                         maxy: float) -> list[dict]:
        rows = self.con.execute(
            "SELECT * FROM b3_entities WHERE etype IN ('TEXT','MTEXT') "
            "AND maxx>=? AND minx<=? AND maxy>=? AND miny<=?",
            (minx, maxx, miny, maxy)).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            d["points"] = json.loads(d.pop("points_json"))
            out.append(d)
        self._log("b3", {"op": "texts_in_bbox",
                         "bbox": [minx, miny, maxx, maxy]}, len(out))
        return out

    def b3_entities_of_type(self, etype: str, bbox: list[float] | None = None
                            ) -> list[dict]:
        sql = "SELECT * FROM b3_entities WHERE etype=?"
        params: list = [etype]
        if bbox:
            sql += " AND maxx>=? AND minx<=? AND maxy>=? AND miny<=?"
            params += [bbox[0], bbox[2], bbox[1], bbox[3]]
        rows = self.con.execute(sql, params).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            d["points"] = json.loads(d.pop("points_json"))
            out.append(d)
        self._log("b3", {"op": "entities_of_type", "etype": etype,
                         "bbox": bbox}, len(out))
        return out

    def close(self) -> None:
        self.con.close()


def _cmd_build(args) -> None:
    manifest = build_index(
        args.project_id, Path(args.out), db_path=Path(args.db),
        pav_dxf=Path(args.pav_dxf) if args.pav_dxf else None,
        grid_cell=args.grid_cell, include_b1=not args.no_b1)
    print(json.dumps({k: manifest[k] for k in
                      ("project_id", "project_name", "n1_row_counts", "b2_edges",
                       "b3", "b1", "build_seconds", "manifest_sha256")},
                     ensure_ascii=False, indent=2))


def _cmd_query(args) -> None:
    query = json.loads(args.json)
    idx = SessionIndex(Path(args.index))
    kind, op = args.kind, query.get("op")
    if kind == "b1":
        if op == "query":
            result = idx.b1_query(
                query.get("text", ""), classe=query.get("classe"),
                familia=query.get("familia"), field=query.get("field"),
                tier=query.get("tier"), obra=query.get("obra"),
                pav=query.get("pav"), item=query.get("item"),
                top_k=query.get("top_k", 5))
        else:
            raise SystemExit(f"op b1 desconhecida: {op}")
    elif kind == "b2":
        if op == "item":
            result = idx.b2_item(query["name"])
        elif op == "neighbors":
            result = idx.b2_neighbors(query["name"])
        elif op == "list":
            result = idx.b2_list(query.get("classe"))
        else:
            raise SystemExit(f"op b2 desconhecida: {op}")
    elif kind == "b3":
        if op == "entities_near":
            result = idx.b3_entities_near(
                query["x"], query["y"], query["radius"], query.get("types"))
        elif op == "texts_in_bbox":
            b = query["bbox"]
            result = idx.b3_texts_in_bbox(b[0], b[1], b[2], b[3])
        elif op == "entities_of_type":
            result = idx.b3_entities_of_type(query["etype"], query.get("bbox"))
        else:
            raise SystemExit(f"op b3 desconhecida: {op}")
    else:
        raise SystemExit(f"kind desconhecido: {kind}")
    idx.close()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="constrói índice B1+B2(+B3) de sessão")
    p_build.add_argument("--project-id", required=True)
    p_build.add_argument("--out", required=True, help="pasta do índice (dossiê)")
    p_build.add_argument("--db", default=str(DEFAULT_DB))
    p_build.add_argument("--pav-dxf", default=None,
                         help="DXF limpo do pavimento (Fase-1) para B3")
    p_build.add_argument("--grid-cell", type=float, default=DEFAULT_GRID_CELL)
    p_build.add_argument("--no-b1", action="store_true",
                         help="pula camada semântica (só B2+B3)")
    p_build.set_defaults(func=_cmd_build)

    p_query = sub.add_parser("query", help="consulta o índice (loga em jsonl)")
    p_query.add_argument("--index", required=True)
    p_query.add_argument("--kind", required=True, choices=["b1", "b2", "b3"])
    p_query.add_argument("--json", required=True)
    p_query.set_defaults(func=_cmd_query)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
