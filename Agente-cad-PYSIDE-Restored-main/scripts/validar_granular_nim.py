#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validar_granular_nim.py — Validação visual granular por elemento (viga individual).

Pipeline:
  1. Abre DXF reverso (LV_stog_quality.dxf ou LV_gerado.dxf)
  2. Encontra cada viga pelo bbox (via TEXT NOMENCLATURA layer)
  3. Recorta imagem da área da viga → PNG
  4. Gera a mesma viga com gerar_lv_dxf_stog.py --item VX
  5. Recorta imagem da viga gerada → PNG
  6. Envia par ao NIM vision para comparação
  7. Gera relatório granular por viga

Uso:
  python scripts/validar_granular_nim.py --obra DADOS-OBRAS/Obra_TREINO_16 --n 3
  python scripts/validar_granular_nim.py --obra DADOS-OBRAS/Obra_TREINO_16 --viga V1
  python scripts/validar_granular_nim.py --obra DADOS-OBRAS/Obra_TREINO_16 --sem-api
"""

import sys, io, builtins as _builtins
_orig_print = _builtins.print
def print(*args, **kwargs):
    kwargs.setdefault('flush', True)
    _orig_print(*args, **kwargs)

for _stream in (sys.stdout, sys.stderr):
    try:
        if _stream and not _stream.closed and hasattr(_stream, 'reconfigure'):
            _stream.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

import argparse
import base64
import json
import math
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

# ─── Configuração Backends de Vision ────────────────────────────────────────
NVIDIA_BASE_URL     = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL_DEF    = "meta/llama-3.2-90b-vision-instruct"
NIM_API_KEY_ENV     = "NVIDIA_API_KEY"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL    = "anthropic/claude-3.5-sonnet"
OPENROUTER_KEY_ENV  = "OPENROUTER_API_KEY"

RENDER_DPI = 150
BBOX_PAD   = 50    # padding em unidades DXF ao redor do bbox de cada viga

# ─── Prompt de comparação granular LV ───────────────────────────────────────
PROMPT_GRANULAR_LV = """\
Compare estas duas imagens de uma VIGA LATERAL (LV) de fôrma estrutural.
LEFT image = Engenharia Reversa (reference). RIGHT image = DXF Gerado (candidate).

Each image shows: a cross-section view (left part) + Face A elevation (middle) + Face B elevation (right).

Count and compare carefully:
- How many sarrafo lines are visible in the cross-section of each image?
- How many panels (vertical divisions) are in Face A and Face B of each image?
- Are diagonal hatch patterns (laje hachura) present in both faces?
- Are the proportions (height vs length) similar between both images?

Score each criterion 0-100 where 100=identical, 0=completely different:
- corte_sarrafos: sarrafo count/position match in cross-section
- corte_paineis: panel outlines in cross-section match
- face_paineis_quant: number of panels in faces A and B match
- face_sarrafos_dist: sarrafo distribution in faces match
- face_laje_hachura: diagonal hatch patterns present and similar
- proporcoes_gerais: overall proportions match

Reply with ONLY valid JSON, no other text:
{"corte_sarrafos":0,"corte_paineis":0,"face_paineis_quant":0,"face_sarrafos_dist":0,"face_laje_hachura":0,"proporcoes_gerais":0,"ausentes":[],"extras":[],"resumo":""}

Replace each 0 with your actual score based on what you observe."""


# ─── Utilitários DXF ────────────────────────────────────────────────────────

def _entity_bbox(e):
    """Retorna (xmin, ymin, xmax, ymax) de uma entidade, ou None se não determinável."""
    try:
        t = e.dxftype()
        if t in ('LINE',):
            pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        elif t == 'LWPOLYLINE':
            pts = [(pt[0], pt[1]) for pt in e.get_points()]
        elif t == 'TEXT':
            pts = [(e.dxf.insert.x, e.dxf.insert.y)]
        elif t == 'MTEXT':
            pts = [(e.dxf.insert.x, e.dxf.insert.y)]
        elif t == 'INSERT':
            pts = [(e.dxf.insert.x, e.dxf.insert.y)]
        elif t == 'HATCH':
            pts = []
            for path in e.paths:
                for edge in (path.edges if hasattr(path, 'edges') else []):
                    if hasattr(edge, 'start'):
                        pts.append((edge.start.x, edge.start.y))
                    if hasattr(edge, 'end'):
                        pts.append((edge.end.x, edge.end.y))
                if hasattr(path, 'vertices'):
                    pts.extend([(v[0], v[1]) for v in path.vertices])
        elif t == 'DIMENSION':
            pts = [(e.dxf.defpoint.x, e.dxf.defpoint.y)]
        else:
            return None
        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)
    except Exception:
        return None


def find_viga_bboxes(dxf_path: Path, n_max: int = 20):
    """
    Encontra bounding boxes individuais de cada viga no DXF LV.

    Estratégia:
    - Coleta TEXT/MTEXT em layers de nomenclatura com padrão "V\\d+" como ancora
    - Agrupa por linha (Y próximo ±tolerance)
    - Para cada linha, coleta TODAS as entidades dentro da banda Y
    - Retorna dict {viga_nome: (x0, y0, x1, y1)} com padding BBOX_PAD

    Returns dict viga_name → (xmin, ymin, xmax, ymax) em coords DXF.
    """
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    # 1. Coletar âncoras de texto (viga names)
    NOME_LAYERS = {'NOMENCLATURA', 'nomenclatura', '5', 'Texto Seção', 'CARIMBO'}
    NOME_RE = re.compile(r'^V\s*\d+', re.IGNORECASE)

    anchors = []  # (y_center, viga_name, x_anchor)
    for e in msp:
        try:
            if e.dxftype() not in ('TEXT', 'MTEXT'):
                continue
            layer = e.dxf.layer
            text = e.dxf.text if e.dxftype() == 'TEXT' else e.text
            text = text.strip()
            # Aceitar V1, V01, V001, V1.A, V1.B, V-1 etc.
            m = re.match(r'V[\s-]?(\d+)', text, re.IGNORECASE)
            if not m:
                continue
            vname = f"V{m.group(1)}"
            x = e.dxf.insert.x
            y = e.dxf.insert.y
            anchors.append((y, vname, x))
        except Exception:
            continue

    if not anchors:
        print(f"  [WARN] Nenhum texto de viga encontrado em {dxf_path.name}")
        return {}

    # 2. Agrupar por Y-linha (tolerance 80cm)
    Y_TOL = 80
    anchors.sort(key=lambda a: -a[0])  # top → bottom

    rows = []  # [(y_center, viga_name, [x_anchors])]
    for y, vname, x in anchors:
        placed = False
        for row in rows:
            if abs(row[0] - y) < Y_TOL:
                # atualizar y_center como média
                row[2].append(x)
                placed = True
                # prefer mais curto sem sufixo
                if len(vname) < len(row[1]):
                    row[1] = vname
                break
        if not placed:
            rows.append([y, vname, [x]])

    # Filtrar duplicatas de mesmo vname (manter a primeira por Y)
    seen = {}
    rows_unique = []
    for row in rows:
        vname = row[1]
        if vname not in seen:
            seen[vname] = True
            rows_unique.append(row)
    rows = rows_unique[:n_max]

    # 3. Para cada linha, coletar todas as entidades dentro da banda Y
    # band_half = 0.45 × min_gap garante que bandas adjacentes não se sobreponham
    # (gap=193 → band_half=86.8, sem overlap entre vigas adjacentes)
    if len(rows) >= 2:
        y_gaps = [abs(rows[i][0] - rows[i+1][0]) for i in range(len(rows)-1)]
        band_half = min(y_gaps) * 0.45
    else:
        band_half = 300

    # Layers administrativos que inflam o bbox mas não são estruturais
    _ADMIN_LAYERS = frozenset({'Folhas', 'CARIMBO', 'CARIMBO_LAYER', 'folhas', 'carimbo'})

    # Coletar todos os bboxes de entidades para determinar extent
    # Excluir layers administrativos (cards, carimbos)
    all_entity_bboxes = []
    for e in msp:
        try:
            if e.dxf.layer in _ADMIN_LAYERS:
                continue
        except Exception:
            pass
        bb = _entity_bbox(e)
        if bb:
            all_entity_bboxes.append(bb)

    result = {}
    for row_y, vname, x_list in rows:
        y_lo = row_y - band_half
        y_hi = row_y + band_half

        # Filtrar entidades dentro da banda Y, excluindo zona de sentinelas (x < -5000)
        row_bbs = [bb for bb in all_entity_bboxes
                   if not (bb[3] < y_lo or bb[1] > y_hi)
                   and bb[0] > -5000.0]  # excluir sentinelas em x negativo extremo

        if not row_bbs:
            # Fallback sem filtro x (caso o DXF use coordenadas negativas legítimas)
            row_bbs = [bb for bb in all_entity_bboxes
                       if not (bb[3] < y_lo or bb[1] > y_hi)]

        if not row_bbs:
            continue

        x0 = min(bb[0] for bb in row_bbs) - BBOX_PAD
        y0 = min(bb[1] for bb in row_bbs) - BBOX_PAD
        x1 = max(bb[2] for bb in row_bbs) + BBOX_PAD
        y1 = max(bb[3] for bb in row_bbs) + BBOX_PAD

        result[vname] = (x0, y0, x1, y1)
        print(f"  bbox {vname}: x=[{x0:.0f},{x1:.0f}] y=[{y0:.0f},{y1:.0f}] "
              f"({x1-x0:.0f}×{y1-y0:.0f})")

    return result


def _build_subset_dxf(source_path: Path, bbox,
                       padding: float = 150.0) -> 'ezdxf.document.Drawing':
    """
    Cria um documento ezdxf temporário contendo apenas as entidades que
    intersectam o bbox expandido. Muito mais rápido de renderizar do que
    o DXF completo com milhares de entidades.
    """
    x0, y0, x1, y1 = bbox
    x0 -= padding; y0 -= padding
    x1 += padding; y1 += padding

    src = ezdxf.readfile(str(source_path))
    new_doc = ezdxf.new('R2018')

    # Copiar layers
    for layer in src.layers:
        try:
            if layer.dxf.name not in new_doc.layers:
                new_doc.layers.add(layer.dxf.name, color=layer.dxf.color)
        except Exception:
            pass

    # Copiar blocos (necessário para INSERT)
    for blk in src.blocks:
        if blk.name.startswith('*'):
            continue
        try:
            new_blk = new_doc.blocks.new(blk.name)
            for e in blk:
                try:
                    new_blk.add_entity(e.copy())
                except Exception:
                    pass
        except Exception:
            pass

    _SKIP_LAYERS = frozenset({'Folhas', 'CARIMBO', 'folhas', 'carimbo'})

    new_msp = new_doc.modelspace()
    count = 0
    for e in src.modelspace():
        # Excluir layers administrativos (cards, carimbos)
        try:
            if e.dxf.layer in _SKIP_LAYERS:
                continue
        except Exception:
            pass
        bb = _entity_bbox(e)
        if bb is None:
            # Entidades sem bbox determinável: incluir se layer relevante
            try:
                new_msp.add_entity(e.copy())
                count += 1
            except Exception:
                pass
            continue
        # Verificar sobreposição com bbox expandido, excluindo zona de sentinelas
        if bb[0] < -5000:   # sentinelas em x muito negativo → ignorar
            continue
        if bb[2] < x0 or bb[0] > x1 or bb[3] < y0 or bb[1] > y1:
            continue
        try:
            new_msp.add_entity(e.copy())
            count += 1
        except Exception:
            pass

    return new_doc, count


def render_dxf_bbox(dxf_path: Path, bbox, dpi: int = RENDER_DPI,
                    save_path: Optional[Path] = None) -> bytes:
    """
    Renderiza DXF recortado ao bbox (xmin, ymin, xmax, ymax).
    Usa subset DXF para velocidade — apenas entidades na região de interesse.
    Retorna bytes PNG.
    """
    x0, y0, x1, y1 = bbox
    w = x1 - x0
    h = y1 - y0
    aspect = w / h if h > 0 else 2.0
    fig_w = max(6, min(aspect * 5, 20))
    fig_h = max(3, 5)

    # Construir subset doc com apenas as entidades do bbox
    t0 = time.time()
    doc, n_ents = _build_subset_dxf(dxf_path, bbox)
    print(f"  Subset: {n_ents} entidades em {time.time()-t0:.1f}s")

    ctx = RenderContext(doc)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_aspect('equal')
    ax.axis('off')
    fig.patch.set_facecolor('#1a1a24')
    ax.set_facecolor('#1a1a24')

    try:
        backend = MatplotlibBackend(ax)
        frontend = Frontend(ctx, backend)
        frontend.draw_layout(doc.modelspace(), finalize=True)
    except Exception as e:
        ax.text(0.5, 0.5, f"Render err:\n{str(e)[:60]}",
                transform=ax.transAxes, fontsize=8, color='red',
                ha='center', va='center')

    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight',
                facecolor='#1a1a24', pad_inches=0.05)
    plt.close(fig)
    buf.seek(0)
    data = buf.read()
    data = _dark_to_white_bg(data)

    if save_path:
        save_path.write_bytes(data)
        print(f"  Salvo: {save_path.name} ({len(data)//1024}KB)")

    return data


def _dark_to_white_bg(png_bytes: bytes) -> bytes:
    """Converte fundo escuro (#1a1a24) → branco, ACI7 white → preto."""
    try:
        import PIL.Image
        import numpy as np
        img = PIL.Image.open(io.BytesIO(png_bytes)).convert('RGB')
        arr = np.array(img, dtype=np.uint8)
        bg_r, bg_g, bg_b = 26, 26, 36
        tol = 20
        bg_mask = (
            (np.abs(arr[:,:,0].astype(int) - bg_r) < tol) &
            (np.abs(arr[:,:,1].astype(int) - bg_g) < tol) &
            (np.abs(arr[:,:,2].astype(int) - bg_b) < tol)
        )
        arr[bg_mask] = [255, 255, 255]
        white_mask = (arr[:,:,0] > 240) & (arr[:,:,1] > 240) & (arr[:,:,2] > 240) & ~bg_mask
        arr[white_mask] = [30, 30, 30]
        img2 = PIL.Image.fromarray(arr, 'RGB')
        buf = io.BytesIO()
        img2.save(buf, format='PNG', optimize=True)
        buf.seek(0)
        return buf.read()
    except Exception:
        return png_bytes


def generate_single_viga(obra_path: Path, viga_name: str,
                          generator_script: Path, out_dir: Path) -> Optional[Path]:
    """
    Chama gerar_lv_dxf_stog.py --item VNAME e retorna o path do DXF gerado.
    O output vai para out_dir/LV_preview_{viga_name}.dxf
    """
    out_path = out_dir / f"LV_preview_{viga_name}.dxf"
    cmd = [
        sys.executable, str(generator_script),
        '--obra', str(obra_path),
        '--item', viga_name,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=60,
            cwd=generator_script.parent.parent
        )
        if result.returncode != 0:
            print(f"  [ERRO] Generator: {result.stderr[-300:]}")
            return None
        # O gerador salva como LV_preview_{viga_name}.dxf em Fase-6_Execucao_CAD/
        fase6_path = obra_path / 'Fase-6_Execucao_CAD' / f'LV_preview_{viga_name}.dxf'
        if fase6_path.exists():
            return fase6_path
        # Fallback: LV_gerado.dxf se só 1 viga gerada
        lv_gerado = obra_path / 'Fase-6_Execucao_CAD' / 'LV_gerado.dxf'
        if lv_gerado.exists():
            return lv_gerado
        print(f"  [WARN] DXF gerado não encontrado para {viga_name}")
        return None
    except subprocess.TimeoutExpired:
        print(f"  [ERRO] Timeout gerando {viga_name}")
        return None
    except Exception as e:
        print(f"  [ERRO] {e}")
        return None


# ─── Scoring Programático (DXF comparison) ───────────────────────────────────

_SKIP_LAYERS = {'Folhas', 'CARIMBO'}
_SARRAFO_LAYERS = {'SARR_2.2x7', 'SARRAFO_2_2X7', 'SARR_2.2x10', 'SARRAFO_2_2X10'}
_PAINEL_LAYERS  = {'Painéis', 'Paineis', 'Pain\xe9is', 'PAINEL'}
_LAJE_LAYERS    = {'SCO-___-LAJ', 'Hachura', 'SCO-___-LAJ-HAT'}


def _count_entities_in_bbox(dxf_path: Path, bbox, padding=100.0) -> dict:
    """Conta entidades por layer/tipo dentro de um bbox (± padding)."""
    try:
        doc = ezdxf.readfile(str(dxf_path))
    except Exception:
        return {}
    msp = doc.modelspace()
    x0, y0, x1, y1 = bbox[0]-padding, bbox[1]-padding, bbox[2]+padding, bbox[3]+padding

    counts = {}
    for e in msp:
        try:
            lay = getattr(e.dxf, 'layer', '')
            if lay in _SKIP_LAYERS:
                continue
            t = e.dxftype()
            # Ponto representativo da entidade
            if t == 'LINE':
                px = e.dxf.start.x
                py = e.dxf.start.y
                if px < -5000:
                    continue
            elif t == 'LWPOLYLINE':
                pts = list(e.get_points())
                if not pts: continue
                px, py = pts[0][0], pts[0][1]
            elif t == 'HATCH':
                # Usar centroide aproximado
                paths = e.paths
                if not paths: continue
                px_list, py_list = [], []
                for path in paths:
                    if hasattr(path, 'vertices'):
                        for v in path.vertices:
                            px_list.append(v[0])
                            py_list.append(v[1])
                if not px_list: continue
                px = sum(px_list) / len(px_list)
                py = sum(py_list) / len(py_list)
            elif t in ('TEXT', 'MTEXT', 'INSERT', 'DIMENSION'):
                ins = getattr(e.dxf, 'insert', None) or getattr(e.dxf, 'defpoint', None)
                if ins is None: continue
                px, py = ins.x, ins.y
            else:
                continue
            if x0 <= px <= x1 and y0 <= py <= y1:
                key = lay
                counts[key] = counts.get(key, 0) + 1
        except Exception:
            continue
    return counts


def _count_all_entities(dxf_path: Path) -> dict:
    """Conta todas as entidades do DXF por layer (excluindo admin)."""
    return _count_entities_in_bbox(dxf_path, (-1e9, -1e9, 1e9, 1e9), padding=0)


def _layer_count(counts: dict, layers: set) -> int:
    return sum(v for k, v in counts.items() if k in layers or
               any(pat.lower() in k.lower() for pat in layers))


def score_ratio(gen: int, rev: int) -> float:
    """Retorna score 0-100 baseado na razão gen/rev (penaliza excesso e falta)."""
    if rev == 0 and gen == 0:
        return 100.0
    if rev == 0:
        return max(0.0, 100.0 - min(gen, 50) * 2)
    ratio = gen / rev
    if ratio > 1.0:
        ratio = 1.0 / ratio  # penaliza excesso igual a falta
    return round(ratio * 100, 1)


def compare_dxf_structural(reverso_path: Path, reverso_bbox,
                            gen_path: Path) -> dict:
    """
    Scoring programático: compara contagens de entidades por layer entre
    reverso (na bbox da viga) e gerado (todas as entidades).

    Retorna dict compatível com o formato NIM: mesmos campos de score.
    """
    rev = _count_entities_in_bbox(reverso_path, reverso_bbox, padding=5)
    gen = _count_all_entities(gen_path)

    # Sarrafos (linhas no corte e nas faces)
    rev_sarr  = _layer_count(rev, _SARRAFO_LAYERS)
    gen_sarr  = _layer_count(gen, _SARRAFO_LAYERS)

    # Painéis (LWPOLYLINE de contorno)
    rev_pain  = _layer_count(rev, _PAINEL_LAYERS)
    gen_pain  = _layer_count(gen, _PAINEL_LAYERS)

    # Hachura laje
    rev_laje  = _layer_count(rev, _LAJE_LAYERS)
    gen_laje  = _layer_count(gen, _LAJE_LAYERS)

    # Ancoragem / Madeira (elementos estruturais gerais)
    rev_anc   = rev.get('BARRA_ANCORAGEM', 0) + rev.get('Madeira', 0)
    gen_anc   = gen.get('BARRA_ANCORAGEM', 0) + gen.get('Madeira', 0)

    # Proporções: total de entidades (exclui COTA que é dimensional)
    skip_dim  = {'COTA', 'NOMENCLATURA', 'Folhas', 'CARIMBO', '0', '5'}
    rev_total = sum(v for k, v in rev.items() if k not in skip_dim)
    gen_total = sum(v for k, v in gen.items() if k not in skip_dim)

    sc_sarr_lines  = score_ratio(gen_sarr, rev_sarr)
    sc_pain_face   = score_ratio(gen_pain, rev_pain)
    sc_laje        = score_ratio(gen_laje, rev_laje)
    sc_prop        = score_ratio(gen_total, rev_total)
    sc_anc         = score_ratio(gen_anc, rev_anc)

    # Mapear para os campos NIM equivalentes
    result = {
        'corte_sarrafos':     sc_sarr_lines,   # sarrafos presentes
        'corte_paineis':      sc_pain_face,     # painéis contorno
        'face_paineis_quant': sc_pain_face,     # quantidade painéis
        'face_sarrafos_dist': sc_sarr_lines,    # distribuição sarrafos
        'face_laje_hachura':  sc_laje,          # hachura laje
        'proporcoes_gerais':  sc_prop,          # total entidades
        'ausentes': [],
        'extras':   [],
        'resumo': (
            f"Prog: sarr={gen_sarr}/{rev_sarr} "
            f"pain={gen_pain}/{rev_pain} "
            f"laje={gen_laje}/{rev_laje} "
            f"total={gen_total}/{rev_total}"
        ),
        '_method': 'programmatic',
        '_rev_counts': {k: v for k, v in sorted(rev.items(), key=lambda x: -x[1])[:10]},
        '_gen_counts': {k: v for k, v in sorted(gen.items(), key=lambda x: -x[1])[:10]},
    }
    return result


# ─── NIM Vision API ──────────────────────────────────────────────────────────

_NIM_SCORE_FIELDS = [
    'corte_sarrafos', 'corte_paineis', 'face_paineis_quant',
    'face_sarrafos_dist', 'face_laje_hachura', 'proporcoes_gerais'
]

def _extract_from_markdown(raw: str) -> dict:
    """Extrai scores de resposta em bullet-list markdown quando JSON não foi encontrado."""
    result = {}
    for field in _NIM_SCORE_FIELDS:
        # Padrão: "field...:** 80" ou "field...: 80" ou "field...**80**"
        m = re.search(
            rf'{re.escape(field)}[^:\n]*:?\s*\**(\d{{1,3}})\**',
            raw, re.IGNORECASE
        )
        if m:
            val = int(m.group(1))
            if 0 <= val <= 100:
                result[field] = val
    # Extrair resumo
    m_res = re.search(r'resumo[^:]*:["\s*]*(.+?)(?:\n|$)', raw, re.IGNORECASE)
    if m_res:
        result['resumo'] = m_res.group(1).strip().strip('"*').strip()
    result.setdefault('ausentes', [])
    result.setdefault('extras', [])
    # Retornar apenas se extraiu pelo menos 3 campos numéricos
    if sum(1 for f in _NIM_SCORE_FIELDS if f in result) >= 3:
        return result
    return {}


def _parse_nim_response(raw: str) -> dict:
    """Tenta extrair JSON da resposta do modelo. Múltiplas estratégias."""
    # Estratégia 1: limpar markdown e parsear JSON
    clean = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
    clean = re.sub(r'```\s*$', '', clean, flags=re.MULTILINE).strip()
    # Unescape markdown: \_ → _ (llama às vezes escapa underscores)
    clean = clean.replace('\\_', '_').replace('\\*', '*')
    m = re.search(r'\{.*\}', clean, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    # Estratégia 2: bullet-list markdown
    result = _extract_from_markdown(raw)
    if result:
        return result
    return {'raw': raw, 'erro': 'JSON não encontrado na resposta'}


def compare_with_nim(img_reverso: bytes, img_gerado: bytes,
                     viga_name: str, api_key: str) -> dict:
    """
    Envia par de imagens ao NIM vision (NVIDIA API) e retorna dict com scores.
    """
    try:
        from openai import OpenAI
    except ImportError:
        return {'erro': 'openai não instalado'}

    # Montar imagem side-by-side
    img_combined = _make_side_by_side(img_reverso, img_gerado, viga_name)
    b64 = base64.b64encode(img_combined).decode('utf-8')

    base_url = NVIDIA_BASE_URL
    model    = NVIDIA_MODEL_DEF
    use_key  = api_key

    print(f"  Backend: NIM ({model})")
    client = OpenAI(base_url=base_url, api_key=use_key)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT_GRANULAR_LV.replace(
                        "UMA VIGA LATERAL (LV) específica",
                        f"UMA VIGA LATERAL (LV) — {viga_name}"
                    )},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ]
            }],
            max_tokens=800, temperature=0.0
        )
        raw = resp.choices[0].message.content.strip()
        return _parse_nim_response(raw)
    except Exception as e:
        return {'erro': str(e)}


def _make_side_by_side(img_left: bytes, img_right: bytes,
                        title: str = "") -> bytes:
    """Cria imagem side-by-side com título."""
    try:
        import PIL.Image
        import PIL.ImageDraw
        import PIL.ImageFont

        left = PIL.Image.open(io.BytesIO(img_left)).convert('RGB')
        right = PIL.Image.open(io.BytesIO(img_right)).convert('RGB')

        # Resize ao mesmo height
        target_h = max(left.height, right.height, 400)
        def resize_keep_ar(img, h):
            w = int(img.width * h / img.height)
            return img.resize((w, h), PIL.Image.LANCZOS)

        left = resize_keep_ar(left, target_h)
        right = resize_keep_ar(right, target_h)

        header_h = 36
        total_w = left.width + right.width + 6
        total_h = target_h + header_h

        combined = PIL.Image.new('RGB', (total_w, total_h), (240, 240, 240))
        combined.paste(left, (0, header_h))
        combined.paste(right, (left.width + 6, header_h))

        # Header text
        draw = PIL.ImageDraw.Draw(combined)
        draw.rectangle([(0,0),(total_w, header_h)], fill=(50, 50, 80))
        draw.text((10, 8), f"Reverso (original) — {title}", fill=(255,255,255))
        draw.text((left.width + 16, 8), f"Gerado — {title}", fill=(255, 220, 100))

        buf = io.BytesIO()
        combined.save(buf, format='PNG')
        buf.seek(0)
        return buf.read()
    except Exception:
        # Fallback: apenas concatenar bytes (left)
        return img_left


def score_from_result(res: dict) -> float:
    """Score médio ponderado dos critérios LV."""
    keys_weights = [
        ('corte_sarrafos', 0.20),
        ('corte_paineis', 0.15),
        ('face_paineis_quant', 0.20),
        ('face_sarrafos_dist', 0.20),
        ('face_laje_hachura', 0.15),
        ('proporcoes_gerais', 0.10),
    ]
    total_w = 0.0
    total_s = 0.0
    for k, w in keys_weights:
        v = res.get(k)
        if v is not None:
            try:
                total_s += float(v) * w
                total_w += w
            except Exception:
                pass
    return round(total_s / total_w, 1) if total_w > 0 else 0.0


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Validação visual granular por viga — NIM vision')
    parser.add_argument('--obra', required=True,
                        help='Path da obra (ex: DADOS-OBRAS/Obra_TREINO_16)')
    parser.add_argument('--n', type=int, default=3,
                        help='Número de vigas a validar (default: 3)')
    parser.add_argument('--viga', type=str, default=None,
                        help='Viga específica (ex: V1). Sobrepõe --n')
    parser.add_argument('--dpi', type=int, default=RENDER_DPI,
                        help='DPI para renderização (default: 150)')
    parser.add_argument('--sem-api', action='store_true',
                        help='[obsoleto] Mantido por compatibilidade')
    parser.add_argument('--nim', action='store_true',
                        help='Adicionar scoring visual via NIM API além do programático')
    parser.add_argument('--out-dir', type=str, default=None,
                        help='Diretório para salvar imagens de debug (default: Fase-6_Execucao_CAD/granular/)')
    args = parser.parse_args()

    obra_path = Path(args.obra)
    if not obra_path.is_absolute():
        obra_path = Path('D:/Agente-cad-PYSIDE') / obra_path
    obra_path = obra_path.resolve()

    fase6 = obra_path / 'Fase-6_Execucao_CAD'
    out_dir = Path(args.out_dir) if args.out_dir else fase6 / 'granular'
    out_dir.mkdir(parents=True, exist_ok=True)

    # Localizar DXF reverso LV (engenharia reversa = STOG original)
    # O gerador também usa LV_stog_quality.dxf — precisamos do mais recente
    # O reverso é identificado por ser o arquivo de referência STOG (tamanho maior)
    reverso_candidates = sorted(fase6.glob('LV_stog_quality*.dxf'),
                                key=lambda p: p.stat().st_size, reverse=True)
    if not reverso_candidates:
        reverso_candidates = sorted(fase6.glob('LV_reverso*.dxf'),
                                    key=lambda p: p.stat().st_size, reverse=True)
    if not reverso_candidates:
        print(f"[ERRO] LV reverso não encontrado em {fase6}")
        return 1
    reverso_dxf = reverso_candidates[0]

    # Localizar DXF gerado (o mais recente LV_stog_quality ou preview)
    # O gerado pode ser o mesmo arquivo se foi sobrescrito, ou LV_preview_*.dxf
    # Para o pipeline granular, usamos --item para gerar individualmente
    gen_dxf_default = fase6 / 'LV_stog_quality.dxf'

    # Localizar gerador
    script_dir = Path(__file__).parent
    generator = script_dir / 'gerar_lv_dxf_stog.py'
    if not generator.exists():
        print(f"[ERRO] gerar_lv_dxf_stog.py não encontrado em {script_dir}")
        return 1

    # API key NIM
    api_key = os.environ.get(NIM_API_KEY_ENV, '')
    if not api_key and not args.sem_api:
        # Tentar ler do .env
        for env_file in [obra_path / '.env', Path('D:/Agente-cad-PYSIDE/.env'),
                         Path('D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/.env')]:
            if env_file.exists():
                for line in env_file.read_text(encoding='utf-8', errors='replace').splitlines():
                    if line.startswith('NVIDIA_API_KEY='):
                        api_key = line.split('=', 1)[1].strip().strip('"\'')
                        break
            if api_key:
                break
        if not api_key:
            print(f"[WARN] {NIM_API_KEY_ENV} não definido — usando --sem-api automaticamente")
            args.sem_api = True

    print(f"\n{'='*70}")
    print(f"VALIDAÇÃO GRANULAR LV: {obra_path.name}")
    print(f"  Reverso: {reverso_dxf.name}")
    print(f"  Scoring: programático + {'NIM visual' if getattr(args, 'nim', False) else 'sem NIM visual'}")
    print(f"{'='*70}")

    # 1. Encontrar bboxes das vigas no reverso
    print("\n[1] Detectando vigas no DXF reverso...")
    viga_bboxes = find_viga_bboxes(reverso_dxf)
    if not viga_bboxes:
        print("[ERRO] Nenhuma viga encontrada no DXF reverso")
        return 1
    print(f"  {len(viga_bboxes)} vigas detectadas: {sorted(viga_bboxes.keys(), key=lambda v: int(re.search(r'\\d+', v).group()) if re.search(r'\\d+', v) else 0)[:10]}")

    # 2. Selecionar vigas a processar
    def sort_key(v):
        m = re.search(r'\d+', v)
        return int(m.group()) if m else 0

    if args.viga:
        vigas_to_process = [args.viga.upper()]
    else:
        all_sorted = sorted(viga_bboxes.keys(), key=sort_key)
        vigas_to_process = all_sorted[:args.n]

    print(f"\n[2] Processando {len(vigas_to_process)} viga(s): {vigas_to_process}")

    # 3. Processar cada viga
    results = {}
    for viga_name in vigas_to_process:
        print(f"\n  --- {viga_name} ---")

        if viga_name not in viga_bboxes:
            print(f"  [SKIP] {viga_name} não encontrada no reverso")
            continue

        bbox = viga_bboxes[viga_name]

        # 3a. Renderizar reverso
        rev_png_path = out_dir / f"{viga_name}_reverso.png"
        print(f"  Renderizando reverso ({rev_png_path.name})...")
        img_reverso = render_dxf_bbox(reverso_dxf, bbox, dpi=args.dpi,
                                       save_path=rev_png_path)

        # 3b. Gerar DXF individual
        print(f"  Gerando DXF {viga_name}...")
        gen_dxf = generate_single_viga(obra_path, viga_name, generator, fase6)

        img_gerado = None
        if gen_dxf and gen_dxf.exists():
            # 3c. Renderizar gerado: usar bbox da viga no DXF gerado
            print(f"  Detectando bbox no gerado ({gen_dxf.name})...")
            gen_bboxes = find_viga_bboxes(gen_dxf, n_max=5)
            # Pegar o primeiro bbox (deve ser o único ou o mais relevante)
            if gen_bboxes:
                gen_bbox = list(gen_bboxes.values())[0]
            else:
                # Fallback: bbox de tudo no gerado
                print("  [WARN] Sem texto no gerado — renderizando tudo")
                gen_bbox = _full_dxf_bbox(gen_dxf)

            gen_png_path = out_dir / f"{viga_name}_gerado.png"
            print(f"  Renderizando gerado ({gen_png_path.name})...")
            img_gerado = render_dxf_bbox(gen_dxf, gen_bbox, dpi=args.dpi,
                                          save_path=gen_png_path)
        else:
            print(f"  [WARN] Gerado não disponível para {viga_name}")

        # 3d. Salvar side-by-side para inspeção
        if img_gerado:
            side_path = out_dir / f"{viga_name}_comparacao.png"
            from PIL import Image as _PIL_Image
            try:
                combined = _make_side_by_side(img_reverso, img_gerado, viga_name)
                side_path.write_bytes(combined)
                print(f"  Side-by-side: {side_path.name}")
            except Exception as e:
                print(f"  [WARN] Side-by-side: {e}")

        # 3e. Scoring: NIM vision (padrão) + programático (suplementar)
        nim_result = {}
        prog_result = {}
        if gen_dxf and gen_dxf.exists():
            # Scoring programático (rápido, sempre)
            prog_result = compare_dxf_structural(reverso_dxf, bbox, gen_dxf)
            prog_sc = score_from_result(prog_result)
            print(f"  Prog score: {prog_sc:.1f}/100 | {prog_result.get('resumo','')[:70]}")

            # NIM vision (principal)
            if not args.sem_api and img_gerado and api_key:
                print(f"  Chamando NIM ({NVIDIA_MODEL_DEF})...")
                t0 = time.time()
                nim_result = compare_with_nim(img_reverso, img_gerado, viga_name, api_key)
                elapsed = time.time() - t0
                if 'erro' in nim_result:
                    print(f"  [ERRO NIM] {nim_result['erro']}")
                    nim_result = prog_result  # fallback para programático
                    nim_result['_fallback'] = 'programmatic'
                else:
                    sc = score_from_result(nim_result)
                    print(f"  NIM score: {sc:.1f}/100 | {nim_result.get('resumo','')[:80]} ({elapsed:.1f}s)")
            elif args.sem_api:
                nim_result = prog_result
                print("  [SEM-API] usando score programático")
            else:
                nim_result = prog_result
        else:
            print("  [SKIP] Gerado não disponível — sem score")

        results[viga_name] = {
            'bbox_reverso': bbox,
            'gen_dxf': str(gen_dxf) if gen_dxf else None,
            'nim': nim_result,
            'score': score_from_result(nim_result) if nim_result and 'erro' not in nim_result else None,
            'rev_png': str(rev_png_path),
            'gen_png': str(out_dir / f"{viga_name}_gerado.png") if img_gerado else None,
        }

    # 4. Relatório final
    print(f"\n{'='*70}")
    print(f"RELATÓRIO GRANULAR — {obra_path.name}")
    print(f"{'='*70}")
    for vname, r in results.items():
        sc = r.get('score')
        sc_str = f"{sc:.1f}/100" if sc is not None else "N/A (sem API)"
        nim = r.get('nim', {})
        resumo = nim.get('resumo', '') if isinstance(nim, dict) else ''
        print(f"  {vname:6} | Score: {sc_str} | {resumo[:60]}")
        if isinstance(nim, dict) and nim.get('ausentes'):
            print(f"         Ausentes: {', '.join(nim['ausentes'][:5])}")

    # Salvar JSON
    report_path = out_dir / 'relatorio_granular.json'
    report_path.write_text(
        json.dumps({'obra': obra_path.name, 'vigas': results}, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    print(f"\n  Relatório salvo: {report_path}")
    print(f"  Imagens em: {out_dir}")
    return 0


def _full_dxf_bbox(dxf_path: Path):
    """Retorna bbox de todo o conteúdo do DXF."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    xs, ys = [], []
    for e in msp:
        bb = _entity_bbox(e)
        if bb:
            xs.extend([bb[0], bb[2]])
            ys.extend([bb[1], bb[3]])
    if xs:
        return (min(xs)-50, min(ys)-50, max(xs)+50, max(ys)+50)
    return (-100, -100, 1000, 500)


if __name__ == '__main__':
    sys.exit(main())
