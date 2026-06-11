#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engenharia_reversa_dxf.py — Extração de ground truth a partir de DXFs de entrega STOG.

Lê os DXFs finais (PL=Pilares, LV=Vigas Laterais, FV=Fundos Vigas, LJ=Lajes)
e extrai as fichas de referência (ground truth) para a obra.

Confiança dos dados extraídos:
  - Nomes/IDs dos elementos: ALTA (extraído de labels MTEXT no DXF)
  - Contagem de elementos: ALTA (contagem de labels únicos)
  - Altura (Pé Direito): MEDIA (extraído de DIMENSION com texto "Pé DIREITO")
  - B e H: BAIXA (requer parsing espacial complexo — marcado confidence=0.3)

CLI:
  python scripts/engenharia_reversa_dxf.py \\
    --obra ../DADOS-OBRAS/Obra_TREINO_21 \\
    --pavimento "12 PAV"
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# ── Item 4: MTEXT format-code stripper ───────────────────────────────────────
# MTEXT raw group-code 1 embeds control sequences like {\fRomans|b0;P1\H0.7x;{30}}
# that our streaming parser previously passed through verbatim.
_RE_MTEXT_COLOR    = re.compile(r'\\[Cc]\d+;')
_RE_MTEXT_HEIGHT   = re.compile(r'\\[Hh][\d.]+[xX]?;?')
_RE_MTEXT_WIDTH    = re.compile(r'\\[Ww][\d.]+;')
_RE_MTEXT_OBLIQUE  = re.compile(r'\\[Qq][\d.]+;')
_RE_MTEXT_TRACKING = re.compile(r'\\[Tt][\d.]+;')
_RE_MTEXT_ALIGN    = re.compile(r'\\[Aa]\d+;')
_RE_MTEXT_FONT     = re.compile(r'\\[fF][^|;{}]*(?:\|[^;{}]*)*;')
_RE_MTEXT_PARA_SET = re.compile(r'\\p[ilqt][^;]*;')  # \pi, \pl, \pq, \pt
_RE_MTEXT_STACK    = re.compile(r'\\S([^;^{}]*)\^([^;{}]*);')
_RE_MTEXT_TOGGLE   = re.compile(r'\\[LlOoKk]')
_RE_MTEXT_NBSP     = re.compile(r'\\~')
_RE_MTEXT_PARA     = re.compile(r'\\[Pp]')
_RE_MTEXT_ESCSEMI  = re.compile(r'\\;')


def _clean_mtext_format(raw: str) -> str:
    """Limpa códigos de formatação MTEXT deixando apenas o texto puro."""
    s = raw
    s = _RE_MTEXT_PARA.sub('\n', s)       # \P → quebra de parágrafo
    s = _RE_MTEXT_NBSP.sub(' ', s)         # \~ → espaço normal
    s = _RE_MTEXT_STACK.sub(r'\1', s)      # \S{a}^{b}; → mantém numerador
    s = _RE_MTEXT_COLOR.sub('', s)
    s = _RE_MTEXT_HEIGHT.sub('', s)
    s = _RE_MTEXT_WIDTH.sub('', s)
    s = _RE_MTEXT_OBLIQUE.sub('', s)
    s = _RE_MTEXT_TRACKING.sub('', s)
    s = _RE_MTEXT_ALIGN.sub('', s)
    s = _RE_MTEXT_FONT.sub('', s)
    s = _RE_MTEXT_PARA_SET.sub('', s)
    s = _RE_MTEXT_TOGGLE.sub('', s)
    s = _RE_MTEXT_ESCSEMI.sub(';', s)
    s = s.replace('{', '').replace('}', '')
    s = s.replace('%%c', 'Ø').replace('%%C', 'Ø')
    s = s.replace('%%d', '°').replace('%%D', '°')
    s = s.replace('%%p', '±').replace('%%P', '±')
    return s.strip()
# ─────────────────────────────────────────────────────────────────────────────


def _load_ezdxf():
    try:
        import ezdxf
        return ezdxf
    except ImportError:
        print("[ERROR] ezdxf nao instalado: pip install ezdxf")
        sys.exit(1)


def _stream_text_entities(dxf_path: Path) -> list[dict]:
    """
    Parser streaming de DXF: lê apenas entidades TEXT/MTEXT/DIMENSION
    sem carregar o arquivo inteiro na memória (ezdxf usa 5-7x o tamanho do arquivo).
    Retorna lista de dicts com keys: type, layer, text, measurement.
    Suporta ASCII e CP1252 com fallback UTF-8.
    """
    WANT_TYPES = {'TEXT', 'MTEXT', 'DIMENSION'}
    results = []

    for encoding in ('utf-8', 'cp1252', 'latin-1'):
        try:
            with open(dxf_path, 'r', encoding=encoding, errors='replace') as fh:
                lines = fh.readlines()
            break
        except Exception:
            continue
    else:
        return results

    i = 0
    n = len(lines)
    while i < n:
        code = lines[i].strip()
        if code == '0' and i + 1 < n:
            etype = lines[i + 1].strip().upper()
            if etype in WANT_TYPES:
                entity = {'type': etype, 'layer': '0', 'text': '', 'measurement': None, 'x': None, 'y': None}
                i += 2
                while i < n:
                    c = lines[i].strip()
                    if c == '0':  # next entity
                        break
                    val = lines[i + 1].strip() if i + 1 < n else ''
                    if c == '8':
                        entity['layer'] = val
                    elif c == '1':
                        if etype == 'MTEXT':
                            entity['text'] = _clean_mtext_format(val)
                        else:
                            entity['text'] = val.replace('\\P', '\n').replace('\\p', '\n')
                    elif c == '10' and entity['x'] is None:
                        try:
                            entity['x'] = float(val)
                        except ValueError:
                            pass
                    elif c == '20' and entity['y'] is None:
                        try:
                            entity['y'] = float(val)
                        except ValueError:
                            pass
                    elif c == '42' and etype == 'DIMENSION':
                        try:
                            entity['measurement'] = float(val)
                        except ValueError:
                            pass
                    i += 2
                results.append(entity)
                continue
        i += 1

    return results


def _find_dxf(rev_dir: Path, pattern: str) -> Path | None:
    """Encontra DXF por padrão glob (case insensitive)."""
    for f in rev_dir.iterdir():
        if f.suffix.upper() == '.DXF' and pattern.upper() in f.name.upper():
            return f
    return None


def _extract_pl_data(dxf_path: Path, ezdxf=None) -> tuple[dict, float | None, dict]:
    """
    Lê PL DXF via parser streaming (sem ezdxf) — usa ~1% da RAM do ezdxf.
    Extrai pilar_data, pe_direito e bh_dims em single-pass.
    Retorna: (pilar_data, pe_direito, bh_dims)
    """
    entities = _stream_text_entities(dxf_path)

    s1, s2, s3 = {}, {}, {}
    pe_direito = None

    for ent in entities:
        etype = ent['type']
        txt = ent['text'].strip()
        layer = ent['layer']
        layer_up = layer.upper()

        if etype == 'DIMENSION':
            if pe_direito is None and any(k in txt.upper() for k in ('DIREITO', 'ALTURA')):
                m = ent.get('measurement')
                if m and 200 <= m <= 1500:
                    pe_direito = round(m, 1)
            continue

        matches = re.findall(r'[Pp](\d+)[._]([A-H])', txt)
        if not matches:
            continue

        if any(tl in layer_up for tl in ('TEXTO SE', 'TEXTO_SE', 'SECAO')):
            target = s1
        elif layer_up == 'NOMENCLATURA':
            target = s2
        elif layer == '0':
            target = s3
        else:
            continue

        for num, face in matches:
            pid = f'P{num}'
            if pid not in target:
                target[pid] = {'faces': set()}
            target[pid]['faces'].add(face)

    # Merge: S1 prioritário, S2/S3 só se insuficiente
    pilar_data = dict(s1)
    if len(pilar_data) < 3:
        for pid, data in s2.items():
            if pid not in pilar_data:
                pilar_data[pid] = data
            else:
                pilar_data[pid]['faces'].update(data['faces'])
    if len(pilar_data) < 3:
        for pid, data in s3.items():
            if pid not in pilar_data:
                pilar_data[pid] = data
            else:
                pilar_data[pid]['faces'].update(data['faces'])

    bh_dims = _extract_bh_dims_spatial(entities)
    return pilar_data, pe_direito, bh_dims


_VEM_DA_VIGA = re.compile(r'VEM\s+DA\s+V\d+', re.IGNORECASE)


def _add_viga_ids_from_text(txt: str, viga_data: dict) -> None:
    """Extrai IDs de vigas de um texto e adiciona a viga_data (sem posicao)."""
    # Formato composto: (VA2+V16+V17).A
    compound = re.match(r'\(([^)]+)\)\.([A-Z])', txt, re.IGNORECASE)
    if compound:
        face = compound.group(2).upper()
        inner = compound.group(1)
        for vid_raw in re.findall(r'[Vv][Gg]?(\d+[A-Z]?)', inner):
            if len(vid_raw) > 4:
                continue
            vid = f'V{vid_raw.upper()}'
            if vid not in viga_data:
                viga_data[vid] = {'sides': set()}
            viga_data[vid]['sides'].add(face)
        return

    # Formato grupo dash/plus com face no ultimo: "V524-V727-V525.A"
    trailing_face = re.match(r'^(V\d+(?:[+\-]V\d+)+)\.([A-Z])$', txt.strip(), re.IGNORECASE)
    if trailing_face:
        face = trailing_face.group(2).upper()
        for num in re.findall(r'V(\d+)', trailing_face.group(1), re.IGNORECASE):
            if 1 <= len(num) <= 4:
                vid = 'V' + num.upper()
                if vid not in viga_data:
                    viga_data[vid] = {'sides': set()}
                viga_data[vid]['sides'].add(face)
        return

    matches = re.findall(r'[Vv][Gg]?(\d+[A-Z]?)[._]([A-H])', txt)
    for num, side in matches:
        if len(num) > 4:
            continue
        vid = f'V{num.upper()}'
        if vid not in viga_data:
            viga_data[vid] = {'sides': set()}
        viga_data[vid]['sides'].add(side)

    if not matches:
        for num in re.findall(r'\b[Vv](\d+)\b', txt):
            vid = f'V{num}'
            if vid not in viga_data:
                viga_data[vid] = {'sides': set()}


def _extract_viga_ids_from_lv(dxf_path: Path, ezdxf=None) -> dict:
    """Lê LV DXF via ezdxf (apenas MSP) e extrai IDs de vigas.

    Usa a mesma lógica de extrair_vigas_lv.py para garantir consistência entre
    GT e extração:
      - Passa 1a-1c: layers NOMENCLATURA, Texto Seção*, TEXTO (sem VEM DA)
      - Passo 3: scan de blocos CARIMBO para confirmed_ids
      - Passo 4: VEM DA recovery para vigas confirmadas no bloco CARIMBO
    """
    if ezdxf is None:
        try:
            import ezdxf as _ezdxf
            ezdxf = _ezdxf
        except ImportError:
            # Fallback ao parser streaming se ezdxf indisponivel
            entities = _stream_text_entities(dxf_path)
            viga_data = {}
            for ent in entities:
                if ent['type'] not in ('TEXT', 'MTEXT'):
                    continue
                txt = ent['text'].strip()
                if _VEM_DA_VIGA.search(txt):
                    continue
                _add_viga_ids_from_text(txt, viga_data)
            return viga_data

    try:
        doc = ezdxf.readfile(str(dxf_path))
    except Exception as ex:
        print(f"[WARN] Nao foi possivel abrir {dxf_path.name}: {ex}")
        return {}

    msp = doc.modelspace()
    viga_data = {}

    def _process_msp_layer(layer_cond):
        for e in msp:
            if e.dxftype() not in ('TEXT', 'MTEXT'):
                continue
            if not layer_cond(e.dxf.layer):
                continue
            try:
                txt = e.plain_text().strip() if e.dxftype() == 'MTEXT' else e.dxf.text.strip()
            except Exception:
                continue
            if _VEM_DA_VIGA.search(txt):
                continue
            _add_viga_ids_from_text(txt, viga_data)

    # 1a: NOMENCLATURA
    _process_msp_layer(lambda lyr: 'NOMENCLATURA' in lyr.upper())
    # 1b: Texto Seção* (exceto NOMENCLATURA e TEXTO puro)
    _process_msp_layer(lambda lyr: ('TEXTO' in lyr.upper() and
                                    lyr.upper() != 'TEXTO' and
                                    'NOMENCLATURA' not in lyr.upper()))
    # 1c: TEXTO plain
    _process_msp_layer(lambda lyr: lyr.upper() == 'TEXTO')
    # 1d: layer '5'
    _process_msp_layer(lambda lyr: lyr == '5')

    # Passo 3: scan de blocos nao-MSP para CARIMBO confirmed_ids
    confirmed_ids = set()
    _msp_names = {'*Model_Space', '*Paper_Space', '*Model_Space_0'}
    for block in doc.blocks:
        if block.name in _msp_names or block.name.startswith('*'):
            continue
        for e in block:
            if e.dxftype() not in ('TEXT', 'MTEXT'):
                continue
            if 'CARIMBO' not in e.dxf.layer.upper():
                continue
            try:
                txt = e.plain_text().strip() if e.dxftype() == 'MTEXT' else e.dxf.text.strip()
            except Exception:
                continue
            if _VEM_DA_VIGA.search(txt):
                continue
            for num in re.findall(r'\bV(\d+)\b', txt, re.IGNORECASE):
                if 1 <= len(num) <= 4:
                    confirmed_ids.add('V' + num.upper())

    # Passo 4: VEM DA recovery para confirmed_ids
    if confirmed_ids:
        for e in msp:
            if e.dxftype() not in ('TEXT', 'MTEXT'):
                continue
            try:
                txt = e.plain_text().strip() if e.dxftype() == 'MTEXT' else e.dxf.text.strip()
            except Exception:
                continue
            if not _VEM_DA_VIGA.search(txt):
                continue
            clean = re.sub(r'VEM\s+DA\s+', '', txt, flags=re.IGNORECASE).strip()
            temp = {}
            _add_viga_ids_from_text(clean, temp)
            for vid, data in temp.items():
                if vid not in confirmed_ids:
                    continue
                if vid not in viga_data:
                    viga_data[vid] = {'sides': set()}
                viga_data[vid]['sides'].update(data.get('sides', set()))

    return viga_data


def _extract_laje_ids_from_lj(dxf_path: Path, ezdxf=None) -> dict:
    """Lê LJ DXF via parser streaming e extrai IDs de lajes.

    Exclui referências cruzadas ("VEM DA L{n}") que são apenas ponteiros
    para painéis de outro pavimento sem geometria própria neste DXF.
    """
    entities = _stream_text_entities(dxf_path)
    laje_data = {}
    # Padrões que indicam referência cruzada (não é um painel deste DXF)
    _CROSS_REF = re.compile(r'VEM\s+DA\s+L\d+', re.IGNORECASE)

    for ent in entities:
        if ent['type'] not in ('TEXT', 'MTEXT'):
            continue
        txt = ent['text'].strip()
        # Pular textos que são referências cruzadas ("VEM DA L{n}")
        if _CROSS_REF.search(txt):
            continue
        # Suporta L{n}, L.{n} (ponto), L{n}A (sufixo letra) — ex: L305, L.305, L326A
        for m in re.finditer(r'\b[Ll]\.?(\d+[A-Za-z]?)\b', txt):
            lid = f'L{m.group(1).upper()}'
            if lid not in laje_data:
                laje_data[lid] = {}

    return laje_data


# ── Item 1: B×H spatial extraction via KDTree ────────────────────────────────
_RE_BH = re.compile(r'\b(\d{2,3})\s*[xX]\s*(\d{2,3})\b')  # "30x50", "25 X 60"
_RE_PID_POS = re.compile(r'[Pp](\d+)[._]([A-H])')           # "P12.A"


def _extract_bh_dims_spatial(entities: list[dict]) -> dict:
    """Extrai dimensões B×H de pilares usando proximidade espacial (KDTree).

    Retorna dict: {pid: {'b': float, 'h': float, 'conf': float, 'cx': float, 'cy': float}}
    cx/cy = centróide do grupo de labels do pilar em coordenadas DXF (cm).
    Requer scipy. Silencia graciosamente se indisponível.
    """
    try:
        from scipy.spatial import KDTree
        import numpy as np
    except ImportError:
        return {}

    # 1. Coletar textos de dimensão com posição (ex: "30x50" → b=30, h=50)
    dim_pts, dim_vals = [], []
    for ent in entities:
        if ent.get('x') is None or ent.get('y') is None:
            continue
        m = _RE_BH.search(ent['text'])
        if m:
            b, h = int(m.group(1)), int(m.group(2))
            if 10 <= b <= 300 and 10 <= h <= 300:
                dim_pts.append([ent['x'], ent['y']])
                dim_vals.append((float(b), float(h)))

    # 2. Agrupar posições de labels de pilar por ID (centróide do grupo de faces)
    pid_positions: dict[str, list] = {}
    for ent in entities:
        if ent.get('x') is None or ent.get('y') is None:
            continue
        for m in _RE_PID_POS.finditer(ent['text']):
            pid = f'P{m.group(1)}'
            pid_positions.setdefault(pid, []).append([ent['x'], ent['y']])

    if not pid_positions:
        return {}

    # 3. Para cada pilar, calcular centróide e buscar dimensão mais próxima
    # cx/cy são preservados mesmo quando dim não encontrada (para B2/LV-B3 em motor_fase4)
    MAX_DIST = 600.0  # unidades DXF (~60 cm a escala 1:10) — ajustar se necessário
    dim_tree = KDTree(np.array(dim_pts)) if dim_pts else None
    result = {}
    for pid, positions in pid_positions.items():
        centroid = np.mean(positions, axis=0)
        cx = round(float(centroid[0]), 2)
        cy = round(float(centroid[1]), 2)

        if dim_tree is not None:
            dist, idx = dim_tree.query(centroid, k=1)
            if dist <= MAX_DIST:
                b, h = dim_vals[idx]
                # Confidence cresce conforme proximidade: máx 0.78 a dist=0, mín 0.50 a dist=MAX
                conf = round(0.78 - 0.28 * (dist / MAX_DIST), 2)
                result[pid] = {'b': b, 'h': h, 'conf': conf, 'dist': round(float(dist), 1),
                               'cx': cx, 'cy': cy}
                continue

        # Sem dimensão próxima, mas centróide disponível para georeferência
        result[pid] = {'b': None, 'h': None, 'conf': 0.30, 'dist': None, 'cx': cx, 'cy': cy}

    return result
# ─────────────────────────────────────────────────────────────────────────────


def build_pilares_ground_truth(pilar_data: dict, pe_direito: float | None, pavimento: str,
                               bh_dims: dict | None = None) -> dict:
    """Gera fichas de pilares em formato Fase-3."""
    altura = pe_direito if pe_direito else 280.0
    fichas = {}
    def _pilar_sort_key(x):
        digits = ''.join(filter(str.isdigit, x[1:]))
        return (int(digits) if digits else 0, x)
    bh = bh_dims or {}
    n_bh_found = 0
    for pid in sorted(pilar_data.keys(), key=_pilar_sort_key):
        spatial = bh.get(pid)
        if spatial:
            b_val = spatial['b']
            h_val = spatial['h']
            conf  = spatial['conf']
            nota  = f"B×H extraído por proximidade espacial (dist={spatial['dist']} u)"
            n_bh_found += 1
        else:
            b_val, h_val, conf = None, None, 0.30
            nota = "B e H requerem verificação manual — nenhum texto dimensão encontrado próximo"
        fichas[pid] = {
            "b": b_val,
            "h": h_val,
            "altura": altura,
            "confidence": conf,
            "source": "engenharia-reversa-ezdxf",
            "faces_encontradas": sorted(pilar_data[pid]['faces']),
            "nota": nota,
            # Centróide do pilar em coordenadas DXF (cm) — usado por motor_fase4 para B2/LV-B3
            "cx": spatial.get('cx') if spatial else None,
            "cy": spatial.get('cy') if spatial else None,
        }
    fichas["_meta"] = {
        "total": len(pilar_data),
        "bh_extraidos": n_bh_found,
        "obra": "engenharia-reversa",
        "pavimento": pavimento,
        "pe_direito_cm": pe_direito,
        "extraido_em": datetime.now().strftime("%Y-%m-%d"),
        "confidence_nota": "IDs=ALTA | altura=MEDIA | B/H=ESPACIAL(conf≈0.50-0.78) ou BAIXA(conf=0.30)"
    }
    return fichas


def build_vigas_ground_truth(viga_data: dict, pavimento: str) -> dict:
    """Gera fichas de vigas em formato Fase-3."""
    fichas = {}
    def _viga_sort_key(x):
        digits = ''.join(filter(str.isdigit, x[1:]))
        return (int(digits) if digits else 0, x)
    for vid in sorted(viga_data.keys(), key=_viga_sort_key):
        fichas[vid] = {
            "b": None,
            "h": None,
            "comprimento": None,
            "confidence": 0.25,
            "source": "engenharia-reversa-ezdxf",
            "sides_encontrados": sorted(viga_data[vid].get('sides', [])),
            "nota": "Dims requerem verificação manual"
        }
    if fichas:
        fichas["_meta"] = {
            "total": len(viga_data),
            "pavimento": pavimento,
            "extraido_em": datetime.now().strftime("%Y-%m-%d")
        }
    return fichas


def build_lajes_ground_truth(laje_data: dict, pavimento: str) -> dict:
    """Gera fichas de lajes em formato Fase-3."""
    fichas = {}
    def _laje_sort_key(x):
        digits = ''.join(filter(str.isdigit, x[1:]))
        return (int(digits) if digits else 0, x)
    for lid in sorted(laje_data.keys(), key=_laje_sort_key):
        fichas[lid] = {
            "comprimento": None,
            "largura": None,
            "coordenadas": [],
            "area_cm2": None,
            "confidence": 0.25,
            "source": "engenharia-reversa-ezdxf",
            "nota": "Dims requerem verificação manual"
        }
    if fichas:
        fichas["_meta"] = {
            "total": len(laje_data),
            "pavimento": pavimento,
            "extraido_em": datetime.now().strftime("%Y-%m-%d")
        }
    return fichas


def _load_dxf_paths_from_discovery(obra: Path, pavimento: str) -> dict:
    """Carrega caminhos DXF do dxf_discovery.json se disponível.

    Tenta primeiro match exato; se falhar, tenta match por sufixo
    (ex: 'TIPO 14 AO 17 PAV' casa com 'RES.DIAMOND - TORRE 1 - TIPO 14 AO 17 PAV').
    """
    discovery_path = obra.parent / "dxf_discovery.json"
    if not discovery_path.exists():
        return {}
    try:
        with open(discovery_path, encoding='utf-8') as f:
            discovery = json.load(f)
        obra_data = discovery.get(obra.name, {})
        # 1) Exact match
        pav_data = obra_data.get(pavimento, {})
        # 2) Suffix match: discovery key ends with pavimento
        if not pav_data:
            pav_upper = pavimento.upper()
            for key, val in obra_data.items():
                if key.upper().endswith(pav_upper):
                    pav_data = val
                    break
        # 3) Contains match: discovery key contains pavimento
        if not pav_data:
            for key, val in obra_data.items():
                if pav_upper in key.upper():
                    pav_data = val
                    break
        return {k: Path(v) if v else None for k, v in pav_data.items()}
    except Exception as ex:
        print(f"[WARN] Nao foi possivel carregar discovery: {ex}")
        return {}


def run(obra_path: str, pavimento: str) -> None:
    ezdxf = _load_ezdxf()
    obra = Path(obra_path)
    rev_dir = obra / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    out_dir = obra / "Fase-3_Interpretacao_Extracao"

    if not rev_dir.exists():
        print(f"[ERROR] Diretório de engenharia reversa não encontrado: {rev_dir}")
        sys.exit(1)

    print(f"[INFO] === engenharia_reversa_dxf.py | Obra: {obra.name} | Pav: {pavimento} ===")
    print(f"[INFO] Diretório: {rev_dir}")

    # Tentar usar discovery.json para caminhos exatos por pavimento
    disc_paths = _load_dxf_paths_from_discovery(obra, pavimento)
    if disc_paths:
        print(f"[INFO] Usando caminhos do dxf_discovery.json para pav '{pavimento}'")

    # --- Pilares (PL) ---
    pl_dxf = disc_paths.get('PL') or _find_dxf(rev_dir, "- PL -") or _find_dxf(rev_dir, "PL -") or _find_dxf(rev_dir, "PL_")
    if pl_dxf:
        print(f"[INFO] PL DXF: {pl_dxf.name}")
        pilar_data, pe_direito, bh_dims = _extract_pl_data(pl_dxf, ezdxf)
        if bh_dims:
            print(f"[INFO] B×H spatial: {len(bh_dims)}/{len(pilar_data)} pilares com dims encontradas")
        pilares_gt = build_pilares_ground_truth(pilar_data, pe_direito, pavimento, bh_dims)
        out_p = out_dir / "Pilares" / "pilares_ground_truth.json"
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, 'w', encoding='utf-8') as f:
            json.dump(pilares_gt, f, indent=2, ensure_ascii=False)
        n = pilares_gt["_meta"]["total"]
        print(f"[INFO] Pilares extraídos: {n} IDs | Pé Direito: {pe_direito}cm -> {out_p}")
    else:
        print("[WARN] PL DXF não encontrado — pulando pilares")
        pilar_data = {}
        pilares_gt = {}

    # --- Vigas Laterais (LV) ---
    lv_dxf = disc_paths.get('LV') or _find_dxf(rev_dir, "- LV -") or _find_dxf(rev_dir, "LV -") or _find_dxf(rev_dir, "LV_")
    if lv_dxf:
        print(f"[INFO] LV DXF: {lv_dxf.name}")
        viga_data = _extract_viga_ids_from_lv(lv_dxf, ezdxf)
        vigas_gt = build_vigas_ground_truth(viga_data, pavimento)
        if vigas_gt:
            out_v = out_dir / "Vigas" / "vigas_ground_truth.json"
            out_v.parent.mkdir(parents=True, exist_ok=True)
            with open(out_v, 'w', encoding='utf-8') as f:
                json.dump(vigas_gt, f, indent=2, ensure_ascii=False)
            n = vigas_gt.get("_meta", {}).get("total", 0)
            print(f"[INFO] Vigas extraídas: {n} IDs -> {out_v}")
        else:
            print("[INFO] Nenhuma viga identificada no LV DXF")
    else:
        print("[WARN] LV DXF não encontrado — pulando vigas")

    # --- Lajes (LJ) ---
    lj_dxf = disc_paths.get('LJ') or _find_dxf(rev_dir, "- LJ -") or _find_dxf(rev_dir, "LJ -") or _find_dxf(rev_dir, "LJ_")
    if lj_dxf:
        print(f"[INFO] LJ DXF: {lj_dxf.name}")
        laje_data = _extract_laje_ids_from_lj(lj_dxf, ezdxf)
        lajes_gt = build_lajes_ground_truth(laje_data, pavimento)
        if lajes_gt:
            out_l = out_dir / "Lajes" / "lajes_ground_truth.json"
            out_l.parent.mkdir(parents=True, exist_ok=True)
            with open(out_l, 'w', encoding='utf-8') as f:
                json.dump(lajes_gt, f, indent=2, ensure_ascii=False)
            n = lajes_gt.get("_meta", {}).get("total", 0)
            print(f"[INFO] Lajes extraídas: {n} IDs -> {out_l}")
        else:
            print("[INFO] Nenhuma laje identificada no LJ DXF")
    else:
        print("[WARN] LJ DXF não encontrado — pulando lajes")

    # --- Resumo ---
    n_pilares = pilares_gt.get("_meta", {}).get("total", 0) if pilares_gt else 0
    n_bh = pilares_gt.get("_meta", {}).get("bh_extraidos", 0) if pilares_gt else 0
    print(f"[INFO] === RESULTADO: {n_pilares} pilares | B×H: {n_bh}/{n_pilares} extraídos ===")
    print(f"[INFO] NOTA: IDs=ALTA | B/H={('ESPACIAL conf~0.5-0.78' if n_bh else 'BAIXA - revisao manual')}.")
    print(f"[INFO] Ground truth salvo em: {out_dir}")


def main():
    parser = argparse.ArgumentParser(description='Extrai ground truth de DXFs de engenharia reversa STOG')
    parser.add_argument('--obra', required=True, help='Path para o diretório da obra')
    parser.add_argument('--pavimento', required=True, help='Identificador do pavimento (ex: "12 PAV")')
    args = parser.parse_args()
    run(args.obra, args.pavimento)


if __name__ == '__main__':
    main()
