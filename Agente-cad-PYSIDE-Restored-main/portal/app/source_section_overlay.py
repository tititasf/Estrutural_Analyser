"""Source-scoped original sections, partitioned without reconstructing CAD."""
from functools import lru_cache
from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import json


@lru_cache(maxsize=8)
def read_sections(path, revision):
    import ezdxf
    from src.core.composite_cut_contours import partition_cut_contours
    doc=ezdxf.readfile(path);polys=[];texts=[]
    for entity in doc.modelspace().query('POLYLINE LWPOLYLINE'):
        pts=[list(p[:2]) for p in entity.get_points()] if entity.dxftype()=='LWPOLYLINE' else [list(v.dxf.location)[:2] for v in entity.vertices]
        if entity.is_closed and pts and pts[0]!=pts[-1]:pts.append(pts[0])
        polys.append(dict(points=pts,layer=entity.dxf.layer))
    for entity in doc.modelspace().query('TEXT MTEXT'):
        texts.append(dict(text=entity.dxf.text if entity.dxftype()=='TEXT' else entity.plain_text(),
                          pos=list(entity.dxf.insert)[:2],layer=entity.dxf.layer))
    return partition_cut_contours(polys,texts)


def measured_items(source, state):
    """Expose the same identities and measurements to the selection list."""
    class Identity:
        def dxf_para_px(self, x, y):
            return [x, y]
    groups = original_groups([], source, state or {}, Identity())
    items = next((g['itens'] for g in groups if g['grupo'] == 'cortes'), [])
    for item in items:
        width, height = item.get('measured_width_cm'), item.get('measured_height_cm')
        measures = f' Â· {width:g}/{height:g} cm' if width is not None else ''
        item['titulo'] = item['rotulo'] + measures + ' Â· medidas da fonte Â· sem referÃªncia de nÃ­vel'
    return items


def original_groups(groups, source, state, transform):
    """Replace intersecting legacy symbols with their measured source parts."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from src.core.composite_cut_contours import source_section_drawing
    path=Path(source);stat=path.stat()
    records=deepcopy(read_sections(str(path.resolve()),(stat.st_mtime_ns,stat.st_size)))
    if not records:return groups
    result=deepcopy(groups)
    original=next((g for g in result if g['grupo']=='cortes'),None)
    if original is None:
        original=dict(grupo='cortes',rotulo='VisÃ£o de Cortes',itens=[]);result.append(original)
    source_shapes=[Polygon(r['points']) for r in records]
    complete=unary_union(source_shapes)
    kept=[]
    for item in original['itens']:
        points=item.get('pontos_dxf') or []
        if len(points)<3:kept.append(item);continue
        p=Polygon(points)
        # Any old connected/partial inference covered by the source partition
        # is superseded as a whole, never drawn on top of its split children.
        if p.is_valid and p.area and p.intersection(complete).area/p.area>.95:
            continue
        kept.append(item)
    fundos=[(Polygon(s['points']),s.get('beam_name')) for s in (state.get('segmentos') or {}).get('fundo',[]) if len(s.get('points') or [])>=3]
    interpreted=next((g for g in result if g['grupo']=='cortes_interpretados'),None)
    if interpreted is None:
        interpreted=dict(grupo='cortes_interpretados',rotulo='Cortes de viga interpretados',itens=[])
        result.append(interpreted)
    # Source measurements remain originals. Only generated interpretation
    # drawings belong to the interpreted group, including in frozen inventories.
    interpreted['itens'] = [item for item in interpreted['itens']
                            if item.get('interpretation_scope') != 'measured_source_geometry'
                            and not str(item.get('item_id', '')).startswith('interpreted:source-section:')]
    for record in records:
        shape=Polygon(record['points']);body=Polygon(record.get('body_points') or record['points'])
        hits=[(p.intersection(body).area,name) for p,name in fundos if p.is_valid and name]
        hits.sort(reverse=True)
        beam=hits[0][1] if hits and hits[0][0]>.5*body.area else None
        kind=record['section_kind'];title=beam or ('Degrau de laje' if kind=='slab_step' else 'Corte de viga')
        drawing=source_section_drawing(record,title)
        for primitive in drawing['primitives']:
            primitive['points']=[transform.dxf_para_px(*p) for p in primitive['points']]
        uid='source-section:'+sha256(json.dumps(record['points'],sort_keys=True).encode()).hexdigest()[:20]
        bounds=body.bounds
        kept.append(dict(item_id=uid,classe_sa='cortes',rotulo=title,beam_name=beam,
                         section_kind=kind,pontos_dxf=record['points'],fora_do_frame=False,
                         highlight_color='#ffe033' if kind=='slab_step' else '#a8fff0',
                         section_drawing=drawing,detail_status='dimensioned',
                         measured_width_cm=min(bounds[2]-bounds[0],bounds[3]-bounds[1]) if kind=='beam' else None,
                         measured_height_cm=max(bounds[2]-bounds[0],bounds[3]-bounds[1]) if kind=='beam' else None,
                         measurement_source='source_closed_pieces',source_components=record['measured_pieces']))
    original.update(itens=kept,total=len(kept),fora_do_frame=sum(bool(i.get('fora_do_frame')) for i in kept))
    interpreted.update(total=len(interpreted['itens']))
    return result
