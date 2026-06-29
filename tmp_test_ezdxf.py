import ezdxf
from ezdxf.addons import Importer
from ezdxf import bbox

dst = ezdxf.new('R2018')

def _import_doc_entities(src_doc, dst_doc):
    importer = Importer(src_doc, dst_doc)
    copies = []
    for entity in src_doc.modelspace():
        copies.append(entity.copy())
    if copies:
        importer.import_entities(copies, dst_doc.modelspace())
    importer.finalize()

s1 = ezdxf.readfile(r'D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-6_Execucao_CAD\LJ_preview_L301.dxf')
_import_doc_entities(s1, dst)

s2 = ezdxf.readfile(r'D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-6_Execucao_CAD\LJ_preview_L302.dxf')
_import_doc_entities(s2, dst)

minxs = [bbox.extents([e]).extmin.x for e in dst.modelspace() if bbox.extents([e]).has_data]
print('Entities:', len(dst.modelspace()))
print('Count < 2000:', sum(1 for x in minxs if x < 2000))
