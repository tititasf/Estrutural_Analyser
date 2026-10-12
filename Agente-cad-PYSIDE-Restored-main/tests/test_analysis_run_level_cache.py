import os
import ezdxf
from src.core import niveis_extractor as levels
from src.core.analysis_run_cache import analysis_run_cache


def test_run_cache_reuses_levels_without_sharing_mutations_and_refreshes_changed_file(tmp_path, monkeypatch):
    source = tmp_path / 'convencao_niveis.dxf'
    ezdxf.new().saveas(source)
    calls = []
    walk = os.walk
    monkeypatch.setattr(os, 'walk', lambda path: (calls.append(path) or walk(path)))
    monkeypatch.setattr(levels, 'extract_elevacao_tipica', lambda texts: [
        {'pav_num': 12, 'chegada': '849,20', 'altura': '2,80'},
        {'pav_num': 13, 'chegada': '852,00', 'altura': '2,80'}])

    @analysis_run_cache
    def collect():
        first = levels.get_pavimento_niveis_abs(str(tmp_path), '13_PAV')
        first['chegada_abs'] = -1
        assert levels.get_pavimento_niveis_abs(str(tmp_path), '13_PAV')['chegada_abs'] == 852
        assert len(calls) == 1
        doc = ezdxf.new()
        doc.modelspace().add_text('changed')
        doc.saveas(source)
        assert levels.get_pavimento_niveis_abs(str(tmp_path), '13_PAV')['altura_cm'] == 280
        assert len(calls) == 2

    collect()
    levels.get_pavimento_niveis_abs(str(tmp_path), '13_PAV')
    assert len(calls) == 3  # no persistent cache leaks into another caller


def test_absent_source_is_cached_only_within_one_run(tmp_path, monkeypatch):
    monkeypatch.setattr(levels, 'extract_elevacao_tipica', lambda texts: [
        {'pav_num': 13, 'chegada': '852,00', 'altura': '2,80'}])
    @analysis_run_cache
    def collect():
        return levels.get_pavimento_niveis_abs(str(tmp_path), '13_PAV')
    assert collect() == {}
    # A new run must rediscover the convention even after a negative result.
    doc = ezdxf.new()
    doc.saveas(tmp_path / 'convencao_niveis.dxf')
    assert collect()['chegada_abs'] == 852
