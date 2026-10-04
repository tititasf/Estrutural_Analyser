import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.core.lv_n3_cut_contract import build_cut_contract, CutContractError
from scripts.arete.lv_n3_cut_draw import generate
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path('scripts/arete/relatorios/20261001_lv_n3_cortes'); root.mkdir(exist_ok=True)
data=json.loads(Path('scripts/arete/relatorios/20260930_lv_visao_corte/validated_cut_inventory.json').read_text(encoding='utf8'))
rows=[]
for beam in data['rows']:
    for idx,cut in enumerate(beam['cuts']):
        row={'beam':beam['beam'],'behavior':beam['behavior'],'cut_index':idx,'id':cut['id']}
        try:
            contract=build_cut_contract(cut)
            path=root/beam['behavior']/beam['beam']/f'VC{idx+1}.dxf'
            doc=generate(contract,path)
            audit=doc.audit()
            if audit.has_errors: raise ValueError(str(audit.errors))
            row.update(status='generated',fingerprint=contract['fingerprint'],warnings=contract['warnings'],
                       entities=len(doc.modelspace()),width=contract['width_cm'],height=contract['height_cm'],slabs=contract['slabs'])
            if beam['beam'] in ('V306','V301','V305') and idx<3:
                fig=plt.figure(figsize=(12,8)); ax=fig.add_axes([0,0,1,1]); ax.set_aspect('equal')
                Frontend(RenderContext(doc),MatplotlibBackend(ax)).draw_layout(doc.modelspace(),finalize=True)
                fig.savefig(path.with_suffix('.png'),dpi=140); plt.close(fig)
        except (CutContractError,ValueError) as exc:
            row.update(status='blocked',reason=str(exc))
        rows.append(row)
(root/'validation.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
from collections import Counter
print(Counter(r['status'] for r in rows))
print(Counter(r.get('reason') for r in rows if r['status']=='blocked'))
