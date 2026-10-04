"""Compare actual P1 generation in isolated outputs/settings, never Fase-4."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts import drawing_mode_config as config
from gerar_pl_dxf_stog import generate_pilar_zone, setup_doc
from scripts.visual_modes import apply_visual_mode


def main():
    source = Path(sys.argv[1])
    output = Path(sys.argv[2])
    output.mkdir(parents=True, exist_ok=True)
    config_path = output / 'test-settings.json'
    if config_path.exists():
        raise RuntimeError('Use a fresh output directory')
    os.environ['ARETE_DRAWING_MODE_CONFIG'] = str(config_path)
    payload = json.loads(source.read_text(encoding='utf-8'))
    results = {}
    for mode in ('NOVA', 'INI'):
        def generate(label):
            doc = setup_doc()
            generate_pilar_zone(doc.modelspace(), payload, 'abcd', visual_mode=mode)
            apply_visual_mode(doc, mode, 'PL')
            audit = doc.audit()
            assert not audit.errors, audit.errors
            doc.saveas(output / f'P1_{mode}_{label}.dxf')
            texts = [e for e in doc.modelspace() if e.dxftype() in {'TEXT', 'MTEXT'}]
            return doc, {'entities': len(doc.modelspace()), 'text_count': len(texts), 'text_heights': [e.dxf.height for e in texts if e.dxftype() == 'TEXT'], 'audit_errors': len(audit.errors)}
        before, baseline = generate('before')
        value = config.effective(mode, 'PL')
        value['appearance']['text_scale'] = 1.5
        value['layers']['NOMENCLATURA']['color'] = 1
        config.save(mode, 'PL', value, config.read_store()['revision'], 'validation')
        after, customized = generate('after')
        assert baseline['text_heights'] and customized['text_heights'] == [n * 1.5 for n in baseline['text_heights']]
        assert after.layers.get('NOMENCLATURA').dxf.color == 1
        assert baseline['entities'] == customized['entities']
        results[mode] = {'before': baseline, 'after': customized, 'layer_color_after': 1}
    (output / 'evidence.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps({mode: {'entities': row['before']['entities'], 'text_scale_verified': 1.5, 'audit_errors': 0} for mode, row in results.items()}))


if __name__ == '__main__':
    main()
