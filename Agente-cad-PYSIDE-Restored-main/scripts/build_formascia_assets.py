"""Extract approved reusable CAD details; original DXFs are read-only."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import ezdxf
from ezdxf import bbox
from ezdxf.addons import Importer

def main():
    refroot=Path('D:/Agente-cad-PYSIDE/Exemplos Modos/FORMASCIA')
    ref=ezdxf.readfile(refroot/'PILARES ABCDEFGH FORSMACIA.dxf')
    approved=ezdxf.readfile(ROOT/'scripts/arete/relatorios/20261004_formascia_abcd_experimento/v03_cotas_niveis/proposta_v03_P1_ABCD.dxf')
    dst=ezdxf.new('R2018');m=dst.modelspace()
    imp=Importer(approved,dst)
    imp.import_table('styles');imp.import_block('_Oblique');imp.finalize()
    ds=approved.dimstyles.get('FORMASCIA-PAINEL-ORIGINAL-v03')
    dst.dimstyles.new('FORMASCIA-PAINEL',dxfattribs={k:v for k,v in ds.dxfattribs().items() if k not in ('name','handle','owner') and not k.endswith('_handle')})
    for name in ('EEEEEEEE','SAR15'):
        original=ref.mline_styles.get(name);st=dst.mline_styles.new(name)
        for key in ('flags','fill_color','start_angle','end_angle'): setattr(st.dxf,key,original.dxf.get(key))
        st.elements.elements.clear()
        for el in original.elements:st.elements.append(el.offset,el.color,el.linetype)
    for name,color in [('FORMASCIA-FOLGA',8),('S1',191),('FORMASCIA-REFORCOS',8)]:dst.layers.new(name,dxfattribs={'color':color})
    dim=ref.entitydb['18C0'];x=dim.dxf.defpoint.x;y=min(dim.dxf.defpoint2.y,dim.dxf.defpoint3.y)
    for handle in ('1911','1912'):
        e=ref.entitydb[handle].copy();m.add_entity(e);e.translate(-x,-y,0);e.dxf.layer='FORMASCIA-FOLGA';e.dxf.color=240 if e.dxftype()=='MTEXT' else 8
    crop=ezdxf.readfile(ROOT/'scripts/arete/relatorios/20261004_formascia_abcd_experimento/referencia_original_P68_ABCD.dxf')
    symbols=[e for e in crop.modelspace() if e.dxf.layer=='S1' and e.dxftype() in ('LINE','HATCH','LWPOLYLINE') and bbox.extents([e]).extmax.y<2700]
    tip=min((e.dxf.start for e in symbols if e.dxftype()=='LINE'),key=lambda p:p.y)
    for original in symbols:
        e=original.copy();m.add_entity(e);e.translate(-tip.x,-tip.y,0);e.dxf.color=191
    grades=ezdxf.readfile(ROOT/'scripts/arete/relatorios/20261004_formascia_grades_experimento/referencia_original_P68_GRADES.dxf')
    originals=[grades.entitydb[h] for h in ('3AF6','3AF7','3AF8','3F5D')]
    b=bbox.extents(originals)
    for original in originals:
        e=original.copy();m.add_entity(e);e.translate(-b.extmin.x,-b.extmin.y,0);e.dxf.layer='FORMASCIA-REFORCOS';e.dxf.color=8
    m.add_lwpolyline([(0,0),(0,15),(15,0)],close=True,dxfattribs={'layer':'FORMASCIA-REFORCOS','color':7,'lineweight':35})
    out=ROOT/'config/formascia/details.dxf';out.parent.mkdir(parents=True,exist_ok=True)
    audit=dst.audit();assert not audit.errors and not audit.fixes,(audit.errors,audit.fixes)
    dst.saveas(out);print(out)

if __name__=='__main__':main()
