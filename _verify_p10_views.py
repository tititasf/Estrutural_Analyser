from pathlib import Path

from portal.app.ficha_reader import resolver_visualizacoes_n1_pilar

root = Path('/opt/cad-analyzer')
obra = root / 'DADOS-OBRAS/thierry/TMC-EST-PE-7000-14P-R03'
central = root / 'scripts/arete/html_fichas/TMC-EST-PE-7000-14P-R03'
views = resolver_visualizacoes_n1_pilar(
    obra, '14_PAV', 'pilares', {'beam_name': 'P10'},
    html_fichas_root=central,
)
for key, value in views.items():
    print(key, bool(value), len(value or ''), '<svg' in (value or ''))
