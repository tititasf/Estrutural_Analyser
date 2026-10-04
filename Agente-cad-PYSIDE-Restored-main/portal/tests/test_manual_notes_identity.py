import json
from portal.app.item_geometry import sidecar_path
from portal.app.routers.qa_routes import _manual_notes_identity


def test_manual_notes_identity_requires_existing_safe_item(tmp_path):
    path = sidecar_path(tmp_path, '13_PAV')
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'created': {'lajes': {'LTESTUX': {'name': 'LTESTUX'}}}}))
    assert _manual_notes_identity(tmp_path, '13_PAV', 'LAJ', 'LTESTUX')
    assert not _manual_notes_identity(tmp_path, '13_PAV', 'LAJ', 'OTHER')
    assert not _manual_notes_identity(tmp_path, '13_PAV', 'LAJ', '../LTESTUX')
    path.write_text(json.dumps({'created': {'lajes': {'LTESTUX': {'name': 'LTESTUX'}}},
                                'deleted': {'lajes': ['LTESTUX']}}))
    assert not _manual_notes_identity(tmp_path, '13_PAV', 'LAJ', 'LTESTUX')
