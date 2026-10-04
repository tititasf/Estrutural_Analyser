"""Report measured candidates separately from published motor results."""
import json
from pathlib import Path
from src.core.lv_n3_cut_contract import build_cut_contract
from src.core.lv_cut_equivalence import section_signature

out=Path('scripts/arete/relatorios/20261002_cut_region_fix')
staged=json.loads((out/'staged.json').read_text(encoding='utf8'))
qa=json.loads((out/'final_qa.json').read_text(encoding='utf8'))
n4=json.loads(Path('scripts/arete/relatorios/20261001_qa_cut_n3_n4/n4_inventory.json').read_text(encoding='utf8'))
old={(r['behavior'],r['beam']):r for r in staged['before']}
refs={r['beam']:len(r.get('section_views') or []) if r.get('n4_exists') else None for r in n4}
sig=lambda r:{repr(section_signature(build_cut_contract(c))) for c in r['cuts']}
lines=['# QA Visão Corte LV — 02/10/2026',
'', '## Estado da entrega', '',
'Correção publicada na VPS e rodada SA acionada pelo motor interpretativo web em 02/10/2026. Job 7ddb2b94-1d3f-4e4e-9f49-91c2042f316b concluído entre 15:25:22 e 15:29:00 UTC: 186/186 cortes materializados em 71 combinações viga/comportamento, modo NOVA. Auditoria final sobre a nova rodada sem erros. Não é aprovação G5 nem selagem da classe.',
'', '## Causas corrigidas', '',
'- Abertura de outra viga: excluir somente o intervalo físico da abertura do pareamento, mantendo o registro nas laterais. Sentido original de A/B e aberturas parcialmente fora do segmento são respeitados.',
'- Regiões de laje: espessura e nível locais de cada slab_step; falta de evidência regional não herda valor global. Tolerância de contato evita atribuir dois perfis ao mesmo limite por arredondamento CAD.',
'- Mantidos os cortes identificados SA/pré-processamento e o agrupamento por seção física. Ausência real de laje fora das aberturas continua válida.',
'', '## Verificação', '',
f"54 testes passaram. Auditoria independente: {qa['pairs']} trechos, {qa['opening_exclusions']} exclusões de abertura, {qa['cuts']} seções em 71 combinações viga/comportamento; {len(qa['errors'])} erros de contrato, duplicação, faixa longitudinal ou interseção com abertura.",
'', 'O total permanece 186: exclusões de perfis falsos são compensadas por diferenças regionais reais. Contagem isolada não prova correção. PNGs V310 e V312 foram lidos; N4 é comparador independente e não alimenta a geração.',
'', '## Inventário por viga', '',
'N4 é o inventário independente de 01/10/2026; indisponível significa sem DXF de referência. Para e Passa são inventários separados; não somar como cortes únicos da mesma viga.',
'', '| Viga | Passa antes | Passa publicado | Para antes | Para publicado | N4 |', '|---|---:|---:|---:|---:|---:|']
rows={(r['behavior'],r['beam']):r for r in qa['rows']}
for beam in sorted({r['beam'] for r in qa['rows']}):
    counts=[]
    for behavior in ('passa','para'):
        counts += [str(len(old.get((behavior,beam),{}).get('cuts',[]))),str(len(rows.get((behavior,beam),{}).get('cuts',[])))]
    lines.append('| '+ ' | '.join([beam,*counts,str(refs.get(beam)) if refs.get(beam) is not None else 'indisponível'])+' |')
lines += ['', '## Diferença de seções físicas (não apenas quantidade)', '', '| Comportamento | Viga | Seções removidas | Seções adicionadas |', '|---|---|---:|---:|']
for key,r in rows.items():
    before,after=sig(old[key]),sig(r)
    if before!=after: lines.append(f'| {key[0]} | {key[1]} | {len(before-after)} | {len(after-before)} |')
lines += ['', '## Próximo FAIL e limitações', '',
'V301 tem 8 seções Passa versus 2 no N4: o DXF original confirma duas alturas (55/120 cm) e quatro combinações de espessura A/B (13/12, 12/12, 12/10 e 13/13 cm). O N4 disponível representa A=13/B=10 nas duas alturas e não enumera as demais combinações desta revisão. Evidências e faixas em V301-EVIDENCIA.md. V310 N3 usa largura 14 cm enquanto N4 apresenta 19 cm; o desenho original identifica V310 como 14/50. V312 preserva três combinações de perfil; a referência N4 não prova que todas sejam equivalentes. A conferência de todos os atributos de todas as vigas continua pendente; não reduzir por quantidade desejada.',
'', 'Arquivos: final_qa.json contém a auditoria da rodada publicada; candidate_qa.json preserva a validação anterior; staged.json preserva o snapshot antes/depois. rodada-web.log comprova a materialização automática; portal-V301-final.png mostra o N3 disponível e os oito cortes agrupados. V310/V312-candidate.png e *-N4-reference.png são evidências visuais. Geradores STOG certificados, N2, DXF original e JSONs Fase-4 não foram alterados.']
(out/'RELATORIO.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
print(out/'RELATORIO.md')
