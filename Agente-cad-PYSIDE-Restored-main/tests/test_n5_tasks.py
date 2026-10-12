import importlib.util
from pathlib import Path
import ezdxf
import pytest
from src.core.n5_tasks import run_assembly_tasks


def test_distinct_classes_preserve_geometry_inventory_and_failures(tmp_path):
    obra = tmp_path / 'obra'
    folder = obra / 'Fase-6_Execucao_CAD'
    folder.mkdir(parents=True)
    for cls, item in [('FV', 'V9'), ('LJ', 'L9')]:
        doc = ezdxf.new('R2018')
        doc.modelspace().add_lwpolyline([(0, 0), (180, 0), (180, 40), (0, 40)], close=True)
        doc.saveas(folder / f'{cls}_preview_{item}.dxf')
    tasks = [(cls, str(obra), cls, dict(item_ids=[item], visual_mode='NOVA'))
             for cls, item in [('FV', 'V9'), ('LJ', 'L9')]]
    spec = importlib.util.spec_from_file_location('n5_parity', Path(__file__).resolve().parents[1] /
        'scripts/arete/relatorios/20261008_n3_performance/compare_dxf.py')
    parity = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parity)
    before = run_assembly_tasks(tasks, 1)
    hashes = {label: parity.canonical(result.output_path) for label, result in before}
    after = run_assembly_tasks(tasks, 2)
    assert {label: parity.canonical(result.output_path) for label, result in after} == hashes
    assert [result.ok_count for _, result in after] == [1, 1]
    assert [result.missing_count for _, result in after] == [0, 0]
    with pytest.raises(ValueError, match='Classe N5 invalida'):
        run_assembly_tasks([('invalid', str(obra), 'INVALID', {})], 1)


def test_duplicate_output_destinations_rejected_before_drawing(tmp_path):
    task = ('LV', str(tmp_path), 'LV', dict(visual_mode='INI',
            lateral_behavior='PARA', lateral_assembly='gradeadas'))
    with pytest.raises(ValueError, match='mesmo destino'):
        run_assembly_tasks([task, task], 2)
    assert not (tmp_path / 'Fase-6_Execucao_CAD').exists()
