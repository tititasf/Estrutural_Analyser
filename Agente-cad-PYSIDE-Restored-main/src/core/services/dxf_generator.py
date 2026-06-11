"""
src/core/services/dxf_generator.py — CAD-11
Wraps the 4 STOG DXF generators as a callable Python service.

Usage (CLI mode, blocking):
    from src.core.services.dxf_generator import DXFGeneratorService
    svc = DXFGeneratorService('D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1')
    ok, path = svc.generate('PL')
    ok, path = svc.generate('PL', item='P1')   # single-item preview

Usage (async mode via QProcess — see generate_dxf_dialog.py):
    svc.build_args('LV', item='V5')  -> (script_path, ['--obra', ..., '--item', 'V5'])
"""
import subprocess
import sys
from pathlib import Path

# Map generator type -> script filename and default output DXF name
_GENERATOR_MAP = {
    'PL': ('gerar_pl_dxf_stog.py',  'PL_stog_quality.dxf'),
    'LV': ('gerar_lv_dxf_stog.py',  'LV_stog_quality.dxf'),
    'FV': ('gerar_fv_dxf_stog.py',  'FV_stog_quality.dxf'),
    'LJ': ('gerar_lj_dxf_stog.py',  'LJ_stog_quality.dxf'),
}

# Preview DXF names per type (when --item is given)
_PREVIEW_PREFIX = {
    'PL': 'PL_preview_',
    'LV': 'LV_preview_',
    'FV': 'FV_preview_',
    'LJ': 'LJ_preview_',
}

# Map item type strings (from DetailCard) to generator type keys
ITEM_TYPE_TO_KEY = {
    'Pilar':        'PL',
    'PILAR':        'PL',
    'Viga Lateral': 'LV',
    'VIGA LATERAL': 'LV',
    'Viga Fundo':   'FV',
    'VIGA FUNDO':   'FV',
    'Laje':         'LJ',
    'LAJE':         'LJ',
}

# Locate scripts dir relative to this file
_SCRIPTS_DIR = Path(__file__).parent.parent.parent.parent / 'scripts'


class DXFGeneratorService:
    """
    Service for generating STOG-quality DXF files from Fase-4 JSON data.

    Parameters
    ----------
    obra_path : str | Path
        Full path to the obra directory (must contain Fase-4_Sincronizacao/).
    """

    def __init__(self, obra_path: str | Path):
        self.obra_path = Path(obra_path)
        self.out_dir = self.obra_path / 'Fase-6_Execucao_CAD'

    # ── Public API ────────────────────────────────────────────────────────────

    def build_args(self, tipo: str, item: str | None = None) -> tuple[Path, list[str]]:
        """
        Build (script_path, args_list) for QProcess.start() or subprocess.

        Parameters
        ----------
        tipo : str
            'PL', 'LV', 'FV', or 'LJ'
        item : str | None
            If given, generates only this item (e.g. 'P1', 'V5', 'L3').

        Returns
        -------
        (script_path, args)
        """
        if tipo not in _GENERATOR_MAP:
            raise ValueError(f"Tipo desconhecido: {tipo}. Use PL/LV/FV/LJ.")
        script_name, _ = _GENERATOR_MAP[tipo]
        script = _SCRIPTS_DIR / script_name
        args = ['--obra', str(self.obra_path)]
        if item:
            args += ['--item', str(item)]
        return script, args

    def expected_output(self, tipo: str, item: str | None = None) -> Path:
        """Return the expected output DXF path (may not exist yet)."""
        _, default_name = _GENERATOR_MAP[tipo]
        if item:
            ext = item.upper().replace('.JSON', '')
            name = f"{_PREVIEW_PREFIX[tipo]}{ext}.dxf"
        else:
            name = default_name
        return self.out_dir / name

    def generate(self, tipo: str, item: str | None = None,
                 timeout: int = 120) -> tuple[bool, Path | None]:
        """
        Blocking generation. Returns (success, output_path).
        Prefer async via QProcess for UI use (see generate_dxf_dialog.py).
        """
        script, args = self.build_args(tipo, item)
        if not script.exists():
            return False, None
        cmd = [sys.executable, str(script)] + args
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, encoding='utf-8', errors='replace',
            )
            ok = result.returncode == 0
            out = self.expected_output(tipo, item)
            return ok and out.exists(), out if out.exists() else None
        except (subprocess.TimeoutExpired, OSError):
            return False, None

    def generate_all(self, tipos: list[str] | None = None,
                     timeout: int = 300) -> dict[str, tuple[bool, Path | None]]:
        """
        Blocking: generate all specified types. Returns {tipo: (ok, path)}.
        Default tipos = ['PL', 'LV', 'FV', 'LJ'].
        """
        if tipos is None:
            tipos = list(_GENERATOR_MAP.keys())
        return {t: self.generate(t, timeout=timeout) for t in tipos}

    @staticmethod
    def key_for_item_type(item_type: str) -> str | None:
        """Map a DetailCard 'type' string to a generator key, or None."""
        for k, v in ITEM_TYPE_TO_KEY.items():
            if k.upper() in item_type.upper():
                return v
        return None
