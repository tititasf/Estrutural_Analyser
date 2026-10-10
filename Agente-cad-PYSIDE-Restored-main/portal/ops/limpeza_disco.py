#!/usr/bin/env python3
"""Autolimpeza segura do disco da VPS (cad-analyzer).

Política (2026-10-10, pedido do dono): manter sempre o mais recente de cada
coisa que se acumula por reprocessamento/auditoria, apagar o resíduo antigo.
Nada referenciado pelo portal_data.db é apagado.  Padrão = simulação (dry-run);
apagar de fato exige --apply.

Regras:
  R1 historical_ficha_storage_v*      mantém a versão mais nova
  R2 /tmp (topo)                      apaga o que não muda há > 2 dias (lista de exceções)
  R3 backups de deploy                mantém as 5 entradas mais novas por pasta + < 3 dias (código está no git)
  R4 DADOS-OBRAS/<obra>/<PAV>_<ts>_*  histórico de HTML de ficha: 3 mais novas por PAV/escopo + < 3 dias
  R5 DADOS-OBRAS/<obra>/estado_<PAV>_*pid<N>.json  mantém pids de rodadas mantidas + 5 mais novos + < 3 dias
  R6 production_sa/<PAV>/<run>        3 mais novas por PAV + < 1 dia + referenciadas no DB
  R7 scripts/arete/relatorios/<dir>   (exceto qa_portal) > 1 dia: apaga só *.dxf e arquivos > 20 MB
                                      que não sejam .md (o texto/evidência fica)
Nunca toca: estado_<PAV>.json canônico, recortes, preprocessamento, .db/.sqlite/.vision fora de backups.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(os.environ.get("CAD_ROOT", "/opt/cad-analyzer"))
TMP = Path("/tmp")
DAY = 86400
NOW = time.time()

TMP_KEEP = re.compile(
    r"^(sa-dev-validation|systemd-private-.*|snap-private-tmp|tmux-.*|\.X.*|\.ICE.*|"
    r"\.font-unix|\.Test-unix|\.XIM-unix|cad-viewer-prewarm|limpeza_.*)$"
)
BACKUP_DIRS = ["backups", "deploy_backups", "_deploy_backups",
               "portal_runtime/deploy_backups", ".deploy"]
RUN_RE = re.compile(r"^(?P<pav>.+?)_(?P<ts>20\d{6}_\d{6})")
ESTADO_RE = re.compile(r"^estado_(?P<pav>.+?)_(?:(?P<scope>[a-z_]+)_)?pid(?P<pid>\d+)\.json$")


def newest_mtime(p: Path) -> float:
    try:
        m = p.lstat().st_mtime
    except OSError:
        return NOW
    if p.is_dir() and not p.is_symlink():
        for dp, dns, fns in os.walk(p):
            for n in fns + dns:
                try:
                    m = max(m, os.lstat(os.path.join(dp, n)).st_mtime)
                except OSError:
                    pass
    return m


def size_of(p: Path) -> int:
    if p.is_file() or p.is_symlink():
        try:
            return p.lstat().st_size
        except OSError:
            return 0
    t = 0
    for dp, _, fns in os.walk(p):
        for n in fns:
            try:
                t += os.lstat(os.path.join(dp, n)).st_size
            except OSError:
                pass
    return t


def db_referenced_names(names: set[str]) -> set[str]:
    """Nomes (basename) que aparecem em qualquer coluna texto do portal_data.db."""
    hit: set[str] = set()
    db = ROOT / "portal_data.db"
    if not db.exists() or not names:
        return hit
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    pat = re.compile("|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)))
    for (t,) in c.execute("select name from sqlite_master where type='table'"):
        cols = [r[1] for r in c.execute(f'pragma table_info("{t}")')]
        for col in cols:
            try:
                for (v,) in c.execute(f'select "{col}" from "{t}" where "{col}" is not null'):
                    if isinstance(v, str):
                        hit.update(pat.findall(v))
            except sqlite3.Error:
                pass
    c.close()
    return hit


class Plan:
    def __init__(self):
        self.items: list[tuple[str, Path, int]] = []

    def add(self, rule: str, p: Path):
        self.items.append((rule, p, size_of(p)))

    def run(self, apply: bool, log):
        tot = defaultdict(int)
        for rule, p, sz in self.items:
            tot[rule] += sz
            log(f"{'DEL' if apply else 'SIM'} {rule} {sz/1e6:9.1f}MB {p}")
            if apply:
                try:
                    if p.is_dir() and not p.is_symlink():
                        shutil.rmtree(p)
                    else:
                        p.unlink()
                except OSError as e:
                    log(f"ERRO {p}: {e}")
        for r in sorted(tot):
            log(f"TOTAL {r}: {tot[r]/1e9:.2f} GB")
        log(f"TOTAL GERAL: {sum(tot.values())/1e9:.2f} GB ({'apagado' if apply else 'simulação'})")


def keep_newest(entries, n, min_age_days, key=lambda p: p.name):
    """Devolve a lista a apagar: tudo além dos n mais novos e mais velho que min_age."""
    ordered = sorted(entries, key=key, reverse=True)
    return [p for p in ordered[n:] if NOW - newest_mtime(p) > min_age_days * DAY]


def r1_historical(plan: Plan):
    vs = [p for p in ROOT.glob("historical_ficha_storage_v*") if p.is_dir()]
    num = lambda p: int(re.sub(r"\D", "", p.name.rsplit("_v", 1)[-1]) or 0)  # noqa: E731
    for p in keep_newest(vs, 1, 1, key=num):
        plan.add("R1_historical", p)


def r2_tmp(plan: Plan):
    for p in TMP.iterdir():
        if TMP_KEEP.match(p.name):
            continue
        if NOW - newest_mtime(p) > 2 * DAY:
            plan.add("R2_tmp", p)


def r3_backups(plan: Plan):
    for d in BACKUP_DIRS:
        base = ROOT / d
        if base.is_dir():
            for p in keep_newest(list(base.iterdir()), 5, 3, key=lambda p: p.lstat().st_mtime):
                plan.add("R3_backups", p)


def r4_r5_obras(plan: Plan, kept_pids: set[str]):
    for obra in (ROOT / "DADOS-OBRAS").iterdir():
        if not obra.is_dir():
            continue
        groups = defaultdict(list)
        for p in obra.iterdir():
            m = RUN_RE.match(p.name) if p.is_dir() else None
            if m:
                # resto após o timestamp: [_microseg][_escopo][_pid] → só o escopo agrupa
                rest = re.sub(r"^_\d{6}(?=_|$)", "", p.name[m.end("ts"):])
                scope = re.sub(r"_\d+$", "", rest).strip("_")
                groups[(m["pav"], scope)].append(p)
        for (_pav, _scope), runs in groups.items():
            ordered = sorted(runs, key=lambda p: p.name, reverse=True)
            for p in ordered[:3]:
                pid = p.name.rsplit("_", 1)[-1]
                if pid.isdigit():
                    kept_pids.add(pid)
            for p in keep_newest(runs, 3, 3):
                plan.add("R4_html_runs", p)
        est = defaultdict(list)
        for p in obra.glob("estado_*_pid*.json"):
            m = ESTADO_RE.match(p.name)
            if m:
                est[(m["pav"], m["scope"])].append(p)
        for _k, files in est.items():
            for p in keep_newest(files, 5, 3, key=lambda p: p.stat().st_mtime):
                if ESTADO_RE.match(p.name)["pid"] not in kept_pids:
                    plan.add("R5_estado_pid", p)


def r6_production_sa(plan: Plan, kept_pids: set[str]):
    runs_by_pav = defaultdict(list)
    for p in (ROOT / "DADOS-OBRAS").glob("*/Fase-6_Execucao_CAD/production_sa/*/*"):
        if p.is_dir():
            runs_by_pav[p.parent].append(p)
    all_names = {p.name for rs in runs_by_pav.values() for p in rs}
    refs = db_referenced_names(all_names)
    for _pav, runs in runs_by_pav.items():
        for p in sorted(runs, key=lambda p: p.name, reverse=True)[:3]:
            kept_pids.add(p.name.rsplit("_", 1)[-1])
        for p in keep_newest(runs, 3, 1):
            if p.name not in refs:
                plan.add("R6_production_sa", p)


def r7_relatorios(plan: Plan):
    base = ROOT / "scripts" / "arete" / "relatorios"
    if not base.is_dir():
        return
    for d in base.iterdir():
        if not d.is_dir() or d.name in ("qa_portal",) or NOW - newest_mtime(d) < 1 * DAY:
            continue
        for dp, _, fns in os.walk(d):
            for n in fns:
                f = Path(dp) / n
                try:
                    big = f.lstat().st_size > 20e6
                except OSError:
                    continue
                if n.lower().endswith(".dxf") or (big and not n.lower().endswith(".md")):
                    plan.add("R7_relatorios", f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="apaga de fato (padrão: simulação)")
    ap.add_argument("--log", default="/var/log/cad-limpeza.log")
    a = ap.parse_args()
    out = open(a.log, "a", encoding="utf-8") if a.apply else None

    def log(s):
        line = time.strftime("%F %T ") + s
        print(line)
        if out:
            out.write(line + "\n")

    plan = Plan()
    kept: set[str] = set()
    r1_historical(plan)
    r2_tmp(plan)
    r3_backups(plan)
    r6_production_sa(plan, kept)
    r4_r5_obras(plan, kept)
    r7_relatorios(plan)
    plan.run(a.apply, log)
    st = shutil.disk_usage("/")
    log(f"DISCO: {st.used/1e9:.1f}/{st.total/1e9:.1f} GB ({st.used*100//st.total}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
