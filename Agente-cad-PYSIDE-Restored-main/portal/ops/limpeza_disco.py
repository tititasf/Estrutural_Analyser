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
  (R5/R6 só apagam depois de capturar a rodada em historico_rodadas.sqlite; falhou = mantém)
  R7 scripts/arete/relatorios/<dir>   (exceto qa_portal) > 1 dia: apaga só *.dxf e arquivos > 20 MB
                                      que não sejam .md (o texto/evidência fica)
  R8 /tmp/sa-dev-validation/*/project_snapshot.sqlite3  > 6 h e nenhum dev_sa_cycle rodando
                                      (cópia descartável do banco; o resto do ciclo fica)
  R9 scripts/arete/html_fichas/<obra>/<PAV>_<ts>_*  3 mais novas por obra/PAV/escopo + < 1 dia
                                      + referenciadas no DB; .staging/<obra>/* > 1 dia
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import historico_rodadas  # noqa: E402

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


class _SemEstado:
    """Encaminha ao plano tudo exceto R5 (usado quando o histórico falhou)."""
    def __init__(self, plan):
        self.plan = plan

    def add(self, rule, p):
        if rule != "R5_estado_pid":
            self.plan.add(rule, p)


class Plan:
    def __init__(self):
        self.items: list[tuple[str, Path, int]] = []

    def add(self, rule: str, p: Path):
        self.items.append((rule, p, size_of(p)))

    def run(self, apply: bool, log):
        tot = defaultdict(int)
        for rule, p, sz in self.items:
            if apply and rule == 'R1_historical' and p in historical_pinned_versions([p]):
                log(f"KEEP R1_historical referenced asset {p}")
                continue
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


def historical_pinned_versions(versions):
    """Relocated packs are live assets while a portal link or DB refers to them."""
    pinned = set()
    physical = {p: p.resolve(strict=True) for p in versions}
    html_root = ROOT / 'scripts/arete/html_fichas'
    if html_root.exists():
        def onerror(error):
            raise error
        for directory, dirs, files in os.walk(html_root.resolve(strict=True), onerror=onerror):
            for name in dirs + files:
                link = Path(directory) / name
                if not link.is_symlink():
                    continue
                target = link.resolve()
                for version, base in physical.items():
                    if target == base or target.is_relative_to(base):
                        pinned.add(version)
    names_by_version = {
        version: {version.name} | {p.name for p in version.glob('*/*') if p.is_dir()}
        for version in versions
    }
    refs = db_referenced_names(set().union(*names_by_version.values())) if versions else set()
    pinned.update(v for v, names in names_by_version.items() if names & refs)
    return pinned


def r1_historical(plan: Plan):
    vs = [p for p in ROOT.glob("historical_ficha_storage_v*") if p.is_dir()]
    # Any inspection error aborts cleanup rather than deleting an unknown asset.
    pinned = historical_pinned_versions(vs)
    num = lambda p: int(re.sub(r"\D", "", p.name.rsplit("_v", 1)[-1]) or 0)  # noqa: E731
    for p in keep_newest(vs, 1, 1, key=num):
        if p not in pinned:
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


def r4_r5_obras(plan: Plan, kept_pids: set[str], falhas: set[str]):
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
                rid = f"{obra.name}/{ESTADO_RE.match(p.name)['pav']}/estado:{p.stem}"
                pid = ESTADO_RE.match(p.name)["pid"]
                pids_falhos = {f.rsplit("_", 1)[-1] for f in falhas}
                if pid not in kept_pids and pid not in pids_falhos and rid not in falhas:
                    plan.add("R5_estado_pid", p)


def r6_production_sa(plan: Plan, kept_pids: set[str], falhas: set[str]):
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
            rid = f"{p.parents[3].name}/{p.parent.name}/{p.name}"
            if p.name not in refs and rid not in falhas:
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


def _processo_rodando(trecho: str) -> bool:
    for c in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            if trecho in c.read_bytes().decode(errors="ignore"):
                return True
        except OSError:
            continue
    return False


def r8_snapshots_dev(plan: Plan):
    # dev_sa_cycle.py copia o banco inteiro (~1,4 GB) para cada ciclo e não apaga
    # no fim: 20 ciclos lotaram o disco em 11/10.  O resto do ciclo (relatório,
    # contexto, pre) fica; só a cópia do banco sai, e nunca com ciclo rodando.
    if _processo_rodando("dev_sa_cycle"):
        return
    for f in (TMP / "sa-dev-validation").glob("*/project_snapshot.sqlite3"):
        if NOW - f.stat().st_mtime > 6 * 3600:
            plan.add("R8_snapshot_dev", f)


def r9_html_fichas(plan: Plan):
    # Cada rodada de pilares ABCD gera ~2,5 GB de SVG (volume extra lotou em 10/10).
    # Por obra: 3 mais novas por (PAV, escopo) + < 1 dia + referenciadas no DB.
    # Rodada que é symlink para historical_* perde só o link.
    # .staging/<obra>/<run> = export interrompido; sai com > 1 dia.
    base = ROOT / "scripts" / "arete" / "html_fichas"
    if not base.is_dir():
        return
    groups = defaultdict(list)
    for obra in base.iterdir():
        if not obra.is_dir() or obra.name == ".staging":
            continue
        for p in obra.iterdir():
            m = RUN_RE.match(p.name)
            if m and (p.is_dir() or p.is_symlink()):
                groups[(obra.name, m["pav"], p.name[m.end("ts"):].strip("_"))].append(p)
    candidatos = [p for runs in groups.values() for p in keep_newest(runs, 3, 1)]
    refs = db_referenced_names({p.name for p in candidatos})
    for p in candidatos:
        if p.name not in refs:
            plan.add("R9_html_fichas", p)
    for p in (base / ".staging").glob("*/*"):
        if NOW - newest_mtime(p) > 1 * DAY:
            plan.add("R9_html_staging", p)


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

    # Registro histórico ANTES de apagar; rodada cuja captura falhou não é apagada.
    try:
        falhas = historico_rodadas.capturar_tudo(log=log)
    except Exception as e:  # noqa: BLE001
        log(f"HIST indisponível ({e}); rodadas e estados não serão apagados nesta execução")
        falhas = None
    plan = Plan()
    kept: set[str] = set()
    r1_historical(plan)
    r2_tmp(plan)
    r3_backups(plan)
    if falhas is None:
        r6_production_sa(Plan(), kept, set())   # só para saber quais pids manter
        r4_r5_obras(_SemEstado(plan), kept, set())
    else:
        r6_production_sa(plan, kept, falhas)
        r4_r5_obras(plan, kept, falhas)
    r7_relatorios(plan)
    r8_snapshots_dev(plan)
    r9_html_fichas(plan)
    plan.run(a.apply, log)
    st = shutil.disk_usage("/")
    log(f"DISCO: {st.used/1e9:.1f}/{st.total/1e9:.1f} GB ({st.used*100//st.total}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
