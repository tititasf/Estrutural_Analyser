"""Freeze the same structural neighborhood on both sides of a manual change."""
from io import BytesIO
from pathlib import Path
import base64
import hashlib
from datetime import datetime, timezone


def primitives(rows):
    result = []
    for row in rows:
        drawing = row.get('drawing') or row.get('section_drawing') or {}
        if drawing.get('primitives'):
            result.extend(drawing['primitives'])
        else:
            points = drawing.get('points') or row.get('points') or row.get('pts') or []
            if points:
                result.append(dict(kind='polygon', points=points, color='#7dd3fc'))
    return result


def capture(directory, floor, result):
    from PIL import Image, ImageDraw, ImageFont
    import cairosvg
    from . import ficha_reader, dxf_preview
    from .routers.viewer_routes import encontrar_estrutural_limpo
    source = ficha_reader._fonte_estrutural_producao(Path(directory), floor)
    if not source:
        found = encontrar_estrutural_limpo(Path(directory), {}, floor)
        source = Path(found['path']) if found else None
    if not source or not source.is_file():
        return dict(status='unavailable', reason='Estrutural limpo não encontrado neste pavimento')
    before = primitives(result.get('before', []))
    after = primitives(result.get('after', []))
    points = [p for primitive in before+after for p in primitive.get('points', [])]
    if not points:
        return dict(status='unavailable', reason='Item sem coordenadas para enquadrar o contexto')
    xs, ys = zip(*points)
    target = [min(xs), min(ys), max(xs), max(ys)]
    pad = max(220, max(target[2]-target[0], target[3]-target[1])*.4)
    bbox = [target[0]-pad, target[1]-pad, target[2]+pad, target[3]+pad]
    width, height, header = 1000, 850, 70
    transform = dxf_preview.renderizar_dxf_svg_com_transform_cacheado(source,
        Path(directory)/'.previews'/'audit_context', bbox=tuple(bbox),
        largura_px=width, altura_px=height, margem_pct=0)
    base = Image.open(BytesIO(cairosvg.svg2png(bytestring=transform.svg,
        output_width=width, output_height=height))).convert('RGB')
    canvas = Image.new('RGB', (width*2, height+header+480), '#0b1424')
    from matplotlib.font_manager import findfont
    font = ImageFont.truetype(findfont('DejaVu Sans'),size=20)
    small_font = ImageFont.truetype(findfont('DejaVu Sans'),size=12)
    state = ficha_reader.ler_estado_pavimento(Path(directory), floor)
    nearby = []
    affected = {(i['classe'], i['item_id']) for i in result['affected']}
    for cls in ('pilares', 'lajes', 'fundo', 'lateral_a_para', 'lateral_b_para', 'lateral_a_passa', 'lateral_b_passa', 'cortes'):
        for item in ficha_reader.listar_itens_n1(state, cls):
            pts = item.get('points') or []
            if not pts or (cls, item.get('item_id')) in affected:
                continue
            px, py = zip(*pts)
            if max(px)<bbox[0] or min(px)>bbox[2] or max(py)<bbox[1] or min(py)>bbox[3]:
                continue
            nearby.append(dict(classe=cls, item_id=item.get('item_id'), titulo=item.get('titulo'),
                               points=pts, campos=item.get('campos')))
    # CAD background plus current neighboring highlights, with frozen identities.
    colors = dict(pilares='#94a3b8', lajes='#22c55e', fundo='#38bdf8', cortes='#a8fff0')
    for index, panel in enumerate((before, after)):
        image = base.copy()
        painter = ImageDraw.Draw(image)
        for item in nearby:
            pts = [transform.dxf_para_px(*p[:2]) for p in item['points']]
            if len(pts)>=2:
                painter.line(pts+[pts[0]], fill=colors.get(item['classe'], '#e4b785'), width=1)
        for primitive in panel:
            pts = [transform.dxf_para_px(*p[:2]) for p in primitive['points']]
            color = primitive.get('color') or '#7dd3fc'
            if primitive['kind']=='text' and pts:
                painter.text(pts[0], str(primitive.get('text') or ''), fill=color)
            elif len(pts)>=2:
                painter.line(pts+([pts[0]] if primitive['kind']=='polygon' else []), fill=color, width=3)
        start = transform.dxf_para_px(target[0], target[3])
        end = transform.dxf_para_px(target[2], target[1])
        painter.rectangle((start[0]-8,start[1]-8,end[0]+8,end[1]+8), outline='#ffe033', width=2)
        canvas.paste(image, (width*index,header))
        title = 'Antes · item destacado' if index==0 else ('Depois · destaque excluído; estrutural preservado'
                    if result['action']=='delete' else 'Depois · alteração salva')
        ImageDraw.Draw(canvas).text((width*index+20,12),title,font=font,fill='white')
        ImageDraw.Draw(canvas).text((width*index+20,40),floor+' · mesma região e escala · área do item em amarelo',font=small_font,fill='#cbd5e1')
    # Keep semantic field edits visible too: their CAD contour may be unchanged.
    from .structural_audit import render
    detail = Image.open(BytesIO(render(result.get('before', []), result.get('after', []), result['action'])))
    ImageDraw.Draw(canvas).text((20,height+header+10),
        'Detalhe do item · geometria e dados antes/depois',font=font,fill='white')
    canvas.paste(detail, (width//2,height+header+40))
    output = BytesIO(); canvas.save(output,format='PNG')
    return dict(status='captured', png_base64=base64.b64encode(output.getvalue()).decode(),
        captured_at=datetime.now(timezone.utc).isoformat(),
        source=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        bbox_dxf=list(transform.bbox_dxf), target_bbox_dxf=target, nearby_items=nearby,
        width=canvas.width, height=canvas.height)
