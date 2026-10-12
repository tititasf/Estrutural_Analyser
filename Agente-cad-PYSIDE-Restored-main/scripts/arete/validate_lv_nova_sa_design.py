"""Read-only real SA smoke with DXF audit and full PNG evidence."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import ezdxf
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from src.core.vigas_drawing_config import apply_lv_config
from src.core.lv_nova_sa_adapter import generate_ab
from scripts.arete.lv_n3_cut_draw import generate_local_sections
from src.core.n5_lateral_frames import assemble_lateral_frames


def render(doc, path):
    fig=plt.figure(figsize=(24,8),facecolor='black')
    ax=fig.add_axes((0,0,1,1),facecolor='black')
    Frontend(RenderContext(doc),MatplotlibBackend(ax)).draw_layout(doc.modelspace(),finalize=True)
    ax.axis('off')
    fig.savefig(path,dpi=160,facecolor='black')
    plt.close(fig)


def main():
    root=Path(__file__).parent/'relatorios'/'20261004_nova_lv_design_experimentos'
    sources=json.loads((root/'prepared_V301.json').read_text(encoding='utf8'))
    out=root/'integration_v1'
    out.mkdir(exist_ok=True)
    rows=[]
    for assembly in ('gradeadas','sarrafeadas'):
        manifests=[]
        variant_sources={}
        for side in ('A','B'):
            contract=apply_lv_config(sources[side],dict(comportamento_laterais_vigas=assembly))
            variant_sources[side]=contract
            path=out/f'V301_{side}_{assembly}.dxf'
            runs=generate_ab(contract,path)
            manifests.append(path.with_suffix('.units')/'manifest.json')
            doc=ezdxf.readfile(path)
            audit=doc.audit()
            render(doc,path.with_suffix('.png'))
            rows.append(dict(side=side,assembly=assembly,path=str(path),
                runs=len(runs),segments=sum(len(r['segments']) for r in runs),
                length_cm=sum(s['length'] for r in runs for s in r['segments']),
                source_length_cm=sum(p['width'] for p in contract['panels']),
                entities=len(doc.modelspace()),audit_errors=len(audit.errors)))
        cuts=out/f'V301_CORTE_{assembly}.dxf'
        generate_local_sections(variant_sources,cuts,'NOVA','PARA')
        manifests.append(cuts.with_suffix('.units')/'manifest.json')
        dst=ezdxf.new('R2018')
        # Explicit local packing experiment. This fixture index is PL; it is
        # not the absent uploaded LV index and does not certify production N5.
        templates=root.parent/'20261002_nova_design'
        pages=out/f'N5_{assembly}_pages'
        result=assemble_lateral_frames(dst,manifests,assembly=assembly,behavior='PARA',
            frame_path=templates/'moldura_NOVA_aprovada.dxf',
            index_path=templates/'INDICE_NOVA_original.dxf',
            obra='Obra_TREINO_1',pavimento='13_PAV',pages_dir=pages)
        result['validation_scope']='local geometry packing; PL index fixture, not published LV index'
        result['audit_errors']=len(dst.audit().errors)
        n5=out/f'N5_V301_{assembly}.dxf'
        dst.saveas(n5)
        n5.with_suffix('.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf8')
        render(ezdxf.readfile(pages/'page_006.dxf'),n5.with_suffix('.png'))
    (out/'ledger.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
    print(json.dumps(rows,indent=2))


if __name__=='__main__':main()
