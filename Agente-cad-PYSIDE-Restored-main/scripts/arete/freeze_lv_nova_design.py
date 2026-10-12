"""Freeze approved evidence and drawing definitions, without production data writes."""
from pathlib import Path
from hashlib import sha256
import json
import ezdxf
from ezdxf.addons import Importer

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'scripts/arete/relatorios/20261004_nova_lv_design_experimentos'
ASSETS = ROOT / 'scripts/arete/assets/lv_nova'
REFS = {
    'gradeadas': ('50179d0b49bf40deb82a6e521a4869c1', '043777de3ae54b34b2629c52734a4237', '2b7b2809625a4f11b155a2adf987362c'),
    'sarrafeadas': ('fb30eb299e9b4ee1b9562d4add3bb3d2', 'e26cf34591374409abe3ff8d4f40b11c', '64bd6bc1764d44cea01987295f0afdb3'),
}


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    entries = []
    for variant, (crop, ab, cut) in REFS.items():
        for kind, source_id in [('ab', ab), ('cut', cut)]:
            source = EVIDENCE / (crop + '_crops') / (source_id + '.dxf')
            ref = ezdxf.readfile(source)
            doc = ezdxf.new('R2013')
            imp = Importer(ref, doc)
            for table in ('layers', 'styles', 'dimstyles', 'linetypes'):
                imp.import_table(table)
            if variant == 'gradeadas' and kind == 'cut':
                imp.import_block('PRESILHA METÁLICA 1')
            imp.finalize()
            # Pattern samples carry definitions only, never beam dimensions.
            names = set()
            for entity in ref.modelspace().query('HATCH'):
                name = 'SOLID' if entity.dxf.solid_fill else entity.dxf.pattern_name
                if name in names:
                    continue
                sample = entity.copy()
                sample.paths.clear()
                sample.paths.add_polyline_path([(0, 0), (1, 0), (1, 1), (0, 1)], is_closed=True)
                doc.modelspace().add_entity(sample)
                names.add(name)
            target = ASSETS / f'{variant}_{kind}_style.dxf'
            doc.saveas(target)
            assert not doc.audit().errors
        version = 'dual_v11' if variant == 'gradeadas' else 'dual_v13'
        for folder, prefix, count in [('dual_v20', 'AB', 6), (version, 'VC', 5)]:
            for index in range(1, count + 1):
                path = EVIDENCE / folder / variant / f'{prefix}{index:02}.dxf'
                doc = ezdxf.readfile(path)
                assert not doc.audit().errors, path
                entries.append({'path': path.relative_to(ROOT).as_posix(),
                                'sha256': sha256(path.read_bytes()).hexdigest(),
                                'assembly': variant, 'case': path.stem,
                                'entities': len(doc.modelspace()), 'approval': '2026-10-05'})
    manifest = {'schema': 'cad.lv.nova.approved/v1', 'status': 'design_approved',
                'integration_verified': False, 'entries': entries}
    target = EVIDENCE / 'approved_design_manifest.json'
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{len(entries)} approved DXFs frozen; four drawing-definition assets exported.')


if __name__ == '__main__':
    main()
