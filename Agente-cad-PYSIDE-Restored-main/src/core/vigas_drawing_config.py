"""Preferências do pavimento aplicadas somente a cópias dos contratos N3."""
from copy import deepcopy


def normalize_config(config=None):
    config = config or {}
    result = {
        'comportamento_laterais_vigas': config.get('comportamento_laterais_vigas', 'sarrafeadas'),
        'fundos_vigas_possui_garfos': config.get('fundos_vigas_possui_garfos', 'nao'),
    }
    if result['comportamento_laterais_vigas'] not in {'gradeadas', 'sarrafeadas'}:
        raise ValueError('Laterais: escolha gradeadas ou sarrafeadas')
    if result['fundos_vigas_possui_garfos'] not in {'sim', 'nao'}:
        raise ValueError('Garfos: escolha sim ou nao')
    return result


def apply_lv_config(contract, config=None):
    result = deepcopy(contract)
    config = normalize_config(config)
    result['vigas_config'] = config
    grade = config['comportamento_laterais_vigas'] == 'gradeadas'
    for panel in result.get('panels', []):
        panel['panel_type'] = 'Grade' if grade else 'Sarrafeado'
        for index in (1, 2):
            panel[f'grade_h{index}'] = float(panel.get(f'height{index}') or 0) if grade else 0.0
    return result


def apply_fv_config(contract, config=None):
    result = deepcopy(contract)
    config = normalize_config(config)
    result['vigas_config'] = config
    result['possui_garfos'] = config['fundos_vigas_possui_garfos'] == 'sim'
    # A distribuição geométrica depende da regra do dono; não inventar garfos.
    return result


def require_supported_generation(config, sections=None):
    config = normalize_config(config)
    if config['fundos_vigas_possui_garfos'] == 'sim' and (not sections or 'fundos_viga' in sections):
        raise ValueError('A regra de desenho dos garfos ainda precisa ser definida. A opção Sim está salva; o N3 de fundos com garfos ainda não pode ser gerado.')
