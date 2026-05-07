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

# ─── Providers de Visão (NVIDIA NIM preferido, fallback Anthropic) ────────────
OPENAI_OK = False
ANTHROPIC_OK = False
try:
    from openai import OpenAI as _OpenAI
    OPENAI_OK = True
except ImportError:
    pass
try:
    import anthropic as _anthropic_mod
    ANTHROPIC_OK = True
except ImportError:
    pass

# ─── Constantes ───────────────────────────────────────────────────────────────
DATA_DIR_DEFAULT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
DISCOVERY_JSON   = DATA_DIR_DEFAULT / "dxf_discovery.json"
TIPOS_DXF        = ["PL", "LV", "FV", "LJ"]
GERADO_NOMES     = {
    "PL": "PL_gerado.dxf",
    "LV": "LV_gerado.dxf",
    "FV": "FV_gerado.dxf",
    "LJ": "LJ_gerado.dxf",
}
RENDER_DPI   = 150    # resolução PNG (maior = mais detalhe, mais lento)
TILES_DEFAULT = 3     # grid N×N para fragmentação
MAX_IMG_KB   = 1800   # limite de tamanho de tile para API

# Providers e modelos suportados
NVIDIA_BASE_URL  = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL_DEF = "meta/llama-3.2-90b-vision-instruct"
ANTHROPIC_MODEL  = "claude-opus-4-5"

VISION_MODEL = NVIDIA_MODEL_DEF  # default

PROMPT_TILE = """\
Você é um engenheiro civil especialista em projetos estruturais analisando desenhos CAD.

Você está comparando duas imagens de um mesmo TILE (fragmento) de um pavimento estrutural:
- Tile ESQUERDO: DXF ORIGINAL (STOG — projeto de referência profissional)
- Tile DIREITO: DXF GERADO (output de pipeline automático de engenharia reversa)

IMPORTANTE: O DXF gerado pode não ter carimbo, bordas ou elementos administrativos do STOG.
Foque APENAS nos elementos estruturais: pilares, vigas, lajes, cotas, nomenclatura estrutural.
Se o tile mostrar área em branco/vazia (sem elementos estruturais), retorne score=null.

Analise os elementos estruturais presentes neste tile:
1. **Dimensões/Cotas**: Valores de cotas/medidas estruturais coincidem?
2. **Geometria**: Formas, posições e proporções dos elementos estruturais estão corretas?
3. **Labels/Nomenclatura**: Textos P1/P2/V1/L1 etc. presentes e corretos?
4. **Padrão de linhas**: Tipos de linha adequados por elemento?
5. **Elementos ausentes**: Algum elemento estrutural do STOG falta no gerado?

Retorne JSON APENAS (sem markdown), com esta estrutura exata:
{
  "score": <0-100 ou null se tile vazio>,
  "tile_tem_conteudo": true/false,
  "dimensoes": {"ok": true/false, "nota": "..."},
  "geometria": {"ok": true/false, "nota": "..."},
  "labels": {"ok": true/false, "nota": "..."},
  "linhas": {"ok": true/false, "nota": "..."},
  "elementos_ausentes": ["lista ou []"],
  "resumo": "frase curta"
}"""

PROMPT_FULL = """\
Você é um engenheiro civil especialista em projetos estruturais analisando desenhos CAD.

Você está comparando dois DXFs de um pavimento estrutural tipo {tipo}:
- Imagem ESQUERDA: DXF ORIGINAL STOG (projeto profissional de referência)
- Imagem DIREITA: DXF GERADO automaticamente por pipeline de engenharia reversa

Tipo: {tipo} — {desc_tipo}

CONTEXTO: O gerado não terá elementos administrativos (carimbo, selo, norte, bordas).
O pipeline extrai APENAS o conteúdo estrutural. Avalie fidelidade estrutural, não completude administrativa.

Avalie:
1. **Elementos estruturais**: Todos os pilares/vigas/lajes do STOG estão no gerado?
2. **Dimensões**: Cotas estruturais (B×H pilares, largura vigas, espessura lajes) corretas?
3. **Layout espacial**: Distribuição e posicionamento dos elementos é fiel?
4. **Nomenclatura**: Labels (P1, V1, etc.) corretos e completos?
5. **Usabilidade**: O gerado seria suficiente para orientar execução em obra?

Retorne JSON APENAS (sem markdown):
{{
  "score_global": <0-100>,
  "elementos_estruturais": <0-100>,
  "dimensoes": <0-100>,
  "layout": <0-100>,
  "nomenclatura": <0-100>,
  "usabilidade": <0-100>,
  "pontos_criticos": ["problemas sérios que impediriam uso em obra"],
  "pontos_positivos": ["acertos notáveis do pipeline"],
  "suficiente_para_obra": true/false,
  "resumo_executivo": "2-3 frases avaliando qualidade estrutural do gerado"
}}"""

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
    Lida com: markdown fences, texto antes do JSON, "Resposta final:" etc.
    """
    import re
    text = text.strip()
    # Remove markdown fences
    if text.startswith("```"):
        lines = text.split('\n')
        start = 1
        end = len(lines) - 1 if lines and lines[-1].strip() == '```' else len(lines)
        text = '\n'.join(lines[start:end]).strip()
    # Se ainda tem texto antes do JSON, extrair o primeiro bloco { ... }
    m = re.search(r'\{[\s\S]*\}', text)
    if m:
        text = m.group(0)
    return text.strip()


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
    text = _strip_json(resp.choices[0].message.content)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_response": text, "parse_error": True}


def api_call_anthropic(client, prompt: str, image_bytes: bytes,
                       model: str, max_tokens: int = 1024) -> dict:
    """Chama Claude vision (Anthropic API)."""
    b64 = png_to_base64(image_bytes)
    media_type = "image/png" if image_bytes[:4] == b'\x89PNG' else "image/jpeg"

    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": b64,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    )
    text = _strip_json(msg.content[0].text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_response": text, "parse_error": True}


def api_call(client, prompt: str, image_bytes: bytes,
             model: str, max_tokens: int = 1024) -> dict:
    """Dispatcher: detecta tipo de client e chama o provider correto."""
    if hasattr(client, '_provider') and client._provider == 'nvidia':
        return api_call_nvidia(client, prompt, image_bytes, model, max_tokens)
    elif hasattr(client, 'messages'):
        # Anthropic client
        return api_call_anthropic(client, prompt, image_bytes, model, max_tokens)
    else:
        # OpenAI-compatible (NVIDIA ou outro)
        return api_call_nvidia(client, prompt, image_bytes, model, max_tokens)


def analisar_tiles(client, tiles_sbs: list, model: str,
                   verbose: bool = True) -> list:
    """Analisa cada tile (side-by-side) via API. Retorna lista de resultados."""
    resultados = []
    for r, c, tile_bytes in tiles_sbs:
        if verbose:
            print(f"    Tile ({r},{c}): {len(tile_bytes)//1024}KB → API...", end=" ")
        try:
            res = api_call(client, PROMPT_TILE, tile_bytes, model)
            score = res.get("score", "?")
            if verbose:
                print(f"score={score}")
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
    """Analisa imagem completa (full side-by-side) via API."""
    prompt = PROMPT_FULL.format(tipo=tipo, desc_tipo=DESC_TIPO.get(tipo, tipo))
    if verbose:
        print(f"    Full image: {len(sbs_bytes)//1024}KB → API...", end=" ")
    try:
        res = api_call(client, prompt, sbs_bytes, model, max_tokens=1500)
        if verbose:
            print(f"score={res.get('score_global', '?')}")
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
                t = e.dxftype()
                ent[t] = ent.get(t, 0) + 1
                l = getattr(e.dxf, 'layer', '0')
                lyr[l] = lyr.get(l, 0) + 1
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

    # 2. Renderizar DXFs para PNG
    # Para PL: usar pilares individuais Fase-5 (mais representativo para comparação)
    obra_dir = dxf_stog.parent
    # Subir até encontrar a obra (busca por Fase-1 no caminho)
    for p in dxf_stog.parents:
        if (p / "Fase-1_Ingestao").exists():
            obra_dir = p
            break

    use_sample_pilares = (tipo == "PL")

    if verbose:
        print(f"    Renderizando STOG...", end=" ")
    try:
        png_stog = render_dxf_to_array(dxf_stog)
        if verbose:
            print(f"{len(png_stog)//1024}KB")
    except Exception as e:
        print(f"\n    ERRO render STOG: {e}")
        resultado["visual"] = {"error": f"render_stog: {e}"}
        resultado["score_final"] = est["score_estrutural"]
        return resultado

    if verbose:
        print(f"    Renderizando Gerado (Fase-5 samples)...", end=" ")
    try:
        # Todos os tipos usam samples individuais da Fase-5 (escala legível)
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

    # Salvar PNGs individuais
    out_dir.mkdir(parents=True, exist_ok=True)
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
) -> dict:
    """Valida todos os tipos disponíveis de um pavimento."""
    obra_dir = data_dir / obra_nome
    pav_discovery = discovery.get(obra_nome, {}).get(pav_nome, {})

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

        res_tipo = validar_tipo(
            tipo, dxf_stog, dxf_gen, pav_out,
            client=client, model=model, n_tiles=n_tiles, verbose=verbose,
        )
        resultados_tipo[tipo] = res_tipo

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

    # Salvar JSON do pavimento
    json_path = pav_out / "validation_visual.json"
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
    parser.add_argument("--tipo",     default=None,  choices=["PL","LV","FV","LJ"], help="Validar só este tipo")
    parser.add_argument("--data-dir", default=str(DATA_DIR_DEFAULT), help="Diretório DADOS-OBRAS/")
    parser.add_argument("--out-dir",  default="D:/Agente-cad-PYSIDE/validacao_visual", help="Onde salvar imagens/JSONs")
    parser.add_argument("--tiles",    default=TILES_DEFAULT, type=int, help=f"Grid N×N de tiles (default: {TILES_DEFAULT})")
    parser.add_argument("--model",    default=VISION_MODEL, help=f"Modelo Claude (default: {VISION_MODEL})")
    parser.add_argument("--sem-api",  action="store_true", help="Pular análise API (só estrutural)")
    parser.add_argument("--todos-pavimentos", action="store_true", help="Validar todos os pavimentos da obra")
    parser.add_argument("--all-obras", action="store_true", help="Validar TODAS as obras (1 pav representativo por obra)")
    parser.add_argument("--obras",    default=None,  help="Subset de obras separadas por vírgula (ex: Obra_TREINO_21,Obra_TREINO_14)")
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
            # Fallback para Anthropic
            anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if anthropic_key and ANTHROPIC_OK:
                client = _anthropic_mod.Anthropic(api_key=anthropic_key)
                if model_used == VISION_MODEL:
                    model_used = ANTHROPIC_MODEL
                print(f"[INFO] Provider: Anthropic | Modelo: {model_used}")
            else:
                if not OPENAI_OK:
                    print("[AVISO] openai não instalado: pip install openai")
                elif not nvidia_key:
                    print("[AVISO] NVIDIA_API_KEY não encontrada.")
                if not ANTHROPIC_OK:
                    print("[AVISO] anthropic não instalado: pip install anthropic")
                elif not os.environ.get("ANTHROPIC_API_KEY"):
                    print("[AVISO] ANTHROPIC_API_KEY não encontrada.")
                print("[AVISO] Nenhum provider disponível — rodando só análise estrutural.")

    args.model = model_used

    tipos = [args.tipo] if args.tipo else None

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
                    tipos=tipos, verbose=verbose,
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
                tipos=tipos, verbose=verbose,
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
            tipos=tipos, verbose=verbose,
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
