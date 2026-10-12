"""Conservative retention of published HTML packs; dry run unless --apply.

Only scripts/arete/html_fichas is eligible. Original obra data, QA records,
approved assets and databases are never deletion targets.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import ExitStack, closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import time

RUN = re.compile(r"^(.+?)_(20\d{6}_\d{6})(.*)$")
TERMINAL = {"concluido", "falhou", "cancelado"}
METADATA = {"index.html", "README.txt", "arete_manifest.json", "estado_pilares_abcd.json"}
LOCKS = ("html_pack_retention", "headless_sa", "headless_sa_global",
         "headless_sa_pil", "headless_sa_laj", "headless_sa_fv", "headless_sa_lv")


def inventory(pack: Path) -> dict:
    files = {}
    newest = pack.stat().st_mtime
    unsafe = False
    for folder, dirs, names in os.walk(pack, followlinks=False):
        base = Path(folder)
        for name in dirs + names:
            p = base / name
            if p.is_symlink():
                unsafe = True
                continue
            st = p.stat()
            newest = max(newest, st.st_mtime)
            if p.is_file():
                files[p.relative_to(pack).as_posix()] = (st.st_size, st.st_mtime_ns)
    return {"path": pack, "files": files, "newest": newest, "mtime": pack.stat().st_mtime,
            "bytes": sum(v[0] for v in files.values()), "unsafe": unsafe}


def published_plan(packs: list[dict], keep: int, cutoff: float) -> list[dict]:
    """Keep N versions of every relative asset, with both reader sort orders.

    A partial run never covers the other items. Unique files pin their pack.
    A pack is removed only if every asset has N newer retained providers.
    """
    groups = defaultdict(list)
    for pack in packs:
        match = RUN.match(pack["path"].name)
        if match:
            # PID/microsecond suffixes are not used to merge unknown pack kinds.
            groups[(pack["path"].parent, match[1], match[3])].append(pack)
    result = []
    for group in groups.values():
        protected = set()
        for ordering in (lambda p: p["path"].name, lambda p: p["mtime"], lambda p: p["newest"]):
            versions = defaultdict(list)
            for pack in sorted(group, key=ordering, reverse=True):
                keys = [k for k in pack["files"] if k not in METADATA]
                # Empty/incomplete packs cannot supersede a published version.
                if not any(k.endswith(".html") and k != "index.html" for k in keys):
                    protected.add(pack["path"])
                    continue
                # Also retain all ties at the boundary: filesystem iteration
                # order is not an identity guarantee for equal directory mtimes.
                if any(len(versions[k]) < keep or ordering(pack) == versions[k][keep - 1] for k in keys):
                    protected.add(pack["path"])
                for key in keys:
                    versions[key].append(ordering(pack))
        for pack in group:
            if pack["path"] not in protected and not pack["unsafe"] and pack["newest"] < cutoff:
                result.append(dict(pack, reason="superseded_per_asset"))
    return result


def connect(db: Path):
    return sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)


def busy(conn) -> bool:
    return any(row[0] not in TERMINAL for row in conn.execute("SELECT DISTINCT status FROM portal_jobs"))


def referenced(conn, packs: list[dict], obras: list[Path]) -> set[Path]:
    """Pin live catalogue/QA references; terminal job logs remain audit history."""
    pinned = set()

    def visit(text):
        if not isinstance(text, str):
            return
        for pack in packs:
            if pack["path"].name in text:
                pinned.add(pack["path"])

    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for table in tables:
        if table in {"portal_membros", "portal_jobs", "portal_job_meta"}:
            continue
        quote = '"' + table.replace('"', '""') + '"'
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({quote})")
                if any(t in r[2].upper() for t in ("TEXT", "CHAR"))]
        if not cols:
            continue
        names = ','.join('"' + c.replace('"', '""') + '"' for c in cols)
        for row in conn.execute(f"SELECT {names} FROM {quote}"):
            for value in row:
                visit(value)
    # Canonical state and durable user/QA overrides are outside generated packs.
    for obra in obras:
        paths = list(obra.glob("*.json"))
        for name in (".portal_overrides", "arete_approved"):
            paths.extend((obra / name).rglob("*.json"))
        for p in paths:
            if p.is_symlink():
                continue
            with p.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    visit(line)
    return pinned


def open_paths() -> list[str]:
    paths = []
    proc = Path("/proc")
    if not proc.is_dir():
        raise RuntimeError("Apply is supported only on Linux with /proc available")
    for process in proc.iterdir():
        if not process.name.isdigit():
            continue
        refs = [process / "cwd"]
        try:
            refs.extend((process / "fd").iterdir())
        except FileNotFoundError:
            continue
        for ref in refs:
            try:
                paths.append(os.readlink(ref))
            except FileNotFoundError:
                continue
    return paths


def plan(root: Path, keep: int, min_hours: float, discarded_days: float):
    published = []
    discarded = []
    now = time.time()
    for obra in root.iterdir():
        if not obra.is_dir() or obra.is_symlink():
            continue
        if obra.name in {".staging", ".parity_failed"}:
            for pack in obra.glob("*/*"):
                if pack.is_dir() and not pack.is_symlink() and RUN.match(pack.name):
                    row = inventory(pack)
                    if not row["unsafe"] and row["newest"] < now - discarded_days * 86400:
                        discarded.append(dict(row, reason="expired_" + obra.name))
        elif not obra.name.startswith("."):
            for pack in obra.iterdir():
                if pack.is_dir() and not pack.is_symlink() and RUN.match(pack.name):
                    published.append(inventory(pack))
    return published_plan(published, keep, now - min_hours * 3600) + discarded


def resolve_html_root(repo: Path, configured: Path | None = None) -> Path:
    """Allow a relocated root only when its physical path is explicitly pinned."""
    logical = repo / "scripts/arete/html_fichas"
    if configured is None:
        if logical.is_symlink() or logical.resolve() != logical:
            raise RuntimeError("Relocated HTML root requires --html-root with its physical path")
        return logical
    configured = Path(configured)
    if not configured.is_absolute() or configured.resolve(strict=True) != configured:
        raise RuntimeError("Configured HTML root must be an absolute physical directory")
    if not configured.is_dir() or logical.resolve(strict=True) != configured:
        raise RuntimeError("Configured HTML root does not match the portal HTML directory")
    return configured


def run(args) -> dict:
    repo = args.repo_root.resolve()
    configured = getattr(args, 'html_root', None)
    root = resolve_html_root(repo, configured)
    if not root.is_dir():
        return {"status": "no_html_root", "deleted": []}
    sys.path.insert(0, str(repo))
    from scripts.arete.single_instance import acquire_lock, release_lock
    with ExitStack() as stack:
        if args.apply:
            for name in LOCKS:
                handle, _ = acquire_lock(name)
                if handle is None:
                    return {"status": "deferred_busy_lock", "lock": name, "deleted": []}
                stack.callback(release_lock, handle)
        conn = stack.enter_context(closing(connect(args.db or repo / "portal_data.db")))
        active = busy(conn)
        if args.apply and active:
            return {"status": "deferred_active_jobs", "deleted": []}
        candidates = plan(root, args.keep, args.min_hours, args.discarded_days)
        obras = [Path(r[0]) for r in conn.execute("SELECT local_path FROM portal_obras WHERE local_path IS NOT NULL")]
        pinned = referenced(conn, candidates, obras)
        candidates = [p for p in candidates if p["path"] not in pinned]
        result = {"status": "applied" if args.apply else "dry_run", "active_jobs": active,
                  "pinned": len(pinned), "candidate_bytes": sum(p["bytes"] for p in candidates),
                  "candidates": [{"path": str(p["path"]), "bytes": p["bytes"], "reason": p["reason"]}
                                 for p in candidates], "deleted": []}
        if args.apply:
            report_dir = repo / "runtime/html_pack_retention"
            report_dir.mkdir(parents=True, exist_ok=True)
            report = report_dir / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + ".json")
            report.write_text(json.dumps(result, indent=2), encoding="utf-8")
            before = shutil.disk_usage(root).free
            for pack in candidates:
                if busy(conn):
                    result["status"] = "paused_new_job"
                    break
                p = pack["path"]
                # Revalidate tree, age and references before each whole-pack deletion.
                if resolve_html_root(repo, configured) != root:
                    raise RuntimeError("HTML root changed during retention")
                if p.is_symlink() or p.resolve() != p or root not in p.parents:
                    raise RuntimeError("Unsafe deletion target: " + str(p))
                fresh = inventory(p)
                if fresh != {k: v for k, v in pack.items() if k != "reason"}:
                    continue
                if referenced(conn, [pack], obras):
                    continue
                if any(ref == str(p) or ref.startswith(str(p) + "/") for ref in open_paths()):
                    continue
                shutil.rmtree(p)
                result["deleted"].append(str(p))
                report.write_text(json.dumps(result, indent=2), encoding="utf-8")
            result["freed_bytes"] = shutil.disk_usage(root).free - before
            result["report"] = str(report)
            report.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--html-root", type=Path,
                        help="Explicit physical target of the portal HTML root when relocated")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--keep", type=int, default=2)
    parser.add_argument("--min-hours", type=float, default=24)
    parser.add_argument("--discarded-days", type=float, default=7)
    args = parser.parse_args()
    if args.keep < 2 or args.min_hours < 24 or args.discarded_days < 7:
        parser.error("minimum retention: 2 versions, 24 hours published, 7 days discarded")
    print(json.dumps(run(args), indent=2))


if __name__ == "__main__":
    main()
