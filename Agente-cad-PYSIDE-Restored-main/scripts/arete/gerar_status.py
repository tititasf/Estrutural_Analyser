#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gerar_status.py — gera docs/STATUS.md a partir das fontes reais.

Fontes (todas READ-ONLY):
  1. scripts/arete/relatorios/{ts}/RELATORIO.md  -> último resultado por classe/pav
  2. GOLDEN/{obra}/{pav}/{classe}/               -> itens selados
  3. scripts/arete/relatorios/triagem_erros/*.jsonl -> achados por status
  4. DB project_data.vision (modo read-only)     -> fichas/recortes por status

Regra do projeto (MASTERPLAN-PRODUCAO-SOBERANIA §P5 / WS-D): status é DADO, não prosa.
Este arquivo substitui números escritos à mão em docs. Regenerar:

    python scripts/arete/gerar_status.py
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RELATORIOS = _REPO_ROOT / 'scripts' / 'arete' / 'relatorios'
_TRIAGEM = _RELATORIOS / 'triagem_erros'
_GOLDEN = _REPO_ROOT / 'GOLDEN'
_DB_DEFAULT = 'D:/Agente-cad-PYSIDE/project_data.vision'
_OUT = _REPO_ROOT / 'docs' / 'STATUS.md'

_RE_RUN_DIR = re.compile(r'^\d{8}_\d{6}$')
_RE_HEADER = re.compile(r'^#\s*Relat[óo]rio Arete\s*[—-]+\s*(\w+)\s*/\s*(\S+)', re.M)
_RE_RESULT = re.compile(
    r'^##\s*Resultado:\s*(\d+)P\s*/\s*(\d+)F\s*/\s*(\d+)B\s*\|\s*Arete\s*([\d.]+)%', re.M
)


def coletar_relatorios() -> dict:
    """Último RELATORIO.md por (classe, pav). Chave: (classe, pav)."""
    ultimos: dict[tuple, dict] = {}
    if not _RELATORIOS.is_dir():
        return ultimos
    for d in sorted(_RELATORIOS.iterdir()):
        if not (d.is_dir() and _RE_RUN_DIR.match(d.name)):
            continue
        rel = d / 'RELATORIO.md'
        if not rel.is_file():
            continue
        texto = rel.read_text(encoding='utf-8', errors='replace')
        mh = _RE_HEADER.search(texto)
        mr = _RE_RESULT.search(texto)
        if not (mh and mr):
            continue
        classe, pav = mh.group(1).upper(), mh.group(2)
        info = {
            'run': d.name,
            'pass': int(mr.group(1)),
            'fail': int(mr.group(2)),
            'blocked': int(mr.group(3)),
            'pct': float(mr.group(4)),
        }
        atual = ultimos.get((classe, pav))
        if atual is None or info['run'] > atual['run']:
            ultimos[(classe, pav)] = info
    return ultimos


def coletar_golden() -> dict:
    """Contagem de itens selados: {(obra, pav, classe): n}."""
    selados: dict[tuple, int] = {}
    if not _GOLDEN.is_dir():
        return selados
    for obra_dir in _GOLDEN.iterdir():
        if not obra_dir.is_dir() or obra_dir.name.startswith('_'):
            continue
        for pav_dir in obra_dir.iterdir():
            if not pav_dir.is_dir():
                continue
            for classe_dir in pav_dir.iterdir():
                if not classe_dir.is_dir():
                    continue
                n = sum(1 for x in classe_dir.iterdir() if x.is_dir())
                if n:
                    selados[(obra_dir.name, pav_dir.name, classe_dir.name)] = n
    return selados


def coletar_triagem() -> dict:
    """Por arquivo JSONL: contagem por status e por marcado_por."""
    out: dict[str, dict] = {}
    if not _TRIAGEM.is_dir():
        return out
    for f in sorted(_TRIAGEM.glob('*.jsonl')):
        status, autores = Counter(), Counter()
        total = 0
        for linha in f.read_text(encoding='utf-8', errors='replace').splitlines():
            linha = linha.strip()
            if not linha:
                continue
            try:
                e = json.loads(linha)
            except json.JSONDecodeError:
                continue
            total += 1
            status[e.get('status', '?')] += 1
            autores[e.get('marcado_por', 'humano')] += 1
        out[f.name] = {'total': total, 'status': dict(status), 'autores': dict(autores)}
    return out


def coletar_db(db_path: str) -> dict:
    out = {'fichas': [], 'recortes': [], 'erro': None}
    try:
        con = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
        cur = con.cursor()
        cur.execute(
            'SELECT classe, status, COUNT(*) FROM reverse_eng_fichas '
            'GROUP BY classe, status ORDER BY classe, status'
        )
        out['fichas'] = cur.fetchall()
        cur.execute(
            'SELECT status, COUNT(*) FROM reverse_eng_recortes '
            'GROUP BY status ORDER BY status'
        )
        out['recortes'] = cur.fetchall()
        con.close()
    except Exception as exc:  # DB indisponível não pode impedir o STATUS
        out['erro'] = str(exc)
    return out


def gerar(db_path: str = _DB_DEFAULT) -> str:
    agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    relatorios = coletar_relatorios()
    golden = coletar_golden()
    triagem = coletar_triagem()
    db = coletar_db(db_path)

    L: list[str] = []
    L.append('# STATUS — gerado automaticamente, NÃO editar à mão')
    L.append('')
    L.append(f'**Gerado em:** {agora}  ')
    L.append('**Regenerar:** `python scripts/arete/gerar_status.py`  ')
    L.append('**Fontes:** relatórios Arete + GOLDEN/ + triagem JSONL + '
             'DB (read-only). Em conflito com qualquer doc escrito à mão, '
             'ESTE arquivo vence (é o dado).')
    L.append('')

    # ── Última rodada por classe/pav ─────────────────────────────────────
    L.append('## Última rodada Arete por classe (relatório mais recente)')
    L.append('')
    L.append('| Classe | Pav | Run | PASS | FAIL | BLOCKED | Arete % | Golden selado | Alerta |')
    L.append('|--------|-----|-----|------|------|---------|---------|---------------|--------|')
    for (classe, pav), info in sorted(relatorios.items()):
        g = None
        for (obra, gpav, gclasse), n in golden.items():
            if gclasse == classe and gpav == pav:
                g = n
                break
        alerta = ''
        if info['fail'] > 0:
            alerta = '❌ FAIL aberto'
            if g and g > info['pass']:
                alerta += f' · ⚠ golden ({g}) > última rodada ({info["pass"]}) — REGRESSÃO vs selado'
        L.append(
            f"| {classe} | {pav} | {info['run']} | {info['pass']} | {info['fail']} "
            f"| {info['blocked']} | {info['pct']:.1f}% | {g if g is not None else '—'} | {alerta} |"
        )
    L.append('')

    # ── Golden completo ──────────────────────────────────────────────────
    L.append('## Golden selado (todas as obras/pavimentos)')
    L.append('')
    L.append('| Obra | Pavimento | Classe | Itens selados |')
    L.append('|------|-----------|--------|---------------|')
    for (obra, pav, classe), n in sorted(golden.items()):
        L.append(f'| {obra} | {pav} | {classe} | {n} |')
    L.append('')

    # ── Triagem ──────────────────────────────────────────────────────────
    L.append('## Triagem de erros (JSONL)')
    L.append('')
    if triagem:
        L.append('| Arquivo | Total | Por status | Por autor |')
        L.append('|---------|-------|------------|-----------|')
        for nome, t in triagem.items():
            st = ', '.join(f'{k}: {v}' for k, v in sorted(t['status'].items()))
            au = ', '.join(f'{k}: {v}' for k, v in sorted(t['autores'].items()))
            L.append(f'| {nome} | {t["total"]} | {st} | {au} |')
    else:
        L.append('_Nenhum log de triagem encontrado._')
    L.append('')

    # ── DB ───────────────────────────────────────────────────────────────
    L.append('## Banco de dados (read-only)')
    L.append('')
    if db['erro']:
        L.append(f'_DB indisponível: {db["erro"]}_')
    else:
        L.append('**Fichas N2 (`reverse_eng_fichas`):**')
        L.append('')
        L.append('| Classe | Status | Qtde |')
        L.append('|--------|--------|------|')
        for classe, status, n in db['fichas']:
            L.append(f'| {classe} | {status} | {n} |')
        L.append('')
        L.append('**Recortes (`reverse_eng_recortes`):**')
        L.append('')
        L.append('| Status | Qtde |')
        L.append('|--------|------|')
        for status, n in db['recortes']:
            L.append(f'| {status} | {n} |')
    L.append('')
    L.append('---')
    L.append('*Gerado por `scripts/arete/gerar_status.py` — '
             'MASTERPLAN-PRODUCAO-SOBERANIA WS-D.*')
    return '\n'.join(L) + '\n'


def main() -> None:
    # Console Windows pode ser cp1252 — não deixar emoji derrubar o script
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    db_path = sys.argv[1] if len(sys.argv) > 1 else _DB_DEFAULT
    conteudo = gerar(db_path)
    _OUT.write_text(conteudo, encoding='utf-8')
    print(f'[STATUS] Gerado: {_OUT} ({len(conteudo.splitlines())} linhas)')


if __name__ == '__main__':
    main()
