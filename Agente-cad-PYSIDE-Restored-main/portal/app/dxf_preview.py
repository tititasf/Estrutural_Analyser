"""Renderização DXF→PNG (2026-07-06) — para telas que só têm DXF, sem preview
visual pronto (Recortes, N5). Reusa `ezdxf.addons.drawing` (matplotlib Agg,
headless) — biblioteca já instalada, nenhuma dependência nova.

O portal NUNCA escreve nos DXFs originais — só LÊ e rasteriza pra PNG, com
cache em disco (mesmo diretório da obra) pra não re-renderizar a cada request.
"""

from __future__ import annotations

import hashlib
import io
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("portal.dxf_preview")

BBox = tuple[float, float, float, float]  # (x0, y0, x1, y1)


def obter_bbox_dxf(dxf_path: Path) -> Optional[BBox]:
    """Bounding box real (extents) de todas as entidades do modelspace."""
    import ezdxf
    import ezdxf.bbox as ez_bbox

    doc = ezdxf.readfile(str(dxf_path))
    ext = ez_bbox.extents(doc.modelspace())
    if not ext.has_data:
        return None
    return (ext.extmin.x, ext.extmin.y, ext.extmax.x, ext.extmax.y)


def renderizar_dxf_png(
    dxf_path: Path, *, bbox: Optional[BBox] = None,
    largura_px: int = 640, altura_px: int = 480, margem_pct: float = 0.08,
) -> bytes:
    """Rasteriza 1 DXF (ou uma região `bbox` dele) em PNG (fundo escuro, mesmo
    estilo das fichas HTML já geradas pelo SA). `bbox` opcional recorta a
    visualização (usado pra comparar a MESMA região no DXF bruto vs limpo).

    `margem_pct` [2026-07-06] — folga ao redor do bbox. 0.08 (default) dá
    contexto (usado no "bruto"); `margem_pct=0.0` enquadra só a geometria em
    si, sem sobra — usado no "detalhes e convenções" (zoom fechado pra ler
    hachura/cota/texto do recorte com nitidez).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import ezdxf
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    fig = plt.figure(figsize=(largura_px / 100, altura_px / 100), dpi=100)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_facecolor("black")
    ax.set_axis_off()
    ctx = RenderContext(doc)
    backend = MatplotlibBackend(ax)
    Frontend(ctx, backend).draw_layout(msp, finalize=True)

    # [FIX 2026-07-07] `finalize=True` acima reajusta fig.set_size_inches()
    # internamente pra "encaixar" na proporção dos dados, DESCARTANDO o
    # figsize que pedimos (achado ao vivo: pedindo 2400x1153 saía 999x480 —
    # a altura sempre virava o default do matplotlib, 4.8in, e a largura era
    # recalculada só a partir dele). Reforça o tamanho pedido DEPOIS do draw.
    fig.set_size_inches(largura_px / 100, altura_px / 100)

    if bbox is not None:
        x0, y0, x1, y1 = bbox
        margem_x = max((x1 - x0) * margem_pct, 0.5)
        margem_y = max((y1 - y0) * margem_pct, 0.5)
        ax.set_xlim(x0 - margem_x, x1 + margem_x)
        ax.set_ylim(y0 - margem_y, y1 + margem_y)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, facecolor="black")
    plt.close(fig)
    return buf.getvalue()

def renderizar_dxf_svg(
    dxf_path: Path, *, bbox: Optional[BBox] = None,
    largura_px: int = 640, altura_px: int = 480, margem_pct: float = 0.08,
) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import ezdxf
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    fig = plt.figure(figsize=(largura_px / 100, altura_px / 100), dpi=100)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_facecolor("black")
    ax.set_axis_off()
    ctx = RenderContext(doc)
    backend = MatplotlibBackend(ax)
    Frontend(ctx, backend).draw_layout(msp, finalize=True)

    fig.set_size_inches(largura_px / 100, altura_px / 100)

    if bbox is not None:
        x0, y0, x1, y1 = bbox
        margem_x = max((x1 - x0) * margem_pct, 0.5)
        margem_y = max((y1 - y0) * margem_pct, 0.5)
        ax.set_xlim(x0 - margem_x, x1 + margem_x)
        ax.set_ylim(y0 - margem_y, y1 + margem_y)

    buf = io.BytesIO()
    fig.savefig(buf, format="svg", facecolor="black")
    plt.close(fig)
    return buf.getvalue()


def _hash_cache(dxf_path: Path, bbox: Optional[BBox], margem_pct: float, tamanho: tuple[int, int]) -> str:
    chave = f"{dxf_path}|{dxf_path.stat().st_mtime}|{bbox}|{margem_pct}|{tamanho}"
    return hashlib.sha1(chave.encode("utf-8")).hexdigest()[:20]


def renderizar_dxf_png_cacheado(
    dxf_path: Path, cache_dir: Path, *, bbox: Optional[BBox] = None, margem_pct: float = 0.08,
    largura_px: int = 640, altura_px: int = 480,
) -> bytes:
    """Mesma coisa que `renderizar_dxf_png`, mas grava/lê de um cache em disco
    (`cache_dir/.previews/<hash>.png`) pra não re-renderizar toda vez que o
    usuário reabre a mesma tela."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    caminho_cache = cache_dir / f"{_hash_cache(dxf_path, bbox, margem_pct, (largura_px, altura_px))}.png"
    if caminho_cache.is_file():
        return caminho_cache.read_bytes()
    dados = renderizar_dxf_png(dxf_path, bbox=bbox, margem_pct=margem_pct,
                                largura_px=largura_px, altura_px=altura_px)
    try:
        caminho_cache.write_bytes(dados)
    except OSError as exc:
        log.warning("falha ao gravar cache de preview em %s: %s", caminho_cache, exc)
    return dados

def renderizar_dxf_svg_cacheado(
    dxf_path: Path, cache_dir: Path, *, bbox: Optional[BBox] = None, margem_pct: float = 0.08,
    largura_px: int = 640, altura_px: int = 480,
) -> bytes:
    cache_dir.mkdir(parents=True, exist_ok=True)
    caminho_cache = cache_dir / f"{_hash_cache(dxf_path, bbox, margem_pct, (largura_px, altura_px))}.svg"
    if caminho_cache.is_file():
        return caminho_cache.read_bytes()
    dados = renderizar_dxf_svg(dxf_path, bbox=bbox, margem_pct=margem_pct,
                                largura_px=largura_px, altura_px=altura_px)
    try:
        caminho_cache.write_bytes(dados)
    except OSError as exc:
        log.warning("falha ao gravar cache de preview SVG em %s: %s", caminho_cache, exc)
    return dados


def renderizar_dxf_completo_cacheado(
    dxf_path: Path, cache_dir: Path, *, alvo_px: int = 2400, margem_pct: float = 0.03,
) -> bytes:
    """[2026-07-07] Foto INTEIRA em alta resolução — pedido explícito do dono
    ("quero eles inteiros em formato de foto alta dimensão e qualidade"). Usa
    o bbox real do próprio DXF (não um bbox externo recortado) e calcula
    largura/altura mantendo a proporção real do desenho, com o lado maior em
    `alvo_px` — em vez do 640x480 fixo (baixa resolução, usado só pros crops
    pequenos por elemento)."""
    bbox = obter_bbox_dxf(dxf_path)
    if bbox is None:
        return renderizar_dxf_svg_cacheado(dxf_path, cache_dir, largura_px=alvo_px, altura_px=int(alvo_px * 0.75))
    x0, y0, x1, y1 = bbox
    largura_real = max(x1 - x0, 1.0)
    altura_real = max(y1 - y0, 1.0)
    if largura_real >= altura_real:
        largura_px = alvo_px
        altura_px = max(int(alvo_px * (altura_real / largura_real)), 200)
    else:
        altura_px = alvo_px
        largura_px = max(int(alvo_px * (largura_real / altura_real)), 200)
    return renderizar_dxf_svg_cacheado(
        dxf_path, cache_dir, bbox=bbox, margem_pct=margem_pct,
        largura_px=largura_px, altura_px=altura_px,
    )
