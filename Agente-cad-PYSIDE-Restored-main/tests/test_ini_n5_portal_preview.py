from pathlib import Path
from xml.etree import ElementTree

from portal.app.routers import jobs_routes as routes


def test_ini_atlas_uses_native_sheet_positions(tmp_path, monkeypatch):
    path = tmp_path/'N5.dxf'
    path.touch()
    pages = [{'origin': [i % 3 * 4505, -(i // 3) * 3270],
              'width': 4205, 'height': 2970} for i in range(4)]
    monkeypatch.setattr(routes, '_n5_manifest', lambda _: {'frame_layout': {
        'kind': 'ini_frames_v1', 'pages': pages}})
    root = ElementTree.fromstring(routes._n5_pl_tiled_svg('obra', '13_PAV', path, 'INI'))
    images = root.findall('{http://www.w3.org/2000/svg}image')
    assert [(float(e.attrib['x']), float(e.attrib['y'])) for e in images] == [
        (0, 0), (4505, 0), (9010, 0), (0, 3270)]
    assert all('/foto-sheet/' in e.attrib['href'] for e in images)
    assert root.attrib['viewBox'] == '0 0 13215 6240'


def test_ini_sheet_endpoint_resolves_native_filename_and_dimensions(tmp_path, monkeypatch):
    from src.core import n5_sheet_preview
    path = tmp_path/'N5.dxf'
    folder = tmp_path/'N5_pages'
    folder.mkdir()
    (folder/'folha_001.dxf').touch()
    release = {'dxf_path': str(path)}
    monkeypatch.setattr(routes, '_obra_do_membro', lambda *args: None)
    monkeypatch.setattr(routes.repo, 'listar_n5_releases_por_obra', lambda *args: [])
    monkeypatch.setattr(routes, '_select_n5_release', lambda *args: release)
    monkeypatch.setattr(routes, '_n5_manifest', lambda _: {'frame_layout': {
        'kind': 'ini_frames_v1', 'pages': [{'width': 4205, 'height': 2970}]}})
    rendered = []
    def render(p, width, height):
        rendered.append((Path(p).name, width, height))
        return b'<svg xmlns="http://www.w3.org/2000/svg"/>'
    monkeypatch.setattr(n5_sheet_preview, 'render_sheet', render)
    response = routes.n5_pl_foto_sheet('obra', 'PL', 0, None, '13_PAV', 'INI',
                                      None, None, None, {}, None)
    assert response.status_code == 200
    assert rendered == [('folha_001.dxf', 420.5, 297)]
