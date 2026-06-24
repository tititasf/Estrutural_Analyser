# -*- coding: utf-8 -*-
"""
partes_pil.py - Segmentacao por partes (Modelo de Partes v1.1) para PIL.

PIL = 3 partes:
  VISAO_CIMA  - seccao transversal (pequena, em geral a esquerda no recorte)
  ABCD        - 4 faces em elevacao (maior, direita no recorte)
  GRADES      - grades com sarrafos tipados (presente so em recortes separados; N/A no 13_PAV)

Segmentacao:
  - N4: por faixa de X (ABCD: X < -3500, CIMA: -3500 < X < 2500, GRADES: X >= 2500)
  - Recorte: por cluster espacial (dois grupos de centroides X apos normalizacao)
  - Normalizacao de pose: translacao a origem; rotacao 0/90/180/270 (melhor alinhamento)

API:
  segmentar_n4(dxf_path)   -> {'ABCD': [...], 'CIMA': [...], 'GRADES': [...]}
  segmentar_recorte(dxf_path) -> {'ABCD': [...], 'CIMA': [...], 'GRADES': []}
  diff_partes(recorte_path, n4_path, partes=['ABCD','CIMA']) -> dict por parte
"""

import math
from collections import Counter, defaultdict
from pathlib import Path

try:
    import ezdxf
except ImportError:
    raise ImportError("ezdxf nao instalado: pip install ezdxf --break-system-packages")

from forma_canonica_pil import extrair_forma_canonica, diff_forma_canonica

# Limites X para N4 (coordenadas relativas do gerador)
N4_ABCD_X_MAX   = -3500   # entidades ABCD ficam em X < -3500
N4_CIMA_X_MIN   = -3500   # CIMA: -3500 < X < 2500
N4_CIMA_X_MAX   =  2500
N4_GRADES_X_MIN =  2500   # GRADES: X >= 2500

# Layers exclusivos de GRADES — sempre atribuidos a GRADES independente do centróide X
# (evita DIMENSION leaking para CIMA por ter ponto de texto em X=0)
GRADES_ONLY_LAYERS = frozenset(['SARR_2.2x10', 'SARR_3.5x7'])

# Tolerancias G2 (do masterplan)
TOL_GEOM_PCT   = 0.01   # comprimento geometrico +-1%
TOL_HATCH_PCT  = 0.02   # area hatch +-2%
TOL_TEXT_POS   = 2.0    # posicao texto +-2cm


def _centroid_x(entity):
    """Retorna coordenada X media da entidade (melhor esforco)."""
    dtype = entity.dxftype()

    # DIMENSION: dxf.insert é sempre (0,0,0) — usar defpoint/text_midpoint
    if dtype == 'DIMENSION':
        for attr in ('defpoint', 'text_midpoint', 'defpoint2'):
            try:
                return getattr(entity.dxf, attr).x
            except Exception:
                pass
        return None

    # HATCH: extrair X médio dos vértices do boundary path
    if dtype == 'HATCH':
        try:
            xs = []
            for path in entity.paths:
                if hasattr(path, 'vertices'):
                    xs.extend(v[0] for v in path.vertices if v)
                elif hasattr(path, 'edges'):
                    for edge in path.edges:
                        if hasattr(edge, 'start'):
                            xs.append(edge.start[0])
            if xs:
                return sum(xs) / len(xs)
        except Exception:
            pass
        return None

    pts = []
    try: pts.append(entity.dxf.start.x)
    except Exception: pass
    try: pts.append(entity.dxf.end.x)
    except Exception: pass
    try: pts.append(entity.dxf.insert.x)
    except Exception: pass
    try: pts.append(entity.dxf.center.x)
    except Exception: pass
    try:
        verts = list(entity.get_points())
        if verts:
            pts.extend(v[0] for v in verts)
    except Exception: pass
    if not pts:
        return None
    return sum(pts) / len(pts)


def _entity_length(entity):
    """Comprimento geometrico aproximado da entidade (cm)."""
    dtype = entity.dxftype()
    try:
        if dtype == 'LINE':
            s = entity.dxf.start
            e = entity.dxf.end
            return math.hypot(e.x - s.x, e.y - s.y)
        elif dtype in ('LWPOLYLINE', 'POLYLINE'):
            pts = list(entity.get_points())
            total = 0.0
            for i in range(1, len(pts)):
                total += math.hypot(pts[i][0]-pts[i-1][0], pts[i][1]-pts[i-1][1])
            return total
        elif dtype == 'ARC':
            r = entity.dxf.radius
            ang = (entity.dxf.end_angle - entity.dxf.start_angle) % 360
            return r * math.radians(ang)
        elif dtype == 'CIRCLE':
            return 2 * math.pi * entity.dxf.radius
    except Exception:
        pass
    return 0.0


def _entity_hatch_area(entity):
    """Area aproximada do hatch (cm2)."""
    if entity.dxftype() != 'HATCH':
        return 0.0
    try:
        total = 0.0
        for path in entity.paths:
            pts = []
            for edge in path.edges:
                if hasattr(edge, 'start'):
                    pts.append(edge.start)
            if len(pts) >= 3:
                n = len(pts)
                area = abs(sum(pts[i][0]*pts[(i+1)%n][1] - pts[(i+1)%n][0]*pts[i][1]
                               for i in range(n))) / 2
                total += area
        return total
    except Exception:
        return 0.0


def segmentar_n4(dxf_path):
    """
    Segmenta entidades do N4 nas 3 zonas por faixa de X.
    Retorna dict com listas de entidades por parte.
    GRADES sempre preenchida (para relatorio); excluida da comparacao com recortes 13_PAV.
    """
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    partes = {'ABCD': [], 'CIMA': [], 'GRADES': []}

    for e in msp:
        # Layers exclusivos de GRADES: sempre GRADES independente de centróide X
        # (DIMENSION entities têm insert point no CIMA range mas medem geometria em GRADES)
        try:
            layer = e.dxf.layer
        except Exception:
            layer = ''
        if layer in GRADES_ONLY_LAYERS:
            partes['GRADES'].append(e)
            continue

        cx = _centroid_x(e)
        if cx is None:
            partes['CIMA'].append(e)
            continue
        if cx < N4_ABCD_X_MAX:
            partes['ABCD'].append(e)
        elif cx < N4_CIMA_X_MAX:
            partes['CIMA'].append(e)
        else:
            partes['GRADES'].append(e)

    return partes


def segmentar_recorte(dxf_path):
    """
    Segmenta recorte N2 em VISAO_CIMA vs ABCD por clustering de X.
    Normaliza coordenadas para origem antes do clustering.
    Retorna dict com listas de entidades. GRADES sempre vazia para recortes N2.
    """
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    entities = list(msp)

    # Coletar todos os centroides X
    cx_vals = []
    cx_map = {}
    for e in entities:
        cx = _centroid_x(e)
        if cx is not None:
            cx_vals.append(cx)
            cx_map[id(e)] = cx

    if not cx_vals:
        return {'ABCD': entities, 'CIMA': [], 'GRADES': []}

    x_min = min(cx_vals)
    x_max = max(cx_vals)
    x_span = max(x_max - x_min, 1.0)

    # Encontrar ponto de corte entre CIMA (esquerda) e ABCD (direita)
    # Estrategia: o gap maior entre clusters define o corte
    sorted_xs = sorted(set(round(cx, 1) for cx in cx_vals))
    if len(sorted_xs) < 2:
        return {'ABCD': entities, 'CIMA': [], 'GRADES': []}

    # Encontrar maior gap
    gaps = [(sorted_xs[i+1] - sorted_xs[i], sorted_xs[i], sorted_xs[i+1])
            for i in range(len(sorted_xs)-1)]
    gaps.sort(reverse=True)
    best_gap, g_lo, g_hi = gaps[0]
    split_x = (g_lo + g_hi) / 2.0

    # Se nao ha gap claro (span < 10% total), tratar tudo como ABCD
    if best_gap < 0.05 * x_span:
        return {'ABCD': entities, 'CIMA': [], 'GRADES': []}

    partes = {'ABCD': [], 'CIMA': [], 'GRADES': []}
    for e in entities:
        cx = cx_map.get(id(e))
        if cx is None or cx > split_x:
            partes['ABCD'].append(e)
        else:
            partes['CIMA'].append(e)

    return partes


def metricas_parte(entities):
    """
    Calcula metricas deterministicas de uma lista de entidades (uma parte).
    Retorna dict com: contagens, geometria, textos, hatches.
    """
    contagem = Counter()       # (layer, dxftype) -> count
    geometria = defaultdict(float)  # layer -> comprimento total
    textos = []                # list of (layer, string)
    hatches = defaultdict(float)  # layer -> area total

    for e in entities:
        layer = getattr(e.dxf, 'layer', '0')
        dtype = e.dxftype()
        contagem[(layer, dtype)] += 1

        L = _entity_length(e)
        if L > 0:
            geometria[layer] += L

        if dtype in ('TEXT', 'MTEXT'):
            try: textos.append((layer, e.dxf.text.strip()))
            except:
                try: textos.append((layer, e.text.strip()))
                except: pass

        if dtype == 'HATCH':
            hatches[layer] += _entity_hatch_area(e)

    return {
        'contagem': dict(contagem),
        'geometria': dict(geometria),
        'textos': textos,
        'hatches': dict(hatches),
        'n_entidades': sum(contagem.values()),
    }


def diff_metricas(m_ref, m_n4, parte_nome='?'):
    """
    Compara metricas ref vs n4. Retorna diffs e gate result.
    """
    diffs = []

    # --- Contagem de entidades (exata) ---
    ref_cnt = m_ref['contagem']
    n4_cnt  = m_n4['contagem']
    all_keys = set(ref_cnt) | set(n4_cnt)
    for key in sorted(all_keys):
        r = ref_cnt.get(key, 0)
        n = n4_cnt.get(key, 0)
        if r != n:
            layer, dtype = key
            diffs.append({
                'tipo': 'contagem',
                'parte': parte_nome,
                'layer': layer,
                'dxftype': dtype,
                'ref': r,
                'n4': n,
                'delta': n - r,
                'pct': round((n-r)/max(r,1)*100, 1),
            })

    # --- Geometria (+-1%) ---
    ref_geom = m_ref['geometria']
    n4_geom  = m_n4['geometria']
    all_layers = set(ref_geom) | set(n4_geom)
    for layer in sorted(all_layers):
        r = ref_geom.get(layer, 0.0)
        n = n4_geom.get(layer, 0.0)
        if r > 0 and abs(n - r) / r > TOL_GEOM_PCT:
            diffs.append({
                'tipo': 'geometria',
                'parte': parte_nome,
                'layer': layer,
                'ref': round(r, 2),
                'n4': round(n, 2),
                'pct_diff': round(abs(n-r)/r*100, 2),
            })
        elif r == 0 and n > 0:
            diffs.append({
                'tipo': 'geometria_extra',
                'parte': parte_nome,
                'layer': layer,
                'ref': 0,
                'n4': round(n, 2),
            })

    # --- Textos (exatos) ---
    # Layers cujos textos NÃO são reproduzíveis pelo gerador STOG N4:
    #   NOMENCLATURA: labels de face (P18.A vs P18.C) e contagens "X sar" — o
    #     gerador gera as 4 faces ABCD enquanto o recorte mostra apenas a face
    #     visível da fachada; counts "X sar" dependem de dados não presentes na ficha.
    #   Texto Seção / texto: anotações especiais (CAMBOTA, CORTE A-A, ENCH.) —
    #     contexto de desenho humano não reproduzível automaticamente.
    _SKIP_TEXT_LAYERS = {
        'NOMENCLATURA', 'Texto Seção', 'TEXTO SECAO', 'TEXTO_SECAO',
        'Texto Secao', 'texto', 'TEXTO',
    }
    _skip_norm = {l.upper().strip() for l in _SKIP_TEXT_LAYERS}
    ref_texts = sorted(set(t for layer, t in m_ref['textos']
                           if layer.upper().strip() not in _skip_norm))
    n4_texts  = sorted(set(t for layer, t in m_n4['textos']
                           if layer.upper().strip() not in _skip_norm))
    missing = set(ref_texts) - set(n4_texts)
    extra   = set(n4_texts) - set(ref_texts)
    for txt in sorted(missing):
        diffs.append({'tipo': 'texto_ausente', 'parte': parte_nome, 'texto': txt})
    for txt in sorted(extra):
        diffs.append({'tipo': 'texto_extra', 'parte': parte_nome, 'texto': txt[:50]})

    # --- Hatches (+-2%) ---
    ref_h = m_ref['hatches']
    n4_h  = m_n4['hatches']
    all_h = set(ref_h) | set(n4_h)
    for layer in sorted(all_h):
        r = ref_h.get(layer, 0.0)
        n = n4_h.get(layer, 0.0)
        if r > 0 and abs(n - r) / r > TOL_HATCH_PCT:
            diffs.append({
                'tipo': 'hatch_area',
                'parte': parte_nome,
                'layer': layer,
                'ref': round(r, 2),
                'n4': round(n, 2),
                'pct_diff': round(abs(n-r)/r*100, 2),
            })

    gate = 'PASS' if not diffs else 'FAIL'
    return {
        'gate': 'G2',
        'parte': parte_nome,
        'resultado': gate,
        'n_diffs': len(diffs),
        'diffs': diffs,
        'ref_entidades': m_ref['n_entidades'],
        'n4_entidades':  m_n4['n_entidades'],
    }


def comparar_pil(recorte_path, n4_path, partes_ativas=None, verbose=True):
    """
    Compara PIL recorte vs N4 por parte.
    partes_ativas: lista de partes a comparar. Default: ['ABCD', 'CIMA']
                   (GRADES excluida por padrao - nao existe no recorte 13_PAV)
    """
    if partes_ativas is None:
        partes_ativas = ['ABCD', 'CIMA']

    seg_rec = segmentar_recorte(str(recorte_path))
    seg_n4  = segmentar_n4(str(n4_path))

    resultados = {}

    for parte in partes_ativas:
        ents_rec = seg_rec.get(parte, [])
        ents_n4  = seg_n4.get(parte, [])

        if not ents_rec:
            resultados[parte] = {
                'gate': 'G2', 'parte': parte,
                'resultado': 'N/A', 'motivo': 'Parte ausente no recorte',
                'ref_entidades': 0, 'n4_entidades': len(ents_n4),
            }
            continue

        m_ref = metricas_parte(ents_rec)
        m_n4  = metricas_parte(ents_n4)

        res = diff_metricas(m_ref, m_n4, parte)
        resultados[parte] = res

        if verbose:
            status = res['resultado']
            print(f"  G2/{parte}: {status}  ref={res['ref_entidades']} n4={res['n4_entidades']}  diffs={res['n_diffs']}")
            if res.get('diffs'):
                for d in res['diffs'][:8]:
                    if d['tipo'] == 'contagem':
                        print(f"    cnt ({d['layer']},{d['dxftype']}): ref={d['ref']} n4={d['n4']} delta={d['delta']}")
                    elif d['tipo'] == 'geometria':
                        print(f"    geom {d['layer']}: ref={d['ref']:.1f} n4={d['n4']:.1f} diff={d['pct_diff']:.1f}%")
                    elif d['tipo'] in ('texto_ausente','texto_extra'):
                        print(f"    {d['tipo']}: '{d.get('texto','')[:40]}'")
                if res['n_diffs'] > 8:
                    print(f"    ... +{res['n_diffs']-8} diffs")

    # GRADES: sempre reportar como N/A se nao comparada
    if 'GRADES' not in partes_ativas:
        grades_n = len(seg_n4.get('GRADES', []))
        resultados['GRADES'] = {
            'gate': 'G2', 'parte': 'GRADES',
            'resultado': 'N/A',
            'motivo': 'Parte GRADES ausente nos recortes do 13_PAV',
            'ref_entidades': 0, 'n4_entidades': grades_n,
        }
        if verbose and grades_n > 0:
            print(f"  G2/GRADES: N/A (excluido - {grades_n} entidades no N4 nao comparadas)")

    return resultados


# Partes ja cobertas pelo extrator de forma canonica (§G2 v1.2).
# AR-1' item 3: ABCD validado 32/35 (sessao 2026-06-13), CIMA validado 32/35
# na sequencia (mesma regua + normalizacao de "Texto Seção" CIMA: empty TEXT
# e rotulos de material SAR/CHP/CONC/GRV -> texto_vazio/texto_convencao_robo).
# GRADES permanece fora (N/A no 13_PAV).
CANONICO_PARTES_PRONTAS = frozenset(['ABCD', 'CIMA'])


def comparar_pil_canonico(recorte_path, n4_path, partes_ativas=None, verbose=True):
    """
    Compara PIL recorte vs N4 por parte usando a FORMA CANONICA (§G2 v1.2):
    paineis[] (fôrma: painel/sarrafo/chapa/perfil/hachura, contagem + tamanho +-0.5cm),
    cotas[] (valores + contagem), textos[] (conteudos + contagem).

    partes_ativas: default ['ABCD', 'CIMA']. GRADES nunca entra (N/A no 13_PAV).
    Partes fora de CANONICO_PARTES_PRONTAS sao reportadas como 'PENDENTE'
    (nao contam para PASS/FAIL do item; ABCD primeiro, depois CIMA - ordem do usuario).
    """
    if partes_ativas is None:
        partes_ativas = ['ABCD', 'CIMA']

    seg_rec = segmentar_recorte(str(recorte_path))
    seg_n4 = segmentar_n4(str(n4_path))

    resultados = {}

    for parte in partes_ativas:
        ents_rec = seg_rec.get(parte, [])
        ents_n4 = seg_n4.get(parte, [])

        if not ents_rec:
            resultados[parte] = {
                'gate': 'G2', 'parte': parte,
                'resultado': 'N/A', 'motivo': 'Parte ausente no recorte',
                'ref_entidades': 0, 'n4_entidades': len(ents_n4),
            }
            continue

        if parte not in CANONICO_PARTES_PRONTAS:
            resultados[parte] = {
                'gate': 'G2', 'parte': parte,
                'resultado': 'PENDENTE',
                'motivo': 'Regua canonica ainda nao avaliada para esta parte (AR-1\': ABCD primeiro)',
                'ref_entidades': len(ents_rec), 'n4_entidades': len(ents_n4),
            }
            if verbose:
                print(f"  G2/{parte}: PENDENTE (regua canonica ainda nao avaliada)")
            continue

        fc_ref = extrair_forma_canonica(ents_rec, 'recorte')
        fc_n4 = extrair_forma_canonica(ents_n4, 'n4')
        diff = diff_forma_canonica(fc_ref, fc_n4)

        resultados[parte] = {
            'gate': 'G2', 'parte': parte,
            'resultado': diff['gate'],
            'forma_canonica_ref': fc_ref.to_dict(),
            'forma_canonica_n4': fc_n4.to_dict(),
            'diff': diff,
            'ref_entidades': len(ents_rec), 'n4_entidades': len(ents_n4),
        }

        if verbose:
            print(f"  G2/{parte} (canonico): {diff['gate']}")
            print(f"    paineis: {'PASS' if diff['paineis']['pass'] else 'FAIL'}")
            for cat, det in diff['paineis']['detalhe'].items():
                if not det['pass']:
                    print(f"      {cat}: ref={det['ref_count']} n4={det['n4_count']} casados={det['casados']}"
                          f" so_ref={det['so_ref'][:3]} so_n4={det['so_n4'][:3]}")
            cd = diff['cotas']['detalhe']
            print(f"    cotas: {'PASS' if diff['cotas']['pass'] else 'FAIL'}"
                  f" ref={cd['ref_count']} n4={cd['n4_count']} casados={cd['casados']}")
            if not diff['cotas']['pass']:
                print(f"      so_ref={cd['so_ref']}")
                print(f"      so_n4={cd['so_n4']}")
            td = diff['textos']['detalhe']
            print(f"    textos: {'PASS' if diff['textos']['pass'] else 'FAIL'}"
                  f" ref={td['ref_count']} n4={td['n4_count']} casados={td['casados']}")
            if not diff['textos']['pass']:
                print(f"      so_ref={td['so_ref']}")
                print(f"      so_n4={td['so_n4']}")

    if 'GRADES' not in partes_ativas:
        grades_n = len(seg_n4.get('GRADES', []))
        resultados['GRADES'] = {
            'gate': 'G2', 'parte': 'GRADES',
            'resultado': 'N/A',
            'motivo': 'Parte GRADES ausente nos recortes do 13_PAV',
            'ref_entidades': 0, 'n4_entidades': grades_n,
        }

    return resultados

    