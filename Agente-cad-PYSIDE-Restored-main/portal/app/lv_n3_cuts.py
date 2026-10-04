"""Cache derivado por seção SA, isolado por pavimento, origem e fingerprint."""
from pathlib import Path
import json
import os
import tempfile
from hashlib import sha256
from src.core.lv_n3_cut_contract import build_cut_contract, CutContractError


def layer(cut):
    try:
        contract=build_cut_contract(cut)
    except CutContractError as exc:
        return {'available':False,'svg':None,'reason':str(exc)}
    return {'available':True,'lazy':True,'svg':None,'fingerprint':contract['fingerprint'],
            'warnings':contract['warnings']}


def resolve(obra_dir,floor,behavior,cut,mode='NOVA'):
    from scripts.arete.lv_n3_cut_draw import generate
    from . import dxf_preview
    contract=build_cut_contract(cut)
    mode=str(mode).upper() if str(mode).upper() in {"INI", "NOVA", "MOLDE_1", "MOLDE_2", "MOLDE_3"} else "NOVA"
    renderer=Path(__file__).resolve().parents[2]/'scripts'/'arete'/'lv_n3_cut_draw.py'
    renderer_hash=sha256(renderer.read_bytes()).hexdigest()[:16]
    from scripts.drawing_mode_config import overrides, key_for
    config_hash=sha256(json.dumps(overrides(mode,key_for('LV',behavior)),sort_keys=True).encode()).hexdigest()[:16]
    target=Path(obra_dir)/'Fase-6_Execucao_CAD'/'n3_cut_inventory'/floor/behavior/cut['beam']/mode/(contract['fingerprint']+'-'+renderer_hash+'-'+config_hash)
    target.mkdir(parents=True,exist_ok=True)
    path=target/'section.dxf'
    if not path.is_file():
        fd,tmp=tempfile.mkstemp(prefix='section-',suffix='.dxf',dir=target); os.close(fd)
        try:
            generate(contract,tmp,mode,behavior)
            os.replace(tmp,path)
        finally:
            Path(tmp).unlink(missing_ok=True)
        (target/'contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf8')
    svg=dxf_preview.renderizar_dxf_svg_cacheado(path,Path(obra_dir)/'.portal_cache'/'lv_n3_cuts',largura_px=1200,altura_px=700).decode('utf8')
    return {'available':True,'svg':svg,'origin':'sa_cut_contract','visual_mode':mode,
            'fingerprint':contract['fingerprint'],'warnings':contract['warnings']}


def materialize_pavimento(obra_dir, floor, mode='NOVA', item_names=None):
    """Rebuild the current inventory, then resolve every section in its scope.

    Cached drawings are reusable only by contract, renderer and mode fingerprint;
    their directory contents never determine the published inventory.
    """
    from .ficha_reader import ler_estado_pavimento, listar_itens_n1
    from .lv_ficha import montar_ficha_lv
    state = ler_estado_pavimento(obra_dir, floor)
    if not state:
        raise RuntimeError('estado SA ausente para Visao Corte')
    selected = set(item_names or ())
    stats = dict(floor=floor, visual_mode=mode, beams=0, expected=0,
                 generated=0, errors=[], rows=[])
    for behavior in ('para', 'passa'):
        beams = sorted({item['beam_name'] for side in ('a', 'b')
                        for item in listar_itens_n1(state, f'lateral_{side}_{behavior}')})
        for beam in beams:
            if selected and beam not in selected:
                continue
            stats['beams'] += 1
            try:
                cuts = montar_ficha_lv(obra_dir, floor, beam, behavior, state,
                                      include_svgs=False)['cut_views']
                if not cuts:
                    raise RuntimeError('nenhuma secao interpretada para os segmentos')
            except Exception as exc:
                stats['errors'].append(f'{behavior}/{beam}: {exc}')
                continue
            stats['expected'] += len(cuts)
            for cut in cuts:
                row = dict(beam=beam, behavior=behavior, id=cut['id'])
                try:
                    result = resolve(obra_dir, floor, behavior, cut, mode)
                    if not result.get('available') or '<svg' not in (result.get('svg') or ''):
                        raise RuntimeError(result.get('reason') or 'SVG indisponivel')
                    row.update(status='generated', fingerprint=result['fingerprint'])
                    stats['generated'] += 1
                except Exception as exc:
                    row.update(status='blocked', reason=str(exc))
                    stats['errors'].append(f"{behavior}/{beam}/{cut['id']}: {exc}")
                stats['rows'].append(row)
    return stats
