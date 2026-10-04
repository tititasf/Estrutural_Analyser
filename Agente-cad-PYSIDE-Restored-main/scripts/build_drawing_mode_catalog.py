"""Extract legacy configuration without importing Qt/Tk or executing robot code."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PL = ROOT / '_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25'


def defaults(path, method='get_default_config'):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == method:
            for child in ast.walk(node):
                if isinstance(child, ast.Return) and isinstance(child.value, ast.Dict):
                    # The LV numbering defaults are the sole computed leaf.
                    for item in ast.walk(child.value):
                        if isinstance(item, ast.Dict):
                            for index, value in enumerate(item.values):
                                if isinstance(value, ast.DictComp):
                                    assert ast.unparse(value) == "{str(i): f'N{i}' for i in range(1, 21)}"
                                    item.values[index] = ast.parse(repr({str(i): f'N{i}' for i in range(1, 21)}), mode='eval').body
                    return ast.literal_eval(child.value)
    raise ValueError(f'No literal defaults: {path}/{method}')


def merge(left, right):
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(left.get(key), dict):
            merge(left[key], value)
        else:
            left[key] = value
    return left


def native(source, json_path=None, method='get_default_config'):
    value = defaults(source, method)
    if json_path and json_path.exists():
        merge(value, json.loads(json_path.read_text(encoding='utf-8-sig')))
    value.pop('templates', None)
    return {'source': str(source.relative_to(ROOT)).replace('\\', '/'), 'values': value}


def main():
    lvroot = ROOT / '_ROBOS_ABAS/Robo_Laterais_de_Vigas'
    fvroot = ROOT / '_ROBOS_ABAS/Robo_Fundos_de_Vigas/compactador-producao'
    ljpath = ROOT / '_ROBOS_ABAS/Robo_Lajes/laje_src/config/app_config.json'
    catalog = {
        'schema_version': 1,
        'PL': {
            'cima': native(PL / 'src/robots/Robo_Pilar_Visao_Cima.py', PL / 'config/config_cima.json'),
            'abcd': native(PL / 'src/robots/Robo_Pilar_ABCD.py', PL / 'config/config_abcd.json'),
            'grades': native(PL / 'src/robots/ROBO_GRADES.py', PL / 'config/config_grades.json'),
        },
        'LV': {'faces': native(lvroot / 'robo_laterais_viga_pyside.py', lvroot / 'config.json', '_obter_config_padrao')},
        'FV': {'fundo': native(fvroot / 'Robo_fundos_TASF_limpo_copy_22.py', fvroot / 'config.json')},
        'LJ': {'planta': {'source': str(ljpath.relative_to(ROOT)).replace('\\', '/'), 'values': json.loads(ljpath.read_text(encoding='utf-8-sig'))}},
    }
    target = ROOT / 'config/drawing_mode_legacy_catalog.json'
    target.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(target)


if __name__ == '__main__':
    main()
