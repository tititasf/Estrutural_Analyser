# -*- coding: utf-8 -*-
"""
kb_mapa_codigo.py — gera docs/CONHECIMENTO/MAPA-CODIGO.md a partir das docstrings.

Uma linha por módulo: caminho, papel (1ª frase da docstring) e marca:
  ★ canônico     citado pelo CLAUDE.md ou pela seção 1 do LOOPING-CANONICO
  ✗ descontinuado docstring ou pasta marcam legado/descontinuado/quarentena
  · sem docstring módulo sem descrição (candidato a documentar)

Gerado — não editar à mão. Rodar depois de criar/renomear módulos:
    python scripts/kb/kb_mapa_codigo.py
"""
from __future__ import annotations

import ast
import re
import warnings
from datetime import date
from pathlib import Path

from kb_comum import KB_DIR, REPO

PASTAS = [
    ("App — núcleo (src/core)", "src/core", "**/*.py"),
    ("App — UI PySide (src/ui)", "src/ui", "**/*.py"),
    ("App — outros (src/*)", "src", "*/*.py"),
    ("Portal web (portal/app)", "portal/app", "**/*.py"),
    ("Scripts — geradores, motores, obra (scripts/)", "scripts", "*.py"),
    ("Scripts — Arete / QA (scripts/arete)", "scripts/arete", "*.py"),
    ("Scripts — base de conhecimento (scripts/kb)", "scripts/kb", "*.py"),
]
# Só marca forte, em maiúsculas, nas 3 primeiras linhas: o corpo cita "legado" à toa.
RE_LEGADO = re.compile(r"DESCONTINUAD|DEPRECAT|OBSOLET|QUARENTENA")


def _canonicos() -> str:
    txt = (REPO / "CLAUDE.md").read_text(encoding="utf-8", errors="replace")
    lc = (REPO / "docs" / "LOOPING-CANONICO.md").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"\n## 1\b.*?(?=\n## 2\b)", lc, re.S)
    return txt + (m.group(0) if m else "")


def _papel(p: Path) -> tuple[str, bool]:
    src = p.read_text(encoding="utf-8", errors="replace")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            doc = ast.get_docstring(ast.parse(src)) or ""
    except SyntaxError:
        m = re.search(r'^\s*(?:#.*\n)*\s*[rRuU]?("""|\'\'\')(.*?)\1', src, re.S)
        doc = m.group(2) if m else ""
    legado = bool(RE_LEGADO.search(" ".join(doc.strip().splitlines()[:3])))
    linhas = [ln.strip() for ln in doc.strip().splitlines() if ln.strip()]
    if not linhas:
        return "", legado
    primeira = linhas[0]
    # docstring que começa com "nome.py — papel" → fica só o papel
    primeira = re.sub(r"^[\w./-]+\.py\s*[—–:-]+\s*", "", primeira)
    return primeira[:160], legado


def main() -> int:
    canon = _canonicos()
    vistos: set[Path] = set()
    out = [
        "# Mapa de código",
        "",
        f"> Gerado por `scripts/kb/kb_mapa_codigo.py` em {date.today().isoformat()} a partir das "
        "docstrings. Não editar à mão.",
        "> ★ canônico (citado pelo CLAUDE.md / LOOPING-CANONICO §1) · ✗ descontinuado · "
        "· sem docstring",
        "",
    ]
    total = sem_doc = 0
    for titulo, base, pat in PASTAS:
        raiz = REPO / base
        arquivos = sorted(p for p in raiz.glob(pat)
                          if p.resolve() not in vistos and "__pycache__" not in p.parts
                          and p.name != "__init__.py" and "backup" not in p.name
                          and "_broken" not in p.name and "tests" not in p.parts)
        if not arquivos:
            continue
        out += [f"## {titulo} ({len(arquivos)})", "", "| Módulo | Papel |", "|---|---|"]
        for p in arquivos:
            vistos.add(p.resolve())
            papel, legado = _papel(p)
            rel = p.relative_to(REPO).as_posix()
            marca = "✗ " if legado or "_loops_legado" in rel else ("★ " if p.name in canon else "")
            if not papel:
                sem_doc += 1
                papel = "·"
            total += 1
            out.append(f"| {marca}`{rel}` | {papel.replace('|', '/')} |")
        out.append("")
    out.insert(5, f"**{total} módulos**, {sem_doc} sem docstring.")
    out.insert(6, "")
    (KB_DIR / "MAPA-CODIGO.md").write_text("\n".join(out), encoding="utf-8")
    print(f"{total} módulos ({sem_doc} sem docstring) -> {KB_DIR / 'MAPA-CODIGO.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
