"""Translate confirmed SA fabrication panels into the initial iNi contract."""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from copy import deepcopy

import ezdxf
from ezdxf import bbox
from ezdxf.math import Matrix44
from ezdxf.xref import load_modelspace

from .lv_nova_sa_adapter import ab_runs
from .ini_design import draw_ab
from .lv_formascia_design import setup_formascia_resources as setup_ini_resources, normalize_resources
from scripts.drawing_mode_config import apply_config


def generate_ab(source, path, behavior='PASSA', mode='INI'):
    """Generate iNi Lateral N3 drawing from confirmed SA runs."""
    runs = ab_runs(source)
    doc = ezdxf.new('R2018')
    setup_ini_resources(doc)
    unit_dir = Path(path).with_suffix('.units')
    unit_dir.mkdir(parents=True, exist_ok=True)
    units = []
    top = None
    panel_number = 1

    for index, run in enumerate(runs, 1):
        from .lv_nova_design import panel_spans
        run['panel_number_start'] = panel_number
        panel_number += sum(len(panel_spans(s['length'])) for s in run['segments'])
        for endpoint, segment in [('start',run['segments'][0]), ('end',run['segments'][-1])]:
            candidates = [p for p in source.get('structural_segments', [])
                          if p.get('physical_segment_index', p.get('segment_index')) == segment['segment_index']]
            if candidates:
                panel = candidates[0] if endpoint=='start' else candidates[-1]
                run['support_'+endpoint] = (panel.get('lv_cell',{}).get('support_'+endpoint) or {}).get('name','')
        local = draw_ab(run)
        apply_config(local, mode, 'LV', behavior)
        local.header['$INSUNITS'] = 5
        unit_path = unit_dir / f'AB_{index:03d}.dxf'
        normalize_resources(local)
        local.saveas(unit_path)
        units.append(dict(file=unit_path.name, kind='AB', beam=run['beam'],
                          side=run['side'], segments=[s['segment_index'] for s in run['segments']],
                          contract=run, sha256=sha256(unit_path.read_bytes()).hexdigest()))
        sources=[local]
        if run['assembly_variant']=='gradeadas':
            from .lv_formascia_grades import prepare_grades
            from scripts.visual_modes import apply_visual_mode
            from .ini_lv_design import protect_timber, restore_timber, finish_grades
            grade=prepare_grades(None,run,1)
            protected = protect_timber(grade)
            apply_visual_mode(grade,mode,'LV',behavior)
            restore_timber(protected)
            finish_grades(grade)
            apply_config(grade,mode,'LV',behavior);normalize_resources(grade)
            grade_path=unit_dir/f'GRADE_{index:03d}.dxf';grade.saveas(grade_path)
            units.append(dict(file=grade_path.name,kind='GRADE',beam=run['beam'],
                side=run['side'],segments=[s['segment_index'] for s in run['segments']],
                contract=run,sha256=sha256(grade_path.read_bytes()).hexdigest()))
            sources.append(grade)
        for local in sources:
            top=_append_unit(local,doc,top)

    doc.header['$INSUNITS'] = 5
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    normalize_resources(doc)
    from .ini_lv_design import wood_styles
    wood_styles(doc)
    doc.saveas(path)
    (unit_dir / 'manifest.json').write_text(json.dumps(dict(
        mode=mode, behavior=behavior, assembly_variant=source.get('assembly_variant', 'sarrafeadas'),
        source_hash=sha256(json.dumps(source, sort_keys=True).encode()).hexdigest(), units=units
    ), ensure_ascii=False, indent=2), encoding='utf8')
    return runs


def _append_unit(local,doc,top):
        bounds = bbox.extents(local.modelspace())
        dy = 0. if top is None else top - bounds.extmax.y
        existing = {e.dxf.handle for e in doc.modelspace()}
        for l in local.layers:
            l.dxf.discard('material_handle')
            l.dxf.discard('plotstyle_handle')
        for l in doc.layers:
            l.dxf.discard('material_handle')
            l.dxf.discard('plotstyle_handle')
        load_modelspace(local, doc)
        for entity in doc.modelspace():
            if entity.dxf.handle not in existing and dy:
                # A translation must not reapply the hatch's physical scale.
                # Preserve its expanded pattern definition while moving paths.
                pattern = deepcopy(entity.pattern) if entity.dxftype() == 'HATCH' else None
                entity.transform(Matrix44.translate(0, dy, 0))
                if pattern is not None:
                    entity.pattern = pattern
        return bounds.extmin.y + dy - 60.
