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


def _itens_reprovados(run_dir: Path) -> set[str]:
    """elemento_id dos itens que NÃO passaram, lidos do relatorio.json da rodada.

    O RELATORIO.md só tem contagens; o teste de regressão precisa de nomes.
    Ausência do JSON devolve conjunto vazio (rodada antiga) — nunca derruba o STATUS.
    """
    alvo = run_dir / 'relatorio.json'
    if not alvo.is_file():
        return set()
    try:
        dados = json.loads(alvo.read_text(encoding='utf-8', errors='replace'))
    except (json.JSONDecodeError, OSError):
        return set()
    reprovados = set()
    for item in dados.get('itens') or []:
        veredito = item.get('resultado_final') or item.get('resultado') or 'PASS'
        elemento = item.get('elemento_id')
        if elemento and veredito != 'PASS':
            reprovados.add(str(elemento))
    return reprovados


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
            'reprovados': _itens_reprovados(d),
        }
        atual = ultimos.get((classe, pav))
        if atual is None or info['run'] > atual['run']:
            ultimos[(classe, pav)] = info
    return ultimos


def coletar_golden() -> dict:
    """Itens selados: {(obra, pav, classe): {elemento_id, ...}}.

    Conjunto (e não contagem) porque o teste de regressão é de pertinência:
    "item selado que reprovou na última rodada", não "quantidade caiu".
    """
    selados: dict[tuple, set[str]] = {}
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
                itens = {x.name for x in classe_dir.iterdir() if x.is_dir()}
                if itens:
                    selados[(obra_dir.name, pav_dir.name, classe_dir.name)] = itens
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
    L.append('| Classe | Pav | Run | PASS | FAIL | BLOCKED | Arete % | Golden selado | Regressão | Alerta |')
    L.append('|--------|-----|-----|------|------|---------|---------|---------------|-----------|--------|')
    regressoes: dict[tuple, list[str]] = {}
    for (classe, pav), info in sorted(relatorios.items()):
        selados = None
        for (obra, gpav, gclasse), itens in golden.items():
            if gclasse == classe and gpav == pav:
                selados = itens
                break
        # Regressão REAL = item que está no golden e reprovou nesta rodada.
        # (Comparar contagem de golden com PASS da rodada é inválido: o golden é
        # acumulado e nunca invalidado, e cada rodada pode ter escopo diferente.)
        regrediu = sorted(selados & info['reprovados']) if selados else []
        if regrediu:
            regressoes[(classe, pav)] = regrediu
        alerta = '❌ FAIL aberto' if info['fail'] > 0 else ''
        if regrediu:
            alerta += (' · ' if alerta else '') + f'🔴 {len(regrediu)} selado(s) reprovando'
        L.append(
            f"| {classe} | {pav} | {info['run']} | {info['pass']} | {info['fail']} "
            f"| {info['blocked']} | {info['pct']:.1f}% | {len(selados) if selados else '—'} "
            f"| {len(regrediu) if selados else '—'} | {alerta} |"
        )
    L.append('')

    # ── Regressão real (golden ∩ reprovados) ─────────────────────────────
    L.append('## Regressão vs golden (itens selados que reprovaram na última rodada)')
    L.append('')
    if regressoes:
        total_reg = sum(len(v) for v in regressoes.values())
        L.append(f'**{total_reg} item(ns) selado(s) reprovando.** Cada linha é dívida real: '
                 'o item já passou por todos os gates e hoje não passa.')
        L.append('')
        L.append('| Classe | Pav | Qtde | Itens |')
        L.append('|--------|-----|------|-------|')
        for (classe, pav), itens in sorted(regressoes.items()):
            amostra = ', '.join(itens[:15]) + (' …' if len(itens) > 15 else '')
            L.append(f'| {classe} | {pav} | {len(itens)} | {amostra} |')
        L.append('')
        L.append('> Antes de culpar o motor: confirmar se a rodada é recente. Relatório '
                 'velho contra DB atualizado produz falso positivo em massa.')
    else:
        L.append('_Nenhum item selado reprovando — sem regressão vs golden._')
    L.append('')

    # ── Golden completo ──────────────────────────────────────────────────
    L.append('## Golden selado (todas as obras/pavimentos)')
    L.append('')
    L.append('| Obra | Pavimento | Classe | Itens selados |')
    L.append('|------|-----------|--------|---------------|')
    for (obra, pav, classe), itens in sorted(golden.items()):
        L.append(f'| {obra} | {pav} | {classe} | {len(itens)} |')
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
