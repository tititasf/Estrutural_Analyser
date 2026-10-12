"""Resolve uma montagem LV publicada sem misturar modo, pavimento ou comportamento."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException


def lateral_variant_path(path: Path, classe: str, behavior: str | None,
                         assembly: str | None) -> Path:
    if behavior is None and assembly is None:
        return path
    if classe.upper() != 'LV' or behavior not in {'PARA', 'PASSA'} or assembly not in {'gradeadas', 'sarrafeadas'}:
        raise HTTPException(422, 'Selecione comportamento e montagem válidos das laterais')
    try:
        source = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
        old_suffix = f"_{source['lateral_behavior']}_{source['lateral_assembly']}"
        if source.get('classe') != 'LV' or source.get('visual_mode') not in ('NOVA','MOLDE_1','INI') or not path.stem.endswith(old_suffix):
            raise ValueError('identidade da publicação inválida')
        selected = path.with_name(path.stem[:-len(old_suffix)] + f'_{behavior}_{assembly}.dxf')
        target = json.loads(selected.with_suffix('.json').read_text(encoding='utf-8'))
        for key in ('classe', 'visual_mode', 'obra', 'pavimento'):
            if target.get(key) != source.get(key):
                raise ValueError('inventário de outra publicação')
        if target.get('lateral_behavior') != behavior or target.get('lateral_assembly') != assembly:
            raise ValueError('montagem divergente')
        if (target.get('missing_count') and not target.get('partial')) or not target.get('ok_count') or not selected.is_file():
            raise ValueError('resultado incompleto')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(404, 'Gere o N5 do modo selecionado completo das quatro versões das laterais') from exc
    return selected
