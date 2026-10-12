"""Historical relocation targets must survive retention while publicly linked."""
import importlib.util
import os
from pathlib import Path
import sqlite3

import pytest


@pytest.fixture
def cleanup(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / 'ops/limpeza_disco.py'
    spec = importlib.util.spec_from_file_location('historical_cleanup_test', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(module, 'NOW', module.time.time() + 3 * module.DAY)
    for number in (55, 56):
        pack = tmp_path / f'historical_ficha_storage_v{number}/Obra/PAV_pack'
        pack.mkdir(parents=True)
        (pack / 'P12.svg').write_text('<svg/>')
    return module


def test_unreferenced_old_version_is_eligible(cleanup):
    plan = cleanup.Plan()
    cleanup.r1_historical(plan)
    assert [p.name for _, p, _ in plan.items] == ['historical_ficha_storage_v55']


def test_database_reference_pins_old_version(cleanup):
    with sqlite3.connect(cleanup.ROOT / 'portal_data.db') as db:
        db.execute('create table assets (path text)')
        db.execute('insert into assets values (?)', ('historical_ficha_storage_v55/P12.svg',))
    plan = cleanup.Plan()
    cleanup.r1_historical(plan)
    assert plan.items == []


def test_public_link_pins_target_and_rechecked_before_deletion(cleanup):
    plan = cleanup.Plan()
    cleanup.r1_historical(plan)
    pack = cleanup.ROOT / 'historical_ficha_storage_v55/Obra/PAV_pack'
    public = cleanup.ROOT / 'scripts/arete/html_fichas/Obra'
    public.mkdir(parents=True)
    try:
        (public / 'PAV_pack').symlink_to(pack, target_is_directory=True)
    except OSError:
        pytest.skip('Host lacks symlink privilege; run this test on Linux')
    new_plan = cleanup.Plan()
    cleanup.r1_historical(new_plan)
    assert new_plan.items == []
    plan.run(True, lambda message: None)
    assert (pack / 'P12.svg').is_file()


def test_unreadable_catalogue_aborts_cleanup(cleanup, monkeypatch):
    def fail(names):
        raise sqlite3.OperationalError('unreadable DB')
    monkeypatch.setattr(cleanup, 'db_referenced_names', fail)
    plan = cleanup.Plan()
    with pytest.raises(sqlite3.OperationalError):
        cleanup.r1_historical(plan)
    assert plan.items == []
