"""Apply narrow, guarded portal edits without replacing unrelated changes."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
edits = []

def edit(file, before, after):
    path = ROOT / file
    text = path.read_text(encoding='utf-8')
    assert text.count(before) == 1, (file, text.count(before))
    path.write_text(text.replace(before, after), encoding='utf-8', newline='')
    edits.append(dict(file=file, before=before, after=after))

edit('portal/app/static/drill_grade.js',
     "doc.item.item_id === itemId;",
     "(doc.item.item_id === itemId || doc.item.item_id.indexOf(itemId + '_') === 0);")
edit('portal/app/static/drill_grade.js',
     "else if (iid === 'convencao_pilares')",
     "else if (iid === 'convencao_pilares' || iid.indexOf('convencao_pilares_') === 0)")
edit('portal/app/static/drill_grade.js',
     "else if (iid === 'convencao_niveis')",
     "else if (iid === 'convencao_niveis' || iid.indexOf('convencao_niveis_') === 0)")
edit('portal/app/preprocessamento/sources.py',
     '    return {\n        "detalhes": SourceKind.DETAILS,',
     '    for prefix, kind in (("convencao_pilares", SourceKind.PILLAR_CONVENTION),\n                         ("convencao_niveis", SourceKind.LEVEL_CONVENTION)):\n        if item_id == prefix or item_id.startswith(prefix + "_"):\n            return kind\n    return {\n        "detalhes": SourceKind.DETAILS,')
edit('portal/app/routers/viewer_routes.py',
     '    saida: list[dict] = []\n    for item in ficha_reader.listar_itens_n1(estado, classe):',
     '    saida: list[dict] = []\n    classifications = {str(p.get("name") or p.get("key")): p.get("classification")\n                       for p in estado.get("pilares", [])} if classe == "pilares" else {}\n    for item in ficha_reader.listar_itens_n1(estado, classe):')
edit('portal/app/routers/viewer_routes.py',
     '            "classe_sa": classe,',
     '            "classe_sa": classe,\n            "classification": classifications.get(str(item.get("item_id"))),')

helper = '''
  // Convenção do pilar já interpretada pelo SA; desconhecidos ficam explícitos.
  function corPilar(item) {
    var c = String(item.classification || '').trim().toUpperCase();
    if (c === 'NASCE') return '#ff4545';
    if (c === 'MORRE') return '#ffe033';
    if (['SEGUE', 'CONTINUA', 'PASSA'].indexOf(c) !== -1) return '#4ea1ff';
    return '#a8b0bd';
  }
'''
legend = '<span style="color:#4ea1ff">● Segue</span> · <span style="color:#ffe033">● Morre aqui</span> · <span style="color:#ff4545">● Nasce no próximo pavimento</span> · <span style="color:#a8b0bd">● Indeterminado</span>'
edit('portal/app/templates/obra_detalhe.html',
     '  function gruposDestaqueParaExibicao(gruposOriginais) {',
     helper + '\n  function gruposDestaqueParaExibicao(gruposOriginais) {')
edit('portal/app/templates/obra_detalhe.html',
     ": alternaFundo ? ['#4ea1ff', '#c9a27e'][idxItem % 2] : corGrupo;",
     ": alternaFundo ? ['#4ea1ff', '#c9a27e'][idxItem % 2] : gLat === 'pilares' ? corPilar(item) : corGrupo;")
edit('portal/app/templates/obra_detalhe.html',
     "'<span class=\"meta\" id=\"destaque-info\"></span>';",
     "'<span class=\"meta\" id=\"destaque-info\"></span>' +\n      '<span class=\"destaque-pilares-legenda\" style=\"flex-basis:100%;font-size:.72rem\">" + legend + "</span>';")
edit('portal/app/templates/obra_detalhe.html',
     "&dm=20260929fastboot", "&dm=20260930convencao")
edit('portal/app/templates/viewer.html', '  function desenhar() {', helper + '\n  function desenhar() {')
edit('portal/app/templates/viewer.html',
     '      var cor = CORES[grupo.grupo] || "#fff";\n      grupo.itens.forEach(function (item) {',
     '      var corGrupo = CORES[grupo.grupo] || "#fff";\n      grupo.itens.forEach(function (item) {\n        var cor = grupo.grupo === "pilares" ? corPilar(item) : corGrupo;')
edit('portal/app/templates/viewer.html',
     '  Itens em vermelho têm geometria fora da prancha — erro de interpretação a investigar,\n  não são desenháveis aqui.',
     '  ' + legend + '\n  · Geometria fora da prancha é indicada no título do item.')
(ROOT / 'scripts/pillar_colors_edits_20260930.json').write_text(json.dumps(edits, ensure_ascii=False), encoding='utf-8')
