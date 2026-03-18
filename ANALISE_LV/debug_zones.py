import json

params = json.load(open('D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v3.json'))
treino1_13pav = [p for p in params if 'TREINO_1' in p.get('obra','') and '13' in p.get('dxf_source','')]
treino1_13pav.sort(key=lambda x: (round(x.get('insert',{}).get('y',0),-2), x.get('insert',{}).get('x',0)))

last_y = None
for p in treino1_13pav:
    ins = p.get('insert',{})
    z = p.get('zone',{})
    iy = round(ins.get('y',0), -2)
    if iy != last_y:
        print('--- Y~%d ---' % iy)
        last_y = iy
    fa = p['face_a']
    print('  %-15s ins=(%6.0f,%6.0f) xl=%-8s xr=%-8s FA=%2d tot=%s' % (
        p['viga'], ins.get('x',0), ins.get('y',0),
        str(z.get('x_left')), str(z.get('x_right')),
        fa['panel_count'], fa['total_width']))
