from portal.app import ficha_reader as fr


def test_lazy_views_keep_vectors_and_do_not_fall_back_to_old_packs(tmp_path, monkeypatch):
    pack = tmp_path / 'TIPO_20261009_pilares_abcd'
    pillars = pack / 'pilares'
    assets = pack / 'propostas'
    pillars.mkdir(parents=True)
    assets.mkdir()
    plain = '<svg viewBox="0 0 10 10"><path id="plain" d="M0 0L1 1"/></svg>'
    far = '<svg viewBox="0 0 100 100"><path id="far"/></svg>'
    (assets / 'P8_sa_plain.svg').write_text(plain, encoding='utf-8')
    (assets / 'P8_sa_far.svg').write_text(far, encoding='utf-8')
    (pillars / 'P8.html').write_text(
        '<script>if(txt.indexOf("<svg")>=0){load(txt);}</script>'
        '<div data-n1panel="near"><div data-layer="sa_plain" '
        'data-proposal-src="../propostas/P8_sa_plain.svg"></div>'
        '<div data-layer="sa"><svg><path id="tag"/></svg></div></div>'
        '<div data-n1panel="far"><div data-proposal-src="../propostas/P8_sa_far.svg"></div></div>',
        encoding='utf-8',
    )
    monkeypatch.setattr(fr, '_encontrar_dir_ficha_item', lambda *args: pack)
    def no_legacy(*args):
        raise AssertionError('Complete current views must not parse legacy packs')
    monkeypatch.setattr(fr, '_parse_html_cache', no_legacy)
    views = fr.resolver_visualizacoes_n1_pilar(tmp_path, 'TIPO', 'pilares', {'beam_name': 'P8'})
    assert views['proximo'] == plain
    assert views['distante'] == far


def test_lazy_asset_cannot_escape_pack(tmp_path):
    folder = tmp_path / 'pack' / 'pilares'
    folder.mkdir(parents=True)
    (tmp_path / 'outside.svg').write_text('<svg/>', encoding='utf-8')
    html = folder / 'P1.html'
    html.write_text('<div data-n1panel="far"><div data-proposal-src="../../outside.svg"></div></div>', encoding='utf-8')
    assert fr._parse_pilar_n1_views_cache(str(html), html.stat().st_mtime)['distante'] is None


def test_generic_reader_parses_card_metadata_without_vector_dom(tmp_path, monkeypatch):
    import bs4
    svg = '<svg class="img-geo" aria-label="N1 lado B seg 2" viewBox="0 0 2 2"><path d="M0 0L2 2"/></svg>'
    html = tmp_path / 'P1.html'
    html.write_text('<script>const prefix="<svg";</script><div class="face-card">N1 lado B seg 2' + svg + '</div>', encoding='utf-8')
    original = bs4.BeautifulSoup.__init__
    def skeleton_only(self, text, *args, **kwargs):
        assert '<path' not in text
        return original(self, text, *args, **kwargs)
    monkeypatch.setattr(bs4.BeautifulSoup, '__init__', skeleton_only)
    cards = fr._parse_html_cache(str(html), html.stat().st_mtime)
    assert len(cards) == 1
    assert (cards[0]['nivel'], cards[0]['lado'], cards[0]['segmento']) == ('N1', 'B', '2')
    assert cards[0]['svg'] == svg
