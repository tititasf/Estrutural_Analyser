"""Explain inventory multiplication without editing production interpretation."""
import json
import math
from pathlib import Path

folder = Path(__file__).parent/'relatorios'/'20261001_dynamic_cut'
rows = json.loads((folder/'inventory.json').read_text(encoding='utf8'))
n4rows = json.loads((folder.parent/'20261001_qa_cut_n3_n4'/'n4_inventory.json').read_text(encoding='utf8'))
references = {r['beam']: r for r in n4rows if r['n4_exists']}
comparable = [r for r in rows if r['behavior']=='passa' and r['beam'] in references]
contracts = [c['qa_contract'] for r in comparable for c in r['cuts']]
dimensions = sum(len({(c['qa_contract']['width_cm'], c['qa_contract']['height_cm'])
                      for c in r['cuts']}) for r in comparable)
assert len(contracts) == 90 and dimensions == 37
details = json.loads((folder/'causes_live.json').read_text(encoding='utf8'))
confirmed = []
for row in details:
    for side in ('a', 'b'):
        seg = row[side]
        start, end = seg['points'][0], seg['points'][-1]
        length = math.dist(start, end)
        ux, uy = (end[0]-start[0])/length, (end[1]-start[1])/length
        interval = sorted((p[0]-start[0])*ux+(p[1]-start[1])*uy
                          for p in (row['pair']['start'], row['pair']['end']))
        for opening in seg['beam_openings']:
            low = opening.get('position_cm')
            width = opening.get('width_cm')
            if low is None or width is None:
                continue
            high = low+width
            if interval[0] >= low-.5 and interval[1] <= high+.5:
                confirmed.append(dict(beam=row['beam'], cut=row['cut'], side=side,
                                      opening=opening['name'], pair_length=row['pair']['length_cm'],
                                      interval=interval, opening_interval=[low, high]))
(folder/'opening_overlap_causes.json').write_text(json.dumps(confirmed, indent=2), encoding='utf8')
lines = [
    '# Investigação do excesso de Visão Corte — 01/10/2026', '',
    'A verificação anterior provou sobreposição longitudinal, mas não validou a semântica',
    'de cada faixa pareada. Conclusão anterior de geração completa não era aprovação da quantidade.', '',
    'Comparação equivalente: 31 vigas Passa com referência N4. N3: 90 cortes; N4: 34.',
    'Os 90 N3 têm apenas 37 combinações por viga de largura/altura. As outras 53 variantes',
    'são introduzidas por espessura, desnível ou ausência de laje. Isto é uma decomposição',
    'da contagem, não autorização para agrupar ignorando lajes.', '',
    '## Falha confirmada: aberturas não participam do contrato do corte calculado', '',
    '`pair_sections` recorta o intervalo apenas pelas interseções dos polígonos de laje.',
    'Não consulta `segment.beam_openings`. `_profile` inclui largura/altura/nível/lajes,',
    'mas não as aberturas. `build_cut_contract` desenha concreto integral para esses pares.',
    'Nos casos abaixo, a faixa que virou uma seção sem laje coincide com a abertura de outra viga:', '',
    '| Viga | Viga da abertura | Trecho pareado (cm) | Largura da abertura no segmento (cm) |',
    '|---|---|---:|---:|',
]
seen = set()
for item in confirmed:
    key = (item['beam'], item['opening'], item['cut'], item['pair_length'])
    if key in seen:
        continue
    seen.add(key)
    lines.append(f"| {item['beam']} | {item['opening']} | {item['pair_length']} | {round(item['opening_interval'][1]-item['opening_interval'][0], 2)} |")
lines += ['', 'Não se deve suprimir todo trecho curto nem toda ausência de laje: há casos legítimos.',
          'A correção precisa considerar o intervalo da abertura e sua geometria; separar cortes',
          'nominais e regiões de encontro/abertura, sem desenhar a abertura como concreto integral.', '',
          '## Medidas contraditórias multiplicam seções', '',
          '- V301: 8 N3 / 2 N4. Duas alturas (55/120) vezes quatro combinações de lajes',
          '  (12/12, 12/10, 13/12, 13/13; desnível B de 7). N4 usa 13/10 nos dois cortes.',
          '- V302: 8 N3 / 1 N4. Identificados e calculados divergem no desnível (0/3 cm),',
          '  nas lajes e na altura (55/58 cm). Um corte vem da abertura da V310.',
          '- V312: 4 N3 / 1 N4. Entre as variantes há seção sem lajes sobre abertura VF301.',
          '- V330: 6 N3 / 2 N4. Duas alturas (71/120), fragmentos de encontro com vigas,',
          '  ausência de laje em faixas e corte identificado com desnível 72,1/69,1 cm.',
          '- VF301: 5 N3 / 1 N4. Identificados usam altura 48 e desnível 7; calculados usam',
          '  altura 55 e desnível 0. Ainda precisa verificar a convenção de altura do símbolo.', '',
          f"Dos 90 contratos, {sum(any(not c['slabs'][s] for s in ('A','B')) for c in contracts)} têm ausência de laje em pelo menos um lado;",
          f"{sum(all(not c['slabs'][s] for s in ('A','B')) for c in contracts)} não têm laje em nenhum lado. Ausência por interseção vazia é atualmente tratada",
          'como ausência física confirmada. Nem todas essas ausências foram validadas visualmente.', '',
          '## Limites e próximo trabalho técnico', '',
          'Não alterei o motor ou os dados durante esta investigação. Não reduzi contagens para',
          'forçar paridade N4. Necessário: incorporar aberturas no recorte dos pares; distinguir',
          'ausência comprovada de contato não resolvido; reconciliar símbolo/SA/anotação',
          'de lajes e altura em cada localização antes de unificar seções.',
          'N4 é referência humana, mas quantidade menor não prova completude de todas as variantes.', '',
          'Evidências: `inventory.json`, `causes_live.json`, `opening_overlap_causes.json`.',
          'Auditoria de aberturas realizada por leitura do SA atual na VPS; N1 e N2 preservados.']
(folder/'EXCESSO-CAUSAS.md').write_text('\n'.join(lines)+'\n', encoding='utf8')
print('Confirmed opening intervals:', len(confirmed))
print(folder/'EXCESSO-CAUSAS.md')
