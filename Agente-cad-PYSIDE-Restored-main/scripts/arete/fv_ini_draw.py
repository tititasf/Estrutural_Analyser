"""iNi adapter: certified FV contracts, end assemblies, original iNi palette.

The certified generator and the approved modes are left unchanged.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import gerar_fv_dxf_stog as motor
original_visual_mode = motor.apply_visual_mode


def appearance(doc, mode, cls, *args, **kwargs):
    result = original_visual_mode(doc, mode, cls, *args, **kwargs)
    from src.core.lv_formascia_design import normalize_resources
    normalize_resources(doc)
    return result


if __name__ == '__main__':
    if '--visual-mode' not in sys.argv or sys.argv[sys.argv.index('--visual-mode') + 1] != 'INI':
        raise ValueError('This adapter is exclusively for iNi')
    motor.apply_visual_mode = appearance
    motor._MOTOR_SOURCES += [Path(__file__), ROOT / 'src/core/ini_fv_design.py']
    motor.main()
