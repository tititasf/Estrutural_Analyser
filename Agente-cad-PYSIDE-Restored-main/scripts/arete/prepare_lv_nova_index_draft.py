"""Separate LV index proposal; never register or replace uploaded documents."""
import json
from hashlib import sha256
from pathlib import Path
import ezdxf
from ezdxf import bbox
from src.core.n5_pillar_frames import (
    SheetBuilder, INDEX_ORIGINS, W, H, UX, UY, UW, UH, flatten_editable,
)


def main():
    reports = Path(__file__).parent / 'relatorios'
    templates = reports / '20261002_nova_design'
    evidence = reports / '20261004_nova_lv_design_experimentos/integration_v1'
    out = reports / '20261006_lv_nova_integracao/index_draft'
    out.mkdir(parents=True, exist_ok=True)
    index = ezdxf.readfile(templates / 'INDICE_NOVA_original.dxf')
    frame = ezdxf.readfile(templates / 'moldura_NOVA_aprovada.dxf')
    ms = index.modelspace()
    # Keep the original cover and index layout. The four PL detail pages are
    # replaced in a NEW proposal document, never in the owner's uploaded DXF.
    for entity in list(ms):
        b = bbox.extents([entity], fast=True)
        if b.has_data and any(x-.01 <= b.center.x <= x+W+.01 and
                              y-.01 <= b.center.y <= y+H+.01
                              for x, y in INDEX_ORIGINS[2:]):
            ms.delete_entity(entity)
    builder = SheetBuilder(index, frame, obra='Obra_TREINO_1', pavimento='13_PAV',
                           classe_title='LATERAIS DE VIGAS')
    titles = ['CAPA', 'ÍNDICE', 'LEGENDA DAS LATERAIS', 'AB GRADEADO',
              'AB SARRAFEADO', 'VISÃO CORTE — DUAS MONTAGENS']
    for i in range(2, 6):
        x, y = INDEX_ORIGINS[i]
        builder.place(index, frame, builder.frame_entities,
                      x-2017.803539105, y-1429.188948938)
        label = builder.page_label.copy(); label.dxf.text = f'{i+1:02d}'
        label.translate(x-2017.803539105, y-1429.188948938, 0)
        ms.add_entity(label)
        ms.add_text(titles[i], dxfattribs={'height': 20, 'color': 7,
                    'insert': (x+UX+20, y+UY+UH-40)})
    notes = [
        'GRADEADAS: meio pontalete 3,5 cm verde; extremidades 7 cm laranja.',
        'SARRAFEADAS: verticais 7 cm nas pontas; emendas seguem continuidade.',
        'Topo 2,2 cm somente nas gradeadas, entre verticais das extremidades.',
        'Aberturas: geometria e vazios unidos conforme os contratos SA.',
        'Pontaletes gradeados: comprimento útil / 30, arredondado ao inteiro mais próximo.',
        'Corte gradeado: ferragens centrais e do fundo conforme perfil aprovado.',
        'Corte sarrafeado: garfos externos; sem parafusos nem peças extras.',
        'Para e Passa: mesmo padrão de desenho; contratos independentes.',
        'Dimensões dos exemplos são ilustrativas; produção usa medidas do SA.',
    ]
    x, y = INDEX_ORIGINS[2]
    for n, text in enumerate(notes):
        ms.add_text(text, dxfattribs={'height': 13, 'color': 7,
                    'insert': (x+UX+20, y+UY+UH-90-n*45)})
    for page, assembly in ((3, 'gradeadas'), (4, 'sarrafeadas')):
        folder = evidence / f'V301_A_{assembly}.units'
        manifest = json.loads((folder/'manifest.json').read_text(encoding='utf8'))
        x, y = INDEX_ORIGINS[page]
        top = y+UY+UH-90
        for unit in manifest['units'][:2]:
            doc = ezdxf.readfile(folder/unit['file'])
            entities = list(doc.modelspace()); b = bbox.extents(entities)
            if b.size.x > UW-40 or b.size.y > 280:
                raise ValueError('Exemplo AB excede a proposta de índice')
            builder.place(index, doc, entities, x+UX+20-b.extmin.x, top-b.extmax.y)
            top -= b.size.y+70
    x, y = INDEX_ORIGINS[5]
    for col, assembly in enumerate(('gradeadas', 'sarrafeadas')):
        folder = evidence/f'V301_CORTE_{assembly}.units'
        manifest = json.loads((folder/'manifest.json').read_text(encoding='utf8'))
        doc = ezdxf.readfile(folder/manifest['units'][0]['file'])
        entities = list(doc.modelspace()); b = bbox.extents(entities)
        ms.add_text(assembly.upper(), dxfattribs={'height': 16, 'color': 7,
            'insert': (x+UX+30+col*650, y+UY+UH-90)})
        builder.place(index, doc, entities, x+UX+30+col*650-b.extmin.x,
                      y+UY+UH-140-b.extmax.y)
    target = out/'INDICE_NOVA_LV_proposta.dxf'
    flatten_editable(index)
    index.saveas(target)
    # SheetBuilder preserves the owner's calibrated origins and pagination.
    dst = ezdxf.new('R2018')
    exporter = SheetBuilder(dst, frame, obra='Obra_TREINO_1', pavimento='13_PAV',
                            classe_title='LATERAIS DE VIGAS')
    exporter.blocks = builder.blocks + 10
    result = exporter.finish(index, out/'pages', index_titles=titles,
                             index_sha256=sha256(target.read_bytes()).hexdigest())
    result['scope'] = 'unregistered LV index proposal; not a production N5'
    for page, title in zip(result['pages'], titles): page['title'] = title
    (out/'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    from scripts.arete.validate_lv_nova_sa_design import render
    for n in (2, 3, 4, 5):
        render(ezdxf.readfile(out/'pages'/f'page_{n:03d}.dxf'), out/f'page_{n+1:02d}.png')
    print(target)


if __name__ == '__main__': main()
