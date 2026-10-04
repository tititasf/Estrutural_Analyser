"""Apply a narrowly scoped migration without changing surrounding CRLF files."""
from pathlib import Path

root = Path(__file__).resolve().parents[2]

def edit(relative, change):
    path = root / relative
    content = path.read_bytes()
    text = content.decode('utf-8')
    newline = '\r\n' if '\r\n' in text else '\n'
    text = text.replace('\r\n', '\n')
    text = change(text)
    path.write_bytes(text.replace('\n', newline).encode('utf-8'))

def lv(text):
    start = text.index('    (sectionDrawings || []).forEach(function (drawing) {')
    end = text.index('    svg.appendChild(group);', start)
    return text[:start] + '    window.StructuralSections.draw(doc, group, sectionDrawings, toSvg);\n' + text[end:]

def template(text):
    text = text.replace("    cortes: '#4fc3a1'", "    cortes: '#a8fff0',\n    cortes_interpretados: '#ff9a1f'")
    text = text.replace("    } else if (g === 'cortes') {", "    } else if (g === 'cortes_interpretados') {\n      partes = [m('#ff9a1f', 'Cortes de viga interpretados · pares A/B'), 'cotas em cm'];\n    } else if (g === 'cortes') {")
    marker = '              visiveis++;\n'
    assert text.count(marker) == 1
    text = text.replace(marker, marker + "              if (item.section_drawing) {\n                window.StructuralSections.draw(document, overlay, [item.section_drawing], function(p) { return p; }, {names: mostrarRotulos});\n                return;\n              }\n")
    marker = '<script src="/static/lv_ficha.js'
    start = text.index(marker)
    line = text[start:text.index('\n', start)]
    # Reuse the application's standard release/cache version query.
    text = text[:start] + line.replace('lv_ficha.js', 'structural_sections.js') + '\n' + text[start:]
    return text

edit('portal/app/static/lv_ficha.js', lv)
edit('portal/app/templates/obra_detalhe.html', template)
