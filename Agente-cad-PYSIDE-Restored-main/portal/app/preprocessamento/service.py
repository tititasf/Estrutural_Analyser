"""Lote isolado: pacotes imutáveis e índice SQLite transacional próprio.

Coleta SA isolada ou leitura de evidência da mesma fonte. O índice publica todas
as referências do pavimento, preservando as referências dos outros andares.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .adapters.cuts import inventory_cuts
from .adapters.level_crossing import survey_levels
from .crosscheck import check_facts
from .freshness import changed_sources
from .runner import RunnerError, _write_atomic, build_inventory_result, resolve_declared_sources
from .sources import SourceKind, raw_level_references
from .store import _safe_dir

ENGINE_VERSION = "preprocess-context-v4-levels"


def _tower_dependencies(sources, tower):
    """Liga convenções da mesma planta ou uma convenção única do pavimento.

    Convenções de outro bruto só são compartilhadas quando há exatamente uma
    candidata validada dessa classe. Com duas alternativas, o pacote fica sem
    decisão, preservando o isolamento entre torres e revisões.
    """
    result = [tower]
    bindings = {}
    for kind in (SourceKind.PILLAR_CONVENTION, SourceKind.LEVEL_CONVENTION):
        candidates = [source for source in sources if source.kind is kind]
        local = [source for source in candidates if source.bruto_id == tower.bruto_id]
        selected = local if len(local) == 1 else candidates if not local and len(candidates) == 1 else []
        result.extend(selected)
        bindings[kind.value] = {
            "status": "bound" if selected else "ambiguous" if candidates else "missing",
            "scope": "tower" if local and selected else "floor_unique" if selected else None,
            "selected_source_ids": [source.source_id for source in selected],
            "candidate_source_ids": [source.source_id for source in candidates],
        }
    return result, bindings


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def index_connection(obra_dir):
    root = Path(obra_dir) / "preprocessamento" / "v1"
    root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(root / "index.sqlite3", timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS floors (floor TEXT PRIMARY KEY, run_id TEXT, path TEXT, hash TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS history (run_id TEXT PRIMARY KEY, floor TEXT, path TEXT, hash TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS work_revisions (revision INTEGER PRIMARY KEY, payload TEXT)")
    conn.commit()
    return conn


def read_floor(obra_dir, floor):
    path = Path(obra_dir) / "preprocessamento/v1/index.sqlite3"
    if not path.is_file():
        return None
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as conn:
        row = conn.execute("SELECT path, hash FROM floors WHERE floor=?", (floor,)).fetchone()
    if row is None:
        return None
    target = (Path(obra_dir) / row[0]).resolve()
    if (Path(obra_dir) / "preprocessamento/v1").resolve() not in target.parents:
        raise RunnerError("índice fora do armazenamento próprio")
    result = json.loads(target.read_text(encoding="utf-8"))
    if digest(result) != row[1]:
        raise RunnerError("consolidado corrompido")
    return result


def run_floor(*, obra_dir, obra_id, pavimento, declarations, frozen_sources=None,
              run_id=None, output_root=None, progress=None, known_floors=()):
    obra_dir = Path(obra_dir).resolve()
    floor = _safe_dir("pavimento", pavimento)
    run_id = _safe_dir("run_id", run_id or uuid.uuid4().hex)
    declarations = list(declarations)
    sources = resolve_declared_sources(obra_dir=obra_dir, obra_id=obra_id,
                                      pavimento_id=floor, declarations=declarations)
    frozen = {s.source_id: s.revision for s in sources}
    raw_references = raw_level_references(obra_dir, sources)
    frozen.update({s["source_id"]: s["revision"] for s in raw_references})
    if frozen_sources is not None and frozen != frozen_sources:
        raise RunnerError("recortes alterados desde o enfileiramento")
    if any(not s.validated and s.kind is not SourceKind.LEVEL_CONVENTION for s in sources):
        raise RunnerError("recortes pendentes de validação")
    towers = [s for s in sources if s.kind is SourceKind.TOWER]
    if not towers:
        raise RunnerError("nenhuma torre elegível")
    serialized = [{**asdict(s), "kind": s.kind.value} for s in sources] + list(raw_references)
    root = Path(output_root).resolve() if output_root else obra_dir / "preprocessamento/v1"
    directory = root / floor / "runs" / run_id
    if directory.exists():
        raise RunnerError("run_id já publicado; use nova revisão")
    packages = {}
    for number, tower in enumerate(towers):
        if progress:
            progress({"completed": number, "total": len(towers), "stage": tower.item_id})
        dependencies, bindings = _tower_dependencies(sources, tower)
        raw_reference = next((s for s in raw_references if s["bruto_id"] == tower.bruto_id), None)
        level_crop = next((s for s in dependencies if s.kind is SourceKind.LEVEL_CONVENTION), None)
        level_reference = raw_reference or ({**asdict(level_crop), "kind": level_crop.kind.value}
                                             if level_crop else None)
        scope = {"obra_id": obra_id, "pavimento_id": floor, "recorte_id": tower.source_id,
                 "source_revision": tower.revision}
        package = {"schema_version": 1, "engine_version": ENGINE_VERSION, "run_id": run_id,
                   "scope": scope, "sources": [s for s in serialized if s["source_id"] in
                                                ({d.source_id for d in dependencies} |
                                                 ({raw_reference["source_id"]} if raw_reference else set()))],
                   "status": "partial", "review": "unreviewed", "convention_bindings": bindings}
        try:
            inventory = build_inventory_result(
                obra_dir=obra_dir, obra_id=obra_id, pavimento_id=floor,
                declarations=[{"bruto_id": s.bruto_id, "item_id": s.item_id} for s in dependencies])
            pillar = inventory["pillars"][tower.source_id]
            labels = inventory["structural_labels"][tower.source_id]
            levels, level_inventory = survey_levels(
                obra_dir / tower.relative_path, source_id=tower.source_id,
                floor=floor, pillars=pillar["items"], labels=labels["items"],
                raw_reference=level_reference, obra_dir=obra_dir,
            )
            cuts = inventory_cuts(obra_dir / tower.relative_path, source_id=tower.source_id)
            conflicts = check_facts(levels)
            conflicts.extend({"kind": "ambiguous_convention_binding", "source_kind": kind,
                              "candidate_source_ids": binding["candidate_source_ids"]}
                             for kind, binding in bindings.items() if binding["status"] == "ambiguous")
            package.update(pillars=pillar, structural_labels=labels,
                           pillar_conventions=inventory["pillar_conventions"],
                           level_conventions=inventory["level_conventions"], cuts=cuts,
                           levels=levels, level_inventory=level_inventory,
                           conflicts=conflicts, modules=inventory["modules"])
            package["modules"].update(cuts=cuts["status"], levels="partial", details="not_supported")
            from .sa_levels import enrich_package
            enrich_package(obra_dir, floor, package, progress)
            package['conflicts'] = check_facts(package['levels']) + [
                c for c in conflicts if c.get('kind') == 'ambiguous_convention_binding']
            package["dependencies"] = {
                "inventory": [tower.source_id], "cuts": [tower.source_id],
                "pillars": [s.source_id for s in dependencies if s.kind is not SourceKind.LEVEL_CONVENTION],
                "levels": ([s.source_id for s in dependencies if s.kind is not SourceKind.PILLAR_CONVENTION]
                           + ([raw_reference["source_id"]] if raw_reference else [])),
            }
        except Exception as exc:
            package.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        packages[tower.source_id] = package
        if progress:
            progress({"completed": number + 1, "total": len(towers), "stage": "tower_finished"})
    if changed_sources(obra_dir, serialized):
        raise RunnerError("fonte alterada durante pré-processamento; lote não publicado")
    if progress:
        progress({"completed": len(towers), "total": len(towers), "stage": "before_publish"})
    references = {}
    for source_id, package in packages.items():
        name = hashlib.sha256(source_id.encode()).hexdigest() + ".json"
        _write_atomic(directory / "towers" / name, package)
        references[source_id] = {"path": f"towers/{name}", "hash": digest(package),
                                 "status": package["status"], "scope": package["scope"]}
    result = {"schema_version": 1, "engine_version": ENGINE_VERSION, "run_id": run_id,
              "obra_id": obra_id, "pavimento_id": floor, "sources": serialized,
              "created_at": datetime.now(timezone.utc).isoformat(),
              "status": "failed" if all(p["status"] == "failed" for p in packages.values()) else "partial",
              "towers": references, "details": {"status": "not_supported",
                    "source_ids": [s.source_id for s in sources if s.kind is SourceKind.DETAILS]},
              "coverage": {"total": len(towers), "processed": sum(p["status"] != "failed" for p in packages.values()),
                           "failed": sum(p["status"] == "failed" for p in packages.values())},
              "sa_consumption": "scoped_context_available"}
    _write_atomic(directory / "floor.json", result)
    if output_root is None:
        conn = index_connection(obra_dir)
        try:
            conn.execute("BEGIN IMMEDIATE")
            if changed_sources(obra_dir, serialized):
                raise RunnerError("fonte alterada antes do commit; histórico não promovido")
            if progress:
                progress({"completed": len(towers), "total": len(towers), "stage": "before_commit"})
            relative = (directory / "floor.json").relative_to(obra_dir).as_posix()
            conn.execute("INSERT INTO history VALUES (?,?,?,?)", (run_id, floor, relative, digest(result)))
            conn.execute("INSERT OR REPLACE INTO floors VALUES (?,?,?,?)", (floor, run_id, relative, digest(result)))
            floors = {r["floor"]: {"run_id": r["run_id"], "path": r["path"], "hash": r["hash"]}
                      for r in conn.execute("SELECT * FROM floors")}
            for pending in known_floors:
                floors.setdefault(pending, {"status": "pending"})
            conn.execute("INSERT INTO work_revisions(payload) VALUES (?)",
                         (json.dumps({"obra_id": obra_id, "floors": floors}, sort_keys=True),))
            conn.commit()
        finally:
            conn.close()
    return result


def read_tower(obra_dir, floor, source_id):
    ref = floor["towers"][source_id]
    # O caminho deriva da identidade, não aceita path arbitrário do manifesto.
    name = hashlib.sha256(source_id.encode()).hexdigest() + ".json"
    path = Path(obra_dir) / "preprocessamento/v1" / _safe_dir("pavimento", floor["pavimento_id"]) / "runs" / _safe_dir("run", floor["run_id"]) / "towers" / name
    package = json.loads(path.read_text(encoding="utf-8"))
    if digest(package) != ref["hash"] or package["scope"] != ref["scope"]:
        raise RunnerError("pacote da torre corrompido")
    return package
