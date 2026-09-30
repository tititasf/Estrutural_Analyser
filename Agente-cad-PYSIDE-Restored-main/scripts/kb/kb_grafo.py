#!/usr/bin/env python3
"""Grafo da base global — o que a aba "Base Global" do portal desenha.

Junta num só JSON, versionado junto do código (vai para a VPS no deploy):

- fontes do inventário (`_inventario.json`, gerado por kb_inventario.py) com status;
- referências entre elas (link markdown e caminho entre crases que existe no disco);
- decisões do dono (DECISOES-DO-DONO.md), com fonte e revogação;
- termos do glossário (GLOSSARIO.md), com fonte;
- módulos de código citados pelas fontes (papel e docstring vêm do MAPA-CODIGO.md);
- regras da semantic_rag_kb (todas as tiers; leitura somente no DB real);
- hubs das 4 classes (PIL, LV, FV, LAJ).

E calcula as **lacunas** — o que falta ou está solto: fonte viva sem ligação,
referência quebrada, decisão/termo sem fonte achável, módulo citado sem docstring,
regra ainda T0, e a cobertura por classe.

Uso:
    python scripts/kb/kb_inventario.py      # se o inventário estiver velho
    python scripts/kb/kb_grafo.py           # grava docs/CONHECIMENTO/grafo.json
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kb_comum import KB_DIR, REPO, WORKSPACE, _RE_CLASSE  # noqa: E402

SAIDA = KB_DIR / "grafo.json"
REPO_PREFIXO = REPO.name + "/"
CLASSES = ("PIL", "LV", "FV", "LAJ")
VIVOS = {"entrada", "canonico", "ativo"}

_RE_LINK = re.compile(r"\]\(([^)#\s]+)")
_RE_CRASE = re.compile(r"`([^`\s]+\.(?:md|py|ya?ml|json))`")
_RE_LINHA = re.compile(r"^\|(.+)\|\s*$")


def _ler(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _classes_do_texto(path: str, titulo: str, texto: str, minimo: int = 5) -> list[str]:
    """No caminho/título basta uma menção; no corpo, `minimo` (doc longo cita tudo)."""
    return [c for c, rx in _RE_CLASSE.items()
            if rx.search(path) or rx.search(titulo) or len(rx.findall(texto)) >= minimo]


class Resolvedor:
    """Acha a fonte/módulo que um caminho citado aponta — ou diz que não existe."""

    def __init__(self, fontes: list[dict]):
        self.por_path = {f["path"]: f["path"] for f in fontes}
        self.por_nome: dict[str, list[str]] = defaultdict(list)
        for f in fontes:
            self.por_nome[Path(f["path"]).name].append(f["path"])

    def fonte(self, ref: str, base: Path | None) -> str | None:
        ref = ref.strip().removeprefix("./")
        cands = []
        if base is not None:
            cands.append((base / ref))
        cands += [REPO / ref, REPO / "docs" / ref, WORKSPACE / ref]
        existente = None
        for c in cands:
            try:
                rel = c.resolve().relative_to(WORKSPACE).as_posix()
            except (ValueError, OSError):
                continue
            if rel in self.por_path:
                return rel
            if existente is None and c.is_file():
                existente = rel
        nomes = self.por_nome.get(Path(ref).name, [])
        if len(nomes) == 1:
            return nomes[0]
        return existente  # arquivo real fora do inventário (relatório, dado) — vira nó "arquivo"

    @staticmethod
    def codigo(ref: str, base: Path | None) -> str | None:
        for c in ([base / ref] if base else []) + [REPO / ref, WORKSPACE / ref]:
            try:
                if c.is_file():
                    return c.resolve().relative_to(REPO).as_posix()
            except (ValueError, OSError):
                continue
        return None


def _expandir(ref: str) -> list[str]:
    """`docs/SEMANTICA-{PILAR,VIGA}.md` e `docs/interviews/*.md` viram os arquivos reais."""
    m = re.search(r"\{([^}]+)\}", ref)
    if m:
        return [x for alt in m.group(1).split(",") for x in _expandir(ref[:m.start()] + alt + ref[m.end():])]
    if "*" in ref and not ref.startswith(("/", "..")) and ":" not in ref:
        achados = sorted({p.relative_to(REPO).as_posix() for p in REPO.glob(ref)}
                         | {p.relative_to(WORKSPACE).as_posix() for p in WORKSPACE.glob(ref)})
        return achados or [ref]
    return [ref]


def _refs(texto: str) -> list[str]:
    out = [m.group(1) for m in _RE_LINK.finditer(texto) if not m.group(1).startswith("http")]
    for m in _RE_CRASE.finditer(texto):
        out += _expandir(m.group(1))
    return list(dict.fromkeys(out))


def _tabela(texto: str) -> list[tuple[str, list[str]]]:
    """Linhas de tabela markdown com a seção (##) em que estão."""
    secao, out = "", []
    for ln in texto.splitlines():
        if ln.startswith("## "):
            secao = ln[3:].strip()
        m = _RE_LINHA.match(ln.strip())
        if m and not set(ln.strip()) <= set("|-: "):
            out.append((secao, [c.strip() for c in m.group(1).split("|")]))
    return out


def _mapa_codigo() -> dict[str, dict]:
    out = {}
    for _, cols in _tabela(_ler(KB_DIR / "MAPA-CODIGO.md")):
        if len(cols) >= 2 and cols[0].startswith("`"):
            nome = cols[0].strip("` ★✗")
            out[nome] = {"papel": cols[1], "docstring": cols[1] != "·",
                         "canonico": "★" in cols[0], "descontinuado": "✗" in cols[0]}
    return out


def _regras() -> list[dict]:
    db = WORKSPACE / "project_data.vision"
    if not db.exists():
        return []
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(semantic_rag_kb)")}
        if not {"tier", "classe", "regra_semantica"} <= cols:
            return []
        rows = con.execute("SELECT id, classe, regra_semantica, tier, field_id FROM semantic_rag_kb").fetchall()
    finally:
        con.close()
    return [{"id": r[0], "classe": (r[1] or "").upper(), "texto": r[2] or "", "tier": r[3] or "T0",
             "campo": r[4] or ""} for r in rows]


def construir() -> dict:
    inv = json.loads((KB_DIR / "_inventario.json").read_text(encoding="utf-8"))
    fontes = inv["fontes"]
    res = Resolvedor(fontes)
    mapa = _mapa_codigo()
    nos: dict[str, dict] = {}
    arestas: set[tuple[str, str, str]] = set()
    lacunas: list[dict] = []

    def no(id_: str, **kw) -> None:
        nos.setdefault(id_, {"id": id_, **kw})

    def aresta(s: str, t: str, tipo: str) -> None:
        if s != t:
            arestas.add((s, t, tipo))

    for c in CLASSES:
        no(f"classe:{c}", label=c, tipo="classe", status="canonico")

    def ligar_codigo(origem: str, ref: str, base: Path | None) -> bool:
        cod = res.codigo(ref, base)
        if not cod:
            return False
        info = mapa.get(cod, {})
        no(f"codigo:{cod}", label=Path(cod).name, tipo="codigo", path=cod,
           status="legado" if info.get("descontinuado") else ("canonico" if info.get("canonico") else "ativo"),
           titulo=info.get("papel", ""), docstring=info.get("docstring", True))
        aresta(origem, f"codigo:{cod}", "cita")
        return True

    def ligar_refs(origem: str, texto: str, base: Path | None, vivo: bool) -> int:
        n = 0
        for ref in _refs(texto):
            if ref.endswith(".py"):
                n += ligar_codigo(origem, ref, base)
                continue
            alvo = res.fonte(ref, base)
            if alvo and f"fonte:{alvo}" not in nos:
                no(f"fonte:{alvo}", label=Path(alvo).name, tipo="fonte", status="fora_inventario",
                   grupo="arquivo", path=alvo, classes=[])
            if alvo:
                aresta(origem, f"fonte:{alvo}", "cita"); n += 1
            elif (vivo and "/" in ref and ref.endswith(".md")
                  and not any(x in ref for x in ("<", "$", "*", "...", "timestamp"))):
                lacunas.append({"tipo": "referencia_quebrada", "no": origem, "detalhe": ref})
        return n

    # fontes — todos os nós primeiro, para uma citação nunca criar o nó antes da hora
    textos = {}
    for f in fontes:
        fid = f"fonte:{f['path']}"
        p = WORKSPACE / f["path"]
        texto = _ler(p) if p.suffix in (".md", ".yaml", ".yml", ".txt") else ""
        textos[fid] = (texto, p.parent, f["status"] in VIVOS)
        cls = _classes_do_texto(f["path"], f.get("titulo", ""), texto)
        no(fid, label=f.get("titulo") or f["nome"], tipo="fonte", status=f["status"], grupo=f["grupo"],
           path=f["path"], data=f.get("data"), linhas=f.get("linhas"), citado_por=f.get("citado_por", 0),
           motivo=f.get("motivo", ""), classes=cls)
        for c in cls:
            aresta(fid, f"classe:{c}", "classe")
    for fid, (texto, base, viva) in textos.items():
        if texto:
            ligar_refs(fid, texto, base, viva)

    # decisões do dono
    dec = KB_DIR / "DECISOES-DO-DONO.md"
    anterior = ""
    for secao, cols in _tabela(_ler(dec)):
        if len(cols) < 6 or not re.fullmatch(r"D-\d+", cols[0]):
            continue
        did = f"decisao:{cols[0]}"
        estado = cols[5].replace("*", "")
        cls = _classes_do_texto("", "", cols[3], minimo=1)
        no(did, label=cols[0], tipo="decisao", titulo=cols[3], data=cols[1], escopo=cols[2], secao=secao,
           estado=estado, status="historico" if "revogada" in estado else "canonico", classes=cls)
        for c in cls:
            aresta(did, f"classe:{c}", "classe")
        fonte_txt = anterior if cols[4].startswith("idem") else cols[4]
        anterior = fonte_txt
        if not ligar_refs(did, fonte_txt, dec.parent, True):
            lacunas.append({"tipo": "decisao_sem_fonte", "no": did, "detalhe": cols[4]})
        m = re.search(r"revogada por (D-\d+)", estado)
        if m:
            aresta(f"decisao:{m.group(1)}", did, "revoga")

    # glossário
    glo = KB_DIR / "GLOSSARIO.md"
    anterior = ""
    for secao, cols in _tabela(_ler(glo)):
        if len(cols) < 3 or not cols[0].startswith("**"):
            continue
        termo = cols[0].strip("* ")
        tid = f"termo:{termo}"
        cls = _classes_do_texto(termo, "", cols[1], minimo=1)
        no(tid, label=termo, tipo="termo", titulo=cols[1], secao=secao, status="canonico", classes=cls)
        for c in cls:
            aresta(tid, f"classe:{c}", "classe")
        fonte_txt = anterior if cols[2].startswith("idem") else cols[2]
        anterior = fonte_txt
        if not ligar_refs(tid, fonte_txt, glo.parent, True):
            lacunas.append({"tipo": "termo_sem_fonte", "no": tid, "detalhe": cols[2]})

    # regras semânticas
    for r in _regras():
        rid = f"regra:{r['id']}"
        no(rid, label=f"{r['classe'] or '?'}·{r['tier']}", tipo="regra", titulo=r["texto"][:400],
           tier=r["tier"], campo=r["campo"], status="canonico" if r["tier"] in ("T1", "T2") else "ativo",
           classes=[r["classe"]] if r["classe"] in CLASSES else [])
        if r["classe"] in CLASSES:
            aresta(rid, f"classe:{r['classe']}", "classe")

    # lacunas estruturais
    grau = Counter()
    for s, t, tipo in arestas:
        if tipo != "classe":
            grau[s] += 1; grau[t] += 1
    for n in nos.values():
        if n["tipo"] == "fonte" and n["status"] in VIVOS and grau[n["id"]] == 0:
            lacunas.append({"tipo": "fonte_orfa", "no": n["id"], "detalhe": "viva, sem citar nem ser citada"})
        if n["tipo"] == "codigo" and not n.get("docstring", True):
            lacunas.append({"tipo": "codigo_sem_docstring", "no": n["id"], "detalhe": n["path"]})
    cobertura = {}
    for c in CLASSES:
        viz = [nos[s] for s, t, tp in arestas if t == f"classe:{c}" and tp == "classe"]
        cont = Counter((n["tipo"], n.get("tier") if n["tipo"] == "regra" else n["status"]) for n in viz)
        cobertura[c] = {
            "fontes_vivas": sum(v for (tp, st), v in cont.items() if tp == "fonte" and st in VIVOS),
            "fontes_canonicas": cont[("fonte", "canonico")],
            "decisoes": sum(v for (tp, _), v in cont.items() if tp == "decisao"),
            "termos": sum(v for (tp, _), v in cont.items() if tp == "termo"),
            "regras_validadas": cont[("regra", "T1")] + cont[("regra", "T2")],
            "regras_t0": cont[("regra", "T0")],
        }
        if cobertura[c]["regras_t0"]:
            lacunas.append({"tipo": "regras_nao_validadas", "no": f"classe:{c}",
                            "detalhe": f"{cobertura[c]['regras_t0']} regras T0 aguardando validação"})
    for n in nos.values():
        n["grau"] = grau[n["id"]]
    for lc in lacunas:
        nos.get(lc["no"], {}).setdefault("lacunas", []).append(lc["tipo"])

    return {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "inventario_de": inv.get("gerado_em"),
        "contagens": dict(Counter(n["tipo"] for n in nos.values())),
        "cobertura": cobertura,
        "nos": sorted(nos.values(), key=lambda n: n["id"]),
        "arestas": [{"s": s, "t": t, "tipo": tp} for s, t, tp in sorted(arestas)],
        "lacunas": lacunas,
    }


def main() -> int:
    g = construir()
    SAIDA.write_text(json.dumps(g, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{SAIDA.relative_to(REPO)}: {g['contagens']} · {len(g['arestas'])} arestas · "
          f"{len(g['lacunas'])} lacunas {dict(Counter(l['tipo'] for l in g['lacunas']))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
