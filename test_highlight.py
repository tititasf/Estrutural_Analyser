import sys, sqlite3
from pathlib import Path
sys.path.insert(0, 'd:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main')
sys.path.insert(0, 'd:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/consulta-publica-api')
from services.ficha_service import resolver_item_e_fichas
from portal.app.ficha_reader import _fonte_estrutural_producao
from portal.app.dxf_preview import renderizar_dxf_svg_com_transform_cacheado

conn = sqlite3.connect('d:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/consulta-publica-api/public_consulta.db')
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT * FROM public_codes WHERE code='NWxt8llvs5'").fetchone()
if not row:
    row = conn.execute("SELECT * FROM public_codes WHERE kind='item' LIMIT 1").fetchone()
print('Row:', dict(row))
res = resolver_item_e_fichas(row)
if res:
    obra_dir, item, _ = res
    print('Item ID:', item.get('item_id'), 'Points:', item.get('points'))
    estrutural = _fonte_estrutural_producao(obra_dir, row['pavimento'])
    print('Estrutural:', estrutural)
    if estrutural:
        res_tf = renderizar_dxf_svg_com_transform_cacheado(
            estrutural, Path(obra_dir) / '.previews' / 'estrutural_limpo',
            largura_px=1400, altura_px=900, margem_pct=0.03
        )
        tf = res_tf.transform
        pts = [(round(tf.dxf_para_px(float(p[0]), float(p[1]))[0], 1), round(tf.dxf_para_px(float(p[0]), float(p[1]))[1], 1)) for p in item.get('points', [])]
        print('Px points:', pts)
