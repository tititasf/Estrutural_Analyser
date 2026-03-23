#!/usr/bin/env python3
"""
RAG Query — CAD-ANALYZER
Interface de consulta semântica ao índice FAISS de elementos estruturais.
Uso: python scripts/rag_query.py "pilar com b=20 h=50" [--tipo pilar] [--obra Obra_TREINO_1] [--k 5]
"""
import sys, os, json, argparse
from pathlib import Path

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

FAISS_DIR  = Path('D:/Agente-cad-PYSIDE/data/vectors/faiss')
MODEL_NAME = 'all-MiniLM-L6-v2'
EMBED_DIM  = 384

# ── CORES TERMINAL ──────────────────────────────────────────────────────────
C = {
    'reset':  '\033[0m',
    'bold':   '\033[1m',
    'dim':    '\033[2m',
    'orange': '\033[38;5;208m',
    'blue':   '\033[38;5;33m',
    'green':  '\033[38;5;34m',
    'yellow': '\033[38;5;220m',
    'red':    '\033[38;5;196m',
    'grey':   '\033[38;5;245m',
    'white':  '\033[38;5;255m',
}

TIPO_COR = {'pilar': C['orange'], 'viga': C['blue'], 'laje': C['green']}

def cor(tipo): return TIPO_COR.get(tipo, C['white'])

def normalize(vecs):
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return (vecs / norms).astype(np.float32)

# ── CARREGAMENTO ─────────────────────────────────────────────────────────────

def load_index(tipo=None):
    """Carrega índice FAISS e metadados. tipo=None → índice geral."""
    if tipo:
        idx_path  = FAISS_DIR / f'{tipo}s.index'
        meta_path = FAISS_DIR / f'{tipo}s_meta.json'
    else:
        idx_path  = FAISS_DIR / 'estruturais.index'
        meta_path = FAISS_DIR / 'estruturais_meta.json'

    if not idx_path.exists():
        print(f'{C["red"]}[ERRO] Índice não encontrado: {idx_path}{C["reset"]}')
        print(f'       Rode: python scripts/rag_ingestor.py --rebuild')
        sys.exit(1)

    index = faiss.read_index(str(idx_path))
    with open(meta_path, encoding='utf-8') as f:
        meta = json.load(f)
    return index, meta

# ── QUERY ────────────────────────────────────────────────────────────────────

def query(text, tipo=None, obra=None, k=5, threshold=0.3):
    """Busca semântica. Retorna lista de resultados com score."""
    model = SentenceTransformer(MODEL_NAME)
    index, meta = load_index(tipo)

    # Embed query
    vec = model.encode([text], show_progress_bar=False)
    vec = normalize(vec)

    # Buscar mais resultados para filtrar por obra depois
    k_search = k * 5 if obra else k
    k_search = min(k_search, index.ntotal)

    scores, ids = index.search(vec, k_search)
    scores = scores[0]
    ids    = ids[0]

    results = []
    for score, fid in zip(scores, ids):
        if fid < 0 or score < threshold:
            continue
        m = meta[fid] if tipo else next((m for m in meta if m.get('faiss_id') == fid), None)
        if m is None:
            continue
        if obra and m.get('obra') != obra:
            continue
        results.append({'score': float(score), 'meta': m})
        if len(results) >= k:
            break

    return results

# ── DISPLAY ──────────────────────────────────────────────────────────────────

def fmt_conf(c):
    """Formata confidence com cor."""
    try:
        v = float(c)
        if v >= 0.80: clr = C['green']
        elif v >= 0.50: clr = C['yellow']
        elif v >= 0.30: clr = C['orange']
        else: clr = C['red']
        return f'{clr}{v:.2f}{C["reset"]}'
    except:
        return str(c)

def fmt_score(s):
    if s >= 0.90: clr = C['green']
    elif s >= 0.70: clr = C['yellow']
    elif s >= 0.50: clr = C['orange']
    else: clr = C['red']
    return f'{clr}{s:.3f}{C["reset"]}'

def print_result(i, r, verbose=False):
    m     = r['meta']
    tipo  = m.get('tipo', '?')
    tid   = m.get('id', '?')
    obra  = m.get('obra', '?')
    pav   = m.get('pavimento', '?')
    score = r['score']
    dados = m.get('dados', {})

    tc = cor(tipo)
    print(f'\n  {C["bold"]}#{i+1}{C["reset"]} {tc}{tipo.upper()} {tid}{C["reset"]}  '
          f'{C["grey"]}obra={obra}  pav={pav}{C["reset"]}  '
          f'sim={fmt_score(score)}')

    # Dimensões principais
    if tipo == 'pilar':
        b   = dados.get('b') or dados.get('largura', '?')
        h   = dados.get('h') or dados.get('comprimento', '?')
        alt = dados.get('altura', '?')
        conf= dados.get('confidence', '?')
        src = dados.get('source', dados.get('bh_source', ''))
        print(f'     {C["white"]}b={b}cm  h={h}cm  alt={alt}cm{C["reset"]}  '
              f'conf={fmt_conf(conf)}  src={C["dim"]}{src}{C["reset"]}')
        faces = dados.get('faces_encontradas', dados.get('sides', []))
        if faces:
            print(f'     faces: {C["dim"]}{" ".join(faces)}{C["reset"]}')
    elif tipo == 'viga':
        b    = dados.get('b', '?')
        h    = dados.get('h', '?')
        comp = dados.get('comprimento', '?')
        conf = dados.get('confidence', '?')
        src  = dados.get('source', '')
        print(f'     {C["white"]}b={b}cm  h={h}cm  comp={comp}cm{C["reset"]}  '
              f'conf={fmt_conf(conf)}  src={C["dim"]}{src}{C["reset"]}')
    elif tipo == 'laje':
        comp = dados.get('comprimento', '?')
        larg = dados.get('largura', '?')
        area = dados.get('area_cm2', '?')
        conf = dados.get('confidence', '?')
        modo = dados.get('modo_selecionado', '')
        print(f'     {C["white"]}comp={comp}cm  larg={larg}cm  area={area}cm²{C["reset"]}  '
              f'conf={fmt_conf(conf)}  modo={C["dim"]}{modo}{C["reset"]}')

    nota = dados.get('nota', '')
    if nota:
        print(f'     nota: {C["dim"]}{nota}{C["reset"]}')

    if verbose:
        print(f'     text: {C["dim"]}{m.get("text","")}{C["reset"]}')


# ── FIND-ELEMENT ─────────────────────────────────────────────────────────────

def find_element(element_id: str, tipo=None, obra=None):
    """
    Busca elemento por ID exato (P17, V5, L3) nos metadados.
    Retorna lista de correspondências encontradas.
    """
    tipos = [tipo] if tipo else ['pilar', 'viga', 'laje']
    found = []
    for t in tipos:
        idx_path  = FAISS_DIR / f'{t}s.index'
        meta_path = FAISS_DIR / f'{t}s_meta.json'
        if not meta_path.exists():
            continue
        with open(meta_path, encoding='utf-8') as f:
            meta = json.load(f)
        for m in meta:
            mid = str(m.get('id', m.get('elemento_id', '')))
            if mid.upper() == element_id.upper():
                if obra and m.get('obra') != obra:
                    continue
                found.append({'tipo': t, 'meta': m})
    return found

def print_find_element(element_id, tipo=None, obra=None):
    results = find_element(element_id, tipo, obra)
    print(f'\n{C["bold"]}find-element:{C["reset"]} {C["yellow"]}{element_id}{C["reset"]}')
    if not results:
        print(f'  {C["red"]}Elemento não encontrado no corpus FAISS.{C["reset"]}')
        return
    for r in results:
        m = r['meta']
        t = r['tipo']
        tc = cor(t)
        print(f'\n  {tc}{t.upper()} {m.get("id","?")}{C["reset"]}  '
              f'obra={m.get("obra","?")}  pav={m.get("pavimento","?")}')
        d = m.get('dados', {})
        if t == 'pilar':
            print(f'    b={d.get("b","?")}cm  h={d.get("h","?")}cm  alt={d.get("altura","?")}cm  '
                  f'conf={d.get("confidence","?")}')
        elif t == 'viga':
            print(f'    b={d.get("b","?")}cm  h={d.get("h","?")}cm  comp={d.get("comprimento","?")}cm  '
                  f'conf={d.get("confidence","?")}')
        elif t == 'laje':
            print(f'    esp={d.get("espessura","?")}cm  area={d.get("area_cm2","?")}cm²  '
                  f'conf={d.get("confidence","?")}')
    print(f'\n  {C["dim"]}Total: {len(results)} ocorrência(s) no corpus{C["reset"]}')


# ── DIMS-REPORT ────────────────────────────────────────────────────────────────

def dims_report(tipo=None, obra=None):
    """Relatório de distribuição de dimensões do corpus FAISS."""
    tipos = [tipo] if tipo else ['pilar', 'viga', 'laje']

    print(f'\n{C["bold"]}=== DIMS REPORT — Distribuição do Corpus ==={C["reset"]}')
    if obra: print(f'  Filtrando por obra: {C["yellow"]}{obra}{C["reset"]}')

    for t in tipos:
        meta_path = FAISS_DIR / f'{t}s_meta.json'
        if not meta_path.exists():
            continue
        with open(meta_path, encoding='utf-8') as f:
            meta = json.load(f)

        if obra:
            meta = [m for m in meta if m.get('obra') == obra]

        if not meta:
            print(f'\n  {C["dim"]}[{t.upper()}] sem dados{C["reset"]}')
            continue

        tc = cor(t)
        print(f'\n  {tc}{C["bold"]}[{t.upper()}]{C["reset"]}  n={len(meta)}')

        dim_keys = {
            'pilar': [('b', 'cm'), ('h', 'cm'), ('altura', 'cm'), ('confidence', '')],
            'viga':  [('b', 'cm'), ('h', 'cm'), ('comprimento', 'cm'), ('confidence', '')],
            'laje':  [('espessura', 'cm'), ('area_cm2', 'cm²'), ('confidence', '')],
        }

        for campo, unidade in dim_keys.get(t, []):
            vals = []
            for m in meta:
                d = m.get('dados', {})
                v = d.get(campo)
                if v is not None:
                    try: vals.append(float(v))
                    except: pass
            if not vals:
                continue
            mn  = min(vals); mx = max(vals)
            avg = sum(vals) / len(vals)
            med = sorted(vals)[len(vals)//2]
            cov = f'{len(vals)}/{len(meta)}'
            u   = unidade
            print(f'    {campo:<15} min={mn:>8.1f}{u}  max={mx:>8.1f}{u}  '
                  f'avg={avg:>8.1f}{u}  med={med:>8.1f}{u}  cov={cov}')
    print()


# ── ANOMALIES ────────────────────────────────────────────────────────────────

def cmd_anomalies(obra: str, verbose: bool = False):
    """Executa AnomalyDetector para obra específica e exibe resultados."""
    try:
        from rag_anomaly_detector import AnomalyDetector
        from rag_pre_stog_gate    import carregar_elementos_fase3
    except ImportError as e:
        print(f'{C["red"]}[ERRO] rag_anomaly_detector não disponível: {e}{C["reset"]}')
        return

    OBRAS_DIR = Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS')
    obra_path = OBRAS_DIR / obra if not Path(obra).exists() else Path(obra)
    obra_nome = obra_path.name

    if not obra_path.exists():
        print(f'{C["red"]}[ERRO] Obra não encontrada: {obra_path}{C["reset"]}')
        return

    elementos = carregar_elementos_fase3(obra_path, obra_nome)
    if not elementos:
        print(f'{C["yellow"]}[SKIP] Nenhum elemento Fase 3 em {obra_nome}{C["reset"]}')
        return

    print(f'\n{C["bold"]}=== ANOMALY REPORT — {obra_nome} ==={C["reset"]}')
    print(f'  {len(elementos)} elementos carregados...\n')

    detector = AnomalyDetector()
    report   = detector.report_obra(obra_nome, elementos)

    # Resumo por categoria
    CAT_COR = {
        'NORMAL':   C['green'],
        'INCOMUM':  C['yellow'],
        'SUSPEITO': C['orange'],
        'ANÔMALO':  C['red'],
    }
    cats = [('NORMAL', report.normais), ('INCOMUM', report.incomuns),
            ('SUSPEITO', report.suspeitos), ('ANÔMALO', report.anomalos)]
    for cat, items in cats:
        if items:
            print(f'  {CAT_COR[cat]}{cat:<10}{C["reset"]} {len(items):>3} elementos')

    print(f'\n  Score médio: {C["bold"]}{report.score_medio:.4f}{C["reset"]}')
    print(f'  Gate:        {C["green"] if report.gate_status == "PASS" else C["red"]}'
          f'{report.gate_status}{C["reset"]}')
    print(f'  Bloqueados:  {len(report.bloqueados)}')

    if report.bloqueados:
        print(f'\n  {C["red"]}{C["bold"]}BLOQUEADOS:{C["reset"]}')
        for s in report.bloqueados:
            print(f'    {cor(s.tipo)}{s.tipo.upper()} {s.elemento_id}{C["reset"]}  '
                  f'anomaly={s.anomaly_score:.3f}  dim={s.dim_status}')
            for a in s.alertas_dim:
                print(f'      {C["red"]}dim: {a}{C["reset"]}')

    if verbose:
        print(f'\n  {C["dim"]}Suspeitos:{C["reset"]}')
        for s in report.suspeitos:
            print(f'    {cor(s.tipo)}{s.tipo.upper()} {s.elemento_id}{C["reset"]}  '
                  f'anomaly={s.anomaly_score:.3f}  sem={s.semantic_sim:.3f}')
    print()


# ── COMPARE-OBRAS ────────────────────────────────────────────────────────────

def compare_obras(obra_a: str, obra_b: str):
    """Compara distribuição de elementos entre duas obras."""
    print(f'\n{C["bold"]}=== COMPARE-OBRAS ==={C["reset"]}')
    print(f'  {C["yellow"]}A:{C["reset"]} {obra_a}  vs  {C["yellow"]}B:{C["reset"]} {obra_b}\n')

    tipos = [('pilar', C['orange']), ('viga', C['blue']), ('laje', C['green'])]
    for t, tc in tipos:
        meta_path = FAISS_DIR / f'{t}s_meta.json'
        if not meta_path.exists():
            continue
        with open(meta_path, encoding='utf-8') as f:
            meta = json.load(f)

        ea = [m for m in meta if m.get('obra') == obra_a]
        eb = [m for m in meta if m.get('obra') == obra_b]
        if not ea and not eb:
            continue

        print(f'  {tc}{C["bold"]}[{t.upper()}]{C["reset"]}')
        print(f'    Contagem:  A={len(ea)}  B={len(eb)}')

        dim_keys = {
            'pilar': [('b', 'cm'), ('h', 'cm'), ('altura', 'cm')],
            'viga':  [('b', 'cm'), ('h', 'cm'), ('comprimento', 'cm')],
            'laje':  [('espessura', 'cm'), ('area_cm2', 'cm²')],
        }

        for campo, unidade in dim_keys.get(t, []):
            def get_vals(entries):
                vals = []
                for m in entries:
                    v = m.get('dados', {}).get(campo)
                    if v is not None:
                        try: vals.append(float(v))
                        except: pass
                return vals

            va = get_vals(ea); vb = get_vals(eb)
            if not va and not vb:
                continue
            avg_a = sum(va)/len(va) if va else 0
            avg_b = sum(vb)/len(vb) if vb else 0
            delta = avg_b - avg_a
            delta_str = f'{C["red"]}{delta:+.1f}{C["reset"]}' if abs(delta) > 5 else f'{C["dim"]}{delta:+.1f}{C["reset"]}'
            print(f'    {campo:<14}  A: avg={avg_a:>7.1f}{unidade}  B: avg={avg_b:>7.1f}{unidade}  Δ={delta_str}')
        print()


# ── STATS ────────────────────────────────────────────────────────────────────

def print_stats():
    reg_path = FAISS_DIR / 'REGISTRY.json'
    if not reg_path.exists():
        print(f'{C["red"]}Índice não encontrado.{C["reset"]} Rode: python scripts/rag_ingestor.py --rebuild')
        return

    reg = json.load(open(reg_path, encoding='utf-8'))
    t   = reg.get('total', {})

    print(f'\n{C["bold"]}=== CAD-ANALYZER RAG — REGISTRY ==={C["reset"]}')
    print(f'  Última atualização: {C["yellow"]}{reg.get("ultima_atualizacao","?")}{C["reset"]}')
    print(f'  Total vetores:      {C["bold"]}{t.get("geral","?")}{C["reset"]}')
    print(f'  {C["orange"]}Pilares:{C["reset"]}  {t.get("pilares",0):>4}')
    print(f'  {C["blue"]}Vigas:  {C["reset"]}  {t.get("vigas",0):>4}')
    print(f'  {C["green"]}Lajes:  {C["reset"]}  {t.get("lajes",0):>4}')

    ingestoes = reg.get('ingestoes', [])
    print(f'\n  {C["bold"]}Obras ingeridas ({len(ingestoes)}):{C["reset"]}')
    for r in ingestoes:
        el = r.get('elementos', {})
        p  = el.get('pilar', 0)
        v  = el.get('viga', 0)
        l  = el.get('laje', 0)
        print(f'    {C["white"]}{r["obra"]:<30}{C["reset"]} '
              f'{C["orange"]}P={p:>3}{C["reset"]} '
              f'{C["blue"]}V={v:>3}{C["reset"]} '
              f'{C["green"]}L={l:>3}{C["reset"]} '
              f'total={r["total"]:>3}')

    # Verificar índices por tipo
    print(f'\n  {C["bold"]}Índices FAISS:{C["reset"]}')
    for nome in ['estruturais', 'pilares', 'vigas', 'lajes']:
        p = FAISS_DIR / f'{nome}.index'
        if p.exists():
            idx = faiss.read_index(str(p))
            size_kb = p.stat().st_size // 1024
            print(f'    {C["green"]}✓{C["reset"]} {nome:<20} {idx.ntotal:>4} vetores  ({size_kb} KB)')
        else:
            print(f'    {C["red"]}✗{C["reset"]} {nome:<20} não encontrado')

    print()

# ── EXEMPLOS ─────────────────────────────────────────────────────────────────

def print_examples():
    print(f'\n{C["bold"]}=== Exemplos de consulta ==={C["reset"]}')
    examples = [
        ('pilar 20x50', None, None),
        ('viga com comprimento maior que 500cm', 'viga', None),
        ('laje sintética sem contorno', 'laje', None),
        ('pilar cambotado com bulge', 'pilar', None),
        ('viga de balanço BA', 'viga', 'Obra_TREINO_1'),
        ('pilar com confidence alto', 'pilar', None),
        ('laje com h= detectado', 'laje', None),
    ]
    for q, t, o in examples:
        flags = ''
        if t: flags += f' --tipo {t}'
        if o: flags += f' --obra {o}'
        print(f'  python scripts/rag_query.py "{q}"{flags}')
    print()

# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='RAG Query — CAD-ANALYZER Semantic Search',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Exemplos:\n'
               '  python scripts/rag_query.py "pilar 20x50"\n'
               '  python scripts/rag_query.py "viga balanco" --tipo viga --k 3\n'
               '  python scripts/rag_query.py "laje sintetica" --tipo laje --obra Obra_TREINO_1\n'
    )
    parser.add_argument('query',   nargs='?', help='Texto da consulta semântica')
    parser.add_argument('--tipo',  choices=['pilar','viga','laje'], help='Filtrar por tipo de elemento')
    parser.add_argument('--obra',  help='Filtrar por obra específica')
    parser.add_argument('--k',     type=int, default=5, help='Número de resultados (default=5)')
    parser.add_argument('--threshold', type=float, default=0.20, help='Score mínimo (default=0.20)')
    parser.add_argument('--verbose', action='store_true', help='Mostrar texto embedado')
    parser.add_argument('--stats',          action='store_true', help='Mostrar estatísticas do índice')
    parser.add_argument('--examples',       action='store_true', help='Mostrar exemplos de uso')
    parser.add_argument('--find-element',   metavar='ID',        help='Buscar elemento por ID (P17, V5, L3)')
    parser.add_argument('--dims-report',    action='store_true', help='Relatório de distribuição de dimensões')
    parser.add_argument('--anomalies',      metavar='OBRA',      help='Detectar anomalias em obra específica')
    parser.add_argument('--compare-obras',  nargs=2,             metavar=('OBRA_A','OBRA_B'),
                                            help='Comparar distribuição entre duas obras')
    args = parser.parse_args()

    if args.stats:
        print_stats()
    elif args.examples:
        print_examples()
    elif getattr(args, 'find_element', None):
        print_find_element(args.find_element, tipo=args.tipo, obra=args.obra)
    elif getattr(args, 'dims_report', False):
        dims_report(tipo=args.tipo, obra=args.obra)
    elif getattr(args, 'anomalies', None):
        cmd_anomalies(args.anomalies, verbose=args.verbose)
    elif getattr(args, 'compare_obras', None):
        compare_obras(args.compare_obras[0], args.compare_obras[1])
    elif args.query:
        print(f'\n{C["bold"]}Consulta:{C["reset"]} {C["yellow"]}{args.query}{C["reset"]}', end='')
        if args.tipo: print(f'  tipo={C["white"]}{args.tipo}{C["reset"]}', end='')
        if args.obra: print(f'  obra={C["white"]}{args.obra}{C["reset"]}', end='')
        print(f'  k={args.k}')

        results = query(args.query, tipo=args.tipo, obra=args.obra,
                        k=args.k, threshold=args.threshold)

        if not results:
            print(f'\n{C["red"]}Nenhum resultado encontrado.{C["reset"]}')
            print(f'Tente reduzir --threshold (atual: {args.threshold}) ou ampliar a busca.')
        else:
            print(f'{C["dim"]}─── {len(results)} resultado(s) ───{C["reset"]}')
            for i, r in enumerate(results):
                print_result(i, r, verbose=args.verbose)
        print()
    else:
        parser.print_help()
        print_examples()
