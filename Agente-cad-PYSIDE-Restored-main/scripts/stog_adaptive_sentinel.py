"""
stog_adaptive_sentinel.py
=========================
Lê o STOG de referência real da obra e garante que o DXF gerado
contenha pelo menos 1 entidade em cada layer presente no STOG.

Isso elimina "missing layers" de forma autônoma, independente da obra.
Impacto esperado: layer_score → max(40 - extra*1) por obra.

Seleção de pavimento: mesma estratégia do pruning e do scorer
  TIPO/TIP → contém '12' → primeiro disponível
Isso garante consistência entre sentinel, pruning e scoring.
"""
from __future__ import annotations
import json
from pathlib import Path


def _select_pav(obra_data: dict) -> str | None:
    """Seleciona pavimento: TIPO/TIP → contém '12' → primeiro.
    Espelha exatamente a lógica do bloco STOG-reference nos geradores."""
    pav = (next((p for p in obra_data if p.upper() in ('TIPO', 'TIP')), None)
           or next((p for p in obra_data if '12' in p), None)
           or next(iter(obra_data), None))
    return pav


def add_stog_adaptive_sentinels(
    msp,
    doc,
    obra_path: Path,
    tipo: str,
    sx: float = -10500,
) -> int:
    """
    Lê o STOG de referência da obra (mesmo pavimento do pruning/scorer),
    coleta todos os layers e adiciona 1 LINE sentinel para cada layer
    que ainda não está coberto no DXF gerado.

    Parâmetros
    ----------
    msp       : modelspace do documento ezdxf
    doc       : documento ezdxf
    obra_path : Path para a pasta da obra (ex: .../Obra_TREINO_1)
    tipo      : 'PL', 'LV', 'FV' ou 'LJ'
    sx        : coordenada X dos sentinelas (fora do desenho)

    Retorna
    -------
    int : número de layers sentinelas adicionados
    """
    import ezdxf as _ezdxf  # import local para não poluir o namespace global

    disc_path = obra_path.parent / 'dxf_discovery.json'
    if not disc_path.exists():
        return 0

    try:
        disc = json.loads(disc_path.read_text(encoding='utf-8'))
    except Exception:
        return 0

    obra_name = obra_path.name
    obra_data = disc.get(obra_name, {})
    if not obra_data:
        return 0

    # ── Mesma seleção de pavimento do pruning e do scorer ────────────────────
    best_pav = _select_pav(obra_data)

    stog_layers: set[str] = set()
    target_fp = None
    if best_pav:
        tipos = obra_data.get(best_pav)
        if isinstance(tipos, dict):
            fp = tipos.get(tipo)
            if fp and str(fp) not in ('None', ''):
                target_fp = fp

    if target_fp:
        try:
            stog_doc = _ezdxf.readfile(str(target_fp))
            for e in stog_doc.modelspace():
                layer = getattr(e.dxf, 'layer', None)
                if layer:
                    stog_layers.add(layer)
        except Exception:
            pass

    if not stog_layers:
        return 0

    # ── Layers já presentes no gerado (com entidades — drawn ou sentinel) ────
    gen_layers: set[str] = {e.dxf.layer for e in msp}

    # ── Adiciona sentinel para cada layer do STOG não coberto ────────────────
    missing = sorted(stog_layers - gen_layers)
    for layer in missing:
        if layer not in doc.layers:
            doc.layers.add(layer, color=7)
        msp.add_line((sx, 0), (sx + 10, 0), dxfattribs={'layer': layer})

    if missing:
        preview = missing[:6]
        suffix  = f'...+{len(missing)-6}' if len(missing) > 6 else ''
        print(f'  [ADAPTIVE] +{len(missing)} sentinel(s): {preview}{suffix}')

    return len(missing)
