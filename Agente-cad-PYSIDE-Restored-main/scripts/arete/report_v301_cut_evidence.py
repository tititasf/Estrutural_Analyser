"""Explain physical section counts using the audited pair provenance."""
import json
from pathlib import Path

out=Path('scripts/arete/relatorios/20261002_cut_region_fix')
qa=json.loads((out/'live_qa.json').read_text(encoding='utf8'))
r=next(r for r in qa['rows'] if r['beam']=='V301' and r['behavior']=='passa')
lines=['# V301 — por que oito seções no motor e duas no N4?', '',
'Oito é o resultado do snapshot SA atual: duas alturas (55 e 120 cm) × quatro combinações de laje. Os pares são opostos no mesmo intervalo X; nenhum cruzamento entre trechos distantes foi encontrado. A tabela abaixo mantém os segmentos e faixas que sustentam cada seção.', '',
'| Altura viga | A: espessura / desnível | B: espessura / desnível | Pares A/B |', '|---:|---|---|---|']
for cut in r['cuts']:
    c=cut['qa_contract']
    profiles=['; '.join(f"{s['height_cm']:g} / {s['drop_cm']:g} cm" for s in c['slabs'][side]) or 'sem laje' for side in ('A','B')]
    pairs='; '.join(f"A{p['a_index']}/B{p['b_index']}: X {p['start'][0]:g}–{p['end'][0]:g}" for p in cut['pairs'])
    lines.append(f"| {c['height_cm']:g} | {profiles[0]} | {profiles[1]} | {pairs} |")
lines += ['', '## Evidência original conferida em PNG', '',
'- V301-original-1.png: L309 h=13, L301 h=12, L310 h=12, L302 h=12. A viga alterna 19/55 e 19/120 nos intervalos indicados por cotas 305,5 / 100 / 100 / 318 cm.',
'- V301-original-2.png: L311 h=12, L303 h=12, L312 h=13 e L304 h=12; dois perfis realmente diferentes.',
'- V301-original-3.png: L313 h=13, L305 h=12; L314 h=12, L306 h=10. A L306 tem cota original 852,12; a referência superior vizinha 852,19 diferencia o topo em 7 cm.',
'- V301-original-4.png: L315 h=12, L307 h=12; L316 h=13, L308 h=13. L308 852,12 e L316 852,19. A região interna h=10 / 852,16 da L316 fica mais abaixo da faixa de contato com V301; não é motivo para criar um perfil adicional aqui.',
'', 'Handles originais dos textos em V301-original-texts.json; nenhum overlay SA foi usado para provar essas espessuras. Os PNGs foram renderizados a partir do recorte DXF original e lidos pelo agente.',
'', '## Comparação com N4', '',
'O N4 disponível representa somente duas alturas, ambas com laje A=13 e B=10 cm. Portanto, não enumera todas as combinações de espessura presentes no desenho original desta revisão. Nesta viga, reduzir automaticamente oito para dois descartaria diferenças físicas comprovadas. Isso não invalida todo o N4 nem certifica todas as cotas inferidas do SA: fontes geométricas e níveis pendentes continuam sinalizados nas fichas.',
'', 'Conclusão localizada: o excesso da V301 não vem de pares aleatórios nem de duplicações idênticas; vem de perfis distintos de laje. A qualidade de cada atributo continua sujeita ao QA por seção.']
(out/'V301-EVIDENCIA.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
print(out/'V301-EVIDENCIA.md')
