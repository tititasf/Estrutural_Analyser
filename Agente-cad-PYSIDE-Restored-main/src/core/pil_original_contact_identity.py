"""Reconcile automatic PIL names only against a proved original local contact.

The source reader remains independent: no name is propagated by proximity,
no position is moved, and every proposed name/section is measured again.
"""
from __future__ import annotations

import copy
import json
import hashlib
from pathlib import Path


def serialize_original_contact_slot(slot):
    """Keep compact source authority without heavy rendering evidence."""
    if not isinstance(slot, dict):
        return slot
    result = {k: copy.deepcopy(slot[k]) for k in
              ('name', 'dim', 'corner', 'behavior', 'nivel', 'n')
              if slot.get(k) is not None}
    evidence = slot.get('original_identity_evidence') or {}
    if (slot.get('source') in ('original_contact_identity', 'original_contact_section')
            and evidence.get('source_sha256') and evidence.get('pillar_points')
            and evidence.get('positions_preserved')
            and all(evidence.get(k) for k in
                    ('wall_handles', 'beam_handles', 'section_handles'))):
        result['source'] = slot['source']
        result['original_identity_evidence'] = {
            k: copy.deepcopy(evidence[k]) for k in
            ('source_sha256', 'pillar_points', 'positions_preserved',
             'wall_handles', 'beam_handles', 'section_handles')}
    return result


def _restore_original_contact_provenance(pillar, source_sha256):
    pending = pillar.pop('_pil_original_provenance_pending', [])
    points = json.dumps(pillar.get('points'), sort_keys=True)
    for face, family, prior in pending:
        evidence = prior.get('original_identity_evidence') or {}
        if (not source_sha256 or evidence.get('source_sha256') != source_sha256 or
                not evidence.get('positions_preserved') or
                not all(evidence.get(k) for k in ('wall_handles', 'beam_handles', 'section_handles')) or
                json.dumps(evidence.get('pillar_points'), sort_keys=True) != points):
            continue
        value = pillar['face_beams'].get(face, {}).get(family)
        slots = value if isinstance(value, list) else [value]
        matching = [s for s in slots if isinstance(s, dict) and
                    all(s.get(k) == prior.get(k) for k in ('name', 'dim', 'corner'))]
        if len(matching) != 1:
            continue
        slot = matching[0]
        if slot.get('is_validated') or slot.get('validated') or slot.get('human_override'):
            continue
        slot.update(source=prior['source'], original_identity_evidence=copy.deepcopy(evidence))


def reconcile_original_contact_identity(source_path, report, beams):
    from portal.app.qa_cad_gate import measure
    from src.core.pillar_abcd_tables import build_abcd_tables_from_pillar, _short_face_role, _pillar_bbox
    try:
        source_sha256 = hashlib.sha256(Path(source_path).read_bytes()).hexdigest()
    except OSError:
        source_sha256 = None
    changed = []
    for name, pillar in (report or {}).items():
        if not isinstance(pillar, dict) or not isinstance(pillar.get('face_beams'), dict):
            continue
        _restore_original_contact_provenance(pillar, source_sha256)
        tables = build_abcd_tables_from_pillar(pillar, beams=beams)
        snapshot = {'collections': {'pilares': [{**copy.deepcopy(pillar),
                                                'interpretacao_abcd': tables}]}}
        reading = measure(source_path, snapshot)
        for index, contact in enumerate(reading['contacts']):
            names = contact.get('identity_path_review', {}).get('names', [])
            geometry = contact.get('geometry_only', {})
            section_only = (contact.get('status') == 'measured' and
                            set(contact.get('errors') or {}) == {'dimensoes'} and
                            contact.get('section') and contact.get('beam_handles') and
                            contact.get('wall_handles') and contact.get('section_handles'))
            if section_only:
                names = [contact['beam']]
                geometry = contact
            if len(names) != 1 or (names[0] == contact['beam'] and not section_only) or not geometry.get('section'):
                continue
            if contact['role'] not in ('chega', 'interior', 'passa'):
                continue
            passage = contact['role'] == 'passa'
            if passage and (not section_only or contact.get('aspect') != 'passa_corner'
                    or not contact.get('corner') or not contact.get('source_contact_face')):
                continue
            face = contact['face']
            validated = pillar.get('validated_fields') or []
            if any(str(field).startswith((f'p_s{face}_v_', 'v_ch', 'v_int'))
                   for field in validated):
                continue
            rows = snapshot['collections']['pilares'][0]['interpretacao_abcd']['faces'][face][contact['role']]
            targets = [(i,r) for i,r in enumerate(rows) if r['nome'] == contact['beam']
                       and (not passage or r.get('canto') == contact['corner'])]
            # Ambiguous repeated contacts require a separate physical binding.
            if len(targets) != 1:
                continue
            row_index, row = targets[0]
            candidate = copy.deepcopy(snapshot)
            proposed = candidate['collections']['pilares'][0]['interpretacao_abcd']['faces'][face][contact['role']][row_index]
            proposed['nome'], proposed['dim'] = names[0], geometry['section']
            target_role = contact['role']
            pbb = _pillar_bbox(pillar.get('points') or [])
            if contact['role'] == 'interior' and face in ('C', 'D') and pbb:
                vertical = pbb[3]-pbb[1] >= pbb[2]-pbb[0]
                target_role = _short_face_role(geometry['section'], pillar['points'], vertical=vertical)
                if target_role != contact['role']:
                    face_rows = candidate['collections']['pilares'][0]['interpretacao_abcd']['faces'][face]
                    face_rows[contact['role']].remove(proposed)
                    proposed['papel'] = target_role
                    face_rows.setdefault(target_role, []).append(proposed)
            proofs = [c for c in measure(source_path, candidate)['contacts']
                      if c['face'] == face and c['role'] == target_role and c['beam'] == names[0]
                      and (not passage or c.get('corner') == contact.get('corner'))]
            if not proofs:
                continue
            if len(proofs) > 1:
                # Renaming an automatic alias may produce a duplicate of an
                # already correct row. Accept only the same independently
                # measured physical contact, never another nearby arrival.
                fields = ('status', 'errors', 'face', 'role', 'beam', 'section',
                          'width_cm', 'distances_cm', 'dist_esq_cm', 'dist_dir_cm',
                          'aspect', 'corner', 'source_contact_face', 'pillar_handle',
                          'wall_handles', 'beam_handles', 'section_handles')
                signatures = []
                for item in proofs:
                    signature = {key: item.get(key) for key in fields}
                    for key in ('wall_handles', 'beam_handles', 'section_handles'):
                        signature[key] = sorted(item.get(key) or [])
                    signatures.append(json.dumps(signature, sort_keys=True))
                if (len(set(signatures)) != 1 or
                        not proofs[0].get('distances_cm')):
                    continue
            proof = proofs[0]
            if (proof['status'] != 'measured' or proof['errors'] or
                proof['beam'] != names[0] or proof['face'] != face or
                set(proof.get('wall_handles', [])) != set(geometry['wall_handles']) or
                not proof.get('beam_handles') or not proof.get('section_handles')):
                continue
            if passage and any(proof.get(k) != contact.get(k)
                    for k in ('aspect','corner','source_contact_face')):
                continue
            family = 'para' if contact['role'] == 'chega' else 'interior'
            if passage:
                slots = [s for key,s in pillar['face_beams'].get(face, {}).items()
                         if key in ('passa_esq','passa_dir') and isinstance(s,dict)]
            else:
                slots = pillar['face_beams'].get(face, {}).get(family, [])
            matches = [slot for slot in slots if slot.get('name') == contact['beam']
                       and slot.get('corner') == row.get('canto')]
            implicit_corner = False
            if (not matches and not passage and contact['role'] == 'interior'
                    and row.get('canto') == face+face):
                # The canonical table supplies CC/DD for an interior slot
                # without a stored corner. Bind only its unique named slot;
                # the independently remeasured walls/distances still veto it.
                matches = [slot for slot in slots if slot.get('name') == contact['beam']
                           and not slot.get('corner')]
                implicit_corner = bool(matches)
            if not matches and section_only and contact['role'] == 'interior':
                # Table normalization can classify a full-width para slot as
                # interior. Bind its same physical corner, never a near slot.
                slots = pillar['face_beams'].get(face, {}).get('para', [])
                matches = [slot for slot in slots if slot.get('name') == contact['beam']
                           and slot.get('corner') == row.get('canto')]
            if len(matches) != 1:
                continue
            slot = matches[0]
            if slot.get('is_validated') or slot.get('validated') or slot.get('human_override'):
                continue
            if implicit_corner or target_role != contact['role']:
                # Rebuilding ABCD can reclassify a renamed short-face slot as
                # Passa. A manually patched row is insufficient evidence that
                # the canonical representation still denotes the proved contact.
                rebuilt_pillar = copy.deepcopy(pillar)
                rebuilt_slot = rebuilt_pillar['face_beams'][face][family][slots.index(slot)]
                rebuilt_slot.update(name=names[0], dim=geometry['section'],
                                    source='original_contact_section' if section_only else 'original_contact_identity')
                if target_role != contact['role']:
                    rebuilt_pillar['face_beams'][face][family].remove(rebuilt_slot)
                    rebuilt_slot['corner'] = row.get('canto')
                    rebuilt_pillar['face_beams'][face].setdefault('para', []).append(rebuilt_slot)
                rebuilt_tables = build_abcd_tables_from_pillar(rebuilt_pillar, beams=beams)
                rebuilt = measure(source_path, {'collections': {'pilares': [
                    {**rebuilt_pillar, 'interpretacao_abcd': rebuilt_tables}]}})
                stable = [c for c in rebuilt['contacts'] if c['face'] == face and
                          c['role'] == target_role and c['beam'] == names[0]]
                if (len(stable) != 1 or stable[0]['status'] != 'measured' or
                        stable[0]['errors'] or not stable[0].get('beam_handles') or
                        not stable[0].get('section_handles') or
                        set(stable[0].get('wall_handles', [])) != set(proof['wall_handles'])):
                    continue
            before = {'name': slot.get('name'), 'dim': slot.get('dim')}
            if target_role != contact['role']:
                slots.remove(slot)
                slot['corner'] = row.get('canto')
                slots = pillar['face_beams'][face].setdefault('para', [])
                slots.append(slot)
            slot.update(name=names[0], dim=geometry['section'],
                        source='original_contact_section' if section_only else 'original_contact_identity',
                        original_identity_evidence={
                            'source_sha256': reading['source_sha256'], 'before': before,
                            'pillar_points': copy.deepcopy(pillar.get('points')),
                            'wall_handles': proof['wall_handles'], 'beam_handles': proof['beam_handles'],
                            'section_handles': proof['section_handles'], 'identity_path': proof.get('identity_path'),
                            'positions_preserved': True})
            # If an automatic alias duplicates an already identical physical
            # contact, retain one evidenced slot. Different corners/sections stay.
            slots[:] = [other for other in slots if other is slot or
                        other.get('is_validated') or other.get('validated') or
                        other.get('human_override') or
                        (other.get('name'), other.get('corner'), other.get('dim')) !=
                        (slot['name'], slot.get('corner'), slot['dim'])]
            changed.append({'pillar': name, 'face': face, 'role': target_role,
                            'before_role': contact['role'],
                            'before': before, 'name': slot['name'], 'dim': slot['dim'],
                            'evidence': copy.deepcopy(slot['original_identity_evidence'])})
    return changed
