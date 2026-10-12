import re
from portal.app.dxf_preview import svg_viewer_sem_grupos_neutros as optimize


def test_preserves_exact_paths_order_and_reference_groups():
    svg = b'''<svg><style>*{stroke-linejoin: round; stroke-linecap: butt}</style>
    <g id="neutral"><path d="M 1 2 L 4 5" style="fill:none;stroke:#fff"/></g>
    <g id="clipGroup"><path d="M 6 7 L 8 9" clip-path="url(#clipGroup)"/></g>
    <g id="translated" transform="translate(4,5)"><path d="M 9 10"/></g>
    <g id="faded" opacity=".5"><path d="M 11 12"/></g>
    <g id="multi"><path d="M 13 14"/><path d="M 15 16"/></g></svg>'''
    output=optimize(svg)
    assert b'id="neutral"' not in output
    for name in [b'clipGroup',b'translated',b'faded',b'multi']:
        assert b'id="'+name+b'"' in output
    assert re.findall(rb'<path\b[^>]*?/>', output, re.S)==re.findall(rb'<path\b[^>]*?/>', svg,re.S)


def test_unknown_css_keeps_svg_unchanged():
    for css in [b'g > path {opacity:.3}', b'#neutral {display:none}', b'@media screen {g{fill:red}}']:
        svg=b'<svg><style>'+css+b'</style><g id="neutral"><path d="M 1 2"/></g></svg>'
        assert optimize(svg)==svg


def test_clip_transform_and_geometry_without_neutral_group_stay_identical():
    svg=b'<svg viewBox="0 0 20 20"><defs><clipPath id="c"><path d="M 1 2"/></clipPath></defs><g clip-path="url(#c)"><path d="M 3 4"/></g></svg>'
    assert optimize(svg)==svg
