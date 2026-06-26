#!/usr/bin/env python3
"""
RAG Ingestor — CAD-ANALYZER
Popula FAISS com dados estruturais reais das obras de treino.
Uso: python scripts/rag_ingestor.py [--obra Obra_TREINO_1] [--rebuild]
"""
import sys, os, json, argparse, datetime
from pathlib import Path

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from rag_tier import get_tier, is_indexable, load_tombstones

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OBRAS_DIR  = Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS')
FAISS_DIR  = Path('D:/Agente-cad-PYSIDE/data/vectors/faiss')
FAISS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_NAME = 'all-MiniLM-L6-v2'
EMBED_DIM  = 384

# ── HELPERS ─────────────────────────────────────────────────────────────────

def load_model():
    print(f'[MODEL] Carregando {MODEL_NAME}...')
    return SentenceTransformer(MODEL_NAME)

def normalize(vecs):
    """L2-normalize para cosine similarity com FAISS FlatIP."""
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return (vecs / norms).astype(np.float32)

# ── FORMATADORES DE TEXTO (o que vai ser embedado) ──────────────────────────

def fmt_pilar(id_, data, obra, pav):
    b    = data.get('b') or data.get('largura') or '?'
    h    = data.get('h') or data.get('comprimento') or '?'
    alt  = data.get('altura', '?')
    conf = data.get('confidence', '?')
    src  = data.get('source', '')
    faces = ' '.join(data.get('faces_encontradas', data.get('sides', [])))
    nota = data.get('nota', '')
    bh_src = data.get('bh_source', '')
    return (
        f"Pilar {id_}, Obra: {obra}, Pavimento: {pav}, "
        f"b={b}cm h={h}cm altura={alt}cm, "
        f"confidence={conf}, source={src}, bh_source={bh_src}, "
        f"faces=[{faces}], nota={nota}"
    )

def fmt_viga(id_, data, obra, pav):
    b    = data.get('b', '?')
    h    = data.get('h', '?')
    comp = data.get('comprimento', '?')
    conf = data.get('confidence', '?')
    src  = data.get('source', '')
    sides = ' '.join(data.get('sides', data.get('sides_encontrados', [])))
    nota = data.get('nota', '')
    return (
        f"Viga {id_}, Obra: {obra}, Pavimento: {pav}, "
        f"b={b}cm h={h}cm comprimento={comp}cm, "
        f"confidence={conf}, source={src}, "
        f"sides=[{sides}], nota={nota}"
    )

def fmt_laje(id_, data, obra, pav):
    comp = data.get('comprimento', '?')
    larg = data.get('largura', '?')
    area = data.get('area_cm2', '?')
    conf = data.get('confidence', '?')
    src  = data.get('source', '')
    modo = data.get('modo_selecionado', '')
    nota = data.get('nota', '')
    n_coords = len(data.get('coordenadas', data.get('outline_segs', [])))
    return (
        f"Laje {id_}, Obra: {obra}, Pavimento: {pav}, "
        f"comprimento={comp}cm largura={larg}cm area={area}cm2, "
        f"confidence={conf}, source={src}, modo={modo}, "
        f"n_vertices={n_coords}, nota={nota}"
    )

# ── CARREGADORES DE DADOS ────────────────────────────────────────────────────

def _load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            return json.load(f)
    except Exception as e:
        print(f'  [WARN] Erro ao ler {path}: {e}')
        return {}

def coletar_elementos_obra(obra_path, obra_nome):
    """Retorna lista de (texto, metadata) para todos os elementos da obra."""
    fase3 = obra_path / 'Fase-3_Interpretacao_Extracao'
    if not fase3.exists():
        return []

    elementos = []

    # ── PILARES ──
    for fname in ['pilares_ground_truth.json', 'pilares_bh.json', 'pilares.json']:
        data = _load_json(fase3 / 'Pilares' / fname)
        if data:
            for pid, pdata in data.items():
                if not isinstance(pdata, dict): continue
                # Tentar detectar pavimento a partir do nome do arquivo ou pasta
                pav = '1_PAV'
                txt = fmt_pilar(pid, pdata, obra_nome, pav)
                elementos.append({
                    'text': txt,
                    'tipo': 'pilar',
                    'id': pid,
                    'obra': obra_nome,
                    'pavimento': pav,
                    'arquivo_fonte': fname,
                    'dados': pdata,
                })
            break  # usar apenas o primeiro arquivo encontrado

    # ── VIGAS ──
    for fname in ['vigas_ground_truth.json', 'vigas.json']:
        data = _load_json(fase3 / 'Vigas' / fname)
        if data:
            for vid, vdata in data.items():
                if not isinstance(vdata, dict): continue
                pav = '1_PAV'
                txt = fmt_viga(vid, vdata, obra_nome, pav)
                elementos.append({
                    'text': txt,
                    'tipo': 'viga',
                    'id': vid,
                    'obra': obra_nome,
                    'pavimento': pav,
                    'arquivo_fonte': fname,
                    'dados': vdata,
                })
            break

    # ── LAJES (Fase-3) ──
    for fname in ['lajes_ground_truth.json', 'lajes.json', 'lajes_data.json']:
        data = _load_json(fase3 / 'Lajes' / fname)
        if data:
            for lid, ldata in data.items():
                if not isinstance(ldata, dict): continue
                pav = '1_PAV'
                txt = fmt_laje(lid, ldata, obra_nome, pav)
                elementos.append({
                    'text': txt,
                    'tipo': 'laje',
                    'id': lid,
                    'obra': obra_nome,
                    'pavimento': pav,
                    'arquivo_fonte': fname,
                    'dados': ldata,
                })
            break

    # ── FASE-4: Suplementar com dados atualizados (dims reais) ──
    fase4 = obra_path / 'Fase-4_Sincronizacao'
    if fase4.exists():
        # Lajes Fase-4 (JSONs individuais com dims reais — SUBSTITUI Fase-3 se melhor)
        lj_dir = fase4 / 'JSON_Lajes'
        if lj_dir.exists():
            laje_ids_fase3 = {e['id'] for e in elementos if e['tipo'] == 'laje'}
            for jf in sorted(lj_dir.glob('L*.json')):
                ldata = _load_json(jf)
                lid = ldata.get('nome', jf.stem)
                comp = ldata.get('comprimento', 0)
                if comp and comp > 100:
                    # Remove versão Fase-3 se existir (dados piores)
                    elementos = [e for e in elementos if not (e['tipo'] == 'laje' and e['id'] == lid)]
                    pav = ldata.get('pavimento', '1_PAV')
                    txt = fmt_laje(lid, ldata, obra_nome, pav)
                    elementos.append({
                        'text': txt, 'tipo': 'laje', 'id': lid,
                        'obra': obra_nome, 'pavimento': pav,
                        'arquivo_fonte': jf.name, 'dados': ldata,
                    })

        # Pilares Fase-4 (JSONs com grade_1 atualizado)
        pl_dir = fase4 / 'JSON_Pilares'
        if pl_dir.exists():
            pilar_ids_fase3 = {e['id'] for e in elementos if e['tipo'] == 'pilar'}
            for jf in sorted(pl_dir.glob('P*.json')):
                pdata = _load_json(jf)
                pid = jf.stem
                grade_1 = float(pdata.get('grade_1', 0))
                if grade_1 > 0 and pid not in pilar_ids_fase3:
                    pav = pdata.get('pavimento', '1_PAV')
                    pdata['source'] = 'fase-4-json'
                    pdata['confidence'] = 0.7
                    txt = fmt_pilar(pid, pdata, obra_nome, pav)
                    elementos.append({
                        'text': txt, 'tipo': 'pilar', 'id': pid,
                        'obra': obra_nome, 'pavimento': pav,
                        'arquivo_fonte': jf.name, 'dados': pdata,
                    })

    return elementos

# ── INGESTÃO ────────────────────────────────────────────────────────────────

def ingerir_obras(obras=None, rebuild=False):
    model = None
    tombstones = load_tombstones()

    # Carregar índices existentes ou criar novos
    index_path  = FAISS_DIR / 'estruturais.index'
    meta_path   = FAISS_DIR / 'estruturais_meta.json'
    registry_path = FAISS_DIR / 'REGISTRY.json'

    if rebuild or not index_path.exists():
        index    = faiss.IndexFlatIP(EMBED_DIM)
        all_meta = []
        registry = {'ingestoes': [], 'total': {'pilares': 0, 'vigas': 0, 'lajes': 0}}
        print('[FAISS] Criando índice novo (rebuild)')
    else:
        index    = faiss.read_index(str(index_path))
        all_meta = json.load(open(meta_path, encoding='utf-8')) if meta_path.exists() else []
        registry = json.load(open(registry_path, encoding='utf-8')) if registry_path.exists() else \
                   {'ingestoes': [], 'total': {'pilares': 0, 'vigas': 0, 'lajes': 0}}
        print(f'[FAISS] Índice existente: {index.ntotal} vetores')

    # Descobrir obras
    if obras:
        obra_dirs = [OBRAS_DIR / o for o in obras]
    else:
        obra_dirs = sorted([d for d in OBRAS_DIR.iterdir() if d.is_dir()])

    total_novos = {'pilares': 0, 'vigas': 0, 'lajes': 0}

    for obra_path in obra_dirs:
        obra_nome = obra_path.name
        # Verificar se já foi ingerida (skip se não é rebuild)
        ja_ingerida = any(r['obra'] == obra_nome for r in registry['ingestoes'])
        if ja_ingerida and not rebuild:
            print(f'  [SKIP] {obra_nome} já ingerida')
            continue

        print(f'  [OBRA] {obra_nome}...')
        elementos = coletar_elementos_obra(obra_path, obra_nome)
        if not elementos:
            print(f'    [WARN] Nenhum elemento encontrado em {obra_nome}')
            continue

        indexaveis = []
        quarantined = {}
        for elem in elementos:
            tier = get_tier(elem, tombstones=tombstones)
            elem['tier'] = tier
            if is_indexable(elem, tombstones=tombstones):
                indexaveis.append(elem)
            else:
                quarantined[tier] = quarantined.get(tier, 0) + 1

        if quarantined:
            print(f'    [GUARD] {sum(quarantined.values())} elemento(s) recusados pelo tier: {quarantined}')
        if not indexaveis:
            print('    [SKIP] Nenhum elemento T1+ para indexar (quarentena preservada)')
            continue
        elementos = indexaveis

        if model is None:
            model = load_model()
        textos = [e['text'] for e in elementos]
        vecs   = model.encode(textos, show_progress_bar=False, batch_size=64)
        vecs   = normalize(vecs)

        index.add(vecs)

        offset = len(all_meta)
        for i, elem in enumerate(elementos):
            elem['faiss_id'] = offset + i
            all_meta.append(elem)
            total_novos[elem['tipo']] = total_novos.get(elem['tipo'], 0) + 1

        # Registrar ingestão
        por_tipo = {}
        for e in elementos:
            por_tipo[e['tipo']] = por_tipo.get(e['tipo'], 0) + 1

        registry['ingestoes'].append({
            'obra': obra_nome,
            'data': datetime.datetime.now().isoformat(),
            'elementos': por_tipo,
            'total': len(elementos),
        })
        print(f'    [OK] {len(elementos)} elementos ({por_tipo})')

    # Atualizar totais no registry (elementos usam singular, totais usam plural)
    MAP = {'pilar': 'pilares', 'viga': 'vigas', 'laje': 'lajes'}
    for sing, plur in MAP.items():
        registry['total'][plur] = sum(
            r['elementos'].get(sing, 0) for r in registry['ingestoes']
        )
    registry['total']['geral'] = index.ntotal
    registry['ultima_atualizacao'] = datetime.datetime.now().isoformat()

    # Salvar
    faiss.write_index(index, str(index_path))
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(all_meta, f, ensure_ascii=False, indent=2)
    with open(registry_path, 'w', encoding='utf-8') as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)

    # Índices separados por tipo (plural correto em português)
    PLURAL = {'pilar': 'pilares', 'viga': 'vigas', 'laje': 'lajes'}
    for tipo in ['pilar', 'viga', 'laje']:
        tipo_meta = [m for m in all_meta if m['tipo'] == tipo]
        if not tipo_meta:
            continue
        if model is None:
            model = load_model()
        nome = PLURAL[tipo]
        tipo_idx   = faiss.IndexFlatIP(EMBED_DIM)
        tipo_texts = [m['text'] for m in tipo_meta]
        tipo_vecs  = model.encode(tipo_texts, show_progress_bar=False, batch_size=64)
        tipo_vecs  = normalize(tipo_vecs)
        tipo_idx.add(tipo_vecs)
        faiss.write_index(tipo_idx, str(FAISS_DIR / f'{nome}.index'))
        with open(FAISS_DIR / f'{nome}_meta.json', 'w', encoding='utf-8') as f:
            json.dump(tipo_meta, f, ensure_ascii=False, indent=2)
        print(f'[FAISS] Índice {nome}: {tipo_idx.ntotal} vetores')

    print(f'\n[CONCLUÍDO]')
    print(f'  Total no índice: {index.ntotal} vetores')
    print(f'  Pilares: {registry["total"]["pilares"]}')
    print(f'  Vigas:   {registry["total"]["vigas"]}')
    print(f'  Lajes:   {registry["total"]["lajes"]}')
    print(f'  Índice salvo: {index_path}')
    print(f'  Registry:     {registry_path}')
    return registry

# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='RAG Ingestor — CAD-ANALYZER')
    parser.add_argument('--obra', nargs='+', help='Obras específicas a ingerir')
    parser.add_argument('--rebuild', action='store_true', help='Rebuild completo do índice')
    parser.add_argument('--stats', action='store_true', help='Mostrar estatísticas do índice atual')
    args = parser.parse_args()

    if args.stats:
        reg_path = FAISS_DIR / 'REGISTRY.json'
        if reg_path.exists():
            reg = json.load(open(reg_path, encoding='utf-8'))
            print(f'=== REGISTRY CAD-ANALYZER RAG ===')
            print(f'Total vetores: {reg["total"].get("geral","?")}')
            print(f'Pilares: {reg["total"].get("pilares",0)}')
            print(f'Vigas:   {reg["total"].get("vigas",0)}')
            print(f'Lajes:   {reg["total"].get("lajes",0)}')
            print(f'Última atualização: {reg.get("ultima_atualizacao","")}')
            print(f'Obras ingeridas:')
            for r in reg.get('ingestoes', []):
                print(f'  {r["obra"]}: {r["total"]} elementos {r["elementos"]}')
        else:
            print('Índice não encontrado. Rode: python scripts/rag_ingestor.py')
    else:
        ingerir_obras(obras=args.obra, rebuild=args.rebuild)
