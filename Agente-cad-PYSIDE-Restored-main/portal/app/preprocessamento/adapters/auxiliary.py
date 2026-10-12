"""Granular evidence from every non-plan crop; never manufactures SA values."""
from pathlib import Path
from .level_convention import extract_level_convention
import re
import unicodedata


def semantic_roles(texts: list[dict]) -> list[dict]:
    """Explicit titles identify capabilities, never numerical item authority.

    A combined details crop can contain several roles. Keep the title handle
    and item references separately: co-presence does not prove association.
    """
    roles = []
    for text in texts:
        label = ''.join(c for c in unicodedata.normalize('NFKD', text['text'])
                        if not unicodedata.combining(c)).upper().strip()
        role = None
        if re.fullmatch(r'RESUMO\s+(?:DOS?\s+)?MATERIAIS\s*:?|QUADRO\s+(?:DE\s+)?MATERIAIS\s*:?', label):
            role = 'materials_summary'
        elif re.fullmatch(r'CORTE\s+([A-Z0-9]+)\s*[-–]\s*\1\s*:?\s*', label):
            role = 'named_section'
        elif re.fullmatch(r'(?:CONVENCAO|CONVENCOES|LEGENDA)\s+(?:(?:DE|DOS)\s+)?PILARES\s*:?\s*', label):
            role = 'pillar_legend'
        if role:
            roles.append({'role': role, 'title': text['text'],
                          'title_handle': text['handle'], 'position': text['position'],
                          'authority': 'explicit_title_only'})
    # Generic CONVENÇÕES headings occur in structural drawings without the
    # word PILARES. A complete, nearby trio is a capability candidate only;
    # text co-presence does not certify symbols or classify an SA pillar.
    for header in texts:
        value = header['text'].upper().strip().rstrip(':').strip()
        height = float(header.get('height') or 0)
        if not value.startswith('CONVEN') or height <= 0:
            continue
        nearby = [t for t in texts if t['text'].upper().strip() in {'NASCE', 'SEGUE', 'MORRE'}
                  and sum((a-b)**2 for a, b in zip(t['position'], header['position'])) <= (25*height)**2]
        if {t['text'].upper().strip() for t in nearby} != {'NASCE', 'SEGUE', 'MORRE'}:
            continue
        if len(nearby) != 3:
            continue
        if any(r['title_handle'] == header['handle'] for r in roles):
            continue
        roles.append({'role': 'pillar_legend_candidate', 'title': header['text'],
                      'title_handle': header['handle'], 'position': header['position'],
                      'label_handles': [t['handle'] for t in nearby],
                      'authority': 'explicit_local_term_trio',
                      'symbol_association_status': 'unresolved',
                      'classification_authority': 'none'})
    return roles


def inventory_auxiliary(path: Path, source) -> dict:
    import ezdxf
    document = ezdxf.readfile(str(path))
    texts = []
    for entity in document.modelspace().query('TEXT MTEXT'):
        raw = entity.dxf.text if entity.dxftype() == 'TEXT' else entity.plain_mtext()
        texts.append({'text': str(raw).strip().replace('%%d', '°'),
                      'handle': entity.dxf.handle,
                      'height': float(entity.dxf.height if entity.dxftype() == 'TEXT' else entity.dxf.char_height),
                      'position': list(entity.dxf.insert)[:2]})
    convention = extract_level_convention(path)
    pillar_convention = None
    if any(('CONVEN' in t['text'].upper() or 'LEGENDA' in t['text'].upper())
           and 'PILAR' in t['text'].upper() for t in texts):
        from .pillar_convention import extract_pillar_convention
        pillar_convention = extract_pillar_convention(path)
    proved = [row for row in convention['direct_floor_levels']
              if row.get('selected') and row['selected'].get('method') == 'elevation_triangle']
    roles = semantic_roles(texts)
    from .pillar_legend_symbols import associate_legend_symbols
    legend_symbols = associate_legend_symbols(document, texts, roles)
    references = [t for t in texts if re.fullmatch(r'(?:P|V|VF|L|BL\.)\d+', t['text'], re.I)]
    return {'schema': 'cad.auxiliary.evidence/v1', 'source_id': source.source_id,
            'source_revision': source.revision, 'source_kind': source.kind.value,
            'status': 'observed_unreviewed', 'entity_count': len(document.modelspace()),
            'texts': texts, 'semantic_roles': roles,
            'pillar_legend_symbols': legend_symbols,
            'item_references': references,
            'item_association_status': 'unresolved' if references else 'no_explicit_reference',
            'level_convention': convention if proved else None,
            'pillar_convention': pillar_convention,
            'capabilities': ['text_inventory', 'source_entity_provenance'] +
                            (['geometric_level_markers'] if proved else []),
            'numeric_authority': 'source_geometry_only',
            'warnings': [] if texts else ['no_text_evidence'],
            'unsupported': ['arbitrary_detail_geometry_semantics']}


def crosscheck_reference(reference: dict, auxiliary: list[dict]) -> dict:
    """Compare independent source evidence, never counts copied facts as votes."""
    evidence, conflicts, partial = [], [], []
    for source in auxiliary:
        convention = source.get('level_convention') or {}
        if not reference.get('floor_selection'):
            continue
        floor = reference['floor_selection']['representative_floor']
        import re
        for row in convention.get('direct_floor_levels', []):
            label = re.fullmatch(r'\s*(\d+)\s*[º°oa]?\s*PAV(?:IMENTO)?\.?\s*', row['floor_label'], re.I)
            selected = row.get('selected')
            if not label or int(label[1]) != floor or not selected:
                continue
            item = {'source_id': source['source_id'], 'source_revision': source['source_revision'],
                    'text_handle': selected['text_handle'], 'value': selected['value'],
                    'unit': selected['unit'], 'role': 'same_original_repeated_evidence'}
            evidence.append(item)
            if not selected.get('unit'):
                item['confirmation'] = 'unit_missing_in_crop'
                partial.append(item)
                continue
            if selected['unit'] != reference.get('unit') or abs(selected['value']-reference['top']) > 1e-6:
                conflicts.append(item)
    return {'schema': 'cad.context.qa/v1', 'status': 'conflicting' if conflicts else 'consistent' if len(evidence) > len(partial) else 'partial_confirmation' if partial else 'no_confirmation',
            'partial_confirmation': partial,
            'evidence': evidence, 'conflicts': conflicts, 'independent_vote_count': 0,
            'policy': 'same_original_is_not_independent_confirmation; SA_outputs_are_not_numeric_authority'}
