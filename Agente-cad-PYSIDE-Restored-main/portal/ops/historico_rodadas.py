#!/usr/bin/env python3
"""Registro compacto de rodadas do SA (histórico item a item).

Antes de a autolimpeza (limpeza_disco.py) apagar uma rodada antiga, os campos
de cada item dessa rodada são gravados aqui: assim dá para ver como um item
evoluiu entre rodadas e detectar regressão, sem guardar GBs de saída bruta.

Não é RAG nem fonte de verdade: é série histórica de saídas do motor,
inclusive de versões já corrigidas.  Repetição entre rodadas não é evidência.

Banco: <CAD_ROOT>/historico_rodadas.sqlite
  rodadas(run_id, obra, pavimento, run_name, run_ts, pid, escopo, origem,
          source_dxf, source_revision, context_hash, n1_counts, visual_mode,
          code_rev_captura, captura_tardia, capturado_em)
  campos(fp, json)                       conteúdo deduplicado por hash
  itens(run_id, classe, item, fp)        rodada × item → conteúdo

  code_rev_captura = HEAD do checkout no momento da captura; fica NULL quando
  captura_tardia=1 (capturado > 1 dia após a rodada): versão do código desconhecida.

Uso:
  historico_rodadas.py capturar                       # idempotente
  historico_rodadas.py item --pav 13_PAV --item P18 [--obra Obra_TREINO_1] [--classe PIL] [--escopo '']
  historico_rodadas.py diff --de <run_id|run_name> --para <run_id|run_name>
  historico_rodadas.py rodadas --pav 13_PAV
"""
from __future__ import annotations

import argparse
import signal
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("CAD_ROOT", "/opt/cad-analyzer"))
DB = ROOT / "historico_rodadas.sqlite"
ESTADO_RE = re.compile(r"^estado_(?P<pav>.+?)_(?:(?P<scope>[a-z_]+)_)?pid(?P<pid>\d+)\.json$")

SCHEMA = """
create table if not exists rodadas(
  run_id text primary key, obra text, pavimento text, run_name text, run_ts text,
  pid text, escopo text, origem text, source_dxf text, source_revision text,
  context_hash text, n1_counts text, visual_mode text, code_rev_captura text,
  captura_tardia integer, capturado_em text);
create table if not exists campos(fp text primary key, json text not null);
create table if not exists itens(run_id text, classe text, item text, fp text,
  primary key(run_id, classe, item));
create index if not exists ix_itens_item on itens(item, classe);
create index if not exists ix_rodadas_pav on rodadas(obra, pavimento, run_ts);
"""


def conectar(ro: bool = False) -> sqlite3.Connection:
    if ro:
        return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c = sqlite3.connect(DB)
    c.executescript(SCHEMA)
    return c


# ---------------------------------------------------------------- extração
def _viga(v):
    return {"name": v.get("name"), "dim": v.get("dim"), "behavior": v.get("behavior"),
            "corner": v.get("corner")} if isinstance(v, dict) else v


def _pil(p: dict) -> dict:
    fb = {}
    for face, d in (p.get("face_beams") or {}).items():
        if isinstance(d, dict):
            fb[face] = {"passa_esq": _viga(d.get("passa_esq")), "passa_dir": _viga(d.get("passa_dir")),
                        "para": [_viga(x) for x in d.get("para") or []],
                        "interior": [_viga(x) for x in d.get("interior") or []]}
    lajes = [{"laje": l.get("laje"), "side": l.get("side"), "face": l.get("face"),
              "tipo": l.get("content_type"), "nivel": l.get("nivel"),
              "viga": _viga(l.get("viga")), "source": l.get("source")}
             for l in p.get("lajes") or [] if isinstance(l, dict)]
    out = {k: p.get(k) for k in ("classification", "orientation", "nivel_str",
                                 "lado_A", "lado_B", "lado_C", "lado_D", "atencao", "format")}
    out["bbox"] = [round(float(x), 1) for x in p.get("bbox") or []]
    out.update(lajes=lajes, face_beams=fb, interpretacao_abcd=p.get("interpretacao_abcd"))
    return out


def _seg(s: dict) -> dict:
    out = {k: s.get(k) for k in ("beam_name", "segment_label", "side", "behavior", "length",
                                 "width", "level", "level_source", "level_slabs",
                                 "level_distance_cm", "status", "atencao")}
    cell = s.get("lv_cell") or {}
    if cell:
        out["lv_cell"] = {k: cell.get(k) for k in ("rules", "dim", "depth")}
    return out


def extrair_itens(estado: dict):
    """Gera (classe, item, campos) a partir de um estado_<PAV>[_escopo]_pid*.json."""
    for p in estado.get("pilares") or []:
        yield "PIL", str(p.get("key") or p.get("name")), _pil(p)
    for s in estado.get("slabs") or []:
        yield "LAJ", str(s.get("name")), {k: s.get(k) for k in ("nivel", "height")}
    for c in estado.get("cortes") or []:
        yield "CORTE", str(c.get("uid")), {k: c.get(k) for k in (
            "beam_name", "conf_pct", "own_laje", "neigh_laje", "beam_h", "status", "atencao")}
    for grupo, segs in (estado.get("segmentos") or {}).items():
        classe = "FV" if grupo == "fundo" else "LV"
        for s in segs or []:
            yield classe, str(s.get("uid")), _seg(s)


def _fp(obj) -> tuple[str, str]:
    js = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha1(js.encode()).hexdigest(), js


def _git_head() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def _ts_de_nome(nome: str) -> str:
    m = re.search(r"(20\d{6})_(\d{6})", nome)
    return datetime.strptime(m[1] + m[2], "%Y%m%d%H%M%S").isoformat() if m else ""


def capturar_estado(c, *, run_id, obra, pav, run_name, origem, estado_path: Path,
                    manifest: dict | None, head: str) -> int:
    """Grava uma rodada. Devolve nº de itens; levanta exceção se não conseguiu."""
    if c.execute("select 1 from rodadas where run_id=?", (run_id,)).fetchone():
        return -1
    estado = json.loads(estado_path.read_text(encoding="utf-8")) if estado_path.is_file() else None
    if estado is None and manifest is None:
        raise FileNotFoundError(f"sem estado nem manifest: {run_id}")
    m = ESTADO_RE.match(estado_path.name) if estado_path else None
    run_ts = _ts_de_nome(run_name) or (estado or {}).get("gerado_em", "")
    try:
        tardia = int(time.time() - datetime.fromisoformat(run_ts[:19]).timestamp() > 86400)
    except ValueError:
        tardia = 1
    man = manifest or {}
    ctx = man.get("preprocess_context") or {}
    c.execute("insert into rodadas values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
        run_id, obra, pav, run_name, run_ts, run_name.rsplit("_", 1)[-1],
        (m["scope"] if m else None) or "", origem, man.get("source_dxf"),
        (ctx.get("scope") or {}).get("source_revision"), ctx.get("context_hash"),
        json.dumps(man.get("n1_counts")) if man.get("n1_counts") else None,
        man.get("visual_mode"), None if tardia else head, tardia, datetime.now().isoformat(timespec="seconds")))
    n = 0
    for classe, item, campos in extrair_itens(estado or {}):
        fp, js = _fp(campos)
        c.execute("insert or ignore into campos values(?,?)", (fp, js))
        c.execute("insert or replace into itens values(?,?,?,?)", (run_id, classe, item, fp))
        n += 1
    return n


def capturar_tudo(log=print) -> set[str]:
    """Captura todas as rodadas presentes. Devolve run_ids que FALHARAM (não apagar)."""
    falhas: set[str] = set()
    head = _git_head()
    c = conectar()
    novos = 0
    usados: set[Path] = set()
    for man_path in sorted((ROOT / "DADOS-OBRAS").glob("*/Fase-6_Execucao_CAD/production_sa/*/*/production_manifest.json")):
        run = man_path.parent
        obra = run.parents[3].name
        run_id = f"{obra}/{run.parent.name}/{run.name}"
        try:
            man = json.loads(man_path.read_text(encoding="utf-8"))
            est = Path(man.get("state_path") or "")
            est = est if est.is_file() else (run.parents[3] / est.name if est.name else Path())
            usados.add(est.resolve()) if est.name else None
            n = capturar_estado(c, run_id=run_id, obra=obra, pav=run.parent.name, run_name=run.name,
                                origem="production_sa", estado_path=est, manifest=man, head=head)
            if n >= 0:
                novos += 1
            c.commit()
        except Exception as e:  # noqa: BLE001
            c.rollback()
            falhas.add(run_id)
            log(f"HIST falha {run_id}: {e}")
    # estados órfãos (rodada já sem production_sa) — último registro que resta deles
    for est in sorted((ROOT / "DADOS-OBRAS").glob("*/estado_*_pid*.json")):
        m = ESTADO_RE.match(est.name)
        if not m or est.resolve() in usados:
            continue
        obra = est.parent.name
        run_id = f"{obra}/{m['pav']}/estado:{est.stem}"
        try:
            n = capturar_estado(c, run_id=run_id, obra=obra, pav=m["pav"],
                                run_name=time.strftime("%Y%m%d_%H%M%S", time.localtime(est.stat().st_mtime)) + "_" + m["pid"],
                                origem="estado_pid", estado_path=est, manifest=None, head=head)
            if n >= 0:
                novos += 1
            c.commit()
        except Exception as e:  # noqa: BLE001
            c.rollback()
            falhas.add(run_id)
            log(f"HIST falha {run_id}: {e}")
    tot = c.execute("select count(*) from rodadas").fetchone()[0]
    c.close()
    log(f"HIST capturadas {novos} rodadas novas (total {tot}); falhas {len(falhas)}; "
        f"banco {DB.stat().st_size/1e6:.1f} MB")
    return falhas


# ---------------------------------------------------------------- consulta
def _diff(a: dict, b: dict, pre="") -> list[str]:
    out = []
    for k in sorted(set(a) | set(b)):
        va, vb = a.get(k), b.get(k)
        if va == vb:
            continue
        if isinstance(va, dict) and isinstance(vb, dict):
            out += _diff(va, vb, f"{pre}{k}.")
        else:
            out.append(f"{pre}{k}: {json.dumps(va, ensure_ascii=False)} → {json.dumps(vb, ensure_ascii=False)}")
    return out


def cmd_item(a):
    c = conectar(ro=True)
    q = ("select r.run_ts, r.run_id, r.code_rev_captura, r.escopo, i.classe, i.fp, k.json "
         "from itens i join rodadas r using(run_id) join campos k on k.fp=i.fp "
         "where i.item=? and r.pavimento=?")
    args = [a.item, a.pav]
    if a.obra:
        q += " and r.obra=?"; args.append(a.obra)
    if a.classe:
        q += " and i.classe=?"; args.append(a.classe)
    if a.escopo is not None:
        q += " and r.escopo=?"; args.append(a.escopo)
    rows = c.execute(q + " order by i.classe, r.run_ts", args).fetchall()
    if not rows:
        print("nenhum registro"); return
    ant = {}
    for ts, rid, rev, esc, classe, fp, js in rows:
        prev = ant.get(classe)
        if prev and prev[0] == fp:
            prev[2] += 1
            continue
        if prev and prev[2]:
            print(f"   (sem mudança em mais {prev[2]} rodada(s))")
        print(f"[{classe}] {ts}  {rid}  escopo={esc or 'completo'}  código {rev or '?'}")
        if prev:
            for linha in _diff(json.loads(prev[1]), json.loads(js)):
                print("    " + linha)
        else:
            print("    (primeiro registro)")
        ant[classe] = [fp, js, 0]
    for classe, (_, _, n) in ant.items():
        if n:
            print(f"   [{classe}] sem mudança nas últimas {n} rodada(s)")


def _resolver(c, ref):
    r = c.execute("select run_id from rodadas where run_id=? or run_name=?", (ref, ref)).fetchall()
    if len(r) != 1:
        sys.exit(f"rodada '{ref}' ambígua ou inexistente ({len(r)})")
    return r[0][0]


def cmd_diff(a):
    c = conectar(ro=True)
    ra, rb = _resolver(c, a.de), _resolver(c, a.para)
    get = lambda r: {(cl, it): fp for cl, it, fp in c.execute(  # noqa: E731
        "select classe, item, fp from itens where run_id=?", (r,))}
    A, B = get(ra), get(rb)
    js = lambda fp: json.loads(c.execute("select json from campos where fp=?", (fp,)).fetchone()[0])  # noqa: E731
    so_a, so_b = sorted(set(A) - set(B)), sorted(set(B) - set(A))
    mud = sorted(k for k in set(A) & set(B) if A[k] != B[k])
    print(f"{ra} → {rb}: {len(mud)} mudaram, {len(so_b)} novos, {len(so_a)} sumiram, "
          f"{len(set(A) & set(B)) - len(mud)} iguais")
    for k in so_a:
        print(f"  - {k[0]} {k[1]}")
    for k in so_b:
        print(f"  + {k[0]} {k[1]}")
    for k in mud:
        print(f"  ~ {k[0]} {k[1]}")
        for linha in _diff(js(A[k]), js(B[k])):
            print("      " + linha)


def cmd_rodadas(a):
    c = conectar(ro=True)
    for row in c.execute("select run_ts, run_id, escopo, origem, code_rev_captura, captura_tardia, "
                         "(select count(*) from itens i where i.run_id=r.run_id) "
                         "from rodadas r where pavimento=? order by run_ts", (a.pav,)):
        ts, rid, esc, org, rev, tard, n = row
        print(f"{ts}  {rid}  escopo={esc or 'completo'}  {org}  código {rev or '?'}  itens={n}")


def main():
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("capturar")
    p = sp.add_parser("item"); p.add_argument("--pav", required=True); p.add_argument("--item", required=True)
    p.add_argument("--obra"); p.add_argument("--classe")
    p.add_argument("--escopo", help="'' = rodada completa; ex. pilares, lajes, laterais_viga")
    p = sp.add_parser("diff"); p.add_argument("--de", required=True); p.add_argument("--para", required=True)
    p = sp.add_parser("rodadas"); p.add_argument("--pav", required=True)
    a = ap.parse_args()
    if a.cmd == "capturar":
        capturar_tudo()
    else:
        {"item": cmd_item, "diff": cmd_diff, "rodadas": cmd_rodadas}[a.cmd](a)


if __name__ == "__main__":
    main()
