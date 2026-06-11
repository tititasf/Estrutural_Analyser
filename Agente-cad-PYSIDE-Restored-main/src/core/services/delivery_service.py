"""
src/core/services/delivery_service.py -- CAD-12
Prancha de Entrega (1-clique): gera DXFs + converte para DWG via ODA.

Usage:
    from src.core.services.delivery_service import DeliveryService
    svc = DeliveryService('D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1')
    result = svc.build_delivery()
    # result: {dxfs_ok, dwgs_ok, erros, report_path, tempo_ms}
"""
from __future__ import annotations

import glob
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

try:
    from src.core.services.dxf_generator import DXFGeneratorService
except ImportError:
    DXFGeneratorService = None  # type: ignore[assignment,misc]


def _find_oda() -> str | None:
    """Procura ODAFileConverter.exe no PATH e em caminhos comuns do Windows."""
    import shutil
    found = shutil.which('ODAFileConverter')
    if found:
        return found

    common_paths = [
        r'C:\Program Files\ODA\ODAFileConverter',
        r'C:\Program Files (x86)\ODA\ODAFileConverter',
    ]
    for base in common_paths:
        pattern = os.path.join(base + '*', 'ODAFileConverter.exe')
        matches = glob.glob(pattern)
        if matches:
            return matches[0]

    # Also check Program Files directly
    for pf in [os.environ.get('ProgramFiles', ''), os.environ.get('ProgramFiles(x86)', '')]:
        if not pf:
            continue
        for d in os.listdir(pf) if os.path.isdir(pf) else []:
            if 'ODA' in d.upper():
                candidate = os.path.join(pf, d, 'ODAFileConverter.exe')
                if os.path.isfile(candidate):
                    return candidate
    return None


class DeliveryService:
    """
    Service for one-click delivery: generate DXFs + convert to DWG.

    Parameters
    ----------
    obra_path : str | Path
        Full path to the obra directory.
    """

    def __init__(self, obra_path: str | Path):
        self.obra_path = Path(obra_path)
        self.out_dir = self.obra_path / 'Fase-6_Execucao_CAD'

    def build_delivery(self, tipos: list[str] | None = None,
                       timeout: int = 300) -> dict[str, Any]:
        """
        Execute full delivery pipeline:
        1. Generate all DXFs via DXFGeneratorService
        2. Convert each .dxf to .dwg via ODA (graceful skip if unavailable)
        3. Write delivery_report.json

        Returns dict with keys: dxfs_ok, dwgs_ok, erros, report_path, tempo_ms
        """
        t0 = time.time()
        erros: list[str] = []
        dxfs_ok = 0
        dwgs_ok = 0

        # Step 1: generate DXFs
        if DXFGeneratorService is None:
            return {'dxfs_ok': 0, 'dwgs_ok': 0, 'erros': ['DXFGeneratorService indisponivel'],
                    'report_path': None, 'tempo_ms': 0}
        gen_svc = DXFGeneratorService(self.obra_path)
        results = gen_svc.generate_all(tipos=tipos, timeout=timeout)

        dxf_paths: list[Path] = []
        for tipo, (ok, path) in results.items():
            if ok and path:
                dxfs_ok += 1
                dxf_paths.append(path)
            else:
                erros.append(f"DXF {tipo}: falha na geracao")

        # Step 2: convert to DWG via ODA
        oda_exe = _find_oda()
        if oda_exe and dxf_paths:
            dwg_dir = self.out_dir / 'DWG'
            dwg_dir.mkdir(parents=True, exist_ok=True)

            # ODA converts an entire directory at once
            # We need DXFs in a single input dir (they already are in out_dir)
            try:
                cmd = [
                    oda_exe,
                    str(self.out_dir),   # input dir
                    str(dwg_dir),        # output dir
                    'ACAD2018',          # output version
                    'DWG',               # output format
                    '1',                 # recurse (0=no, 1=yes)
                    '1',                 # audit (0=no, 1=yes)
                ]
                proc = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=120, encoding='utf-8', errors='replace',
                )
                if proc.returncode == 0:
                    # Count converted DWG files
                    for dxf_p in dxf_paths:
                        dwg_p = dwg_dir / dxf_p.with_suffix('.dwg').name
                        if dwg_p.exists():
                            dwgs_ok += 1
                        else:
                            erros.append(f"DWG {dxf_p.stem}: ODA nao gerou arquivo")
                else:
                    erros.append(f"ODA returncode={proc.returncode}: {proc.stderr[:200]}")
            except subprocess.TimeoutExpired:
                erros.append("ODA timeout (120s)")
            except OSError as e:
                erros.append(f"ODA erro: {e}")
        elif not oda_exe:
            log.info("[Delivery] ODA nao encontrado -- DWG conversion skipped")
        # if no dxf_paths, nothing to convert

        # Step 3: write delivery report
        tempo_ms = int((time.time() - t0) * 1000)
        report = {
            'obra': self.obra_path.name,
            'dxfs_ok': dxfs_ok,
            'dwgs_ok': dwgs_ok,
            'oda_found': oda_exe is not None,
            'erros': erros,
            'tempo_ms': tempo_ms,
            'dxf_files': [str(p) for p in dxf_paths],
        }

        self.out_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.out_dir / 'delivery_report.json'
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )

        return {
            'dxfs_ok': dxfs_ok,
            'dwgs_ok': dwgs_ok,
            'erros': erros,
            'report_path': str(report_path),
            'tempo_ms': tempo_ms,
        }
