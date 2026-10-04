"""Exercise real generator CLIs with copied production inputs and isolated DB."""
import functools
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if len(sys.argv) > 1 and sys.argv[1] == '--child':
    from src.core import artifact_governance as governance
    governance.guarded_saveas = functools.partial(governance.guarded_saveas, db_path=os.environ['DRAWING_TEST_DB'])
    generator = sys.argv[2]
    sys.argv = [generator] + sys.argv[3:]
    runpy.run_path(str(ROOT / 'scripts' / generator), run_name='__main__')
else:
    import ezdxf
    from scripts import drawing_mode_config as config
    source = Path(sys.argv[1])
    output = Path(sys.argv[2])
    output.mkdir(parents=True, exist_ok=False)
    os.environ['ARETE_DRAWING_MODE_CONFIG'] = str(output / 'profiles.json')
    os.environ['DRAWING_TEST_DB'] = str(output / 'governance.sqlite')
    os.environ['CAD_MOTOR_HEADLESS'] = '0'
    inputs = output / 'inputs'
    inputs.mkdir()
    for old, new in [('V301_A_source_copy.json', 'V301_A.json'), ('V301_B_source_copy.json', 'V301_B.json'), ('L301_source_copy.json', 'L301.json'), ('FV301_source_copy.json', 'V301_fundo.json')]:
        shutil.copyfile(source / old, inputs / new)
    for behavior in ('PARA', 'PASSA'):
        (inputs / behavior).mkdir()
        for face in ('A', 'B'):
            shutil.copyfile(source / f'V301_{behavior}_{face}_copy.json', inputs / behavior / f'V301_{face}.json')
    evidence = {}
    for mode in config.MODES:
        for cls in ('LV_PARA', 'LV_PASSA', 'FV', 'LJ'):
            def generate(label):
                destination = output / (mode + '_' + cls + '_' + label)
                robot = cls.split('_')[0].lower()
                args = [sys.executable, str(Path(__file__).resolve()), '--child', 'gerar_' + robot + '_dxf_stog.py', '--obra', str(output / 'isolated_obra'), '--item', 'L301' if cls == 'LJ' else 'V301', '--visual-mode', mode]
                if cls == 'LJ':
                    args += ['--json-dir', str(inputs), '--out-dir', str(destination)]
                else:
                    args += ['--input-dir', str(inputs / cls.split('_')[1] if cls.startswith('LV_') else inputs), '--output-dir', str(destination)]
                if cls.startswith('LV_'):
                    args += ['--behavior', cls.split('_')[1].title(), '--view', 'A']
                result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
                (output / (mode + '_' + cls + '_' + label + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
                assert result.returncode == 0, result.stderr
                paths = list(destination.glob('*.dxf'))
                assert len(paths) == 1, result.stdout
                doc = ezdxf.readfile(paths[0])
                assert not doc.audit().errors
                heights = [entity.dxf.height for entity in doc.modelspace().query('TEXT')]
                assert heights, result.stdout
                return {'entities': len(doc.modelspace()), 'text_heights': heights, 'audit_errors': 0, 'path': str(paths[0])}
            before = generate('before')
            value = config.effective(mode, cls)
            value['appearance']['text_scale'] = 1.5
            config.save(mode, cls, value, config.read_store()['revision'], 'cli-validation')
            after = generate('after')
            assert after['text_heights'] == [height * 1.5 for height in before['text_heights']], cls
            assert after['entities'] == before['entities']
            evidence[mode + '/' + cls] = {'before': before, 'after': after, 'text_scale_verified': 1.5}
            print(mode, cls, before['entities'], 'entities; verified 1.5x text', flush=True)
    (output / 'evidence.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
