from portal.app.preprocessamento.sources import SourceKind, _kind
from portal.app.routers import viewer_routes


def test_manual_conventions_keep_their_kind():
    assert _kind('convencao_pilares_selecao_123') is SourceKind.PILLAR_CONVENTION
    assert _kind('convencao_niveis_manual_456') is SourceKind.LEVEL_CONVENTION
    assert _kind('outros_convencao_pilares') is SourceKind.OTHER


def test_viewer_carries_classification_by_identity(monkeypatch):
    class Transform:
        largura_px = altura_px = 100

        def dxf_para_px(self, x, y):
            return x, y

    monkeypatch.setattr(viewer_routes.ficha_reader, 'listar_itens_n1',
                        lambda *_: [{'item_id': name, 'points': [(1, 1), (2, 1), (2, 2)]}
                                    for name in ('P2', 'P1', 'P3', 'P4')])
    state = {'pilares': [{'name': 'P1', 'classification': 'MORRE'},
                         {'name': 'P2', 'classification': 'NASCE'},
                         {'name': 'P3', 'classification': 'SEGUE'}]}
    items = viewer_routes._geometria_dos_itens(state, 'pilares', Transform())
    assert [i['classification'] for i in items] == ['NASCE', 'MORRE', 'SEGUE', None]
