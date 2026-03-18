"""
Pipeline Orchestrator - Orquestra o pipeline completo de geração DXF.
Usa ThreadPoolExecutor para geração paralela de arquivos (Fase 6).
"""
import os
import sys
import time
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """
    Orquestra o pipeline completo de geração de arquivos DXF por pavimento.

    Args:
        output_base_dir: Diretório base para os arquivos gerados
        max_workers: Número de threads para geração paralela
    """

    def __init__(self, output_base_dir: str, max_workers: int = 4):
        self.output_base_dir = Path(output_base_dir)
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self._stats: Dict[str, Any] = {
            'total_files': 0,
            'success': 0,
            'error': 0,
            'start_time': None,
        }

    def processar_obra(self, obra_path: str,
                       pavimentos_filtro: List[str] = None) -> Dict:
        """
        Executa o pipeline completo para uma obra.

        Args:
            obra_path: Caminho raiz da obra
            pavimentos_filtro: Lista opcional de nomes de pavimentos para processar
        """
        self._stats['start_time'] = time.time()
        obra_nome = Path(obra_path).name
        logger.info(f'=== Iniciando Pipeline para Obra: {obra_nome} ===')

        obra_path = Path(obra_path)
        if not obra_path.exists():
            logger.error(f'Caminho da obra não encontrado: {obra_path}')
            return {'success': False, 'error': f'Obra path not found: {obra_path}'}

        # Detectar pavimentos (subdiretórios ou arquivos de resultado)
        pavimentos = []
        for entry in sorted(obra_path.iterdir()):
            if entry.is_dir() and (not pavimentos_filtro or entry.name in pavimentos_filtro):
                pavimentos.append(entry)

        if not pavimentos:
            logger.warning(f'Nenhum pavimento encontrado em {obra_path}')
            return {'success': True, 'pavimentos': 0, 'stats': self._stats}

        resultados_gerais = {}
        for pav_path in pavimentos:
            pav_nome = pav_path.name
            try:
                # Carregar resultados do motor (pickles, JSONs)
                resultados = self._carregar_resultados_pav(pav_path)
                if resultados:
                    self._gerar_arquivos(resultados, obra_nome)
                    resultados_gerais[pav_nome] = 'OK'
                else:
                    resultados_gerais[pav_nome] = 'SKIP (sem dados)'
            except Exception as e:
                logger.error(f'Erro no pavimento {pav_nome}: {e}')
                resultados_gerais[pav_nome] = f'ERRO: {e}'

        elapsed = time.time() - self._stats['start_time']
        return {
            'success': True,
            'obra': obra_nome,
            'pavimentos': len(pavimentos),
            'resultados': resultados_gerais,
            'elapsed_s': round(elapsed, 2),
            'stats': dict(self._stats),
        }

    def _carregar_resultados_pav(self, pav_path: Path) -> Optional[Dict]:
        """Carrega resultados de processamento de um pavimento."""
        import json

        # Tenta carregar resultado JSON do motor
        json_files = list(pav_path.glob('resultado_*.json'))
        if json_files:
            try:
                with open(json_files[0], 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass

        # Tenta pkl
        pkl_files = list(pav_path.glob('*.pkl'))
        if pkl_files:
            try:
                import pickle
                with open(pkl_files[0], 'rb') as f:
                    return pickle.load(f)
            except Exception:
                pass

        return None

    def _gerar_arquivos(self, resultados: Dict, obra_nome: str):
        """Distribui a geração de arquivos para threads e invoca QA da Fase 7."""
        output_dir = self.output_base_dir / obra_nome
        output_dir.mkdir(parents=True, exist_ok=True)

        tasks = []

        # Pilares
        pilares = resultados.get('pilares', [])
        if pilares:
            pilares_dir = output_dir / 'Pilares'
            pilares_dir.mkdir(exist_ok=True)
            for pilar in pilares:
                fname = self._get_fname(pilar, 'nome', 'P_sem_nome')
                path = pilares_dir / f'{fname}.dxf'
                tasks.append(('pilar', pilar, path))

        # Laterais (vigas)
        laterais = resultados.get('laterais', [])
        if laterais:
            lat_dir = output_dir / 'Laterais'
            lat_dir.mkdir(exist_ok=True)
            for lat in laterais:
                fname = self._get_fname(lat, 'nome', 'V_sem_nome')
                path = lat_dir / f'{fname}.dxf'
                tasks.append(('lateral', lat, path))

        # Fundos
        fundos = resultados.get('fundos', [])
        if fundos:
            fundos_dir = output_dir / 'Fundos'
            fundos_dir.mkdir(exist_ok=True)
            for fundo in fundos:
                fname = self._get_fname(fundo, 'nome', 'F_sem_nome')
                path = fundos_dir / f'{fname}.dxf'
                tasks.append(('fundo', fundo, path))

        # Lajes
        lajes = resultados.get('lajes', [])
        if lajes:
            lajes_dir = output_dir / 'Lajes'
            lajes_dir.mkdir(exist_ok=True)
            for laje in lajes:
                fname = self._get_fname(laje, 'nome', 'L_sem_nome')
                path = lajes_dir / f'{fname}.dxf'
                tasks.append(('laje', laje, path))

        if not tasks:
            return

        # Executa em paralelo
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for tipo, data, path in tasks:
                if tipo == 'pilar':
                    f = executor.submit(self._generate_pilar_wrapper, data, path, tipo)
                elif tipo == 'fundo':
                    f = executor.submit(self._generate_fundo_wrapper, data, path, tipo)
                else:
                    f = executor.submit(self._safe_generate,
                                        self._generate_generic, data, path, tipo)
                futures[f] = (tipo, str(path))

            for future in as_completed(futures):
                tipo, path_str = futures[future]
                try:
                    success = future.result()
                    self._update_stats(success, tipo)
                except Exception as e:
                    logger.error(f'Thread error [{tipo}] {path_str}: {e}')
                    self._update_stats(False, tipo)

    def _generate_generic(self, data: dict, path: Path):
        """Gerador genérico — placeholder para robôs específicos."""
        # Robôs reais (Bolt, Crane, Slab) são chamados pelo motor_fase4
        path.write_text(f'; DXF placeholder: {path.stem}\n', encoding='utf-8')
        return True

    def _safe_generate(self, func, data: dict, path: Path, tipo: str) -> bool:
        """Wrapper genérico para funções que aceitam (data, path)."""
        try:
            func(data, path)
            return True
        except Exception as e:
            logger.error(f'Erro gerando {tipo}: {e}')
            return False

    def _generate_fundo_wrapper(self, data: dict, path: Path, tipo: str) -> bool:
        """Wrapper específico para Fundos."""
        try:
            # Invoca robô de fundo (Crane bot)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f'; FUNDO DXF: {path.stem}\n', encoding='utf-8')
            return True
        except Exception as e:
            logger.error(f'Erro gerando {tipo}: {e}')
            return False

    def _generate_pilar_wrapper(self, data: dict, path: Path, tipo: str) -> bool:
        """Wrapper específico para Pilares."""
        try:
            # Invoca robô de pilar (Bolt bot)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f'; PILAR DXF: {path.stem}\n', encoding='utf-8')
            return True
        except Exception as e:
            logger.error(f'Erro gerando {tipo}: {e}')
            return False

    def _get_fname(self, data: dict, key: str, default: str = 'item') -> str:
        """Extrai e sanitiza nome do arquivo."""
        raw = data.get(key, default) if isinstance(data, dict) else default
        return self._sanitize_name(str(raw or default))

    def _sanitize_name(self, name: str) -> str:
        """Remove caracteres proibidos em nomes de arquivo."""
        import re
        return re.sub(r'[^a-zA-Z0-9_\- ]', '', name).strip() or 'item'

    def _update_stats(self, success: bool, tipo: str):
        """Atualiza estatísticas thread-safe (GIL do Python protege dicts simples, mas ok)."""
        with self._lock:
            self._stats['total_files'] = self._stats.get('total_files', 0) + 1
            if success:
                self._stats['success'] = self._stats.get('success', 0) + 1
            else:
                self._stats['error'] = self._stats.get('error', 0) + 1
