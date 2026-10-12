"""Independent N3 fabrication artifacts, selected by structural segment."""
from pathlib import Path
from hashlib import sha256
import json
import os
import tempfile
from copy import deepcopy
from src.core.vigas_drawing_config import LV_ASSEMBLIES, normalize_lv_assembly


def resolve(obra_dir, floor, behavior, beam, side, segment_index=0,
            mode='NOVA', assembly='sarrafeadas', render=True):
    contracts, path, fingerprint = artifact_identity(obra_dir, floor, behavior, beam, side,
                                                    segment_index, mode, assembly)
    from . import dxf_preview
    from scripts.arete.lv_n3_cut_draw import generate_local_panels
    target = path.parent
    target.mkdir(parents=True, exist_ok=True)
    units=path.with_suffix('.units')
    if not path.is_file() or (mode in ('NOVA','MOLDE_1','INI') and not (units/'manifest.json').is_file()):
        fd,tmp=tempfile.mkstemp(suffix='.dxf',dir=target);os.close(fd)
        try:
            generate_local_panels(contracts,tmp,side,mode,behavior)
            temporary_units=Path(tmp).with_suffix('.units')
            if temporary_units.is_dir() and not units.exists():
                try:
                    os.rename(temporary_units,units)
                except FileExistsError:
                    if not (units/'manifest.json').is_file():
                        raise
            os.replace(tmp,path)
        finally:
            Path(tmp).unlink(missing_ok=True)
        (target/'contract.json').write_text(json.dumps(contracts[side],ensure_ascii=False,indent=2),encoding='utf8')
    svg=dxf_preview.renderizar_dxf_svg_cacheado(path,Path(obra_dir)/'.portal_cache'/'lv_n3_panels',largura_px=1200,altura_px=700).decode('utf8') if render else None
    return dict(available=True,svg=svg,path=str(path),assembly_variant=assembly,
                segment_index=segment_index,fingerprint=fingerprint,origin='sa_panel_contract')


def artifact_identity(obra_dir, floor, behavior, beam, side, segment_index=0,
                      mode='NOVA', assembly='sarrafeadas'):
    """Calcula a identidade vigente sem fabricar ou escrever artefatos no N5."""
    from .lv_n3_operations import effective_contracts
    from scripts.drawing_mode_config import overrides, key_for
    assembly=normalize_lv_assembly(assembly)
    if side not in ('A','B') or mode not in ('INI','NOVA','MOLDE_1','MOLDE_2','MOLDE_3'):
        raise ValueError('vista N3 LV invÃ¡lida')
    contracts=effective_contracts(Path(obra_dir),floor,behavior,beam,assembly,mode=mode)
    contract=deepcopy(contracts[side])
    if segment_index>0:
        originals=contract.get('structural_segments') or []
        if originals and int(originals[0].get('segment_index',0)) != segment_index:
            contract['start_adjustment']=0.
        contract['panels']=[p for p in contract['panels'] if
            int(p.get('structural_segment_index',p.get('segment_index',0)))==segment_index]
        contract['structural_segments']=[s for s in contract.get('structural_segments',[])
            if int(s.get('segment_index',0))==segment_index]
        if not contract['panels']:
            raise LookupError('segmento N3 LV nÃ£o encontrado')
    contracts[side]=contract
    from src.core.drawing_renderer_identity import renderer_bytes
    renderer=Path(__file__).resolve().parents[2]/'scripts'/'arete'/'lv_n3_cut_draw.py'
    dependency_hash=b''
    if mode in ('NOVA','INI'):
        from src.core.lv_nova_design import renderer_fingerprint
        if mode == 'INI':
            from src.core.ini_design import renderer_fingerprint
        adapter=renderer.parents[2]/'src'/'core'/('lv_ini_sa_adapter.py' if mode == 'INI' else 'lv_nova_sa_adapter.py')
        dependency_hash=renderer_fingerprint().encode()+renderer_bytes(adapter,mode)
    if mode == 'MOLDE_1':
        from src.core.lv_formascia_design import renderer_fingerprint
        dependency_hash=renderer_fingerprint().encode()
    fingerprint=sha256(json.dumps({'contract':contract,'mode':mode,
        'config':overrides(mode,key_for('LV',behavior))},sort_keys=True).encode()
        +renderer_bytes(renderer,mode)+dependency_hash).hexdigest()
    target=Path(obra_dir)/'Fase-6_Execucao_CAD'/'n3_panel_inventory'/floor/behavior/beam/mode/assembly/fingerprint
    path=target/f'VIEW_{side}.dxf'
    return contracts, path, fingerprint


def materialize(obra_dir,floor,behavior,beam,side,mode='NOVA'):
    return {kind:resolve(obra_dir,floor,behavior,beam,side,mode=mode,assembly=kind,render=False)
            for kind in LV_ASSEMBLIES}


def materialize_pavimento(obra_dir,floor,mode='NOVA',item_names=None,*,max_workers=1):
    """Produce both assemblies for every current SA face, reporting each result."""
    from .ficha_reader import ler_estado_pavimento, listar_itens_n1
    state=ler_estado_pavimento(obra_dir,floor)
    if not state:
        raise RuntimeError('estado SA ausente para painÃ©is N3')
    selected=set(item_names or ())
    stats=dict(floor=floor,visual_mode=mode,expected=0,generated=0,errors=[],rows=[])
    tasks, task_rows = [], []
    for behavior in ('para','passa'):
        for side in 'AB':
            beams=sorted({item['beam_name'] for item in
                          listar_itens_n1(state,f'lateral_{side.lower()}_{behavior}')})
            for beam in beams:
                if selected and beam not in selected:
                    continue
                for assembly in LV_ASSEMBLIES:
                    stats['expected']+=1
                    row=dict(beam=beam,behavior=behavior,side=side,assembly_variant=assembly)
                    if max_workers > 1:
                        tasks.append((str(obra_dir),floor,behavior,beam,side,mode,assembly))
                        task_rows.append(row)
                        stats['rows'].append(row)
                        continue
                    try:
                        result=resolve(obra_dir,floor,behavior,beam,side,mode=mode,
                                       assembly=assembly,render=False)
                        row.update(status='generated',path=result['path'],fingerprint=result['fingerprint'])
                        stats['generated']+=1
                    except Exception as exc:
                        row.update(status='blocked',reason=str(exc))
                        stats['errors'].append(f'{behavior}/{beam}/{side}/{assembly}: {exc}')
                    stats['rows'].append(row)
    if tasks:
        import time
        from src.core.n3_local_tasks import run_panel_tasks
        started=time.monotonic()
        for row, result in zip(task_rows,run_panel_tasks(tasks,max_workers)):
            ok,path,fingerprint,reason,seconds=result
            if ok:
                row.update(status='generated',path=path,fingerprint=fingerprint)
                stats['generated']+=1
            else:
                row.update(status='blocked',reason=reason)
                stats['errors'].append(f"{row['behavior']}/{row['beam']}/{row['side']}/{row['assembly_variant']}: {reason}")
        stats['duration_seconds']=round(time.monotonic()-started,3)
    return stats
