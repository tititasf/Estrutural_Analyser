"""Renderização DXF→PNG (2026-07-06) — para telas que só têm DXF, sem preview
visual pronto (Recortes, N5). Reusa `ezdxf.addons.drawing` (matplotlib Agg,
headless) — biblioteca já instalada, nenhuma dependência nova.

O portal NUNCA escreve nos DXFs originais — só LÊ e rasteriza pra PNG, com
cache em disco (mesmo diretório da obra) pra não re-renderizar a cada request.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger("portal.dxf_preview")

BBox = tuple[float, float, float, float]  # (x0, y0, x1, y1)

# Preview web: lado maior em px. 2400 gerava SVG ~28MB e pan/zoom morto;
# 1200 + traços afinados mantém legibilidade e carrega em fração do tempo.
# Hash de cache inclui PREVIEW_CACHE_TAG — muda a tag → regenera, não reusa
# cache gordo/grosso.
PREVIEW_ALVO_PX = 1200
PREVIEW_CACHE_TAG = "v5structThin"
# Multiplica stroke-width do matplotlib (tipicamente ~0.72).
# v5: fator baixo + CSS non-scaling-stroke em px (linhas do estrutural
# ficam finas em QUALQUER zoom — antes só o overlay de vínculos era fino).
_STROKE_THIN_FACTOR = 0.18
# Espessura visual do estrutural em pixels de tela (não escala com zoom).
_STROKE_SCREEN_PX = 0.55


@dataclass(frozen=True)
class SvgComTransform:
    """SVG + o que o front precisa para mapear pixel ↔ coordenada DXF.

    Sem isto não há como desenhar sobre o estrutural: o clique do usuário chega em
    pixel do SVG e o recorte precisa de coordenada DXF real
    (`docs/MASTERPLAN-CONSOLIDACAO-ENTREGA.md` P1).

    `bbox_dxf` são os limites REAIS dos eixos após o render, não os pedidos. O backend
    CAD do ezdxf força `aspect='equal'`, então o matplotlib expande um dos eixos para
    manter a proporção — usar o bbox pedido erraria o mapeamento no eixo expandido.
    """

    svg: bytes
    bbox_dxf: BBox
    largura_px: int
    altura_px: int

    def px_para_dxf(self, px: float, py: float) -> tuple[float, float]:
        """Pixel do SVG (origem no topo-esquerda) → coordenada DXF."""
        x0, y0, x1, y1 = self.bbox_dxf
        fx = px / self.largura_px if self.largura_px else 0.0
        fy = py / self.altura_px if self.altura_px else 0.0
        # Y do SVG cresce para baixo; Y do DXF cresce para cima.
        return (x0 + fx * (x1 - x0), y1 - fy * (y1 - y0))

    def dxf_para_px(self, x: float, y: float) -> tuple[float, float]:
        """Coordenada DXF → pixel do SVG (inverso exato de `px_para_dxf`)."""
        x0, y0, x1, y1 = self.bbox_dxf
        largura = (x1 - x0) or 1.0
        altura = (y1 - y0) or 1.0
        return ((x - x0) / largura * self.largura_px,
                (y1 - y) / altura * self.altura_px)

    def como_dict(self) -> dict:
        """Payload JSON para o front (o SVG vai por fora, é bytes)."""
        return {
            "bbox_dxf": list(self.bbox_dxf),
            "largura_px": self.largura_px,
            "altura_px": self.altura_px,
        }


def obter_bbox_dxf(dxf_path: Path) -> Optional[BBox]:
    """Bounding box real (extents) de todas as entidades do modelspace."""
    import ezdxf
    import ezdxf.bbox as ez_bbox

    doc = ezdxf.readfile(str(dxf_path))
    ext = ez_bbox.extents(doc.modelspace())
    if not ext.has_data:
        return None
    return (ext.extmin.x, ext.extmin.y, ext.extmax.x, ext.extmax.y)


_RE_STROKE_WIDTH = re.compile(r"stroke-width:\s*([0-9]*\.?[0-9]+)", re.IGNORECASE)


def afinar_tracos_svg(svg: bytes, fator: float = _STROKE_THIN_FACTOR) -> bytes:
    """Afina as linhas do DESENHO estrutural (SVG matplotlib).

    1) Multiplica stroke-width inline (unidades do viewBox).
    2) Injeta CSS com ``vector-effect: non-scaling-stroke`` + largura em **px**:
       sem isso, no zoom-in as linhas do fundo engordam (só os vínculos/
       destaques ficavam finos — achado do dono 2026-07-31).
    """
    if not svg:
        return svg
    try:
        texto = svg.decode("utf-8")
    except UnicodeDecodeError:
        texto = svg.decode("latin-1", errors="replace")

    def _repl(m: re.Match[str]) -> str:
        try:
            v = float(m.group(1)) * float(fator)
        except (TypeError, ValueError):
            return m.group(0)
        if v < 0.04:
            v = 0.04
        return f"stroke-width: {v:.4g}"

    texto = _RE_STROKE_WIDTH.sub(_repl, texto)
    # !important vence o style="" inline do matplotlib (sem !important).
    px = f"{_STROKE_SCREEN_PX:g}"
    estilo = (
        "<style type=\"text/css\" id=\"cad-thin-strokes\"><![CDATA["
        "path,line,polyline,polygon{"
        "vector-effect:non-scaling-stroke!important;"
        f"stroke-width:{px}px!important;"
        "stroke-linecap:butt!important;"
        "stroke-linejoin:miter!important;"
        "}"
        "]]></style>"
    )
    # remove estilo antigo se re-afinarmos
    texto = re.sub(
        r"<style[^>]*id=\"cad-thin-strokes\"[^>]*>.*?</style>",
        "",
        texto,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if 'id="cad-thin-strokes"' not in texto:
        texto = re.sub(
            r"(<svg\b[^>]*>)",
            r"\1" + estilo,
            texto,
            count=1,
            flags=re.IGNORECASE,
        )
    return texto.encode("utf-8")


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

def renderizar_dxf_svg_com_transform(
    dxf_path: Path, *, bbox: Optional[BBox] = None,
    largura_px: int = 640, altura_px: int = 480, margem_pct: float = 0.08,
) -> SvgComTransform:
    """Renderiza SVG e devolve junto a transform pixel ↔ DXF.

    Base do viewer de desenho (P1). Os eixos ocupam a figura inteira
    (`add_axes((0,0,1,1))`), então o mapeamento é linear e exato — mas os limites
    precisam ser lidos DEPOIS do `savefig`, porque é o draw que aplica o
    `aspect='equal'` do backend CAD e ajusta o eixo expandido.
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

    fig.set_size_inches(largura_px / 100, altura_px / 100)

    if bbox is not None:
        x0, y0, x1, y1 = bbox
        margem_x = max((x1 - x0) * margem_pct, 0.5)
        margem_y = max((y1 - y0) * margem_pct, 0.5)
        ax.set_xlim(x0 - margem_x, x1 + margem_x)
        ax.set_ylim(y0 - margem_y, y1 + margem_y)

    buf = io.BytesIO()
    fig.savefig(buf, format="svg", facecolor="black")
    # Limites REAIS pós-draw — o savefig acima já resolveu o aspect.
    lim_x = ax.get_xlim()
    lim_y = ax.get_ylim()
    plt.close(fig)
    return SvgComTransform(
        svg=afinar_tracos_svg(buf.getvalue()),
        bbox_dxf=(float(lim_x[0]), float(lim_y[0]), float(lim_x[1]), float(lim_y[1])),
        largura_px=largura_px,
        altura_px=altura_px,
    )


def renderizar_dxf_svg(
    dxf_path: Path, *, bbox: Optional[BBox] = None,
    largura_px: int = 640, altura_px: int = 480, margem_pct: float = 0.08,
) -> bytes:
    """Só os bytes do SVG. Para desenhar sobre o estrutural use
    `renderizar_dxf_svg_com_transform` — sem a transform não há como converter
    o traço do usuário em coordenada DXF."""
    return renderizar_dxf_svg_com_transform(
        dxf_path, bbox=bbox, largura_px=largura_px,
        altura_px=altura_px, margem_pct=margem_pct,
    ).svg


def _hash_cache(dxf_path: Path, bbox: Optional[BBox], margem_pct: float, tamanho: tuple[int, int]) -> str:
    chave = (
        f"{PREVIEW_CACHE_TAG}|{dxf_path}|{dxf_path.stat().st_mtime}|"
        f"{bbox}|{margem_pct}|{tamanho}|{_STROKE_THIN_FACTOR}|{_STROKE_SCREEN_PX}"
    )
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


def renderizar_dxf_svg_com_transform_cacheado(
    dxf_path: Path, cache_dir: Path, *, bbox: Optional[BBox] = None, margem_pct: float = 0.08,
    largura_px: int = 640, altura_px: int = 480,
) -> SvgComTransform:
    """Igual ao cacheado normal, mas grava a transform ao lado do SVG (`.transform.json`).

    A transform é barata de guardar e cara de recalcular (exige re-render para ler os
    limites pós-draw). Cache incompleto ou corrompido → re-renderiza, nunca devolve
    SVG com transform errada: transform errada desloca em silêncio todo item desenhado.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    base = _hash_cache(dxf_path, bbox, margem_pct, (largura_px, altura_px))
    caminho_svg = cache_dir / f"{base}.svg"
    caminho_meta = cache_dir / f"{base}.transform.json"
    if caminho_svg.is_file() and caminho_meta.is_file():
        try:
            meta = json.loads(caminho_meta.read_text(encoding="utf-8"))
            return SvgComTransform(
                svg=caminho_svg.read_bytes(),
                bbox_dxf=tuple(float(v) for v in meta["bbox_dxf"]),  # type: ignore[arg-type]
                largura_px=int(meta["largura_px"]),
                altura_px=int(meta["altura_px"]),
            )
        except (OSError, ValueError, KeyError, TypeError) as exc:
            log.warning("cache de transform inválido em %s (%s) — re-renderizando",
                        caminho_meta, exc)

    resultado = renderizar_dxf_svg_com_transform(
        dxf_path, bbox=bbox, margem_pct=margem_pct,
        largura_px=largura_px, altura_px=altura_px,
    )
    try:
        caminho_svg.write_bytes(resultado.svg)
        caminho_meta.write_text(
            json.dumps(resultado.como_dict(), ensure_ascii=False), encoding="utf-8"
        )
    except OSError as exc:
        log.warning("falha ao gravar cache de preview SVG+transform em %s: %s",
                    caminho_svg, exc)
    return resultado


def dimensoes_preview_completo(bbox: BBox, alvo_px: int = PREVIEW_ALVO_PX) -> tuple[int, int]:
    """(largura_px, altura_px) do preview inteiro, mantendo a proporção do desenho.

    Extraído de `renderizar_dxf_completo_cacheado` para ser a ÚNICA fonte dessa
    aritmética. Quem precisa mapear clique→DXF sobre esse preview tem de obter a
    transform de `transform_preview_completo`, nunca recalculá-la — foi assim que
    `manual_crop` acabou duplicando a fórmula e ficando acoplado a esta função.
    """
    x0, y0, x1, y1 = bbox
    largura_real = max(x1 - x0, 1.0)
    altura_real = max(y1 - y0, 1.0)
    if largura_real >= altura_real:
        return alvo_px, max(int(alvo_px * (altura_real / largura_real)), 200)
    return max(int(alvo_px * (largura_real / altura_real)), 200), alvo_px


def transform_preview_completo(
    dxf_path: Path, *, cache_dir: Optional[Path] = None,
    alvo_px: int = PREVIEW_ALVO_PX, margem_pct: float = 0.03,
) -> Optional[SvgComTransform]:
    """Transform EXATA do preview inteiro — a mesma imagem servida por /foto.

    Devolve None quando o DXF não tem extents. Use isto para converter
    coordenada de tela em coordenada DXF; reproduzir a conta à mão funciona só
    enquanto ninguém mexe em `alvo_px`/`margem_pct`/proporção, e quando quebra
    o sintoma é recorte deslocado sem erro nenhum.

    Com `cache_dir` reaproveita o SVG que a rota /foto já gerou (mesma chave de
    hash) e só a transform é lida do disco. Sem ele, RE-RENDERIZA: medido no
    13_PAV, 7,4s por chamada — inaceitável numa rota que a tela chama ao abrir.

    [2026-07-31] `alvo_px` default = PREVIEW_ALVO_PX (mesmo da /foto). Antes
    era 2400 enquanto a foto usava 1400 → cache miss + re-render + destaques
    desalinhados + "Carregando foto…" eterno.
    """
    bbox = obter_bbox_dxf(dxf_path)
    if bbox is None:
        return None
    largura_px, altura_px = dimensoes_preview_completo(bbox, alvo_px)
    if cache_dir is not None:
        return renderizar_dxf_svg_com_transform_cacheado(
            dxf_path, cache_dir, bbox=bbox, margem_pct=margem_pct,
            largura_px=largura_px, altura_px=altura_px,
        )
    return renderizar_dxf_svg_com_transform(
        dxf_path, bbox=bbox, margem_pct=margem_pct,
        largura_px=largura_px, altura_px=altura_px,
    )


def renderizar_dxf_completo_cacheado(
    dxf_path: Path, cache_dir: Path, *, alvo_px: int = PREVIEW_ALVO_PX, margem_pct: float = 0.03,
) -> bytes:
    """[2026-07-07] Foto INTEIRA do bruto/torre em SVG.

    [2026-07-31] `alvo_px` = PREVIEW_ALVO_PX (1200): matplotlib gera SVG com
    milhares de path; 2400px → ~28MB e pan/zoom morto. Cache por hash inclui
    tag v3thin1200 + fator de traço fino. Primeira abertura recria o SVG;
    seguintes batem cache.
    """
    bbox = obter_bbox_dxf(dxf_path)
    if bbox is None:
        return renderizar_dxf_svg_cacheado(dxf_path, cache_dir, largura_px=alvo_px, altura_px=int(alvo_px * 0.75))
    largura_px, altura_px = dimensoes_preview_completo(bbox, alvo_px)
    # A foto e o recorte manual compartilham o mesmo cache. Gravar a transform
    # já na primeira abertura evita renderizar milhares de paths uma segunda
    # vez quando o operador confirma o retângulo.
    return renderizar_dxf_svg_com_transform_cacheado(
        dxf_path, cache_dir, bbox=bbox, margem_pct=margem_pct,
        largura_px=largura_px, altura_px=altura_px,
    ).svg
