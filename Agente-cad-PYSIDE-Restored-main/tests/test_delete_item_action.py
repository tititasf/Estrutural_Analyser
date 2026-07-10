from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from main import MainWindow


class FakeItem:
    def __init__(self, item_id, name):
        self.item_id = item_id
        self.name = name

    def data(self, _column, role):
        return self.item_id if role == Qt.UserRole else None

    def text(self, _column):
        return self.name


class FakeTree:
    def __init__(self, selected=()):
        self.selected = list(selected)

    def selectedItems(self):
        return self.selected


class FakeDb:
    def __init__(self, error=None):
        self.deleted = []
        self.error = error

    def delete_beam(self, item_id):
        if self.error:
            raise self.error
        self.deleted.append(item_id)


def make_window(beam, db=None):
    calls = SimpleNamespace(refresh=0, draw=0, logs=[])
    window = SimpleNamespace(
        beams_found=[beam], pillars_found=[], slabs_found=[],
        db=db or FakeDb(),
        canvas=SimpleNamespace(
            draw_beams=lambda _items: setattr(calls, 'draw', calls.draw + 1),
            draw_slabs=lambda _items: None,
            draw_interactive_pillars=lambda _items: None,
        ),
        log=calls.logs.append,
        _update_all_lists_ui=lambda: setattr(calls, 'refresh', calls.refresh + 1),
    )
    return window, calls


def test_delete_fundo_removes_beam_and_warns_about_links_and_validations(monkeypatch):
    beam = {
        'id': 'beam-1',
        'links': {'viga_fundo_seg_1_area_segs': {'contour': [{'validated': True}]}},
        'validated_fields': ['viga_fundo_seg_1_dim'],
    }
    window, calls = make_window(beam)
    messages = []
    monkeypatch.setattr(
        QMessageBox, 'question',
        lambda _parent, _title, text, *_args: messages.append(text) or QMessageBox.Yes,
    )

    MainWindow.delete_item_action(
        window, FakeTree([FakeItem('beam-1', 'FV-V301.A Para.C')]), 'beam_fundo', False,
    )

    assert window.db.deleted == ['beam-1']
    assert window.beams_found == []
    assert calls.refresh == 1
    assert calls.draw == 1
    assert 'vínculos' in messages[0]
    assert 'validações humanas' in messages[0]


def test_delete_cancel_preserves_item(monkeypatch):
    window, calls = make_window({'id': 'beam-1', 'links': {}})
    monkeypatch.setattr(QMessageBox, 'question', lambda *_args: QMessageBox.No)

    MainWindow.delete_item_action(
        window, FakeTree([FakeItem('beam-1', 'FV-V301.C')]), 'beam_fundo', False,
    )

    assert window.db.deleted == []
    assert len(window.beams_found) == 1
    assert calls.refresh == 0


def test_delete_db_error_keeps_item_in_memory(monkeypatch):
    window, calls = make_window(
        {'id': 'beam-1', 'links': {}}, FakeDb(RuntimeError('db locked')),
    )
    monkeypatch.setattr(QMessageBox, 'question', lambda *_args: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, 'critical', lambda *_args: QMessageBox.Ok)

    MainWindow.delete_item_action(
        window, FakeTree([FakeItem('beam-1', 'FV-V301.C')]), 'beam_fundo', False,
    )

    assert len(window.beams_found) == 1
    assert calls.refresh == 0
