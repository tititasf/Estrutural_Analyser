"""Cache derivado por seÃ§Ã£o SA, isolado por pavimento, origem e fingerprint."""
from pathlib import Path
import json
import os
import tempfile
from hashlib import sha256
from src.core.lv_n3_cut_contract import build_cut_contract, CutContractError


def layer(cut, mode='NOVA'):
    try:
        contract=build_cut_contract(cut,allow_multiple_slabs=mode in ('NOVA','MOLDE_1','INI'))
    except CutContractError as exc:
        return {'available':False,'svg':None,'reason':str(exc)}
    return {'available':True,'lazy':True,'svg':None,'fingerprint':contract['fingerprint'],
            'warnings':contract['warnings']}


def artifact_identity(obra_dir,floor,behavior,cut,mode='NOVA',assembly='sarrafeadas'):
    """Compute the current section path without generating or writing in N5."""
    contract=build_cut_contract(cut,allow_multiple_slabs=str(mode).upper() in ('NOVA','MOLDE_1','INI'))
    from src.core.vigas_drawing_config import normalize_lv_assembly
    assembly=normalize_lv_assembly(assembly)
    contract['assembly_variant']=assembly
    contract['fingerprint']=sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest()
    mode=str(mode).upper() if str(mode).upper() in {"INI", "NOVA", "MOLDE_1", "MOLDE_2", "MOLDE_3"} else "NOVA"
    from src.core.drawing_renderer_identity import renderer_bytes
    renderer=Path(__file__).resolve().parents[2]/'scripts'/'arete'/'lv_n3_cut_draw.py'
    renderer_hash=sha256(renderer_bytes(renderer,mode)).hexdigest()[:16]
    if mode in ('NOVA','INI'):
        from src.core.lv_nova_design import renderer_fingerprint
        if mode == 'INI':
            from src.core.ini_design import renderer_fingerprint
        renderer_hash=sha256((renderer_hash+renderer_fingerprint()).encode()).hexdigest()[:16]
    if mode == 'MOLDE_1':
        from src.core.lv_formascia_design import renderer_fingerprint
        renderer_hash=sha256((renderer_hash+renderer_fingerprint()).encode()).hexdigest()[:16]
    from scripts.drawing_mode_config import overrides, key_for
    config_hash=sha256(json.dumps(overrides(mode,key_for('LV',behavior)),sort_keys=True).encode()).hexdigest()[:16]
    target=Path(obra_dir)/'Fase-6_Execucao_CAD'/'n3_cut_inventory'/floor/behavior/cut['beam']/mode/assembly/(contract['fingerprint']+'-'+renderer_hash+'-'+config_hash)
    return contract, target/'section.dxf', mode


def resolve(obra_dir,floor,behavior,cut,mode='NOVA',assembly='sarrafeadas',render=True):
    from scripts.arete.lv_n3_cut_draw import generate
    from . import dxf_preview
    contract,path,mode=artifact_identity(obra_dir,floor,behavior,cut,mode,assembly)
    assembly=contract['assembly_variant']
    target=path.parent
    target.mkdir(parents=True,exist_ok=True)
    unit_dir=path.with_suffix('.units')
    if not path.is_file() or (mode in ('NOVA','MOLDE_1','INI') and not (unit_dir/'manifest.json').is_file()):
        fd,tmp=tempfile.mkstemp(prefix='section-',suffix='.dxf',dir=target); os.close(fd)
        try:
            generate(contract,tmp,mode,behavior)
            os.replace(tmp,path)
        finally:
            Path(tmp).unlink(missing_ok=True)
        (target/'contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf8')
        if mode in ('NOVA','MOLDE_1','INI'):
            unit_dir.mkdir(exist_ok=True)
            data=path.read_bytes()
            unit=(unit_dir/'CORTE_001.dxf')
            unit.write_bytes(data)
            manifest=dict(mode=mode,behavior=behavior.upper(),assembly_variant=assembly,
                units=[dict(file=unit.name,kind='CORTE',beam=contract['beam'],contract=contract,
                            sha256=sha256(data).hexdigest())])
            fd,tmp_manifest=tempfile.mkstemp(suffix='.json',dir=unit_dir);os.close(fd)
            try:
                Path(tmp_manifest).write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
                os.replace(tmp_manifest,unit_dir/'manifest.json')
            finally:
                Path(tmp_manifest).unlink(missing_ok=True)
    svg=dxf_preview.renderizar_dxf_svg_cacheado(path,Path(obra_dir)/'.portal_cache'/'lv_n3_cuts',largura_px=1200,altura_px=700).decode('utf8') if render else None
    return {'available':True,'svg':svg,'path':str(path),'origin':'sa_cut_contract','visual_mode':mode,'assembly_variant':assembly,
            'fabrication':{'width_cm':contract['width_cm'],'height_cm':contract['height_cm'],
                           'mounting':contract['mounting'],'slabs':contract['slabs']},
            'fingerprint':contract['fingerprint'],'warnings':contract['warnings']}


def materialize_pavimento(obra_dir, floor, mode='NOVA', item_names=None, *, max_workers=1):
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
    reference_context = {}
    tasks, task_paths, task_rows = [], {}, []
    for behavior in ('para', 'passa'):
        beams = sorted({item['beam_name'] for side in ('a', 'b')
                        for item in listar_itens_n1(state, f'lateral_{side}_{behavior}')})
        for beam in beams:
            if selected and beam not in selected:
                continue
            stats['beams'] += 1
            try:
                cuts = montar_ficha_lv(obra_dir, floor, beam, behavior, state,
                                      include_svgs=False, reference_context=reference_context)['cut_views']
                if not cuts:
                    raise RuntimeError('nenhuma secao interpretada para os segmentos')
            except Exception as exc:
                stats['errors'].append(f'{behavior}/{beam}: {exc}')
                continue
            from src.core.vigas_drawing_config import LV_ASSEMBLIES
            stats['expected'] += len(cuts)*len(LV_ASSEMBLIES)
            for cut,assembly in ((c,a) for c in cuts for a in LV_ASSEMBLIES):
                row = dict(beam=beam, behavior=behavior, id=cut['id'],assembly_variant=assembly)
                try:
                    if max_workers > 1:
                        # Equivalent occurrences share the same immutable artifact.
                        # Only one worker may write that path in this batch.
                        _, path, _ = artifact_identity(obra_dir, floor, behavior, cut, mode, assembly)
                        key = str(path)
                        if key not in task_paths:
                            task_paths[key] = len(tasks)
                            tasks.append((str(obra_dir), floor, behavior, cut, mode, assembly))
                        task_rows.append((row, task_paths[key]))
                    else:
                        result = resolve(obra_dir, floor, behavior, cut, mode,assembly)
                        if not result.get('available') or '<svg' not in (result.get('svg') or ''):
                            raise RuntimeError(result.get('reason') or 'SVG indisponivel')
                        row.update(status='generated', fingerprint=result['fingerprint'])
                        stats['generated'] += 1
                except Exception as exc:
                    row.update(status='blocked', reason=str(exc))
                    stats['errors'].append(f"{behavior}/{beam}/{cut['id']}: {exc}")
                stats['rows'].append(row)
    if tasks:
        from src.core.n3_local_tasks import run_cut_tasks
        import time
        started = time.monotonic()
        results = run_cut_tasks(tasks, max_workers)
        for row, index in task_rows:
            ok, fingerprint, reason, seconds = results[index]
            if ok:
                row.update(status='generated', fingerprint=fingerprint)
                stats['generated'] += 1
            else:
                row.update(status='blocked', reason=reason)
                stats['errors'].append(f"{row['behavior']}/{row['beam']}/{row['id']}: {reason}")
        stats['duration_seconds'] = round(time.monotonic()-started, 3)
        stats['unique_artifacts'] = len(tasks)
    return stats
