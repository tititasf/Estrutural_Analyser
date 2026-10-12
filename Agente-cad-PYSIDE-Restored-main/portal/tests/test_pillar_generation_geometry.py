from copy import deepcopy

from src.core.pillar_sa_review import eligible, generation_exclusion


def test_unsupported_section_cannot_be_published_as_bbox():
    pillar = {'name': 'any_name', 'points': [[0,0],[100,0],[100,20],[20,20],
              [20,180],[100,180],[100,200],[0,200]]}
    before = deepcopy(pillar)
    assert not eligible(pillar)
    assert '8 faces' in generation_exclusion(pillar)
    assert 'caixa envolvente' in generation_exclusion(pillar)
    assert pillar == before


def test_supported_rectangle_with_extra_collinear_points_and_l_stay_available():
    for points in (
        [[0,0],[10,0],[20,0],[20,100],[0,100],[0,0]],
        [[0,0],[100,0],[100,20],[20,20],[20,100],[0,100]],
    ):
        assert eligible({'points': points})


def test_four_sides_do_not_automatically_mean_rectangular():
    assert not eligible({'points': [[0,0],[100,0],[80,100],[0,100]]})


def test_legacy_without_contour_keeps_existing_validation_path():
    assert eligible({'name': 'legacy'})
    assert not eligible({'classification': 'NASCE'})


def test_n5_keeps_unsupported_item_in_receipt_and_generates_the_others(tmp_path, monkeypatch):
    import json
    import ezdxf
    from src.core import n5_assembler as assembler
    from src.core import n5_pillar_frames
    root = tmp_path / 'obra'
    root.mkdir()
    (root/'estado_PAV.json').write_text(json.dumps({'pilares':[
        {'name':'ok', 'points':[[0,0],[20,0],[20,100],[0,100]]},
        {'name':'unsupported', 'points':[[0,0],[100,0],[100,20],[20,20],
            [20,180],[100,180],[100,200],[0,200]]}]}))
    sources = []
    for index in range(5):
        path = tmp_path / f'preview_{index}.dxf'
        doc = ezdxf.new()
        doc.modelspace().add_line((0,0),(10,10))
        doc.saveas(path)
        sources.append(path)
    monkeypatch.setattr(assembler, '_discover_item_ids', lambda *a:['ok','unsupported'])
    monkeypatch.setattr(assembler, '_get_db_expected_item_ids', lambda *a:{'ok','unsupported'})
    def previews(*args):
        assert args[2] == 'ok', 'unsupported geometry must never reach the importer'
        return sources
    monkeypatch.setattr(assembler, '_find_n3_previews', previews)
    monkeypatch.setattr(n5_pillar_frames,'uploaded_template',lambda *a:None)
    result = assembler.assemble_n5(root,'PL',pavimento='PAV',allow_partial=True)
    assert result.output_path.is_file() and result.ok_count == 1 and result.missing_count == 1
    receipt = json.loads(result.manifest_path.read_text())
    assert receipt['partial'] is True
    pending = next(row for row in receipt['items'] if row['item_id']=='unsupported')
    assert pending['status'] == 'unsupported' and '8 faces' in pending['message']
