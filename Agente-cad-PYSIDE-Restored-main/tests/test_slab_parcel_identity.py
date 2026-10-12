from src.core.slab_parcel_identity import accepted_level_for_parcel, group_source_parcels
from src.core.sa_db_persistence import merge_analysis_collection


def slab(x, handle, level=''):
    return dict(name='L9', source_label_handle=handle, pos=[x+5, 5],
                points=[(x,0),(x+10,0),(x+10,10),(x,10),(x,0)],
                level_str=level, fields={'laje_nivel': level})


def test_disjoint_homonyms_preserve_units_and_unresolved_level():
    left, right = slab(0,'D62'), slab(100,'D63','855.25 m')
    merged, stats = merge_analysis_collection([], [left,right], 'LAJ', 'p')
    assert len(merged) == 2 and len({r['id'] for r in merged}) == 2
    assert stats['duplicatas_laj_descartadas_da_analise'] == 0
    assert accepted_level_for_parcel(left,[right]) == ''
    assert accepted_level_for_parcel(right,[right]) == '855.25 m'


def test_human_decision_is_not_transferred_to_disjoint_homonym():
    old = slab(100,'D63','855.25 m')
    old.update(id='human',is_validated=True)
    merged, _ = merge_analysis_collection([old], [slab(0,'D62')], 'LAJ', 'p')
    assert len(merged) == 2
    left = next(r for r in merged if r['source_label_handle']=='D62')
    assert left['fields']['laje_nivel'] == '' and left['id'] != 'human'


def test_exact_label_authorizes_updated_geometry_but_conflicts_stay_unresolved():
    original, corrected = slab(0,'D62','855.22 m'),slab(0,'D62','855.25 m')
    corrected['points'][1] = (12,0)
    assert len(group_source_parcels([original,corrected])) == 1
    assert accepted_level_for_parcel(corrected,[original]) == '855.22 m'
    assert accepted_level_for_parcel(corrected,[original,corrected]) == ''


def test_database_cleanup_preserves_two_disjoint_source_parcels(tmp_path):
    import sqlite3
    from src.core.database import DatabaseManager
    from src.core.sa_db_persistence import persist_analysis_snapshot
    db = tmp_path / 'parcel.vision'
    DatabaseManager(str(db))
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO projects(id,name) VALUES('p','Teste')")
    merged, _ = merge_analysis_collection([], [slab(0,'D62'),slab(100,'D63')], 'LAJ', 'p')
    persist_analysis_snapshot(db_path=str(db),project_id='p',
        collections={'pillars':[],'slabs':merged,'beams':[]},
        run_id='test',html_dir='test',source_dxf='source.dxf',
        merge_stats={},delete_missing=False)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM slabs WHERE name='L9'").fetchone()[0] == 2


def test_partial_overlap_without_source_proof_cannot_copy_human_seal():
    old, fresh = slab(0,''),slab(5,'')
    for row in (old,fresh):
        row.pop('pos')
    old.update(id='human',is_validated=True)
    merged, _ = merge_analysis_collection([old],[fresh],'LAJ','p')
    assert len(merged) == 2
    assert sum(bool(r.get('is_validated')) for r in merged) == 1
    assert len(group_source_parcels([{'name':'L9'},{'name':'L9'}])) == 2
