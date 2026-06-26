"""
src/core/services/multi_pav_importer.py -- CAD-14
Multi-pavimento: detecta e importa todos os pavimentos de uma obra.

Usage:
    from src.core.services.multi_pav_importer import MultiPavImporter
    imp = MultiPavImporter(db)
    pavs = imp.detect_pavimentos('D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1')
    result = imp.import_all_pavimentos('D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1', project_id)
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

try:
    from src.core.services.fase4_importer import Fase4Importer
except ImportError:
    Fase4Importer = None  # type: ignore[assignment,misc]

_PAV_LIST_PATH = Path('Fase-4_Sincronizacao') / 'pavimentos_lista.json'


class MultiPavImporter:
    """
    Detecta e importa todos os pavimentos de uma obra para o DB.

    Parameters
    ----------
    db : database object with save_pillar / save_slab / save_beam methods
    """

    def __init__(self, db):
        self.db = db

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _load_pavimentos_lista(self, obra_path: str | Path) -> dict:
        """Lê pavimentos_lista.json e retorna o bloco da obra."""
        path = Path(obra_path) / _PAV_LIST_PATH
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
            # Estrutura: {obra_name: {pavimentos: [...], pavimentos_data: {...}}}
            # Retorna o primeiro valor (único por arquivo)
            if raw:
                return list(raw.values())[0]
        except (json.JSONDecodeError, OSError) as e:
            log.warning(f"[MultiPavImporter] Erro ao ler pavimentos_lista: {e}")
        return {}

    # ── Public API ────────────────────────────────────────────────────────────

    def detect_pavimentos(self, obra_path: str | Path) -> list[dict]:
        """
        Detecta os pavimentos disponíveis na obra.

        Returns
        -------
        list of {nome, numero, nivel_chegada, nivel_saida}
        """
        pav_block = self._load_pavimentos_lista(obra_path)
        if not pav_block:
            return []

        pav_names: list[str] = pav_block.get('pavimentos', [])
        pav_data: dict = pav_block.get('pavimentos_data', {})

        result = []
        for name in pav_names:
            data = pav_data.get(name, {})
            result.append({
                'nome':          data.get('nome', name),
                'numero':        data.get('numero', ''),
                'nivel_chegada': data.get('nivel_chegada', '0.0'),
                'nivel_saida':   data.get('nivel_saida', '0.0'),
            })
        return result

    def import_all_pavimentos(
        self,
        obra_path: str | Path,
        project_id: str,
    ) -> dict[str, Any]:
        """
        Importa todos os pavimentos via Fase4Importer.

        Para cada pavimento em pavimentos_lista.json, chama
        Fase4Importer.import_obra() e agrega os resultados.

        Returns
        -------
        {
            pavimentos_importados: int,
            total_pilares: int,
            total_vigas: int,
            total_lajes: int,
            total_conflitos: int,
            erros: list[str],
            por_pavimento: {nome: {pilares, vigas, lajes, conflitos}},
            tempo_ms: int,
        }
        """
        t0 = time.monotonic()

        pavimentos = self.detect_pavimentos(obra_path)
        if not pavimentos:
            return {
                'pavimentos_importados': 0,
                'total_pilares': 0,
                'total_vigas': 0,
                'total_lajes': 0,
                'total_conflitos': 0,
                'erros': ['Nenhum pavimento detectado em pavimentos_lista.json'],
                'por_pavimento': {},
                'tempo_ms': 0,
            }

        if Fase4Importer is None:
            return {
                'pavimentos_importados': 0,
                'total_pilares': 0,
                'total_vigas': 0,
                'total_lajes': 0,
                'total_conflitos': 0,
                'erros': ['Fase4Importer indisponivel'],
                'por_pavimento': {},
                'tempo_ms': 0,
            }

        importer = Fase4Importer(self.db)
        totais = {
            'pilares': 0, 'vigas': 0, 'lajes': 0,
            'conflitos': 0, 'erros': [],
        }
        por_pav: dict[str, dict] = {}

        for pav in pavimentos:
            nome = pav['nome']
            try:
                res = importer.import_obra(str(obra_path), nome, project_id)
                por_pav[nome] = {
                    'pilares':   res.get('pilares', 0),
                    'vigas':     res.get('vigas', 0),
                    'lajes':     res.get('lajes', 0),
                    'conflitos': res.get('conflitos', 0),
                }
                totais['pilares']   += res.get('pilares', 0)
                totais['vigas']     += res.get('vigas', 0)
                totais['lajes']     += res.get('lajes', 0)
                totais['conflitos'] += res.get('conflitos', 0)
                totais['erros'].extend(res.get('erros', []))
                log.info(
                    f"[MultiPavImporter] {nome}: "
                    f"{res.get('pilares',0)}PL {res.get('vigas',0)}VG {res.get('lajes',0)}LJ"
                )
            except Exception as exc:
                msg = f"Erro no pavimento '{nome}': {exc}"
                log.error(f"[MultiPavImporter] {msg}")
                totais['erros'].append(msg)
                por_pav[nome] = {'pilares': 0, 'vigas': 0, 'lajes': 0, 'conflitos': 0}

        elapsed = int((time.monotonic() - t0) * 1000)
        return {
            'pavimentos_importados': len(pavimentos),
            'total_pilares':  totais['pilares'],
            'total_vigas':    totais['vigas'],
            'total_lajes':    totais['lajes'],
            'total_conflitos': totais['conflitos'],
            'erros':          totais['erros'],
            'por_pavimento':  por_pav,
            'tempo_ms':       elapsed,
        }
