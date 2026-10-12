"""Initial iNi appearance, measured from the registered originals (October 2026).

Fabrication geometry comes from the existing SA adapters. This module owns only
the iNi presentation; no source records or other mode profiles are modified.
"""
from pathlib import Path
from hashlib import sha256

# Included in file-based cache keys, including already running portal workers.
LV_PRESENTATION_REVISION = '2026-10-07-native-timber-panel-support-v3'

COLORS = {
    'painéis': 7, 'paineis': 7, 'hachura-chapa': 7, 'compensado': 7,
    'sarrafo_2_2x7': 24, 'sarr_2.2x7': 24, 'sarrafo': 24,
    'sarr_3.5x7': 12, 'meiopontalete': 12, 'meiopontale_3_5x7': 12,
    'sarr_7x7': 18, 'pontalete_7x7': 18,
    'barra_ancoragem': 1, 'barra de ancoragem': 20, 'agulha': 1,
    'perfil_metalico': 255, 'perfil metalico': 255, 'gravata': 255,
    'cota': 4, 'cotas': 4, 'cota seção (2x)': 4,
    'concreto': 251, 'hachura': 251, 'hachuraconcreto': 252,
    'numeração das chapas': 5, 'numeracao': 5,
    'pedireito': 1, 'nível': 1, 'divisao': 142,
    'sarrafo de pressão': 1, 'sarrafo_pressao': 1,
    'nomenclatura': 7, 'texto seção': 7, 'texto': 7,
    'madeira': 24, 'sarrafos': 24, 'meio_pont.': 12,
    'formascia_grade_divisoes': 142, 'sar_2_2x7': 24,
    'sarrafo_de_pressao': 1, 'texto seção': 7, 'texto nível': 1,
}


def reference_style(doc, cls):
    for layer in doc.layers:
        color = COLORS.get(layer.dxf.name.casefold())
        if color is not None:
            layer.dxf.color = color
            layer.dxf.discard('true_color')
    # Dimension blocks retain their own line/number palette, as in PAINEL.
    for dim in doc.modelspace().query('DIMENSION'):
        override = dim.override()
        override.update({'dimclrd': 4, 'dimclre': 4, 'dimclrt': 240})
        override.render()
    doc.header['$INSUNITS'] = 5
    if cls == 'LV':
        from .ini_lv_design import wood_styles
        wood_styles(doc)


def draw_ab(contract):
    from .lv_nova_design import draw_ab as geometry
    from scripts.visual_modes import apply_visual_mode
    timber = []
    doc = geometry(contract, timber_sink=timber)
    from .ini_lv_design import protect_timber, restore_timber, finish_ab
    protected = protect_timber(doc)
    apply_visual_mode(doc, 'INI', 'LV', contract.get('behavior', 'PARA'))
    restore_timber(protected)
    finish_ab(doc, contract, timber)
    return doc


def draw_cut(contract, behavior='PARA'):
    from .lv_nova_design import draw_cut as geometry
    from scripts.visual_modes import apply_visual_mode
    doc = geometry(contract)
    from .ini_lv_design import protect_timber, restore_timber
    protected = protect_timber(doc)
    apply_visual_mode(doc, 'INI', 'LV', behavior)
    restore_timber(protected)
    from .ini_lv_design import finish_cut, finish_sarrafeado_cut
    if contract.get('assembly_variant','sarrafeadas')=='sarrafeadas':
        finish_sarrafeado_cut(doc)
    else:
        finish_cut(doc, contract)
    return doc


def renderer_fingerprint():
    from .lv_nova_design import renderer_fingerprint as geometry
    from .ini_lv_design import ASSET
    return sha256(Path(__file__).read_bytes() + Path(__file__).with_name('ini_lv_design.py').read_bytes()
                  + ASSET.read_bytes() + geometry().encode()).hexdigest()
