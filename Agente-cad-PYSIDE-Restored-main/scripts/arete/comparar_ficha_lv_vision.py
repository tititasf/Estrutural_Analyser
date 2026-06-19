# -*- coding: utf-8 -*-
"""
comparar_ficha_lv_vision.py — Extrai ficha N2 de um recorte LV e valida com vision.

Fluxo por elemento:
  1. Localiza DXF recorte N2 (_motor_ dir)
  2. Extrai ficha com motor_reverso_lv (extração geométrica)
  3. Renderiza recorte N2 → PNG (matplotlib/ezdxf)
  4. Envia PNG + ficha extraída para Claude claude-sonnet-4-6 (vision)
  5. Retorna relatório de comparação estruturado

Uso:
    python comparar_ficha_lv_vision.py V301
    python comparar_ficha_lv_vision.py --todos
    python comparar_ficha_lv_vision.py V301 V303 V330
"""

from __future__ import annotations
import argparse
import base64
import io
import json
import re
import sys
import time
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'scripts'))
sys.path.insert(0, str(REPO / 'scripts' / 'arete'))

OBRA_DIR    = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1")
MOTOR_DIR   = OBRA_DIR / "Fase-2_Triagem/recortes_reversos/ALIMONTI - PARAISO - 13° PAV.- LV - R00_motor"
OUT_DIR     = OBRA_DIR / "Fase-6_Execucao_CAD/comparacao_lv"

# ── Imports condicionais ───────────────────────────────────────────────────────
try:
    import ezdxf
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.config import Configuration, HatchPolicy
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    RENDER_OK = True
except ImportError:
    RENDER_OK = False

try:
    import anthropic
    ANTHROPIC_OK = True
except ImportError:
    ANTHROPIC_OK = False


# ═════════════════════════════════════════════════════════════════════════════
# 1. Render DXF → PNG
# ═════════════════════════════════════════════════════════════════════════════

def dxf_to_png(dxf_path: Path, png_path: Path | None = None,
               max_px: int = 2400) -> Path | None:
    """Renderiza DXF para PNG com crop ao bbox real. Retorna path do PNG ou None."""
    if not RENDER_OK:
        return None
    try:
        doc = ezdxf.readfile(str(dxf_path))

        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
        backend = MatplotlibBackend
        ctx = RenderContext(doc)

        def _vis(layers):
            for lp in layers:
                lp.is_visible = True
        ctx.set_layer_properties_override(_vis)

        config = Configuration(show_defpoints=True, hatch_policy=HatchPolicy.NORMAL)

        # Calcular bbox do conteúdo real (ignorar sentinelas X<-200 e layers de folha)
        _SKIP_LAYERS = {'Folhas', 'CARIMBO', 'ESTRUTURACAO', 'Forcador', 'Perfil Metálico'}
        _SENTINEL_X  = -200.0
        xs, ys = [], []
        for e in doc.modelspace():
            try:
                if getattr(e.dxf, 'layer', '') in _SKIP_LAYERS:
                    continue
                t = e.dxftype()
                if t == 'LINE':
                    if e.dxf.start.x > _SENTINEL_X and e.dxf.end.x > _SENTINEL_X:
                        xs += [e.dxf.start.x, e.dxf.end.x]
                        ys += [e.dxf.start.y, e.dxf.end.y]
                elif t == 'LWPOLYLINE':
                    for pt in e.get_points('xy'):
                        if pt[0] > _SENTINEL_X:
                            xs.append(pt[0]); ys.append(pt[1])
                elif t in ('TEXT', 'MTEXT') and hasattr(e.dxf, 'insert'):
                    if e.dxf.insert.x > _SENTINEL_X:
                        xs.append(e.dxf.insert.x); ys.append(e.dxf.insert.y)
            except Exception:
                pass

        w_dxf = (max(xs) - min(xs)) if xs else 1000
        h_dxf = (max(ys) - min(ys)) if ys else 500
        ratio = w_dxf / max(h_dxf, 1)

        # Dimensões PNG: máx max_px no maior eixo
        if ratio >= 1:
            fw, fh = max_px/100, max(max_px/ratio/100, 4)
        else:
            fw, fh = max(max_px*ratio/100, 4), max_px/100

        fig = plt.figure(figsize=(fw, fh), dpi=100)
        ax  = fig.add_axes([0, 0, 1, 1])
        ax.set_aspect('equal')
        ax.set_axis_off()
        fig.patch.set_facecolor('black')

        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
        bk = MatplotlibBackend(ax)
        fe = Frontend(ctx, bk, config=config)
        fe.draw_layout(doc.modelspace())

        # Forçar xlim/ylim ao bbox real (não ao bbox do matplotlib que inclui sentinelas)
        if xs and ys:
            pad_x = (max(xs) - min(xs)) * 0.02 + 5
            pad_y = (max(ys) - min(ys)) * 0.05 + 5
            ax.set_xlim(min(xs) - pad_x, max(xs) + pad_x)
            ax.set_ylim(min(ys) - pad_y, max(ys) + pad_y)

        out = png_path or dxf_path.with_suffix('.png')
        plt.savefig(str(out), dpi=100, bbox_inches='tight',
                    facecolor='black', edgecolor='none')
        plt.close(fig)
        return out
    except Exception as e:
        print(f"  [render] ERRO: {e}")
        return None


# ═════════════════════════════════════════════════════════════════════════════
# 2. Vision score via Claude
# ═════════════════════════════════════════════════════════════════════════════

_VISION_PROMPT = """\
Você é um especialista em plantas de forma de concreto estrutural (STOG).

Esta imagem é um recorte N2 de uma LATERAL DE VIGA de obra de construção civil.
O recorte contém o desenho técnico STOG feito por humano, incluindo:
- Face A (lateral superior/direita no STOG)
- Face B (lateral oposta)
- Vista Corte/Seção transversal (parte esquerda)
- Cotas STOG em centímetros (camada COTA)

Campos extraídos automaticamente pelo motor de engenharia reversa:
{ficha_json}

Por favor, analise visualmente o recorte e valide cada campo extraído.
Para cada campo, diga: ✓ CORRETO / ✗ INCORRETO / ? NÃO VISÍVEL
Inclua o valor que VOCÊ vê na imagem quando diferente do extraído.

Formato de resposta (JSON):
{{
  "campos_validados": {{
    "h_A": {{"status": "✓|✗|?", "valor_visto": null_ou_numero}},
    "h_B": {{"status": "✓|✗|?", "valor_visto": null_ou_numero}},
    "b_cm": {{"status": "✓|✗|?", "valor_visto": null_ou_numero}},
    "laje_sup_A": {{"status": "✓|✗|?", "valor_visto": null_ou_numero}},
    "laje_inf_A": {{"status": "✓|✗|?", "valor_visto": null_ou_numero}},
    "laje_sup_B": {{"status": "✓|✗|?", "valor_visto": null_ou_numero}},
    "laje_inf_B": {{"status": "✓|✗|?", "valor_visto": null_ou_numero}},
    "tipo_viga": {{"status": "✓|✗|?", "valor_visto": null_ou_string}},
    "n_segmentos_A": {{"status": "✓|✗|?", "valor_visto": null_ou_numero}},
    "n_segmentos_B": {{"status": "✓|✗|?", "valor_visto": null_ou_numero}}
  }},
  "score_geral": 0.0_a_1.0,
  "observacoes": "texto livre sobre discrepâncias principais"
}}
"""


def _png_to_b64(png_path: Path) -> str:
    return base64.standard_b64encode(png_path.read_bytes()).decode()


def validar_com_vision(ficha: dict, png_path: Path) -> dict:
    """Envia PNG + ficha extraída para Claude vision e retorna dict de validação."""
    if not ANTHROPIC_OK:
        return {'erro': 'anthropic não instalado — pip install anthropic'}
    if not png_path.exists():
        return {'erro': f'PNG não encontrado: {png_path}'}

    # Campos resumidos da ficha para o prompt (sem listas gigantes)
    ficha_resumo = {
        'h_A':          ficha.get('h_A', 0),
        'h_B':          ficha.get('h_B', 0),
        'b_cm':         ficha.get('b_geom', 19.0),
        'laje_sup_A':   ficha.get('laje_sup_A', 0),
        'laje_inf_A':   ficha.get('laje_inf_A', 0),
        'laje_sup_B':   ficha.get('laje_sup_B', 0),
        'laje_inf_B':   ficha.get('laje_inf_B', 0),
        'tipo_viga':    ficha.get('tipo_viga', '?'),
        'n_segmentos_A': len(ficha.get('panels_A', [])),
        'n_segmentos_B': len(ficha.get('panels_B', [])),
        'h_section':    ficha.get('h_section', 0),
    }

    prompt = _VISION_PROMPT.format(ficha_json=json.dumps(ficha_resumo, indent=2, ensure_ascii=False))
    img_b64 = _png_to_b64(png_path)

    client = anthropic.Anthropic()
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": img_b64}
                    },
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        text = msg.content[0].text if msg.content else ''
        # Extrair JSON da resposta
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            return json.loads(m.group(0))
        return {'resposta_raw': text[:500], 'erro': 'JSON não encontrado na resposta'}
    except Exception as e:
        return {'erro': str(e)}


# ═════════════════════════════════════════════════════════════════════════════
# 3. Pipeline por elemento
# ═════════════════════════════════════════════════════════════════════════════

def _find_dxf(elem: str) -> Path | None:
    cands = sorted(MOTOR_DIR.glob(f"LV_{elem}_motor_*.dxf"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0] if cands else None


def comparar_elemento(elem: str, usar_vision: bool = True,
                      salvar_png: bool = True) -> dict:
    """Pipeline completo para 1 elemento."""
    from motor_reverso_lv import extrair_ficha_lateral_viga

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    resultado = {'elem': elem, 'ok': False}

    # 1. Localizar DXF
    dxf = _find_dxf(elem)
    if dxf is None:
        resultado['erro'] = f'DXF não encontrado para {elem}'
        return resultado

    # 2. Extrair ficha
    ficha = extrair_ficha_lateral_viga(str(dxf), elem + '_A',
                                        obra_root=str(OBRA_DIR))
    resultado['ficha'] = {
        'h_A':       ficha.get('h_A'),
        'h_B':       ficha.get('h_B'),
        'b_cm':      ficha.get('b_geom'),
        'laje_sup_A':ficha.get('laje_sup_A'),
        'laje_inf_A':ficha.get('laje_inf_A'),
        'laje_sup_B':ficha.get('laje_sup_B'),
        'laje_inf_B':ficha.get('laje_inf_B'),
        'tipo_viga': ficha.get('tipo_viga'),
        'n_segsA':   len(ficha.get('panels_A', [])),
        'n_segsB':   len(ficha.get('panels_B', [])),
        'n_sv':      len(ficha.get('section_views', [])),
        'conf':      ficha.get('_confianca', 0),
        '_source':   ficha.get('_er_meta', {}).get('source', '?'),
    }

    # 3. Render PNG
    png_path = OUT_DIR / f"{elem}_n2.png"
    if salvar_png:
        rendered = dxf_to_png(dxf, png_path)
        resultado['png_path'] = str(rendered) if rendered else None
    else:
        resultado['png_path'] = None

    # 4. Vision score
    if usar_vision and png_path.exists():
        print(f"  [{elem}] Chamando vision API...")
        vision = validar_com_vision(ficha, png_path)
        resultado['vision'] = vision
        if 'score_geral' in vision:
            resultado['score_vision'] = vision['score_geral']

    resultado['ok'] = True
    return resultado


# ═════════════════════════════════════════════════════════════════════════════
# 4. CLI
# ═════════════════════════════════════════════════════════════════════════════

def _all_elems() -> list[str]:
    return sorted(set(
        re.search(r'LV_(V[^_]+)_motor', p.name).group(1)
        for p in MOTOR_DIR.glob('LV_*_motor_*.dxf')
        if re.search(r'LV_(V[^_]+)_motor', p.name)
    ))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Comparação visual ficha LV N2 + vision')
    parser.add_argument('elementos', nargs='*', help='V301 V303 ...')
    parser.add_argument('--todos', action='store_true')
    parser.add_argument('--sem-vision', action='store_true', help='Só extração + PNG, sem Claude API')
    parser.add_argument('--sem-png', action='store_true')
    parser.add_argument('--out', type=str, default=None, help='Path para JSON de saída')
    args = parser.parse_args()

    elems = _all_elems() if args.todos else (args.elementos or ['V301'])
    usar_vision = not args.sem_vision
    salvar_png  = not args.sem_png

    if usar_vision and not ANTHROPIC_OK:
        print("AVISO: anthropic não instalado. Usando --sem-vision.")
        usar_vision = False

    print(f"Comparando {len(elems)} elemento(s): {elems[:5]}{'...' if len(elems)>5 else ''}")
    print(f"Render PNG: {salvar_png} | Vision: {usar_vision}")
    print()

    resultados = []
    for elem in elems:
        print(f"[{elem}] ...", end=' ', flush=True)
        r = comparar_elemento(elem, usar_vision=usar_vision, salvar_png=salvar_png)
        resultados.append(r)
        ficha = r.get('ficha', {})
        sv = f"sv={ficha.get('n_sv',0)}"
        score = f"score={r.get('score_vision','?')}" if usar_vision else ''
        print(f"h={ficha.get('h_A')}/{ficha.get('h_B')} "
              f"ls={ficha.get('laje_sup_A')}/{ficha.get('laje_sup_B')} "
              f"tipo={ficha.get('tipo_viga')} {sv} {score}")

    # Salvar JSON consolidado
    out_path = Path(args.out) if args.out else OUT_DIR / 'comparacao_lv_report.json'
    out_path.write_text(json.dumps(resultados, indent=2, ensure_ascii=False, default=str),
                         encoding='utf-8')
    print(f"\nRelatorio: {out_path}")

    # Resumo de scores
    if usar_vision:
        scores = [r.get('score_vision', 0) for r in resultados if 'score_vision' in r]
        if scores:
            print(f"Scores vision: avg={sum(scores)/len(scores):.2f} "
                  f"min={min(scores):.2f} max={max(scores):.2f}")
