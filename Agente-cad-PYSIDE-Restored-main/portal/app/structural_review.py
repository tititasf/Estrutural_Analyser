"""Human decisions about derived sections, scoped to the work and floor.

Only a matching local profile may carry a validated level. CAD originals and
unrelated intervals never inherit that validation.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import math
import uuid

from . import fv_operations as fv
from .item_geometry import sidecar_path


def path(root, floor):
    sidecar_path(Path(root), floor)  # floor validation shared with geometry
    return Path(root) / '.portal_overrides' / 'section_review' / f'{floor}.json'


def load(root, floor):
    file = path(root, floor)
    return fv._read_json(file) if file.is_file() else {}


def restore_generated(root, floor, started_at, *, inventory=None, beam_names=None):
    """Release current rejections only after their scope has been regenerated.

    Keep the rejected evidence and audit identity; never restore validation.
    Decisions made while a job was running belong to the new review cycle.
    """
    if started_at is None:
        return 0
    scopes = ({(e.get('beam'), e.get('step_uid')) for _, e in inventory_items(inventory)}
              if inventory is not None else None)
    names = {str(n).upper() for n in beam_names} if beam_names is not None else None
    with fv._MUTATION_LOCK:
        decisions = load(root, floor)
        restored = 0
        for record in decisions.values():
            if record.get('action') != 'delete':
                continue
            try:
                rejected_at = datetime.fromisoformat(record['updated_at']).timestamp()
            except (KeyError, ValueError, TypeError):
                continue
            if rejected_at > started_at:
                continue
            entry = record.get('entry') or {}
            if scopes is not None and (entry.get('beam'), entry.get('step_uid')) not in scopes:
                continue
            if names is not None and str(entry.get('beam') or '').upper() not in names:
                continue
            record.update(action='rejected', regenerated_at=datetime.now(timezone.utc).isoformat())
            restored += 1
        if restored:
            file = path(root, floor)
            import shutil
            shutil.copy2(file, file.with_suffix('.' + uuid.uuid4().hex + '.bak'))
            fv._atomic_text(file, json.dumps(decisions, ensure_ascii=False, indent=2))
        return restored


def entry_id(entry):
    from .lv_cut_coverage import profile_key
    from .structural_cut_overlay import _section_geometry
    contract = entry.get('section_contract') or {}
    identity = profile_key(contract) if contract else _section_geometry(entry)
    suffix = sha256(json.dumps(identity).encode()).hexdigest()[:16]
    return f"interpreted:{entry['beam']}:{entry['behavior']}:{entry.get('fundo_id') or ''}:{entry['cut_index']}:{suffix}"


def _signature(entry):
    from .lv_cut_coverage import profile_key
    contract = entry.get('section_contract') or {}
    return sha256(json.dumps(dict(profile=profile_key(contract) if contract else None,
        pairs=sorted((_pair_key(p) for p in entry.get('pairs') or [])),
        step_uid=entry.get('step_uid')),
        sort_keys=True).encode()).hexdigest()


def _pair_key(pair):
    return json.dumps({k: pair.get(k) for k in ('start', 'end', 'profiles')}, sort_keys=True)


def inventory_items(inventory):
    for entry in inventory.get('entries', []):
        if entry['kind'] != 'identified':
            yield entry_id(entry), entry
    for entry in inventory.get('interpreted_slab_sections', []):
        yield f"interpreted:slab-step:{entry['step_uid']}", entry


def decide(root, floor, inventory, item_id, action, actor, comentario=''):
    if action not in ('validate', 'delete'):
        raise ValueError('corte interpretado permite apenas validar ou excluir')
    entry = next((e for uid, e in inventory_items(inventory) if uid == item_id), None)
    if entry is None:
        raise LookupError('corte interpretado não encontrado neste pavimento')
    with fv._MUTATION_LOCK:
        decisions = load(root, floor)
        before = deepcopy(entry)
        record = dict(action=action, actor=actor, updated_at=datetime.now(timezone.utc).isoformat(),
                      signature=_signature(entry), entry=deepcopy(entry), event_id=str(uuid.uuid4()),
                      comentario=comentario.strip())
        # SA may renumber a displayed occurrence. Its latest human decision
        # supersedes earlier decisions about that same physical profile.
        decisions = {uid: old for uid, old in decisions.items()
                     if uid == item_id or not ((old.get('entry') or {}).get('beam') == entry.get('beam')
                                               and old.get('signature') == record['signature'])}
        decisions[item_id] = record
        file = path(root, floor)
        file.parent.mkdir(parents=True, exist_ok=True)
        if file.is_file():
            import shutil
            shutil.copy2(file, file.with_suffix('.' + record['event_id'] + '.bak'))
        fv._atomic_text(file, json.dumps(decisions, ensure_ascii=False, indent=2))
    return dict(affected=[dict(classe='cortes_interpretados', item_id=item_id)],
                action=action, before=[before], after=[] if action == 'delete' else [record['entry']],
                event_id=record['event_id'], comentario=record['comentario'])


def status(decisions, item_id, entry=None):
    record = decisions.get(item_id) or {}
    if not record and entry is not None:
        # Display indexes can change after SA. The measured local section cannot.
        record = next((r for r in decisions.values()
                       if (r.get('entry') or {}).get('beam') == entry.get('beam')
                       and r.get('signature') == _signature(entry)), {})
    # Exclusion hides this occurrence until its next successful generation.
    # The historical rejection never becomes a human validation.
    if record.get('action') == 'delete':
        return 'deleted'
    if record.get('action') == 'validate' and (entry is None or record.get('signature') == _signature(entry)):
        return 'validated'
    return None


def apply_levels(cuts, decisions, beam, slabs):
    """Use a human-confirmed datum only for the same beam and local pair."""
    result = deepcopy(cuts)
    levels = {s.get('name'): s.get('nivel', s.get('level', s.get('laje_nivel')))
              for s in slabs}
    for cut in result:
        if cut.get('kind') == 'identified':
            continue
        matches = []
        rejected = False
        for uid, record in decisions.items():
            entry = record.get('entry') or {}
            if str(entry.get('beam') or '').upper() != str(beam).upper():
                continue
            # Compare the interval itself; segment ids alone may be renumbered.
            if not any(a.get('start') and a.get('end') and
                       _pair_key(a) == _pair_key(b)
                       for a in cut.get('pairs') or [] for b in entry.get('pairs') or []):
                continue
            if record.get('action') in ('delete', 'rejected'):
                rejected = True
                cut.setdefault('excluded_interpreted_reference_ids', []).append(uid)
                if cut.get('beam_datum_source') == 'human_validated_section':
                    cut.pop('beam_top_level_m', None)
                    cut.pop('beam_datum_evidence_ids', None)
                    cut['beam_datum_source'] = 'human_rejected_interpretation'
                    cut['confidence'] = 'review'
                continue
            if record.get('action') != 'validate':
                continue
            contract = entry.get('section_contract') or {}
            # A prior confirmation cannot authorize new beam dimensions even
            # when the adjoining slab pair has retained its identity.
            if any(cut.get(field) is not None and
                   abs(float(cut[field]) - float(contract.get(measure, -1))) > .01
                   for field, measure in (('width_cm', 'width_cm'), ('beam_height_cm', 'height_cm'))):
                continue
            for side in ('A', 'B'):
                for slab in (contract.get('slabs') or {}).get(side, []):
                    level = levels.get(slab.get('name'))
                    if level is not None:
                        datum = float(str(level).replace(',', '.')) + float(slab['drop_cm']) / 100
                        if math.isfinite(datum):
                            matches.append((round(datum, 6), uid))
        datums = {v for v, _ in matches}
        if len(datums) == 1 and not rejected:
            cut.update(beam_top_level_m=datums.pop(), beam_datum_source='human_validated_section',
                       beam_datum_evidence_ids=sorted({uid for _, uid in matches}), confidence='high')
        elif len(datums) > 1:
            cut['attention'] = 'Referências humanas de nível conflitantes; revisar o trecho'
    return result
