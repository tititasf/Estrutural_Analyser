"""One-shot operator helper for the explicitly requested 14_PAV VPS run."""
import hashlib
import json
import sys
from pathlib import Path

from portal.app.config import load_settings
from portal.app.preprocessamento.freshness import changed_sources
from portal.app.preprocessamento.service import ENGINE_VERSION, read_floor, read_tower
from portal.app.preprocessamento.sources import (
    SourceKind, inventory_floor_sources, raw_level_references,
)
from portal.db.connection import get_connection
from portal.db import repository as repo

OBRA_ID = "781becd6-b113-4bec-8d5a-2027f10a65a8"
PAV = "14_PAV"
settings = load_settings()
conn = get_connection(settings.db_path)
obra = repo.obter_obra(conn, OBRA_ID)
assert obra, "obra ausente"
root = Path(obra["local_path"]) if obra.get("local_path") else settings.dados_obras_dir / obra["nome"]
command = sys.argv[1]

if command == "status":
    print("obra", root, "exists", root.is_dir())
    print("portal_db", conn.execute("PRAGMA database_list").fetchone()[2])
    for row in conn.execute(
        "SELECT j.id,j.status,j.enfileirado_em,m.meta_json FROM portal_jobs j "
        "LEFT JOIN portal_job_meta m ON m.job_id=j.id WHERE j.obra_id=? "
        "ORDER BY j.enfileirado_em DESC,j.rowid DESC LIMIT 8", (OBRA_ID,)
    ):
        meta = json.loads(row["meta_json"] or "{}")
        print("job", row["id"], row["status"], row["enfileirado_em"],
              meta.get("etapa"), meta.get("pav"), meta.get("result", {}).get("status"))
    floor = read_floor(root, PAV)
    if floor:
        print("floor", floor["run_id"], floor["coverage"], "stale", changed_sources(root, floor["sources"]))
        for source_id in floor["towers"]:
            package = read_tower(root, floor, source_id)
            inventory = package.get("level_inventory") or {}
            print("tower", package["status"], inventory.get("reference"), inventory.get("coverage"),
                  inventory.get("segment_coverage"))
    else:
        print("floor", "not_started")
elif command == "preprocess":
    kinds = {SourceKind.TOWER, SourceKind.DETAILS, SourceKind.PILLAR_CONVENTION, SourceKind.LEVEL_CONVENTION}
    sources = [source for source in inventory_floor_sources(
        obra_dir=root, obra_id=OBRA_ID, pavimento_id=PAV,
        documents=repo.listar_documentos_por_obra(conn, OBRA_ID),
    ) if source.kind in kinds]
    assert any(source.kind is SourceKind.TOWER for source in sources), "torre ausente"
    pending = [source.item_id for source in sources
               if not source.validated and source.kind is not SourceKind.LEVEL_CONVENTION]
    assert not pending, f"recortes pendentes: {pending}"
    frozen = {source.source_id: source.revision for source in sources}
    frozen.update({source["source_id"]: source["revision"]
                   for source in raw_level_references(root, sources)})
    scope_hash = hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest()
    meta = {"etapa": "preprocessamento", "pav": PAV,
            "scope_hash": scope_hash, "engine_version": ENGINE_VERSION,
            "sources": [{"bruto_id": source.bruto_id, "item_id": source.item_id} for source in sources],
            "frozen_sources": frozen}
    job_id, created = repo.enfileirar_job_unico_por_meta(
        conn, obra_id=OBRA_ID, meta=meta,
        chaves=("etapa", "pav", "scope_hash", "engine_version"),
        engine_version=ENGINE_VERSION,
    )
    print("preprocess_job", job_id, "created", created, "sources", len(sources), flush=True)
elif command == "sa":
    floor = read_floor(root, PAV)
    assert floor and floor["coverage"]["processed"] >= 1, "pré-processamento incompleto"
    assert not changed_sources(root, floor["sources"]), "pré-processamento obsoleto"
    active = conn.execute("SELECT j.id,m.meta_json FROM portal_jobs j LEFT JOIN portal_job_meta m "
                          "ON m.job_id=j.id WHERE j.obra_id=? AND j.status IN ('na_fila','executando')",
                          (OBRA_ID,)).fetchall()
    assert not active, f"job ativo: {[row['id'] for row in active]}"
    from portal.app import pipeline_runner
    engine = pipeline_runner.engine_version(settings.repo_root)
    job_id = repo.enfileirar_job(conn, obra_id=OBRA_ID, engine_version=engine)
    repo.salvar_job_meta(conn, job_id, {"etapa": "sa", "secao": None, "pav": PAV})
    repo.atualizar_estado_obra(conn, OBRA_ID, "processando")
    print("sa_job", job_id, "engine", engine, flush=True)
elif command == "backup":
    import sqlite3
    target = Path("/opt/cad-analyzer/.deploy/preprocess-20260923") / (
        sys.argv[2] if len(sys.argv) > 2 else "prod14-before-sa"
    )
    target.mkdir(parents=True, exist_ok=True)
    for source in (Path("/opt/cad-analyzer/portal_data.db"),
                   Path("/opt/cad-analyzer/project_data.vision")):
        with sqlite3.connect(source) as input_db, sqlite3.connect(target / source.name) as output_db:
            input_db.backup(output_db)
        print("backup", source.name, (target / source.name).stat().st_size, flush=True)
else:
    raise SystemExit("usage: status|preprocess|sa|backup")
