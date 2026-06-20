import glob
from src.core.dxf_loader import DXFLoader
from pathlib import Path

target = Path(r'D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes_reversos\ALIMONTI - PARAISO - 13° PAV.- FV - R00')
for v in ['V302', 'V303', 'V304', 'V301', 'V330']:
    files = list(target.glob(f'*_{v}_*dxf')) + list(target.glob(f'*{v}_*dxf'))
    if not files:
        print(f'{v}: NO FILES FOUND')
        continue
    f = sorted([str(x) for x in files])[-1]
    data = DXFLoader.load_dxf(f)
    texts = [t['text'] for t in data['texts'] if v in t['text']]
    polys = data.get('polylines', [])
    print(f'{v}: Textos={texts}, Polys={len(polys)}')
