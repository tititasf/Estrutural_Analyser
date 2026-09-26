# -*- coding: utf-8 -*-
"""
kb_inventario.py — inventário das fontes de conhecimento do workspace.

Varre as fontes textuais (docs, CLAUDE/AGENTS, squads, skills, comandos) e os
stores legados (ByteRover, LanceDB), e classifica cada fonte por heurística:

  entrada     ponto de entrada lido por todo agente (CLAUDE.md, AGENTS.md, mapa)
  canonico    citado por uma entrada ou marcado "Status: canónico"
  ativo       tocado desde CORTE_ATIVO ou citado por outra fonte
  historico   HISTORICO/, relatórios/handoffs antigos, marcado histórico
  legado      marcado DESCONTINUADO/OBSOLETO/LEGADO/SUPERSEDED/"não usar"
  candidato_obsoleto  sem toque desde CORTE_ATIVO e sem ninguém citando

A classificação é ponto de partida: a curadoria humana/agente sobrescreve via
docs/CONHECIMENTO/fontes_override.yaml (status + motivo por caminho).

Uso:
    python scripts/kb/kb_inventario.py            # grava docs/CONHECIMENTO/_inventario.json + FONTES-E-STATUS.md
    python scripts/kb/kb_inventario.py --resumo   # só imprime contagens
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from datetime import date
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]            # Agente-cad-PYSIDE-Restored-main
WORKSPACE = REPO.parent                                # D:/Agente-cad-PYSIDE
KB_DIR = REPO / "docs" / "CONHECIMENTO"
CORTE_ATIVO = "2026-07-01"
# Saídas geradas por este inventário: citam tudo e não podem contar como citação.
GERADOS = {"FONTES-E-STATUS.md", "_inventario.json"}

ENTRADAS = [
    WORKSPACE / "CLAUDE.md",
    REPO / "CLAUDE.md",
    REPO / "AGENTS.md",
    REPO / "docs" / "LOOPING-CANONICO.md",
    KB_DIR / "MAPA-DO-CONHECIMENTO.md",
]

FONTES_GLOB = [
    ("docs", REPO / "docs", "**/*.md"),
    ("raiz_repo", REPO, "*.md"),
    ("raiz_workspace", WORKSPACE, "*.md"),
    ("docs_workspace", WORKSPACE / "docs", "*.md"),
    ("agents", REPO / ".agents", "**/*.md"),
    ("squads", REPO / "squads", "**/*.md"),
    ("squads_data", REPO / "squads", "**/data/*.json"),
    ("skills_repo", REPO / ".claude" / "skills", "**/SKILL.md"),
    ("arquivo_repo", REPO / "_arquivo", "**/*.md"),
    ("arquivo_workspace", WORKSPACE / "_arquivo", "**/*.md"),
    ("comandos", REPO / ".claude" / "commands", "**/*.md"),
    ("skills_usuario", Path.home() / ".claude" / "skills", "**/*.md"),
]

# Stores fora do texto. Estado medido em 2026-09-25 (imports + última escrita);
# rodar de novo a verificação antes de arquivar qualquer um.
STORES = [
    ("kb_global", WORKSPACE / "KB-GLOBAL", "vivo",
     "índice desta base (kb_build.py); derivado, reconstruível"),
    ("semantic_rag_kb", WORKSPACE / "project_data.vision", "vivo",
     "tabela de regras tieradas (T0/T1/TX); consumida por qa_rag_evidence/qa_rag_curation; 117 regras, 8 T1"),
    ("rag_artifact_validations", WORKSPACE / "project_data.vision", "vivo",
     "validações de artefato N3/N4 + políticas de lock; até 2026-07-22"),
    ("qa_session_index", REPO / "scripts" / "arete" / "qa_session_index.py", "latente",
     "mini-RAG de sessão por pavimento (SQLite); D0–D3 concluídos em julho, sem uso desde"),
    ("obra_rag_db", WORKSPACE / "DADOS-OBRAS", "latente",
     "LanceDB por obra (obra_docs/obra_dxf_inventory); ligado à app PySide (project_manager, obra_rag_pipeline)"),
    ("bytereover_context_tree", REPO / ".brv" / "context-tree", "legado",
     "83 notas ByteRover; última escrita 2026-08-01; conteúdo coberto pelos docs canônicos"),
    ("lancedb_stog_rag_db", WORKSPACE / "DADOS-OBRAS" / "stog_rag_db", "legado",
     "domain_knowledge + stog_kbs; embedder NIM; última escrita 2026-06-04; substituído pela KB global"),
    ("faiss_vectors", WORKSPACE / "data" / "vectors" / "faiss", "legado",
     "213 vetores de 2026-05-28, todos T0 (nunca validados); tombstones até 2026-07-21"),
]

RE_LEGADO = re.compile(
    r"DESCONTINUAD|OBSOLET|DEPRECAT|\bLEGADO\b|SUPERSEDED|SUBSTITU[ÍI]DO POR|N[ÃA]O USAR", re.I)
RE_HIST = re.compile(r"hist[óo]ric|snapshot de|\bv1\.\d .*histórico", re.I)
RE_CANON = re.compile(r"status:?\**\s*can[óô]nic", re.I)
RE_TITULO = re.compile(r"^#\s+(.+)$", re.M)


def _git_datas(raiz: Path) -> dict[str, str]:
    """Última data de commit por arquivo (um único git log)."""
    try:
        out = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "log", "--name-only",
             "--format=@%ad", "--date=short", "--",
             *[str(r.resolve()) for _, r, _ in FONTES_GLOB if r.exists() and r != Path.home() / ".claude" / "skills"
               and r not in (REPO, WORKSPACE)],
             *[str(p) for p in REPO.glob("*.md")], *[str(p) for p in WORKSPACE.glob("*.md")]],
            cwd=raiz, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=180).stdout
    except Exception:
        return {}
    datas: dict[str, str] = {}
    atual = ""
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=raiz,
                         capture_output=True, text=True).stdout.strip()
    for linha in out.splitlines():
        if linha.startswith("@"):
            atual = linha[1:]
        elif linha.strip():
            p = str((Path(top) / linha.strip()).resolve())
            datas.setdefault(p, atual)
    return datas


def _rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(WORKSPACE.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def coletar() -> list[dict]:
    datas = _git_datas(WORKSPACE)
    fontes: list[dict] = []
    vistos: set[Path] = set()
    for grupo, raiz, pat in FONTES_GLOB:
        if not raiz.exists():
            continue
        for p in sorted(raiz.glob(pat)):
            rp = p.resolve()
            if (rp in vistos or not p.is_file() or ".git" in p.parts or "relatorios" in p.parts
                    or p.name in GERADOS):
                continue
            vistos.add(rp)
            txt = p.read_text(encoding="utf-8", errors="replace")
            m = RE_TITULO.search(txt)
            # Marca de status só vale no título ou nas linhas "Status:"/aviso do topo —
            # o corpo cita "caminho legado" o tempo todo sem ser legado.
            topo = [ln for ln in txt[:1500].splitlines()
                    if ln.startswith("#") or re.match(r"^\s*(>\s*)?\**\s*status", ln, re.I)
                    or re.match(r"^\s*>\s*\**\s*(⚠|aviso|nota)", ln, re.I)]
            cab = "\n".join(topo[:6])
            data_git = datas.get(str(rp))
            fontes.append({
                "path": _rel(p), "grupo": grupo, "nome": p.name,
                "titulo": (m.group(1).strip() if m else p.stem)[:140],
                "linhas": txt.count("\n") + 1,
                "data": data_git or date.fromtimestamp(p.stat().st_mtime).isoformat(),
                "data_fonte": "git" if data_git else "mtime",
                "_marca_legado": bool(RE_LEGADO.search(cab)),
                "_marca_hist": bool(RE_HIST.search(topo[0] if topo else "")),
                "_marca_canon": bool(RE_CANON.search(cab)),
                "_texto": txt,
            })
    return fontes


def classificar(fontes: list[dict]) -> None:
    entradas_txt = "\n".join(e.read_text(encoding="utf-8", errors="replace")
                             for e in ENTRADAS if e.exists())
    entradas_rel = {_rel(e) for e in ENTRADAS}
    # Nome repetido (README.md, STATUS.md, PIL.md...) só conta citação com a pasta-mãe.
    repetidos = Counter(f["nome"] for f in fontes)
    for f in fontes:
        partes = f["path"].split("/")
        f["_chave"] = (f["nome"] if repetidos[f["nome"]] == 1
                       else "/".join(partes[-2:]))
    nomes = Counter()
    for f in fontes:
        for g in fontes:
            if g is not f and f["_chave"] in g["_texto"]:
                nomes[f["path"]] += 1
    overrides = {}
    ov = KB_DIR / "fontes_override.yaml"
    if ov.exists():
        overrides = yaml.safe_load(ov.read_text(encoding="utf-8")) or {}
    for f in fontes:
        f["citado_por"] = nomes[f["path"]]
        citado_entrada = f["_chave"] in entradas_txt
        if f["path"] in entradas_rel:
            st, motivo = "entrada", "ponto de entrada dos agentes"
        elif "/_arquivo/" in f["path"] or f["path"].startswith("_arquivo/"):
            st, motivo = "legado", "arquivado em _arquivo/ (harmonização 2026-09-26)"
        elif "HISTORICO" in f["path"] or "/stories/completed/" in f["path"]:
            st, motivo = "historico", "pasta de histórico / story concluída"
        elif f["_marca_legado"] and not citado_entrada:
            st, motivo = "legado", "cabeçalho marca descontinuado/obsoleto/legado"
        elif citado_entrada or f["_marca_canon"]:
            st, motivo = "canonico", ("citado por ponto de entrada" if citado_entrada
                                      else "marcado Status: canónico")
        elif f["_marca_hist"]:
            st, motivo = "historico", "título marca histórico"
        elif f["data"] >= CORTE_ATIVO or f["citado_por"] > 0:
            st, motivo = "ativo", f"tocado em {f['data']} / citado por {f['citado_por']}"
        else:
            st, motivo = "candidato_obsoleto", f"sem toque desde {f['data']} e sem citação"
        o = overrides.get(f["path"])
        if o:
            st, motivo = o.get("status", st), "curadoria: " + o.get("motivo", "")
        f["status"], f["motivo"] = st, motivo


def gravar(fontes: list[dict]) -> None:
    KB_DIR.mkdir(parents=True, exist_ok=True)
    limpo = [{k: v for k, v in f.items() if not k.startswith("_")} for f in fontes]
    stores = [{"path": _rel(p), "grupo": "store", "nome": n, "status": st,
               "motivo": m, "existe": p.exists()} for n, p, st, m in STORES]
    (KB_DIR / "_inventario.json").write_text(
        json.dumps({"gerado_em": date.today().isoformat(), "corte_ativo": CORTE_ATIVO,
                    "fontes": limpo, "stores": stores}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    ordem = ["entrada", "canonico", "ativo", "historico", "legado", "candidato_obsoleto"]
    cont = Counter(f["status"] for f in limpo)
    linhas = [
        "# Fontes de conhecimento — status",
        "",
        f"> Gerado por `scripts/kb/kb_inventario.py` em {date.today().isoformat()}. "
        "Não editar à mão: a curadoria vai em `fontes_override.yaml` e o arquivo é regenerado.",
        "",
        "| Status | Qtde | Significado |",
        "|---|---:|---|",
        f"| entrada | {cont['entrada']} | lido por todo agente antes de agir |",
        f"| canonico | {cont['canonico']} | citado por uma entrada ou marcado canónico — é a verdade vigente |",
        f"| ativo | {cont['ativo']} | em uso (tocado desde {CORTE_ATIVO} ou citado) |",
        f"| historico | {cont['historico']} | registro do passado; consultar só para entender decisões |",
        f"| legado | {cont['legado']} | marcado descontinuado/obsoleto — não seguir |",
        f"| candidato_obsoleto | {cont['candidato_obsoleto']} | sem uso aparente — revisar para arquivar/remover |",
        "",
        "## Stores de conhecimento fora do texto",
        "",
        "| Store | Onde | Status | Estado medido |", "|---|---|---|---|",
        *[f"| {s['nome']} | `{s['path']}` | {s['status']} | {s['motivo']} |" for s in stores],
        "",
    ]
    for st in ordem:
        grupo = sorted((f for f in limpo if f["status"] == st), key=lambda f: f["path"])
        if not grupo:
            continue
        linhas += [f"## {st} ({len(grupo)})", "", "| Fonte | Título | Data | Citado por | Motivo |",
                   "|---|---|---|---:|---|"]
        linhas += [f"| `{f['path']}` | {f['titulo'].replace('|', '/')} | {f['data']} | "
                   f"{f['citado_por']} | {f['motivo']} |" for f in grupo]
        linhas.append("")
    (KB_DIR / "FONTES-E-STATUS.md").write_text("\n".join(linhas), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--resumo", action="store_true")
    args = ap.parse_args()
    fontes = coletar()
    classificar(fontes)
    cont = Counter(f["status"] for f in fontes)
    print(f"{len(fontes)} fontes:", dict(cont))
    if not args.resumo:
        gravar(fontes)
        print(f"-> {KB_DIR / 'FONTES-E-STATUS.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
