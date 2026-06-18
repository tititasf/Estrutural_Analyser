"""
src/core/services/dxf_generator.py — CAD-11
Wraps the 4 STOG DXF generators as a callable Python service.

Usage (CLI mode, blocking):
    from src.core.services.dxf_generator import DXFGeneratorService
    svc = DXFGeneratorService('D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1')
    ok, path = svc.generate('PL')
    ok, path = svc.generate('PL', item='P1')           # combined preview (all zones)
    ok, path = svc.generate('PL', item='P1', zone='abcd')  # zone-isolated DXF

    # Generate all 3 PIL zones for a single item:
    results = svc.generate_pil_zones('P1')
    # {'ABCD': (True, Path(...)), 'CIMA': (True, Path(...)), 'GRADES': (True, Path(...))}

Usage (async mode via QProcess — see generate_dxf_dialog.py):
    svc.build_args('LV', item='V5')  -> (script_path, ['--obra', ..., '--item', 'V5'])
    svc.build_args('PL', item='P1', zone='cima')  -> (..., ['--obra', ..., '--item', 'P1', '--zone', 'cima'])

PIL zone field schemas (for viewer ficha panels):
    PIL_ZONE_FIELDS['ABCD']   = ['nome', 'comprimento', 'largura', 'altura', 'pd_pavimento_cm']
    PIL_ZONE_FIELDS['CIMA']   = ['nome', 'comprimento', 'largura', 'grade_1']
    PIL_ZONE_FIELDS['GRADES'] = ['nome', 'comprimento', 'largura', 'altura', 'grade_1', 'grade_2']
    PIL_ZONE_FIELDS['EFGH']   = ['nome', 'larg1_E', 'larg1_F', 'h1_E', 'h2_E', 'h3_E', 'h1_F', 'h2_F', 'h3_F']
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

# PIL zone-isolated DXF prefix: PL_{ZONE}_preview_{item}.dxf
_PIL_ZONE_PREFIX = 'PL_{zone}_preview_'

# PIL zones supported by the split generator (--zone arg)
PIL_ZONES = ('ABCD', 'CIMA', 'GRADES', 'EFGH')

# Fields per PIL zone — for viewer ficha panels (campos ausentes mostram "—")
PIL_ZONE_FIELDS: dict[str, list[str]] = {
    'ABCD':   ['nome', 'comprimento', 'largura', 'altura', 'pd_pavimento_cm'],
    'CIMA':   ['nome', 'comprimento', 'largura', 'grade_1'],
    'GRADES': ['nome', 'comprimento', 'largura', 'altura', 'grade_1', 'grade_2'],
    'EFGH':   ['nome', 'larg1_E', 'larg1_F', 'h1_E', 'h2_E', 'h3_E', 'h1_F', 'h2_F', 'h3_F'],
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

    def build_args(self, tipo: str, item: str | None = None,
                   zone: str | None = None) -> tuple[Path, list[str]]:
        """
        Build (script_path, args_list) for QProcess.start() or subprocess.

        Parameters
        ----------
        tipo : str
            'PL', 'LV', 'FV', or 'LJ'
        item : str | None
            If given, generates only this item (e.g. 'P1', 'V5', 'L3').
        zone : str | None
            PIL only — 'abcd', 'cima', 'grades', 'efgh', or None/'all'.
            If given, passes --zone to gerar_pl_dxf_stog.py (zone-isolated DXF).

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
        if zone and tipo == 'PL':
            args += ['--zone', zone.lower()]
        return script, args

    def expected_output(self, tipo: str, item: str | None = None,
                        zone: str | None = None) -> Path:
        """Return the expected output DXF path (may not exist yet).

        For PIL with zone, returns PL_{ZONE}_preview_{item}.dxf.
        """
        _, default_name = _GENERATOR_MAP[tipo]
        if item:
            ext = item.upper().replace('.JSON', '')
            if zone and tipo == 'PL' and zone.upper() in PIL_ZONES:
                name = f"PL_{zone.upper()}_preview_{ext}.dxf"
            else:
                name = f"{_PREVIEW_PREFIX[tipo]}{ext}.dxf"
        else:
            name = default_name
        return self.out_dir / name

    def generate_pil_zones(self, item: str,
                           timeout: int = 120) -> dict[str, tuple[bool, Path | None]]:
        """
        Generate zone-isolated DXFs for a PIL item (ABCD, CIMA, GRADES).
        Returns dict: {'ABCD': (ok, path), 'CIMA': (ok, path), 'GRADES': (ok, path)}.
        GRADES is skipped (ok=True, path=None) when grade_1=0 (no ficha yet).
        EFGH is not generated (slot reserved for L/U/T subtypes).
        """
        results: dict[str, tuple[bool, Path | None]] = {}
        for zone in ('ABCD', 'CIMA', 'GRADES'):
            script, args = self.build_args('PL', item=item, zone=zone)
            if not script.exists():
                results[zone] = (False, None)
                continue
            cmd = [sys.executable, str(script)] + args
            try:
                r = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=timeout, encoding='utf-8', errors='replace',
                )
                out = self.expected_output('PL', item=item, zone=zone)
                if r.returncode == 0 and out.exists():
                    results[zone] = (True, out)
                elif r.returncode == 0:
                    # zone omitted by generator (e.g. grades with grade_1=0)
                    results[zone] = (True, None)
                else:
                    results[zone] = (False, None)
            except (subprocess.TimeoutExpired, OSError):
                results[zone] = (False, None)
        return results

    def generate(self, tipo: str, item: str | None = None,
                 timeout: int = 120,
                 zone: str | None = None) -> tuple[bool, Path | None]:
        """
        Blocking generation. Returns (success, output_path).
        Prefer async via QProcess for UI use (see generate_dxf_dialog.py).
        For PIL zone-isolated DXFs use zone='abcd'/'cima'/'grades'.
        """
        script, args = self.build_args(tipo, item, zone=zone)
        if not script.exists():
            return False, None
        cmd = [sys.executable, str(script)] + args
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, encoding='utf-8', errors='replace',
            )
            ok = result.returncode == 0
            out = self.expected_output(tipo, item, zone=zone)
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
