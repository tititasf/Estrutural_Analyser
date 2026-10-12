"""Automatic before/after evidence in the existing UI feedback inbox."""
from io import BytesIO
import json
from pathlib import Path
from urllib.parse import urlencode


def render(before, after, action):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('RGB', (1000, 440), '#0b1424')
    painter = ImageDraw.Draw(image)
    from matplotlib.font_manager import findfont
    font = ImageFont.truetype(findfont('DejaVu Sans'),size=18)
    def primitives(rows):
        result = []
        for row in rows:
            drawing = row.get('drawing') or row.get('section_drawing') or {}
            if drawing.get('primitives'):
                result.extend(drawing['primitives'])
            elif row.get('ficha'):
                from src.core.lv_n3_cut_contract import build_cut_contract, CutContractError
                try:
                    contract = build_cut_contract(dict(id=row.get('uid'), beam=row.get('beam_name'), kind='identified', source_cut=row))
                except CutContractError:
                    contract = None
                if contract:
                    w, h = contract['width_cm'], contract['height_cm']
                    def box(x, y, width, height):
                        result.append(dict(kind='polygon', color='#7dd3fc', points=
                            [[x,y],[x+width,y],[x+width,y+height],[x,y+height]]))
                    box(0,0,w,h)
                    for side in ('A', 'B'):
                        for slab in contract['slabs'][side]:
                            box(-20 if side == 'A' else w,
                                h-slab['drop_cm']-slab['height_cm'],20,slab['height_cm'])
                    result.append(dict(kind='text', color='white', points=[[0,h+5]],
                        text=f"{row.get('beam_name','')} ({w:g}/{h:g})"))
                    for i, side in enumerate(('A', 'B')):
                        for j, slab in enumerate(contract['slabs'][side]):
                            result.append(dict(kind='text',color='white', points=[[-20,h+12+7*(i+j)]],
                                text=f"{side}: {slab['name']} h={slab['height_cm']:g} rebaixo={slab['drop_cm']:g}"))
                else:
                    pts = row.get('points') or row.get('pts') or []
                    if pts:
                        result.append(dict(kind='polygon', points=pts, color='#7dd3fc'))
            else:
                pts = drawing.get('points') or row.get('points') or row.get('pts') or []
                if pts:
                    result.append(dict(kind='polygon', points=pts, color='#7dd3fc'))
        return result
    panels = [primitives(before), primitives(after)]
    all_points = [p for panel in panels for item in panel for p in item.get('points', [])]
    if all_points:
        xs, ys = zip(*all_points)
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        scale = min(450 / max(x1-x0, 1), 330 / max(y1-y0, 1))
    else:
        x0 = y0 = 0
        scale = 1
    for index, panel in enumerate(panels):
        offset = index * 500
        title = 'Antes' if index == 0 else ('Excluído' if action == 'delete' else 'Depois (correto)')
        painter.text((offset + 20, 14), title, font=font, fill='white')
        for item in panel:
            pts = [(offset + 25 + (p[0]-x0)*scale, 400-(p[1]-y0)*scale) for p in item['points']]
            color = item.get('color') or '#7dd3fc'
            if item['kind'] == 'polygon' and len(pts) >= 3:
                painter.polygon(pts, fill='#15283d', outline=color, width=2)
            elif item['kind'] == 'text' and pts:
                painter.text(pts[0], str(item.get('text') or ''), fill=color)
            elif len(pts) >= 2:
                painter.line(pts, fill=color, width=2)
        if not panel:
            painter.text((offset + 100, 210), 'Destaque removido' if action == 'delete' else 'Sem desenho anterior', font=font, fill='white')
        # Retain the actual picked contour as well as semantic dimensions.
        # A geometry-only correction must remain visible in the evidence.
        rows = before if index == 0 else after
        outlines = [r.get('points') or r.get('pts') or [] for r in rows if r.get('ficha')]
        points = [p for outline in outlines for p in outline]
        if points:
            xs, ys = zip(*points)
            ox, oy = min(xs), min(ys)
            ratio = min(160/max(max(xs)-ox,1), 75/max(max(ys)-oy,1))
            painter.rectangle((offset+305,320,offset+490,430),fill='#0b1424',outline='#506079')
            painter.text((offset+310,324),'Contorno selecionado',fill='white')
            for outline in outlines:
                polygon = [(offset+315+(p[0]-ox)*ratio,420-(p[1]-oy)*ratio) for p in outline]
                if len(polygon)>=3:
                    painter.polygon(polygon,outline='#7dd3fc',width=2)
    painter.line([(500, 0), (500, 440)], fill='#506079')
    output = BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def _persist(conn, payload):
    from ..db import repository as repo
    existing = conn.execute('SELECT id FROM portal_apontamento_sessoes WHERE origem_evento=?',
                            ('structural-edit:' + payload['result']['event_id'],)).fetchone()
    if existing:
        return existing[0]
    result, floor, obra_id = payload['result'], payload['floor'], payload['obra_id']
    before, after = result.get('before', []), result.get('after', [])
    action = result.get('action', 'edit')
    labels = ', '.join(i['classe'] + ' / ' + i['item_id'] for i in result['affected'])
    text = f"Ajuste manual · {floor} · {labels} · " + {
        'edit': 'edição salva; comparação antes/depois',
        'create': 'item criado', 'delete': 'exclusão salva; desenho excluído preservado',
        'validate': 'corte validado como referência humana de nível de alta confiança',
    }[action]
    comment = result.get('comentario') or ''
    if comment:
        text += '\nComentário: ' + comment
    evidence = dict(pavimento=floor, action=action, affected=result['affected'], before=before, after=after,
                    comentario=comment)
    context = payload.get('structural_context') or {}
    evidence['structural_context'] = {key:value for key,value in context.items() if key!='png_base64'}
    import base64
    png = base64.b64decode(context['png_base64']) if context.get('png_base64') else render(before, after, action)
    if context.get('status')=='captured':
        text += '\nContexto estrutural antes/depois congelado: mesma região e escala, item marcado em amarelo; '
        text += f"{len(context.get('nearby_items', []))} elementos vizinhos registrados."
    else:
        text += '\nContexto estrutural indisponível: '+str(context.get('reason') or 'evento anterior sem captura do entorno')
    url = payload['base_url'].rstrip('/') + '/app/obras/' + obra_id + '?' + urlencode(dict(pavimento=floor))
    point = dict(texto=text, pagina_url=url, pagina_titulo='Ajuste manual no estrutural',
        seletor_elemento='#doc-viewer-extra', elemento_tag='svg', elemento_role='structural-edit',
        elemento_texto=labels, elemento_json=json.dumps(evidence, ensure_ascii=False),
        clique_x=0, clique_y=0, pagina_x=0, pagina_y=0,
        viewport_largura=context.get('width',1000), viewport_altura=context.get('height',440),
        captura_mime='image/png', captura_blob=png,
        anexos=[dict(nome='antes-depois.png', mime='image/png', blob=png),
                dict(nome='dados-antes-depois.json', mime='application/json',
                     blob=json.dumps(evidence, ensure_ascii=False, indent=2).encode())])
    return repo.inserir_sessao_apontamento_ui(conn, obra_id=obra_id, membro_id=payload['actor'],
        titulo=text, origem_evento='structural-edit:' + result['event_id'],
        paginas=[dict(pagina_url=url, pagina_titulo='Ajuste manual no estrutural', pontos=[point])])


def record(conn, request, membro, obra_id, floor, result, directory):
    from . import fv_operations as fv
    file = Path(directory) / '.portal_overrides' / 'audit_outbox' / (result['event_id'] + '.json')
    file.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(result=result, floor=floor, obra_id=obra_id, actor=membro['id'], base_url=str(request.base_url))
    # Journal the saved mutation before the potentially expensive CAD render.
    fv._atomic_text(file, json.dumps(payload, ensure_ascii=False))
    try:
        from .structural_audit_context import capture
        payload['structural_context'] = capture(directory, floor, result)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception('Structural audit context unavailable: %s', result['event_id'])
        payload['structural_context'] = dict(status='unavailable', reason=str(exc))
    fv._atomic_text(file, json.dumps(payload, ensure_ascii=False))
    try:
        identifier = _persist(conn, payload)
    except Exception:
        # The edit is saved. The inbox retries this durable event, without
        # telling the operator to repeat an already completed mutation.
        import logging
        logging.getLogger(__name__).exception('Structural audit queued: %s', result['event_id'])
        result['apontamento_pendente'] = True
        return None
    payload['delivered'] = identifier
    fv._atomic_text(file, json.dumps(payload, ensure_ascii=False))
    return identifier


def flush(conn, request, membro):
    from ..db import repository as repo
    from .routers.n1_routes import _obra_dir
    from . import fv_operations as fv
    works = repo.listar_todas_obras(conn) if membro.get('papel') == 'dono' else repo.listar_obras_por_membro(conn, membro['id'])
    for work in works:
        try:
            directory = _obra_dir(request, work)
        except Exception:
            continue
        for file in (Path(directory) / '.portal_overrides' / 'audit_outbox').glob('*.json'):
            payload = fv._read_json(file)
            if payload.get('delivered') or payload.get('obra_id') != work['id']:
                continue
            try:
                payload['delivered'] = _persist(conn, payload)
                fv._atomic_text(file, json.dumps(payload, ensure_ascii=False))
            except Exception:
                import logging
                logging.getLogger(__name__).exception('Structural audit remains queued: %s', file.name)
