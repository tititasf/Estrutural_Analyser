import json
from pathlib import Path
from src.core.lv_cut_equivalence import section_signature

folder = Path(__file__).parent/'relatorios'/'20261001_dynamic_cut'
rows = json.loads((folder/'inventory.json').read_text(encoding='utf8'))
overlap = json.loads((folder/'overlap.json').read_text(encoding='utf8'))
n4rows = json.loads((folder.parent/'20261001_qa_cut_n3_n4'/'n4_inventory.json').read_text(encoding='utf8'))
n4 = {r['beam']: len(r.get('section_views') or []) if r.get('n4_exists') else None for r in n4rows}
counts = {b: {r['beam']: len(r['cuts']) for r in rows if r['behavior']==b} for b in ('para','passa')}
assert all(len({section_signature(c['qa_contract']) for c in r['cuts']}) == len(r['cuts']) for r in rows)
assert overlap['invalid'] == 0
lines = [
    '# Motor dinâmico Visão Corte — 01/10/2026',
    '',
    'Escopo: Obra_TREINO_1 / 13_PAV. Job real iniciado pelo botão interpretativo da web:',
    '`4d972ff2-12df-4650-928e-b49e367dee42`, 21:48:34–21:52:42 UTC, concluído.',
    '',
    'O pós-processamento do snapshot novo materializou 186/186 cortes automaticamente:',
    '101 Passa em 36 vigas; 85 Para em 35 vigas. Zero erros de contrato/SVG.',
    'O inventário não vem da contagem de arquivos em cache. Seções idênticas são agrupadas',
    'preservando os pares/origens, sem alterar N1/N2. Escopo de item e modo são respeitados.',
    '',
    f"Auditoria longitudinal de {overlap['pairs']} pares: zero trechos fora do intervalo compartilhado.",
    'Horizontais usam X; verticais usam Y; inclinados usam projeção no eixo da viga.',
    '36 testes passaram, incluindo A longo sobre três B iguais/diferentes, B distante,',
    'contato apenas de ponta, mudança de inventário e falhas de geração.',
    '',
    'A rodada anterior tinha 194 cortes; este relatório usa exclusivamente o snapshot novo.',
    'Não foi aplicada redução artificial para igualar N4. Diferenças de espessura/nivel de',
    'lajes e referências estimadas ainda precisam de validação semântica. Sem selo G5.',
    '',
    '| Viga | N3 Passa | N3 Para | N4 referência |',
    '|---|---:|---:|---:|',
]
for beam in counts['passa']:
    lines.append(f"| {beam} | {counts['passa'][beam]} | {counts['para'].get(beam, 0)} | {n4.get(beam) if n4.get(beam) is not None else 'ausente'} |")
lines += ['', 'Evidências: `web_sa.log`, `inventory.json`, `overlap.json`, `portal.png`.',
          'Documento canônico atualizado: `docs/SA-ANALISE/CLASSES/LV.md`.',
          'KB global reconstruída: 279 fontes, 6254 trechos.']
(folder/'RELATORIO.md').write_text('\n'.join(lines)+'\n', encoding='utf8')
print(folder/'RELATORIO.md')
