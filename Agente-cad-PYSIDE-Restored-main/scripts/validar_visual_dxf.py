#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
validar_visual_dxf.py — Validação visual autônoma: STOG original vs DXF gerado.

Pipeline:
  1. Carrega par de DXFs (STOG original + gerado pelo pipeline)
  2. Renderiza ambos para PNG via ezdxf + MatplotlibBackend
  3. Fragmenta cada imagem em tiles N×N para análise focal
  4. Chama Claude vision (API) para comparar cada tile e a imagem completa
  5. Agrega resultados em validation_visual.json com scores estruturados

Uso:
  python scripts/validar_visual_dxf.py --obra Obra_TREINO_21 --pav 12PAV
  python scripts/validar_visual_dxf.py --obra Obra_TREINO_21 --todos-pavimentos
  python scripts/validar_visual_dxf.py --obra Obra_TREINO_21 --pav 12PAV --tipo PL --tiles 2
  python scripts/validar_visual_dxf.py --obra Obra_TREINO_21 --pav 12PAV --sem-api
"""

import argparse
import base64
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

# ─── Matplotlib headless ──────────────────────────────────────────────────────
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

# ─── ezdxf ────────────────────────────────────────────────────────────────────
try:
    import ezdxf
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
except ImportError:
    print("ERRO: ezdxf não instalado. Execute: pip install ezdxf[draw]")
    sys.exit(1)

# ─── Provider de Visão (NVIDIA NIM) ──────────────────────────────────────────
OPENAI_OK = False
try:
    from openai import OpenAI as _OpenAI
    OPENAI_OK = True
except ImportError:
    pass

# ─── Constantes ───────────────────────────────────────────────────────────────
DATA_DIR_DEFAULT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
DISCOVERY_JSON   = DATA_DIR_DEFAULT / "dxf_discovery.json"
TIPOS_DXF        = ["PL", "LV", "FV", "LJ"]
GERADO_NOMES     = {
    "PL": "PL_stog_quality.dxf",
    "LV": "LV_stog_quality.dxf",
    "FV": "FV_stog_quality.dxf",
    "LJ": "LJ_stog_quality.dxf",
}
RENDER_DPI   = 150    # resolução PNG (maior = mais detalhe, mais lento)
TILES_DEFAULT = 3     # grid N×N para fragmentação
MAX_IMG_KB   = 1800   # limite de tamanho de tile para API

# Providers e modelos suportados
NVIDIA_BASE_URL  = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL_DEF = "meta/llama-3.2-90b-vision-instruct"

VISION_MODEL = NVIDIA_MODEL_DEF  # default

PROMPT_TILE = """\
Você é um engenheiro civil especialista em projetos estruturais analisando desenhos CAD.

Você está comparando duas imagens de um mesmo TILE (fragmento) de um pavimento estrutural:
- Tile ESQUERDO: DXF ORIGINAL (STOG — projeto de referência profissional)
- Tile DIREITO: DXF GERADO (output de pipeline automático de engenharia reversa)

IMPORTANTE: O DXF gerado pode não ter carimbo, bordas ou elementos administrativos do STOG.
Foque APENAS nos elementos estruturais: pilares, vigas, lajes, cotas, nomenclatura estrutural.
Se o tile mostrar área em branco/vazia (sem elementos estruturais), retorne tem_conteudo=false.

Responda cada critério com um número inteiro de 0 a 100:
1. tem_conteudo (true/false): Este tile contém elementos estruturais visíveis?
2. geometria (0-100): Formas, posições e proporções dos elementos estruturais são consistentes entre esquerdo e direito?
3. textos_labels (0-100): Textos, labels e nomenclatura (P1/P2/V1/L1 etc.) estão presentes e coincidem?
4. elementos_ausentes: Liste elementos visíveis no STOG (esquerdo) mas ausentes no gerado (direito).

Retorne JSON APENAS (sem markdown):
{
  "tem_conteudo": true,
  "geometria": 80,
  "textos_labels": 70,
  "elementos_ausentes": [],
  "resumo": "frase curta descrevendo diferenças"
}"""

# ─── Prompts específicos por classe ───────────────────────────────────────────

PROMPT_FULL_PL = """\
Você é um engenheiro civil especialista em projetos estruturais analisando desenhos CAD.

Você está comparando dois DXFs de PLANTA DE PILARES (PL):
- Imagem ESQUERDA: DXF ORIGINAL STOG (projeto profissional de referência)
- Imagem DIREITA: DXF GERADO automaticamente por pipeline de engenharia reversa

CONTEXTO: O gerado não terá carimbo, selo ou bordas administrativas.
O pipeline extrai APENAS o conteúdo estrutural (seções transversais dos pilares).
Avalie fidelidade estrutural — NÃO penalize ausência de elementos administrativos.

Responda cada critério com um número inteiro de 0 a 100:
1. contagem (0-100): O número de pilares visíveis no gerado (direita) é comparável ao STOG (esquerda)?
   Conte os elementos presentes e avalie se a quantidade é proporcional.
2. secao_transversal (0-100): As formas das seções transversais dos pilares (retangular, L, T, U) coincidem entre STOG e gerado?
3. dimensoes_bh (0-100): As anotações de dimensão B×H (ex: 20x50, 25x60) estão presentes no gerado e os valores são comparáveis ao STOG?
4. nomenclatura (0-100): Os labels de identificação dos pilares (P01, P02, etc.) estão presentes, posicionados e correspondem ao STOG?
5. hachura_concreto (0-100): O padrão de hachura de concreto está presente nas seções dos pilares no gerado?
6. layout_espacial (0-100): A distribuição espacial relativa dos pilares (posições x/y) no gerado é fiel ao STOG?

Retorne JSON APENAS (sem markdown):
{
  "contagem": 80,
  "secao_transversal": 75,
  "dimensoes_bh": 70,
  "nomenclatura": 85,
  "hachura_concreto": 60,
  "layout_espacial": 80,
  "criticos": ["lista de falhas críticas que impediriam uso em obra"],
  "observacoes": "nota técnica resumida"
}"""

PROMPT_FULL_LV = """\
Você é um engenheiro civil especialista em projetos estruturais analisando desenhos CAD.

Você está comparando dois DXFs de LANÇAMENTO/DETALHE DE VIGAS (LV):
- Imagem ESQUERDA: DXF ORIGINAL STOG (projeto profissional de referência)
- Imagem DIREITA: DXF GERADO automaticamente por pipeline de engenharia reversa

CONTEXTO: O gerado não terá carimbo, selo ou bordas administrativas.
O pipeline extrai vistas laterais de vigas com cortes transversais (faces ABCD).
Avalie fidelidade estrutural — NÃO penalize ausência de elementos administrativos.

Responda cada critério com um número inteiro de 0 a 100:
1. altura_secao (0-100): As alturas das vigas (h) no gerado são proporcionalmente consistentes com o STOG?
2. barras_longitudinais (0-100): As barras de armadura longitudinal (topo e fundo da viga) estão visíveis no gerado de forma similar ao STOG?
3. estribos (0-100): Os estribos (armadura transversal) estão visíveis no gerado com espaçamento comparável ao STOG?
4. faces_identificadas (0-100): As identificações de face (FACE A, B, C, D ou similar) estão presentes e legíveis no gerado?
5. cotas_dimensoes (0-100): As anotações dimensionais (comprimento de vão, altura) estão presentes e comparáveis ao STOG?
6. continuidade_vigas (0-100): O layout de continuidade/sequência entre seções de viga é consistente entre STOG e gerado?

Retorne JSON APENAS (sem markdown):
{
  "altura_secao": 80,
  "barras_longitudinais": 75,
  "estribos": 70,
  "faces_identificadas": 85,
  "cotas_dimensoes": 70,
  "continuidade_vigas": 80,
  "criticos": ["lista de falhas críticas que impediriam uso em obra"],
  "observacoes": "nota técnica resumida"
}"""

PROMPT_FULL_FV = """\
Você é um engenheiro civil especialista em projetos estruturais analisando desenhos CAD.

Você está comparando dois DXFs de FORMA DE VIGAS (FV):
- Imagem ESQUERDA: DXF ORIGINAL STOG (projeto profissional de referência)
- Imagem DIREITA: DXF GERADO automaticamente por pipeline de engenharia reversa

CONTEXTO: O gerado não terá carimbo, selo ou bordas administrativas.
O pipeline extrai moldes/formas de vigas em vista de plano — painéis, lâminas e sarrafos.
Avalie fidelidade estrutural — NÃO penalize ausência de elementos administrativos.

Responda cada critério com um número inteiro de 0 a 100:
1. numero_paineis (0-100): O número de painéis/seções da forma no gerado é comparável ao STOG?
2. dimensoes_forma (0-100): As dimensões gerais da forma (largura, altura total) no gerado são comparáveis ao STOG?
3. lamelas_sarrafos (0-100): O padrão de lamelas/sarrafos (elementos lineares horizontais) está representado no gerado de forma similar ao STOG?
4. aberturas (0-100): As aberturas, entalhes e recortes na forma estão posicionados corretamente no gerado em relação ao STOG?
5. proporcoes_gerais (0-100): As proporções gerais (relação altura/largura) da forma no gerado são consistentes com o STOG?

Retorne JSON APENAS (sem markdown):
{
  "numero_paineis": 80,
  "dimensoes_forma": 75,
  "lamelas_sarrafos": 70,
  "aberturas": 65,
  "proporcoes_gerais": 80,
  "criticos": ["lista de falhas críticas que impediriam uso em obra"],
  "observacoes": "nota técnica resumida"
}"""

PROMPT_FULL_LJ = """\
Você é um engenheiro civil especialista em projetos estruturais analisando desenhos CAD.

Você está comparando dois DXFs de LANÇAMENTO DE LAJES (LJ):
- Imagem ESQUERDA: DXF ORIGINAL STOG (projeto profissional de referência)
- Imagem DIREITA: DXF GERADO automaticamente por pipeline de engenharia reversa

CONTEXTO: O gerado não terá carimbo, selo ou bordas administrativas.
O pipeline extrai a planta de lajes com layout de nervuras, vigas de borda e pilares.
Avalie fidelidade estrutural — NÃO penalize ausência de elementos administrativos.

Responda cada critério com um número inteiro de 0 a 100:
1. contagem_lajes (0-100): O número de elementos de laje no gerado é comparável ao STOG?
2. vigas_borda (0-100): As vigas de borda estão presentes e posicionadas corretamente no gerado em relação ao STOG?
3. sentido_nervuras (0-100): A direção das nervuras/joists no gerado é consistente com o STOG?
4. ids_lajes (0-100): Os identificadores de laje (L01, L02, etc.) estão presentes e correspondem ao STOG?
5. posicao_pilares (0-100): As posições dos pilares/colunas no gerado são consistentes com o STOG?
6. espessura_anotada (0-100): A espessura da laje está anotada no gerado de forma comparável ao STOG?

Retorne JSON APENAS (sem markdown):
{
  "contagem_lajes": 80,
  "vigas_borda": 75,
  "sentido_nervuras": 70,
  "ids_lajes": 80,
  "posicao_pilares": 85,
  "espessura_anotada": 60,
  "criticos": ["lista de falhas críticas que impediriam uso em obra"],
  "observacoes": "nota técnica resumida"
}"""

# Mapeamento tipo → prompt
PROMPT_FULL_MAP = {
    "PL": PROMPT_FULL_PL,
    "LV": PROMPT_FULL_LV,
    "FV": PROMPT_FULL_FV,
    "LJ": PROMPT_FULL_LJ,
}

# Mantido para retrocompatibilidade (não usado internamente — usar PROMPT_FULL_MAP)
PROMPT_FULL = PROMPT_FULL_LJ


# ─── Funções de score determinístico por classe ───────────────────────────────

def calcular_score_full_pl(res: dict) -> float:
    """Score determinístico para Planta de Pilares (PL)."""
    c  = float(res.get("contagem", 0) or 0)
    st = float(res.get("secao_transversal", 0) or 0)
    d  = float(res.get("dimensoes_bh", 0) or 0)
    n  = float(res.get("nomenclatura", 0) or 0)
    h  = float(res.get("hachura_concreto", 0) or 0)
    ls = float(res.get("layout_espacial", 0) or 0)
    return round(c*0.25 + st*0.20 + d*0.20 + n*0.15 + h*0.10 + ls*0.10, 2)


def calcular_score_full_lv(res: dict) -> float:
    """Score determinístico para Lançamento de Vigas (LV)."""
    a  = float(res.get("altura_secao", 0) or 0)
    bl = float(res.get("barras_longitudinais", 0) or 0)
    e  = float(res.get("estribos", 0) or 0)
    fi = float(res.get("faces_identificadas", 0) or 0)
    cd = float(res.get("cotas_dimensoes", 0) or 0)
    cv = float(res.get("continuidade_vigas", 0) or 0)
    return round(a*0.20 + bl*0.25 + e*0.20 + fi*0.10 + cd*0.15 + cv*0.10, 2)


def calcular_score_full_fv(res: dict) -> float:
    """Score determinístico para Forma de Vigas (FV)."""
    np_ = float(res.get("numero_paineis", 0) or 0)
    df  = float(res.get("dimensoes_forma", 0) or 0)
    ls  = float(res.get("lamelas_sarrafos", 0) or 0)
    ab  = float(res.get("aberturas", 0) or 0)
    pg  = float(res.get("proporcoes_gerais", 0) or 0)
    return round(np_*0.25 + df*0.25 + ls*0.20 + ab*0.15 + pg*0.15, 2)


def calcular_score_full_lj(res: dict) -> float:
    """Score determinístico para Lançamento de Lajes (LJ)."""
    cl = float(res.get("contagem_lajes", 0) or 0)
    vb = float(res.get("vigas_borda", 0) or 0)
    sn = float(res.get("sentido_nervuras", 0) or 0)
    il = float(res.get("ids_lajes", 0) or 0)
    pp = float(res.get("posicao_pilares", 0) or 0)
    ea = float(res.get("espessura_anotada", 0) or 0)
    return round(cl*0.25 + vb*0.20 + sn*0.15 + il*0.15 + pp*0.15 + ea*0.10, 2)


# Mapeamento tipo → função de score
SCORE_CALC_MAP = {
    "PL": calcular_score_full_pl,
    "LV": calcular_score_full_lv,
    "FV": calcular_score_full_fv,
    "LJ": calcular_score_full_lj,
}

DESC_TIPO = {
    "PL": "Planta de Pilares — locação e seção transversal dos pilares",
    "LV": "Lançamento de Vigas — distribuição de vigas por face",
    "FV": "Forma de Vigas — detalhes e dimensões das formas/moldes",
    "LJ": "Lançamento de Lajes — geometria e espessura das lajes",
}


# ─── Utilitários ──────────────────────────────────────────────────────────────

def carregar_discovery(data_dir: Path) -> dict:
    disc_path = data_dir / "dxf_discovery.json"
    if not disc_path.exists():
        raise FileNotFoundError(f"dxf_discovery.json não encontrado em {data_dir}")
    return json.loads(disc_path.read_text(encoding="utf-8"))


def encontrar_gerado(obra_dir: Path, tipo: str) -> Optional[Path]:
    fase6 = obra_dir / "Fase-6_Execucao_CAD"
    nome = GERADO_NOMES.get(tipo)
    if not nome:
        return None
    p = fase6 / nome
    return p if p.exists() else None


def detectar_prancha(dxf_path: Path) -> Optional[list]:
    """
    Detecta se um DXF STOG está em "formato prancha" (LO format):
    múltiplos retângulos LWPOLYLINE de tamanho uniforme dispostos em grade.

    Retorna lista de dicts com bounds dos frames detectados, ou None se
    o DXF não estiver no formato prancha.

    Estrutura de cada frame:
      {'x0': float, 'y0': float, 'x1': float, 'y1': float,
       'w': float, 'h': float,
       'inner_x0': float, 'inner_y0': float,
       'inner_x1': float, 'inner_y1': float}

    inner_* = área interna (sem borda + sem carimbo inferior ~15% h)
    """
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
    except Exception:
        return None

    # Coletar todos os LWPOLYLINE do model space
    candidate_rects = []
    for e in msp:
        if e.dxftype() != 'LWPOLYLINE':
            continue
        try:
            pts = [(pt[0], pt[1]) for pt in e.get_points()]
            if len(pts) < 4:
                continue
            xs = [pt[0] for pt in pts]
            ys = [pt[1] for pt in pts]
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            # Somente retângulos "grandes" com aspect ratio razoável (1:3 a 3:1)
            if w < 300 or h < 200:
                continue
            ar = w / h if h > 0 else 0
            if ar < 0.2 or ar > 8:
                continue
            candidate_rects.append({
                'x0': min(xs), 'y0': min(ys),
                'x1': max(xs), 'y1': max(ys),
                'w': round(w), 'h': round(h)
            })
        except Exception:
            continue

    if len(candidate_rects) < 2:
        return None  # Menos de 2 retângulos — não é prancha

    # Agrupar por tamanho (tolerância 5%)
    from collections import defaultdict
    size_groups: dict = defaultdict(list)
    for r in candidate_rects:
        # Chave de tamanho arredondada a 50 unidades
        key = (round(r['w'] / 50) * 50, round(r['h'] / 50) * 50)
        size_groups[key].append(r)

    # Encontrar grupo dominante (mais retângulos do mesmo tamanho)
    dominant = max(size_groups.values(), key=len)
    if len(dominant) < 2:
        return None  # Sem grupo com 2+ retângulos iguais

    # Eliminar duplicatas (mesma posição ±10 unidades)
    unique_frames = []
    for r in dominant:
        is_dup = any(
            abs(r['x0'] - u['x0']) < 10 and abs(r['y0'] - u['y0']) < 10
            for u in unique_frames
        )
        if not is_dup:
            unique_frames.append(r)

    if len(unique_frames) < 2:
        # Fallback: tentar detecção via INSERT blocks repetidos (carimbo)
        return _detectar_prancha_via_inserts(doc)

    # Calcular área interna (strip borda ~2% e carimbo inferior ~15%)
    frames = []
    for r in unique_frames:
        border_x = r['w'] * 0.02
        border_y = r['h'] * 0.02
        carimbo_h = r['h'] * 0.15  # carimbo ocupa ~15% inferior
        frames.append({
            'x0': r['x0'], 'y0': r['y0'], 'x1': r['x1'], 'y1': r['y1'],
            'w': r['w'], 'h': r['h'],
            'inner_x0': r['x0'] + border_x,
            'inner_y0': r['y0'] + carimbo_h,  # acima do carimbo
            'inner_x1': r['x1'] - border_x,
            'inner_y1': r['y1'] - border_y,
        })

    return frames


def _detectar_prancha_via_inserts(doc) -> Optional[list]:
    """
    Fallback para detectar prancha format quando as bordas são LINEs (não LWPOLYLINEs).
    Detecta repetição de INSERT blocks (carimbo) dispostos em grade regular.

    Estratégia:
    - Encontrar block name com ≥4 INSERT repetições no model space
    - Verificar que posições formam grid regular (espaçamento uniforme em X e Y)
    - Derivar frame bounds a partir das posições do carimbo + espaçamento do grid
    - Carimbo está na parte inferior de cada frame
    """
    from collections import defaultdict, Counter

    msp = doc.modelspace()
    # Coletar posições de cada INSERT por block name
    insert_positions: dict = defaultdict(list)
    for e in msp:
        if e.dxftype() != 'INSERT':
            continue
        try:
            name = e.dxf.name
            x, y = e.dxf.insert.x, e.dxf.insert.y
            insert_positions[name].append((x, y))
        except Exception:
            continue

    # Encontrar block mais repetido (≥4 ocorrências — candidato a carimbo)
    candidates = [(name, positions) for name, positions in insert_positions.items()
                  if len(positions) >= 4]
    if not candidates:
        return None

    # Escolher o candidato com mais repetições
    candidates.sort(key=lambda x: -len(x[1]))
    block_name, positions = candidates[0]

    if len(positions) < 4:
        return None

    # Verificar se posições formam grid regular
    xs = sorted(set(round(p[0] / 10) * 10 for p in positions))
    ys = sorted(set(round(p[1] / 10) * 10 for p in positions))

    if len(xs) < 2 or len(ys) < 2:
        return None  # Não forma grade 2D

    # Calcular espaçamento médio entre colunas e linhas
    x_spacings = [xs[i+1] - xs[i] for i in range(len(xs) - 1)]
    y_spacings = [ys[i+1] - ys[i] for i in range(len(ys) - 1)]

    if not x_spacings or not y_spacings:
        return None

    avg_dx = sum(x_spacings) / len(x_spacings)
    avg_dy = sum(y_spacings) / len(y_spacings)

    # Verificar regularidade (variação < 10%)
    if any(abs(s - avg_dx) > abs(avg_dx) * 0.15 for s in x_spacings):
        return None
    if any(abs(s - avg_dy) > abs(avg_dy) * 0.15 for s in y_spacings):
        return None

    # Estimar tamanho do carimbo a partir do block definition
    carimbo_w = abs(avg_dx)
    carimbo_h_est = abs(avg_dy) * 0.17  # carimbo ~17% da altura do frame

    # Calcular tamanho do frame a partir do espaçamento do grid
    frame_w = abs(avg_dx)
    frame_h = abs(avg_dy)

    # Construir frames a partir das posições do carimbo
    # O INSERT do carimbo está no canto inferior-esquerdo do frame
    # (a posição do INSERT é o ponto de inserção do bloco, normalmente canto inf-esq)
    border_frac = 0.015  # 1.5% de margem de borda
    frames = []
    for pos in positions:
        x0 = pos[0]
        y0 = pos[1]  # base inferior (carimbo está aqui)
        x1 = x0 + frame_w
        y1 = y0 + frame_h

        # Área interna: acima do carimbo, dentro da borda
        border_x = frame_w * border_frac
        border_y = frame_h * border_frac
        carimbo_strip = carimbo_h_est

        frames.append({
            'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1,
            'w': frame_w, 'h': frame_h,
            'inner_x0': x0 + border_x,
            'inner_y0': y0 + carimbo_strip,
            'inner_x1': x1 - border_x,
            'inner_y1': y1 - border_y,
        })

    return frames if len(frames) >= 2 else None


def render_dxf_prancha_strip(dxf_path: Path, frames: list,
                              dpi: int = RENDER_DPI) -> bytes:
    """
    Renderiza DXF em formato prancha mostrando APENAS o conteúdo interno
    de cada frame (sem bordas, sem carimbo).

    Estratégia: renderiza o DXF completo em cada subplot com limites de eixo
    restritos à área interna do frame — matplotlib omite entidades fora do
    viewport, produzindo uma visualização limpa do conteúdo de engenharia.

    Retorna PNG bytes com fundo branco.
    """
    try:
        doc = ezdxf.readfile(str(dxf_path))
        ctx = RenderContext(doc)
    except Exception as e:
        raise RuntimeError(f"render_dxf_prancha_strip: erro ao ler DXF: {e}")

    # Organizar frames em grid (máx 4 colunas)
    n = len(frames)
    cols = min(4, n)
    rows = (n + cols - 1) // cols

    # Tamanho da figura baseado no aspect ratio dos frames
    frame_w = frames[0]['w']
    frame_h = frames[0]['h'] - frames[0]['h'] * 0.15  # altura interna (sem carimbo)
    aspect = frame_w / frame_h if frame_h > 0 else 1.5

    fig_w = cols * 4 * aspect
    fig_h = rows * 4
    fig, axes = plt.subplots(rows, cols, figsize=(max(fig_w, 8), max(fig_h, 6)))
    fig.patch.set_facecolor('#1a1a24')

    # Normalizar axes para lista plana
    if rows == 1 and cols == 1:
        axes_flat = [axes]
    elif rows == 1:
        axes_flat = list(axes)
    elif cols == 1:
        axes_flat = [ax for ax in axes]
    else:
        axes_flat = [ax for row in axes for ax in row]

    for ax in axes_flat:
        ax.set_facecolor('#1a1a24')
        ax.axis('off')

    # Ordenar frames por posição (baixo→cima, esq→dir)
    frames_sorted = sorted(frames, key=lambda f: (-round(f['y0'] / 50), round(f['x0'] / 50)))

    for idx, frame in enumerate(frames_sorted):
        if idx >= len(axes_flat):
            break
        ax = axes_flat[idx]
        try:
            backend = MatplotlibBackend(ax)
            frontend = Frontend(ctx, backend)
            frontend.draw_layout(doc.modelspace(), finalize=True)
            # Restringir viewport à área interna do frame (strips border+carimbo)
            ax.set_xlim(frame['inner_x0'], frame['inner_x1'])
            ax.set_ylim(frame['inner_y0'], frame['inner_y1'])
            ax.set_aspect('equal', adjustable='box')
        except Exception as e:
            ax.text(0.5, 0.5, f"err:\n{str(e)[:30]}",
                    transform=ax.transAxes, fontsize=6, color='red',
                    ha='center', va='center')

    plt.tight_layout(pad=0.3)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', facecolor='#1a1a24')
    plt.close(fig)
    buf.seek(0)
    data = buf.read()
    return _dark_to_white_bg(data)


def render_dxf_to_array(dxf_path: Path, dpi: int = RENDER_DPI,
                         force_white_bg: bool = True):
    """
    Renderiza um DXF para bytes PNG via matplotlib.

    Estratégia: renderizar em fundo PRETO (DXF padrão), depois converter
    para fundo branco invertendo apenas o background (não as entidades).
    Isso garante que ACI 7 (branco) seja visível como linha preta no resultado.
    """
    doc = ezdxf.readfile(str(dxf_path))
    ctx = RenderContext(doc)

    # Sempre renderizar com fundo escuro (CAD default) — ACI 7 = branco visível
    fig, ax = plt.subplots(figsize=(16, 12))
    ax.set_aspect('equal')
    ax.axis('off')
    fig.patch.set_facecolor('#1a1a24')
    ax.set_facecolor('#1a1a24')

    try:
        backend = MatplotlibBackend(ax)
        frontend = Frontend(ctx, backend)
        frontend.draw_layout(doc.modelspace(), finalize=True)
    except Exception as e:
        ax.text(0.5, 0.5, f"Render error:\n{e}", transform=ax.transAxes,
                ha='center', va='center', fontsize=9, color='red')

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', facecolor='#1a1a24')
    plt.close(fig)
    buf.seek(0)
    data = buf.read()

    if force_white_bg:
        data = _dark_to_white_bg(data)

    return data


def _dark_to_white_bg(png_bytes: bytes) -> bytes:
    """
    Converte imagem DXF com fundo escuro (#1a1a24) para fundo branco.
    Preserva todas as entidades (linhas, texto) com suas cores.
    Pixels do fundo escuro → branco.
    Pixels brancos (ACI 7) → preto (mantém visibilidade).
    """
    import PIL.Image
    import numpy as np

    img = PIL.Image.open(io.BytesIO(png_bytes)).convert('RGB')
    arr = np.array(img, dtype=np.uint8)

    # Máscara do fundo: pixels próximos de #1a1a24 (26,26,36)
    bg_r, bg_g, bg_b = 26, 26, 36
    tolerance = 20
    bg_mask = (
        (np.abs(arr[:,:,0].astype(int) - bg_r) < tolerance) &
        (np.abs(arr[:,:,1].astype(int) - bg_g) < tolerance) &
        (np.abs(arr[:,:,2].astype(int) - bg_b) < tolerance)
    )
    # Fundo → branco
    arr[bg_mask] = [255, 255, 255]

    # Pixels muito brancos (ACI 7 = branco puro) → preto escuro para visibilidade
    white_mask = (arr[:,:,0] > 240) & (arr[:,:,1] > 240) & (arr[:,:,2] > 240) & ~bg_mask
    arr[white_mask] = [30, 30, 30]

    img2 = PIL.Image.fromarray(arr, 'RGB')
    buf = io.BytesIO()
    img2.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    return buf.read()


FASE5_SUBDIRS = {
    "PL": "DXF_Pilares",
    "LV": "DXF_Vigas",
    "FV": "DXF_Vigas",   # FV usa as mesmas seções de vigas
    "LJ": "DXF_Lajes",
}
FASE5_PATTERNS = {
    "PL": "P*.dxf",
    "LV": "V*.dxf",
    "FV": "V*.dxf",
    "LJ": "L*.dxf",
}


def render_dxf_samples(obra_dir: Path, tipo: str, n_sample: int = 6,
                       label_prefix: str = "") -> Optional[bytes]:
    """
    Renderiza N elementos individuais da Fase-5 em grade 2×N.
    Funciona para PL (pilares), LV/FV (vigas), LJ (lajes).
    """
    subdir = FASE5_SUBDIRS.get(tipo, "DXF_Pilares")
    pattern = FASE5_PATTERNS.get(tipo, "*.dxf")
    fase5_dir = obra_dir / "Fase-5_Geracao_Scripts" / subdir

    if not fase5_dir.exists():
        return None

    files = sorted(fase5_dir.glob(pattern))[:n_sample]
    if not files:
        return None

    cols = min(3, len(files))
    rows = max(1, (len(files) + cols - 1) // cols)
    fig, axes = plt.subplots(rows, cols, figsize=(5 * cols, 4 * rows))
    fig.patch.set_facecolor('white')

    # Normalizar axes para sempre ser 2D
    if rows == 1 and cols == 1:
        axes = [[axes]]
    elif rows == 1:
        axes = [list(axes)]
    elif cols == 1:
        axes = [[a] for a in axes]
    else:
        axes = [list(row) for row in axes]

    for idx, f_path in enumerate(files):
        r, c = idx // cols, idx % cols
        ax = axes[r][c]
        ax.set_facecolor('white')
        ax.axis('off')
        try:
            doc = ezdxf.readfile(str(f_path))
            ctx = RenderContext(doc)
            backend = MatplotlibBackend(ax)
            Frontend(ctx, backend).draw_layout(doc.modelspace(), finalize=True)
            ax.set_title(f_path.stem, fontsize=7, pad=2)
        except Exception as e:
            ax.text(0.5, 0.5, f"Err:\n{str(e)[:40]}",
                    transform=ax.transAxes, fontsize=6, ha='center')

    # Apagar eixos extras
    for idx in range(len(files), rows * cols):
        r, c = idx // cols, idx % cols
        try:
            axes[r][c].set_visible(False)
        except Exception:
            pass

    prefix = label_prefix or tipo
    fig.suptitle(f"{prefix} — Elementos Gerados (amostra {len(files)})", fontsize=9)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def side_by_side_png(png_stog: bytes, png_gen: bytes,
                     titulo: str, out_path: Path) -> bytes:
    """
    Combina dois PNGs lado a lado com mesma escala.
    Normaliza ambos para a mesma resolução (W×H) para comparação direta.
    """
    import PIL.Image
    from PIL import ImageDraw

    img_stog = PIL.Image.open(io.BytesIO(png_stog)).convert('RGB')
    img_gen  = PIL.Image.open(io.BytesIO(png_gen)).convert('RGB')

    # Normalizar: usar o maior como referência de tamanho (manter aspecto)
    target_w = max(img_stog.width, img_gen.width, 800)
    target_h = max(img_stog.height, img_gen.height, 600)

    def fit_to(img, tw, th):
        """Redimensiona mantendo aspecto, com padding branco."""
        ratio = min(tw / img.width, th / img.height)
        nw = max(1, int(img.width * ratio))
        nh = max(1, int(img.height * ratio))
        img_r = img.resize((nw, nh), PIL.Image.LANCZOS)
        canvas = PIL.Image.new('RGB', (tw, th), (255, 255, 255))
        # Centrar
        xoff = (tw - nw) // 2
        yoff = (th - nh) // 2
        canvas.paste(img_r, (xoff, yoff))
        return canvas

    img_stog = fit_to(img_stog, target_w, target_h)
    img_gen  = fit_to(img_gen, target_w, target_h)

    header_h = 50
    gap = 8
    combined = PIL.Image.new('RGB',
        (target_w * 2 + gap, target_h + header_h),
        (230, 230, 230))

    draw = ImageDraw.Draw(combined)
    combined.paste(img_stog, (0, header_h))
    combined.paste(img_gen, (target_w + gap, header_h))

    # Cabeçalho
    draw.rectangle([0, 0, target_w - 1, header_h - 1], fill=(240, 255, 240))
    draw.rectangle([target_w + gap, 0, target_w * 2 + gap - 1, header_h - 1],
                   fill=(240, 240, 255))
    draw.text((target_w // 2 - 50, 8), "STOG ORIGINAL", fill=(0, 120, 0))
    draw.text((target_w + gap + target_w // 2 - 60, 8),
              "GERADO PIPELINE", fill=(0, 0, 160))
    draw.text((10, 28), titulo, fill=(80, 80, 80))

    buf = io.BytesIO()
    combined.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    data = buf.read()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return data


def tile_image(png_bytes: bytes, n: int):
    """
    Divide PNG em grid N×N.
    Retorna lista de (row, col, bytes_png) para cada tile.
    """
    import PIL.Image
    img = PIL.Image.open(io.BytesIO(png_bytes)).convert('RGB')
    W, H = img.size
    tw = W // n
    th = H // n
    tiles = []
    for r in range(n):
        for c in range(n):
            left   = c * tw
            upper  = r * th
            right  = left + tw if c < n - 1 else W
            lower  = upper + th if r < n - 1 else H
            crop = img.crop((left, upper, right, lower))
            buf = io.BytesIO()
            crop.save(buf, format='PNG', optimize=True)
            tiles.append((r, c, buf.getvalue()))
    return tiles


def combine_tiles_side_by_side(png_stog: bytes, png_gen: bytes, n: int):
    """
    Para cada tile (r,c): combina tile STOG | tile GEN lado a lado.
    Retorna lista de (r, c, bytes_side_by_side).
    """
    import PIL.Image
    tiles_stog = {(r, c): b for r, c, b in tile_image(png_stog, n)}
    tiles_gen  = {(r, c): b for r, c, b in tile_image(png_gen, n)}
    combined = []
    for r in range(n):
        for c in range(n):
            ts = PIL.Image.open(io.BytesIO(tiles_stog[(r, c)])).convert('RGB')
            tg = PIL.Image.open(io.BytesIO(tiles_gen[(r, c)])).convert('RGB')
            h = max(ts.height, tg.height)
            new = PIL.Image.new('RGB', (ts.width + tg.width + 4, h), (200, 200, 200))
            new.paste(ts, (0, 0))
            new.paste(tg, (ts.width + 4, 0))
            buf = io.BytesIO()
            new.save(buf, format='PNG', optimize=True)
            combined.append((r, c, buf.getvalue()))
    return combined


def png_to_base64(png_bytes: bytes, max_kb: int = MAX_IMG_KB) -> str:
    """Converte PNG para base64; comprime se maior que max_kb."""
    import PIL.Image
    if len(png_bytes) > max_kb * 1024:
        # Reduzir qualidade/tamanho
        img = PIL.Image.open(io.BytesIO(png_bytes)).convert('RGB')
        scale = (max_kb * 1024 / len(png_bytes)) ** 0.5
        new_w = max(100, int(img.width * scale))
        new_h = max(100, int(img.height * scale))
        img = img.resize((new_w, new_h), PIL.Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=85, optimize=True)
        png_bytes = buf.getvalue()
    return base64.standard_b64encode(png_bytes).decode()


# ─── Chamadas API ─────────────────────────────────────────────────────────────

def _strip_json(text: str) -> str:
    """
    Extrai JSON de resposta de LLM.
    Lida com: markdown fences, texto antes do JSON, JSON truncado, "Resposta final:" etc.
    Estratégia em camadas:
      1. Remove fences markdown (``` / ```json)
      2. Extrai bloco { ... } mais externo (greedy)
      3. Se JSON inválido por truncamento, tenta fechar com }}
      4. Fallback: extrai { ... } mais curto (innermost match)
    """
    import re
    text = text.strip()

    # 1. Remove markdown fences
    if '```' in text:
        # Remove tudo entre ``` e ```
        text = re.sub(r'```(?:json)?\s*', '', text)
        text = re.sub(r'```', '', text)
        text = text.strip()

    # 2. Tentar extrair o bloco JSON mais externo
    def _try_parse_block(s: str) -> str | None:
        """Retorna a substring JSON válida ou None."""
        # Encontrar todos os blocos {…}
        # Usar stack para encontrar o bloco mais externo equilibrado
        start = s.find('{')
        if start == -1:
            return None
        depth = 0
        for i, ch in enumerate(s[start:], start):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return s[start:i+1]
        # JSON truncado — retornar o que encontramos (tentar fechar)
        return s[start:] + '}' * depth if depth > 0 else None

    block = _try_parse_block(text)
    if block:
        return block.strip()

    return text.strip()


def _extract_score_fallback(text: str, key: str = "score_global") -> float | None:
    """
    Extrai valor numérico de score de texto bruto quando JSON parsing falha.
    Lida com:
      - JSON parcial: "score_global": 75
      - Markdown: **Score Global:** 70
      - Texto livre: Score Global: 70, score_global = 75
    """
    import re

    # Mapeia chave JSON para variantes em linguagem natural (markdown do Llama)
    ALIASES = {
        "score_global":          [r"score\s*global",    r"score_global"],
        "score":                 [r"\bscore\b",          r"score_final"],
        "elementos_estruturais": [r"elementos?\s*estruturais?"],
        "layout":                [r"\blayout\b"],
        "dimensoes":             [r"dimens(?:o|ao|oes|ções)"],
        "nomenclatura":          [r"nomenclatura"],
    }
    aliases = ALIASES.get(key, [key])

    # Padrões a tentar para cada alias
    for alias in aliases:
        patterns = [
            # JSON: "score_global": 75
            rf'["\']?{alias}["\']?\s*[=:]\s*(\d+(?:\.\d+)?)',
            # Markdown bold: **Score Global:** 70
            rf'\*{{0,2}}{alias}\*{{0,2}}\s*[:\-]\s*(\d+(?:\.\d+)?)',
            # Texto livre com separadores
            rf'{alias}[^\d]{{0,20}}(\d+(?:\.\d+)?)',
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                try:
                    val = float(m.group(1))
                    if 0 <= val <= 100:
                        return val
                except ValueError:
                    pass
    return None


def api_call_nvidia(client, prompt: str, image_bytes: bytes,
                    model: str, max_tokens: int = 1024) -> dict:
    """Chama NVIDIA NIM vision (OpenAI-compatible API)."""
    b64 = png_to_base64(image_bytes)
    media_type = "image/png" if image_bytes[:4] == b'\x89PNG' else "image/jpeg"

    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{media_type};base64,{b64}",
                        "detail": "high",
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    )
    raw = resp.choices[0].message.content
    text = _strip_json(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback: extrair campos numéricos via regex
        result = {"raw_response": raw, "parse_error": True}
        for key in ("score_global", "score", "elementos_estruturais", "layout"):
            val = _extract_score_fallback(raw, key)
            if val is not None:
                result[key] = val
        return result


def api_call(client, prompt: str, image_bytes: bytes,
             model: str, max_tokens: int = 1024) -> dict:
    """Dispatcher: chama NVIDIA NIM (OpenAI-compatible)."""
    return api_call_nvidia(client, prompt, image_bytes, model, max_tokens)


def calcular_score_tile(res: dict) -> float | None:
    """
    Calcula score de tile a partir dos campos do PROMPT_TILE.
    Fórmula determinística: geometria*0.60 + textos_labels*0.40
    Retorna None se tile não tem conteúdo estrutural.
    """
    tem_conteudo = res.get("tem_conteudo", True)
    if tem_conteudo is False:
        return None
    geo = float(res.get("geometria", 0) or 0)
    txt = float(res.get("textos_labels", 0) or 0)
    return round(geo * 0.60 + txt * 0.40, 2)


def analisar_tiles(client, tiles_sbs: list, model: str,
                   verbose: bool = True) -> list:
    """Analisa cada tile (side-by-side) via API. Retorna lista de resultados."""
    resultados = []
    for r, c, tile_bytes in tiles_sbs:
        if verbose:
            print(f"    Tile ({r},{c}): {len(tile_bytes)//1024}KB → API...", end=" ")
        try:
            res = api_call(client, PROMPT_TILE, tile_bytes, model)
            # Score determinístico (não depende de campo "score" do LLM)
            score_det = calcular_score_tile(res)
            res["score"] = score_det  # manter chave "score" para retrocompat
            res["tile_tem_conteudo"] = res.get("tem_conteudo", True)
            if verbose:
                print(f"score={score_det}")
        except Exception as e:
            res = {"error": str(e)}
            if verbose:
                print(f"ERRO: {e}")
        res["tile_row"] = r
        res["tile_col"] = c
        resultados.append(res)
        time.sleep(0.3)  # rate limit
    return resultados


def analisar_full(client, sbs_bytes: bytes, tipo: str, model: str,
                  verbose: bool = True) -> dict:
    """Analisa imagem completa (full side-by-side) via API com prompt específico por tipo."""
    prompt = PROMPT_FULL_MAP.get(tipo, PROMPT_FULL_LJ)
    if verbose:
        print(f"    Full image [{tipo}]: {len(sbs_bytes)//1024}KB → API...", end=" ")
    try:
        res = api_call(client, prompt, sbs_bytes, model, max_tokens=2000)
        # Calcular score_global determinístico a partir dos critérios respondidos
        score_fn = SCORE_CALC_MAP.get(tipo, calcular_score_full_lj)
        score_det = score_fn(res)
        # Guardar score original do LLM para auditoria, mas usar o determinístico
        if "score_global" in res:
            res["score_global_llm"] = res["score_global"]
        res["score_global"] = score_det
        if verbose:
            print(f"score={score_det}")
    except Exception as e:
        res = {"error": str(e)}
        if verbose:
            print(f"ERRO: {e}")
    return res


# ─── Análise estrutural (sem API) ─────────────────────────────────────────────

def analisar_estrutural(dxf_stog: Path, dxf_gen: Path) -> dict:
    """
    Compara estrutura de entidades e layers sem visão.

    Nota: STOG DXF tem carimbo/blocos administrativos que o gerado não tem.
    Por isso comparamos por tipos estruturais (LWPOLYLINE, LINE, DIMENSION, TEXT, MTEXT)
    e não por total bruto de entidades.
    """
    # Tipos que o gerado SÍ deve ter (estruturais)
    TIPOS_ESTRUTURAIS = {'LWPOLYLINE', 'LINE', 'DIMENSION', 'TEXT', 'MTEXT',
                         'ARC', 'CIRCLE', 'SPLINE', 'POLYLINE', 'SOLID'}

    def _counts(path):
        try:
            doc = ezdxf.readfile(str(path))
            msp = doc.modelspace()
            ent = {}
            lyr = {}
            for e in msp:
                try:
                    t = e.dxftype()
                    ent[t] = ent.get(t, 0) + 1
                    try:
                        l = e.dxf.layer
                    except Exception:
                        l = '0'
                    lyr[l] = lyr.get(l, 0) + 1
                except Exception:
                    pass  # entidade com atributo problemático — ignora
            return ent, lyr
        except Exception as ex:
            return {}, {"ERROR": str(ex)}

    ent_s, lyr_s = _counts(dxf_stog)
    ent_g, lyr_g = _counts(dxf_gen)

    total_s = sum(ent_s.values())
    total_g = sum(ent_g.values())

    # Comparar apenas tipos estruturais (ignora INSERT/BLOCK administrativos)
    struct_s = sum(v for k, v in ent_s.items() if k in TIPOS_ESTRUTURAIS)
    struct_g = sum(v for k, v in ent_g.items() if k in TIPOS_ESTRUTURAIS)
    ratio_struct = struct_g / max(struct_s, 1)

    # Layers comuns vs ausentes
    # Layers administrativos do STOG que podem estar ausentes no gerado (esperado)
    LAYERS_ADMIN = {'CARIMBO', 'TITULO', 'SELO', 'BORDA', 'FOLHA', 'LEGENDA',
                    'NORTE', 'ESCALA', 'LOGO', 'CABECALHO'}
    lyr_s_struct = {l for l in lyr_s if not any(a in l.upper() for a in LAYERS_ADMIN)}
    missing_layers = sorted(lyr_s_struct - set(lyr_g))
    extra_layers   = sorted(set(lyr_g) - set(lyr_s))

    # Score estrutural baseado em tipos estruturais
    score = 0
    if 0.70 <= ratio_struct <= 1.30:
        score += 60
    elif 0.50 <= ratio_struct <= 1.60:
        score += 40
    elif 0.30 <= ratio_struct <= 2.00:
        score += 20
    else:
        score += 5  # ao menos algo foi gerado

    # Layers estruturais faltando
    layer_score = max(0, 40 - len(missing_layers) * 3 - len(extra_layers) * 1)
    score += layer_score

    return {
        "total_entidades_stog": total_s,
        "total_entidades_gen": total_g,
        "struct_entidades_stog": struct_s,
        "struct_entidades_gen": struct_g,
        "ratio_struct": round(ratio_struct, 3),
        "layers_stog": len(lyr_s),
        "layers_gen": len(lyr_g),
        "layers_faltando": missing_layers,
        "layers_extras": extra_layers,
        "score_estrutural": min(100, score),
        "tipos_entidades_stog": ent_s,
        "tipos_entidades_gen": ent_g,
    }


# ─── Core: validar um tipo ────────────────────────────────────────────────────

def validar_tipo(
    tipo: str,
    dxf_stog: Path,
    dxf_gen: Path,
    out_dir: Path,
    client=None,
    model: str = VISION_MODEL,
    n_tiles: int = TILES_DEFAULT,
    verbose: bool = True,
) -> dict:
    """
    Valida um tipo (PL/LV/FV/LJ) comparando STOG vs Gerado.
    Retorna dict com análise estrutural + visual (se client disponível).
    """
    if verbose:
        print(f"\n  [{tipo}] STOG: {dxf_stog.name} | Gerado: {dxf_gen.name}")

    resultado = {
        "tipo": tipo,
        "dxf_stog": str(dxf_stog),
        "dxf_gen": str(dxf_gen),
        "prancha_format": False,  # atualizado abaixo se detectado
    }

    # 1. Análise estrutural (rápida, sem API)
    if verbose:
        print(f"    Análise estrutural...")
    est = analisar_estrutural(dxf_stog, dxf_gen)
    resultado["estrutural"] = est
    if verbose:
        ratio = est['ratio_struct']
        print(f"    Entidades STOG={est['total_entidades_stog']} "
              f"Gerado={est['total_entidades_gen']} "
              f"struct_ratio={ratio:.2f} "
              f"score_est={est['score_estrutural']}")
        if est["layers_faltando"]:
            print(f"    Layers faltando: {est['layers_faltando'][:5]}")

    if client is None:
        resultado["visual"] = None
        resultado["score_final"] = est["score_estrutural"]
        return resultado

    # Guard: DXF gerado vazio (0 entidades) — LLM daria score incorreto para branco
    if est["total_entidades_gen"] == 0:
        if verbose:
            print(f"    AVISO: DXF gerado vazio (0 entidades) — score = estrutural apenas")
        resultado["visual"] = {"error": "dxf_gerado_vazio", "score_global": 0}
        resultado["score_final"] = est["score_estrutural"]
        return resultado

    # 2. Renderizar DXFs para PNG
    # Para PL: usar pilares individuais Fase-5 (mais representativo para comparação)
    obra_dir = dxf_stog.parent
    # Subir até encontrar a obra (busca por Fase-1 no caminho)
    for p in dxf_stog.parents:
        if (p / "Fase-1_Ingestao").exists():
            obra_dir = p
            break

    use_sample_pilares = (tipo == "PL")

    # Verificar se nim_prerender_worker já renderizou os PNGs (evita render caro)
    out_dir.mkdir(parents=True, exist_ok=True)
    prerender_stog = out_dir / f"{tipo}_stog.png"
    prerender_gen  = out_dir / f"{tipo}_gerado.png"
    _prerender_used = False

    if prerender_stog.exists() and prerender_gen.exists():
        # Checar freshness: PNGs devem ser mais novos que ambos os DXFs
        png_mtime  = min(prerender_stog.stat().st_mtime, prerender_gen.stat().st_mtime)
        stog_mtime = dxf_stog.stat().st_mtime
        gen_mtime  = dxf_gen.stat().st_mtime
        if png_mtime >= max(stog_mtime, gen_mtime):
            png_stog = prerender_stog.read_bytes()
            png_gen  = prerender_gen.read_bytes()
            _prerender_used = True
            if verbose:
                print(f"    [PRE-RENDER] usando PNGs prontos "
                      f"({len(png_stog)//1024}KB + {len(png_gen)//1024}KB)")

    if not _prerender_used:
        # Detectar formato prancha (LO format) no STOG
        prancha_frames = detectar_prancha(dxf_stog)
        if prancha_frames:
            resultado["prancha_format"] = True
            resultado["prancha_n_frames"] = len(prancha_frames)
            if verbose:
                print(f"    Prancha format detectado: {len(prancha_frames)} frames — usando splitter")

        if verbose:
            print(f"    Renderizando STOG...", end=" ")
        try:
            if prancha_frames:
                # Renderizar apenas conteúdo interno de cada frame (sem bordas/carimbo)
                png_stog = render_dxf_prancha_strip(dxf_stog, prancha_frames)
            else:
                png_stog = render_dxf_to_array(dxf_stog)
            if verbose:
                print(f"{len(png_stog)//1024}KB{'  [prancha-strip]' if prancha_frames else ''}")
        except Exception as e:
            print(f"\n    ERRO render STOG: {e}")
            resultado["visual"] = {"error": f"render_stog: {e}"}
            resultado["score_final"] = est["score_estrutural"]
            return resultado

        if verbose:
            print(f"    Renderizando Gerado...", end=" ")
        try:
            # LV e FV: usar DXF consolidado Fase-6 (planta com âncoras reais de engenharia reversa)
            # PL e LJ: usar samples individuais Fase-5 (mais representativo para pilares/lajes)
            if tipo in ("LV", "FV"):
                # Consolidated DXF já posicionado com ancoras_vigas.json — mesmo nível do STOG
                png_gen = render_dxf_to_array(dxf_gen)
            else:
                png_gen = render_dxf_samples(obra_dir, tipo, n_sample=6, label_prefix=tipo)
                if png_gen is None:
                    # Fallback: consolidated DXF
                    if verbose:
                        print(f"Fase-5 vazio, fallback consolidado...", end=" ")
                    png_gen = render_dxf_to_array(dxf_gen)
            if verbose:
                print(f"{len(png_gen)//1024}KB")
        except Exception as e:
            print(f"\n    ERRO render Gerado: {e}")
            resultado["visual"] = {"error": f"render_gen: {e}"}
            resultado["score_final"] = est["score_estrutural"]
            return resultado

        # Salvar PNGs individuais (para uso futuro do nim_prerender_worker e cache)
        (out_dir / f"{tipo}_stog.png").write_bytes(png_stog)
        (out_dir / f"{tipo}_gerado.png").write_bytes(png_gen)

    # 3. Imagem side-by-side completa
    sbs_path = out_dir / f"{tipo}_sbs.png"
    try:
        sbs_bytes = side_by_side_png(
            png_stog, png_gen,
            f"{tipo} — STOG vs Gerado",
            sbs_path
        )
        if verbose:
            print(f"    SBS salvo: {sbs_path.name} ({len(sbs_bytes)//1024}KB)")
    except Exception as e:
        if verbose:
            print(f"    AVISO side-by-side: {e} (usando matplotlib fallback)")
        # Fallback: matplotlib side-by-side
        fig, axes = plt.subplots(1, 2, figsize=(20, 10))
        for ax, png, label in [(axes[0], png_stog, "STOG"), (axes[1], png_gen, "GERADO")]:
            import PIL.Image
            img = PIL.Image.open(io.BytesIO(png))
            ax.imshow(img)
            ax.set_title(label, fontsize=14, fontweight='bold')
            ax.axis('off')
        fig.suptitle(f"{tipo} — STOG vs Gerado", fontsize=16)
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        sbs_bytes = buf.getvalue()
        sbs_path.write_bytes(sbs_bytes)

    # 4. Análise full via API
    if verbose:
        print(f"    Análise visual completa:")
    full_res = analisar_full(client, sbs_bytes, tipo, model, verbose)

    # 5. Tiles side-by-side + análise por tile
    if verbose:
        print(f"    Gerando {n_tiles}×{n_tiles} tiles e analisando...")
    try:
        tiles_sbs = combine_tiles_side_by_side(png_stog, png_gen, n_tiles)
        tile_res = analisar_tiles(client, tiles_sbs, model, verbose)
    except Exception as e:
        print(f"    AVISO tiles: {e}")
        tile_res = [{"error": str(e)}]

    # 6. Score final combinado
    # Estratégia: o full_image score é mais confiável porque o modelo vê o contexto geral.
    # Os tiles penalizam injustamente layouts diferentes (STOG planta vs Gerado seções).
    # Usamos full_image como primário e tiles com peso reduzido (30%) como suporte.
    sg = full_res.get("score_global")
    score_full = float(sg) if isinstance(sg, (int, float)) and sg is not None else None

    scores_tiles = []
    for t in tile_res:
        st = t.get("score")
        tem_conteudo = t.get("tile_tem_conteudo", True)
        if isinstance(st, (int, float)) and st is not None and tem_conteudo is not False:
            scores_tiles.append(float(st))
    score_tiles_avg = round(sum(scores_tiles) / len(scores_tiles), 1) if scores_tiles else None

    # Retry inteligente: full_sg=0 explícito mas tiles bons (>70%) → LLM non-determinism
    # Não retentar quando tiles também são ruins (layout genuinamente diferente)
    if score_full == 0.0 and score_tiles_avg is not None and score_tiles_avg >= 70:
        if verbose:
            print(f"    RETRY full image (full_sg=0 mas tiles_avg={score_tiles_avg:.0f}%)...")
        full_res2 = analisar_full(client, sbs_bytes, tipo, model, verbose=False)
        sg2 = full_res2.get("score_global")
        score_full2 = float(sg2) if isinstance(sg2, (int, float)) and sg2 is not None else None
        if score_full2 is not None and score_full2 > 0:
            if verbose:
                print(f"    Retry OK: full_sg={score_full} → {score_full2} (retry)")
            score_full = score_full2
            full_res["score_global_retry"] = score_full2
            full_res["score_global_original"] = 0.0
            full_res["score_global"] = score_full2
        elif verbose:
            print(f"    Retry confirmou full_sg=0 — layout genuinamente diferente")

    if score_full is not None and score_tiles_avg is not None:
        # full=70%, tiles=30% — full image mais confiável para layouts diferentes
        score_visual = round(score_full * 0.70 + score_tiles_avg * 0.30, 1)
    elif score_full is not None:
        score_visual = score_full
    elif score_tiles_avg is not None:
        score_visual = score_tiles_avg
    else:
        score_visual = None

    # Peso do score estrutural vs visual por tipo:
    # - PL: comparação estrutural não é justa (STOG tem blocos, gerado não)
    #        → usar 90% visual + 10% estrutural (quando visual disponível)
    # - LV/FV/LJ: gerado usa Fase-5 (seções individuais) vs STOG (planta completa)
    #        → score estrutural injusto (ratio sempre baixo por design) → 90% visual
    pesos_visual = {"PL": 0.90, "LV": 0.90, "FV": 0.90, "LJ": 0.90}
    peso_vis = pesos_visual.get(tipo, 0.70)
    peso_est = 1.0 - peso_vis

    if score_visual is not None:
        score_final = round(est["score_estrutural"] * peso_est + score_visual * peso_vis, 1)
    else:
        score_final = float(est["score_estrutural"])

    resultado["visual"] = {
        "full": full_res,
        "tiles": tile_res,
        "score_visual_medio": round(score_visual, 1) if score_visual else None,
    }
    resultado["score_final"] = score_final

    if verbose:
        status = "✅" if score_final >= 85 else ("⚠️" if score_final >= 70 else "❌")
        print(f"    {status} Score final [{tipo}]: {score_final}/100"
              f" (est={est['score_estrutural']} + vis={round(score_visual, 1) if score_visual else 'N/A'})")

    return resultado


# ─── Estabilidade: rodar N vezes e tomar mediana ──────────────────────────────

def validar_tipo_estavel(
    tipo, dxf_stog, dxf_gen, pav_out, client, model, n_tiles, verbose, n_runs=1
) -> dict:
    """
    Roda validar_tipo n_runs vezes e retorna resultado com mediana de score_final.
    Reduz variância LLM (±10pp observado) para scores estáveis.
    """
    if n_runs <= 1:
        return validar_tipo(tipo, dxf_stog, dxf_gen, pav_out, client, model, n_tiles, verbose)

    resultados = []
    scores = []
    for run_i in range(n_runs):
        if verbose:
            print(f"    [Run {run_i+1}/{n_runs}]")
        try:
            r = validar_tipo(tipo, dxf_stog, dxf_gen, pav_out, client, model, n_tiles, verbose=False)
            sf = r.get("score_final")
            if isinstance(sf, (int, float)):
                scores.append(sf)
            resultados.append(r)
        except Exception as e:
            if verbose:
                print(f"    [Run {run_i+1}] ERRO: {e}")

    if not resultados:
        return validar_tipo(tipo, dxf_stog, dxf_gen, pav_out, client, model, n_tiles, verbose)

    # Mediana do score_final
    scores.sort()
    n = len(scores)
    mediana = scores[n // 2] if n % 2 == 1 else round((scores[n//2-1] + scores[n//2]) / 2, 1)

    # Usar o resultado mais próximo da mediana como representativo
    melhor = min(resultados, key=lambda r: abs((r.get("score_final") or 0) - mediana))
    melhor["score_final_mediana"] = mediana
    melhor["n_runs"] = n_runs
    melhor["scores_runs"] = scores
    if verbose:
        status = "✅" if mediana >= 85 else ("⚠️" if mediana >= 70 else "❌")
        print(f"    {status} Score MEDIANA [{tipo}]: {mediana}/100  runs={scores}")
    return melhor


# ─── Core: validar um pavimento ───────────────────────────────────────────────

def validar_pavimento(
    obra_nome: str,
    pav_nome: str,
    discovery: dict,
    data_dir: Path,
    out_dir: Path,
    client=None,
    model: str = VISION_MODEL,
    n_tiles: int = TILES_DEFAULT,
    tipos: list = None,
    verbose: bool = True,
    n_runs: int = 1,
) -> dict:
    """Valida todos os tipos disponíveis de um pavimento."""
    obra_dir = data_dir / obra_nome
    obra_disc = discovery.get(obra_nome, {})

    # Fuzzy match: exact → case-insensitive → suffix → contains
    pav_discovery = obra_disc.get(pav_nome, {})
    if not pav_discovery:
        pav_upper = pav_nome.upper()
        for key, val in obra_disc.items():
            if key.upper() == pav_upper:
                pav_discovery = val; break
        if not pav_discovery:
            for key, val in obra_disc.items():
                if key.upper().endswith(pav_upper):
                    pav_discovery = val; break
        if not pav_discovery:
            for key, val in obra_disc.items():
                if pav_upper in key.upper():
                    pav_discovery = val; break

    if not pav_discovery:
        return {"erro": f"Pavimento '{pav_nome}' não encontrado em discovery para '{obra_nome}'"}

    pav_out = out_dir / obra_nome / pav_nome.replace(' ', '_').replace('/', '-')
    pav_out.mkdir(parents=True, exist_ok=True)

    tipos_para_validar = tipos or TIPOS_DXF
    resultados_tipo = {}

    for tipo in tipos_para_validar:
        dxf_stog_path = pav_discovery.get(tipo)
        if not dxf_stog_path:
            if verbose:
                print(f"  [{tipo}] Sem DXF STOG no discovery — skip")
            continue

        dxf_stog = Path(dxf_stog_path)
        if not dxf_stog.exists():
            if verbose:
                print(f"  [{tipo}] STOG não existe em disco: {dxf_stog} — skip")
            continue

        dxf_gen = encontrar_gerado(obra_dir, tipo)
        if not dxf_gen:
            if verbose:
                print(f"  [{tipo}] DXF gerado não encontrado (Fase-6/{GERADO_NOMES[tipo]}) — skip")
            continue

        try:
            res_tipo = validar_tipo_estavel(
                tipo, dxf_stog, dxf_gen, pav_out,
                client=client, model=model, n_tiles=n_tiles, verbose=verbose,
                n_runs=n_runs,
            )
            resultados_tipo[tipo] = res_tipo
        except Exception as e:
            if verbose:
                print(f"  [{tipo}] ERRO em validar_tipo: {e}")
            resultados_tipo[tipo] = {"erro": str(e), "score_final": None}

    # Score global do pavimento
    scores_pav = [r["score_final"] for r in resultados_tipo.values()
                  if "score_final" in r and isinstance(r["score_final"], (int, float))]
    score_pav = round(sum(scores_pav) / len(scores_pav), 1) if scores_pav else None

    resultado_pav = {
        "obra": obra_nome,
        "pavimento": pav_nome,
        "tipos_validados": list(resultados_tipo.keys()),
        "score_pavimento": score_pav,
        "resultados": resultados_tipo,
    }

    # Salvar JSON do pavimento — merge com existente se só validamos tipo(s) específico(s)
    json_path = pav_out / "validation_visual.json"
    if json_path.exists() and tipos is not None:
        # Merge: preserva resultados anteriores, atualiza apenas os tipos recém-validados
        try:
            existing = json.loads(json_path.read_text(encoding="utf-8"))
            merged_resultados = existing.get("resultados", {})
            merged_resultados.update(resultados_tipo)
            merged_tipos = list(merged_resultados.keys())
            merged_scores = [r["score_final"] for r in merged_resultados.values()
                             if "score_final" in r and isinstance(r["score_final"], (int, float))]
            merged_score = round(sum(merged_scores) / len(merged_scores), 1) if merged_scores else None
            resultado_pav = {
                "obra": obra_nome,
                "pavimento": pav_nome,
                "tipos_validados": merged_tipos,
                "score_pavimento": merged_score,
                "resultados": merged_resultados,
            }
        except Exception:
            pass  # Se falhar no merge, salva como está

    json_path.write_text(
        json.dumps(resultado_pav, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    if verbose:
        status = "✅" if (score_pav or 0) >= 85 else ("⚠️" if (score_pav or 0) >= 70 else "❌")
        print(f"\n  {status} SCORE PAVIMENTO [{pav_nome}]: {score_pav}/100")
        print(f"  JSON: {json_path}")

    return resultado_pav


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Validação visual autônoma: STOG vs Gerado (Claude Vision)"
    )
    parser.add_argument("--obra",     default=None,  help="Nome da obra (ex: Obra_TREINO_21)")
    parser.add_argument("--pav",      default=None,  help="Nome do pavimento (ex: 12PAV)")
    parser.add_argument("--tipo",     action="append", choices=["PL","LV","FV","LJ"], help="Validar este(s) tipo(s) (pode repetir: --tipo PL --tipo FV)")
    parser.add_argument("--data-dir", default=str(DATA_DIR_DEFAULT), help="Diretório DADOS-OBRAS/")
    parser.add_argument("--out-dir",  default="D:/Agente-cad-PYSIDE/validacao_visual", help="Onde salvar imagens/JSONs")
    parser.add_argument("--tiles",    default=TILES_DEFAULT, type=int, help=f"Grid N×N de tiles (default: {TILES_DEFAULT})")
    parser.add_argument("--model",    default=VISION_MODEL, help=f"Modelo Claude (default: {VISION_MODEL})")
    parser.add_argument("--sem-api",  action="store_true", help="Pular análise API (só estrutural)")
    parser.add_argument("--todos-pavimentos", action="store_true", help="Validar todos os pavimentos da obra")
    parser.add_argument("--all-obras", action="store_true", help="Validar TODAS as obras (1 pav representativo por obra)")
    parser.add_argument("--obras",    default=None,  help="Subset de obras separadas por vírgula (ex: Obra_TREINO_21,Obra_TREINO_14)")
    parser.add_argument("--n-runs",   default=1, type=int, help="Rodar N vezes e tomar mediana (estabilidade LLM, default: 1)")
    parser.add_argument("--quiet",    action="store_true", help="Menos output")
    args = parser.parse_args()

    if not args.all_obras and not args.obra and not args.obras:
        parser.error("Especifique --obra, --obras ou --all-obras")

    verbose = not args.quiet
    data_dir = Path(args.data_dir)
    out_dir  = Path(args.out_dir)

    # Carregar discovery
    print(f"[INFO] Carregando discovery de {data_dir}...")
    try:
        discovery = carregar_discovery(data_dir)
    except FileNotFoundError as e:
        print(f"[ERRO] {e}")
        sys.exit(1)

    # Validar obra quando em modo single
    obra_nome = args.obra
    if not args.all_obras and not args.obras:
        if obra_nome not in discovery:
            print(f"[ERRO] Obra '{obra_nome}' não encontrada no discovery.")
            print(f"       Obras disponíveis: {list(discovery.keys())[:5]}...")
            sys.exit(1)

    # Configurar API — prioridade: NVIDIA NIM → Anthropic → sem-api
    client = None
    model_used = args.model

    if not args.sem_api:
        # Tentar NVIDIA NIM primeiro
        nvidia_key = os.environ.get("NVIDIA_API_KEY", "")
        if nvidia_key and OPENAI_OK:
            client = _OpenAI(base_url=NVIDIA_BASE_URL, api_key=nvidia_key)
            client._provider = 'nvidia'
            if model_used == VISION_MODEL:
                model_used = NVIDIA_MODEL_DEF
            print(f"[INFO] Provider: NVIDIA NIM | Modelo: {model_used}")
        else:
            if not OPENAI_OK:
                print("[AVISO] openai não instalado: pip install openai")
            elif not nvidia_key:
                print("[AVISO] NVIDIA_API_KEY não encontrada.")
            print("[AVISO] Nenhum provider disponível — rodando só análise estrutural.")

    args.model = model_used

    tipos = args.tipo if args.tipo else None  # action="append" → lista ou None

    # ─── Modo --all-obras ou --obras ──────────────────────────────────────────
    if args.all_obras or args.obras:
        if args.obras:
            obras_lista = [o.strip() for o in args.obras.split(",") if o.strip()]
            obras_lista = [o for o in obras_lista if o in discovery]
        else:
            obras_lista = sorted(discovery.keys())

        print(f"[INFO] Batch: {len(obras_lista)} obras a validar")
        resumo_global = {}

        for obra_nome in obras_lista:
            # Escolher pav representativo: TIPO > 12PAV > primeiro disponível
            pavimentos = list(discovery[obra_nome].keys())
            pav_nome = (
                next((p for p in pavimentos if p.upper() in ["TIPO", "TIP"]), None)
                or next((p for p in pavimentos if "12" in p), None)
                or (pavimentos[0] if pavimentos else None)
            )
            if not pav_nome:
                resumo_global[obra_nome] = {"erro": "sem pavimentos"}
                continue

            # Verificar se tem Fase-6 DXFs gerados
            obra_dir = data_dir / obra_nome
            tem_gerados = any(
                (obra_dir / "Fase-6_Execucao_CAD" / GERADO_NOMES[t]).exists()
                for t in TIPOS_DXF
            )
            if not tem_gerados:
                print(f"\n[SKIP] {obra_nome}: sem DXFs gerados em Fase-6")
                resumo_global[obra_nome] = {"erro": "sem_gerados"}
                continue

            print(f"\n{'='*70}")
            print(f"  OBRA: {obra_nome} | PAV: {pav_nome}")
            print(f"{'='*70}")

            try:
                res = validar_pavimento(
                    obra_nome, pav_nome, discovery, data_dir, out_dir,
                    client=client, model=args.model, n_tiles=args.tiles,
                    tipos=tipos, verbose=verbose, n_runs=args.n_runs,
                )
                resumo_global[obra_nome] = {
                    "pavimento": pav_nome,
                    "score": res.get("score_pavimento"),
                    "tipos": res.get("tipos_validados", []),
                }
            except Exception as e:
                print(f"  [ERRO] {obra_nome}: {e}")
                resumo_global[obra_nome] = {"erro": str(e)}

        # Salvar resumo global
        out_dir.mkdir(parents=True, exist_ok=True)
        resumo_path = out_dir / "resumo_all_obras.json"
        resumo_path.write_text(
            json.dumps(resumo_global, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        print(f"\n{'='*70}")
        print(f"  RESUMO GLOBAL — {len(obras_lista)} obras")
        print(f"{'='*70}")
        scores = []
        for obra, r in resumo_global.items():
            sc = r.get("score")
            if sc is not None:
                scores.append(sc)
                status = "✅" if sc >= 85 else ("⚠️" if sc >= 70 else "❌")
                tipos_ok = "+".join(r.get("tipos", []))
                pav = r.get("pavimento", "?")
                print(f"  {status} {obra:<30} pav={pav:<15} score={sc}  [{tipos_ok}]")
            else:
                print(f"  ⛔ {obra:<30} {r.get('erro','?')}")
        if scores:
            media = round(sum(scores) / len(scores), 1)
            print(f"\n  MÉDIA GLOBAL: {media}/100 ({len(scores)} obras com score)")
        print(f"\n  Resumo: {resumo_path}")
        return

    # ─── Modo single-obra ─────────────────────────────────────────────────────
    obra_nome = args.obra
    resultados_finais = {}

    if args.todos_pavimentos:
        pavimentos = list(discovery[obra_nome].keys())
        print(f"[INFO] Obra '{obra_nome}': {len(pavimentos)} pavimentos")
        for pav in pavimentos:
            print(f"\n{'='*60}")
            print(f"  Pavimento: {pav}")
            print(f"{'='*60}")
            res = validar_pavimento(
                obra_nome, pav, discovery, data_dir, out_dir,
                client=client, model=args.model, n_tiles=args.tiles,
                tipos=tipos, verbose=verbose, n_runs=args.n_runs,
            )
            resultados_finais[pav] = res
    else:
        # Pavimento específico
        pav_nome = args.pav
        if not pav_nome:
            # Auto-detectar: pegar primeiro disponível
            pavimentos = list(discovery[obra_nome].keys())
            pav_nome = pavimentos[0] if pavimentos else None
            if pav_nome:
                print(f"[INFO] --pav não especificado, usando: '{pav_nome}'")
            else:
                print(f"[ERRO] Nenhum pavimento encontrado para '{obra_nome}'")
                sys.exit(1)

        print(f"\n{'='*60}")
        print(f"  Obra: {obra_nome} | Pavimento: {pav_nome}")
        print(f"{'='*60}")

        res = validar_pavimento(
            obra_nome, pav_nome, discovery, data_dir, out_dir,
            client=client, model=args.model, n_tiles=args.tiles,
            tipos=tipos, verbose=verbose, n_runs=args.n_runs,
        )
        resultados_finais[pav_nome] = res

    # Relatório consolidado
    out_dir.mkdir(parents=True, exist_ok=True)
    consolidado_path = out_dir / f"consolidado_{obra_nome}.json"
    consolidado_path.write_text(
        json.dumps(resultados_finais, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # Resumo final
    print(f"\n{'='*60}")
    print(f"  RESUMO FINAL — {obra_nome}")
    print(f"{'='*60}")
    for pav, res in resultados_finais.items():
        sp = res.get("score_pavimento")
        tipos_ok = res.get("tipos_validados", [])
        status = "✅" if (sp or 0) >= 85 else ("⚠️" if (sp or 0) >= 70 else "❌")
        print(f"  {status} {pav:<30} score={sp}  tipos={'+'.join(tipos_ok)}")
    print(f"\n  Consolidado: {consolidado_path}")
    print(f"  Imagens em: {out_dir}/")


if __name__ == "__main__":
    main()
