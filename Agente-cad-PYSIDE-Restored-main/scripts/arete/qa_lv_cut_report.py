"""Relatório de quantidade e evidência por seção, sem ajustar motores."""
import json,csv,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.core.lv_cut_equivalence import section_signature
root=Path(__file__).parent/'relatorios/20261001_qa_cut_n3_n4'
live=json.loads((root/'live_inventory.json').read_text(encoding='utf8'))
n4=json.loads((root/'n4_inventory.json').read_text(encoding='utf8'))
rows=[]; detail=[]
for ref in n4:
    row={'viga':ref['beam'],'N4':ref.get('n4_drawn_count','ausente')}
    for behavior in ('para','passa'):
        item=next((x for x in live if x['beam']==ref['beam'] and x['behavior']==behavior),None)
        row['N3_'+behavior]=len(item['cuts']) if item else 'sem segmentos'
        if not item: continue
        contracts=[c['qa_contract'] for c in item['cuts'] if 'qa_contract' in c]
        signatures=[section_signature(c) for c in contracts]
        assert len(signatures)==len(set(signatures)),(ref['beam'],behavior,'duplicatas')
        row['pares_'+behavior]=sum(len(c.get('pairs',[])) for c in item['cuts'])
        row['nivel_estimado_'+behavior]=sum('estimado' in c.get('attention','') for c in item['cuts'])
        for idx,cut in enumerate(item['cuts'],1):
            c=cut.get('qa_contract',{})
            detail.append({'viga':ref['beam'],'comportamento':behavior,'corte':idx,'altura':c.get('height_cm'),'largura':c.get('width_cm'),
              'A':str([(s['height_cm'],s['drop_cm']) for s in c.get('slabs',{}).get('A',[])]),
              'B':str([(s['height_cm'],s['drop_cm']) for s in c.get('slabs',{}).get('B',[])]),
              'pares':len(cut.get('pairs',[])),'origens':','.join(cut.get('origins',[])), 'avisos':cut.get('attention','')})
    rows.append(row)
for name,data in [('quantidades.csv',rows),('secoes.csv',detail)]:
    keys=list(dict.fromkeys(k for row in data for k in row))
    with (root/name).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=keys,delimiter=';'); writer.writeheader();writer.writerows(data)
text=['# QA Visão Corte LV — 13_PAV — 01/10/2026', '',
 'Motor SA acionado pela web: job b04117f8-3493-4ea9-add8-4e6622a4fea3, concluído 21:34:11 UTC. Motor de desenho acionado: job 353c8cc9-7d3d-4000-bda2-ff8e78157570.', '',
 'Inventário após SA: 105 cortes Passa em 36 vigas e 89 Para em 35 vigas. N4 local: 34 cortes em 31 vigas; 5 vigas sem CORTE N4 disponível. Quantidades N4 conferidas pela extração live N2 e pela anatomia a/b/c dos DXFs publicados: concordam nas 31 vigas.', '',
 'No conjunto comparável Passa: 94 cortes N3 contra 34 N4, diferença +60. Igualdade de assinatura física por viga foi verificada: zero duplicatas exatas. Isso não aprova a interpretação dos perfis. Mesmo número também não aprova paridade.', '',
 '| Viga | N4 | N3 Passa | N3 Para | Trechos A/B Passa | Cortes com nível estimado Passa |',
 '|---|---:|---:|---:|---:|---:|']
for r in rows: text.append(f"| {r['viga']} | {r['N4']} | {r['N3_passa']} | {r['N3_para']} | {r.get('pares_passa',0)} | {r.get('nivel_estimado_passa',0)} |")
text += ['', '## Diagnóstico', '',
 'V301: 16 trechos A/B agrupados em 8 seções, não 16 cortes. São 4 perfis distintos de laje multiplicados pelas alturas estruturais 55 e 120 cm. A/B (espessura, rebaixo): (12,0)/(12,7), (12,0)/(10,7), (13,0)/(12,7), (13,0)/(13,7). N4 possui apenas dois cortes (55 e 120), com lajes geométricas 13/10 cm. O SA usa espessuras anotadas (incluindo 12 cm onde símbolo mede 10). Há uma divergência de critério/dados de laje comprovada; não é lícito eliminar essas variantes somente para alcançar 2.', '',
 'V302: 8 N3 contra 1 N4. V330: 6 N3 contra 2 N4, cinco entradas com nível estimado. São prioridades de inspeção. V309A: 4 N3 (Passa), três Para; não há CORTE N4 local nem ficha live N2 válida para comparação. Não afirmar erro no N4 da V309A sem referência.', '',
 'O algoritmo exige paralelismo, distância compatível com largura e sobreposição longitudinal; não forma produto cartesiano indiscriminado. Nenhum aviso de distância incompatível foi encontrado neste inventário. Faltam confrontos visuais por trecho para certificar a atribuição de todas as lajes, níveis e altura. Não há veredito G5 de paridade.', '',
 'Conexão web: SA atualiza o snapshot. O inventário Visão Corte é calculado dinamicamente por lv_ficha. Os novos desenhos parametrizados usam lv_n3_cuts.resolve, chamado pelo viewer e pelo job n3_lv_view_item de uma viga. O motor granular SA/desenho de classe não chama esse resolvedor para todas as vigas. Portanto o botão interpretativo sozinho não materializa todo o novo inventário. Nesta QA, a materialização completa foi executada separadamente como cadapp pelo mesmo resolvedor publicado, após acionar os motores web. Não foi alterado motor para ocultar diferenças.', '',
 'Fontes: live_inventory.json (snapshot VPS novo); n4_inventory.json (extração live N2 e DXF); quantidades.csv; secoes.csv; generated.json (materialização por corte). Original N2/N4/Fase-4 preservado.']
(root/'RELATORIO.md').write_text('\n'.join(text)+'\n',encoding='utf8')
print('Relatório e CSVs gravados; zero duplicatas exatas.',flush=True)
