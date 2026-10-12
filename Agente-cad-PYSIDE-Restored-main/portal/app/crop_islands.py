"""Derived detail islands with conservative semantic names and source provenance.

The combined details file remains the lossless complement of the towers.
These additional crops never replace a tower or a manually saved crop.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path


def _plain(value):
    value = unicodedata.normalize('NFKD', str(value))
    return ''.join(c for c in value if not unicodedata.combining(c)).upper().replace('%%D', '°')


def classify_island(texts):
    """Classify evidence, never the layer name or position in a particular work."""
    labels = [_plain(t['text']).strip() for t in texts]
    floor = re.compile(r'^\d+\s*[°ºOA]?\s*PAV(?:IMENTO|\.)?$')
    floors = [t for t, label in zip(texts, labels) if floor.fullmatch(label)]
    decimals = [t for t, label in zip(texts, labels) if re.fullmatch(r'[+-]?\d+[.,]\d{1,2}', label)]
    # An elevation has repeated floor rows in one column and explicit values.
    # "NIVEL 0 - RETIRADO" in shoring schedules is not an altitude convention.
    if len(floors) >= 3 and len(decimals) >= 3:
        height = max(t.get('height', 1) for t in floors)
        column = max(sum(abs(a['pos'][0]-b['pos'][0]) <= 2*height for b in floors) for a in floors)
        if column >= 3:
            return 'convencao_niveis', 'repeated_floor_column_and_decimal_levels'
    pillar_labels = [label for label in labels if 'PILAR' in label]
    terms = {term for label in pillar_labels for term in ('NASC', 'MORR', 'CONTINU', 'MUDA') if term in label}
    if len(terms) >= 2 or any(re.fullmatch(r'CONVENCO?ES?\s*(?:DE|DOS)?\s*PILARES\s*:?|CONVENCAO\s*(?:DE|DOS)?\s*PILARES\s*:', label) for label in labels):
        return 'convencao_pilares', 'explicit_pillar_legend_terms'
    return 'outros', 'unclassified_detail_island'


def ensure_detail_islands(source, out_dir, regions=None):
    import ezdxf
    from scripts.obra_crop_engine import detect_regions, crop_dxf
    source, out_dir = Path(source), Path(out_dir)
    revision = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = out_dir/'islands.json'
    saved = {}
    if manifest.is_file():
        saved = json.loads(manifest.read_text(encoding='utf8'))
        if saved.get('source_sha256') == revision and not saved.get('errors') and all((out_dir/i['file']).is_file() for i in saved.get('islands', [])):
            return saved
    regions = regions or detect_regions(source)
    if regions.get('error'):
        return {'error':regions['error']}
    doc = ezdxf.readfile(source)
    texts = []
    for e in doc.modelspace():
        if e.dxftype() not in ('TEXT','MTEXT'):
            continue
        texts.append({'text':e.dxf.text if e.dxftype()=='TEXT' else e.plain_mtext(),
                      'pos':list(e.dxf.insert)[:2], 'handle':e.dxf.handle,
                      'height':float(e.dxf.height if e.dxftype()=='TEXT' else e.dxf.char_height)})
    result = {'source_sha256':revision, 'islands':[], 'errors':[]}
    # Geometric ordering gives stable names independent of cluster population.
    for index, region in enumerate(sorted(regions['detalhes'],key=lambda r:tuple(r['bbox'])),1):
        x0,y0,x1,y1=region['bbox']
        local=[t for t in texts if x0<=t['pos'][0]<=x1 and y0<=t['pos'][1]<=y1]
        kind, reason=classify_island(local)
        name=f'{kind}_auto_{index:03d}_{revision[:8]}.dxf'
        target=out_dir/name
        # Existing files may be manual/edited or belong to another revision.
        if target.exists():
            previous=next((i for i in saved.get('islands',[]) if i['file']==name),None)
            if saved.get('source_sha256')==revision and previous:
                result['islands'].append(previous)
                continue
            result['errors'].append({'file':name,'reason':'existing_crop_preserved'})
            continue
        crop=crop_dxf(source,target,region['bbox'],padding_pct=.025)
        if crop.get('error'):
            result['errors'].append({'file':name,'reason':crop['error']});continue
        result['islands'].append({'file':name,'kind':kind,'reason':reason,
                                 'bbox':list(region['bbox']), 'entities':crop['entities_copied'],
                                 'text_handles':[t['handle'] for t in local]})
    out_dir.mkdir(parents=True,exist_ok=True)
    temporary=manifest.with_suffix('.tmp')
    temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    temporary.replace(manifest)
    return result
