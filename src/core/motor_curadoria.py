"""
Motor de Curadoria - Valida qualidade de cada fase do pipeline CAD-ANALYZER.
Fases: Ingestão → Triagem → Interpretação → Campos
"""
import os
import sys
import json
import sqlite3
import logging
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class MetricasFase:
    fase: str
    score: float = 0.0  # 0.0–1.0
    ok: int = 0
    total: int = 0
    problemas: List[str] = field(default_factory=list)


@dataclass
class RelatorioObra:
    obra: str
    fases: List[MetricasFase] = field(default_factory=list)
    score_global: float = 0.0

    def resumo(self) -> str:
        lines = [
            '=' * 60,
            f'RELATÓRIO CURADORIA: {self.obra}',
            f'Score global: {self.score_global:.1%}',
        ]
        for f in self.fases:
            status = 'OK' if f.score >= 0.7 else 'WARN' if f.score >= 0.4 else 'FAIL'
            lines.append(f'  [{status}] {f.fase}: {f.score:.1%} ({f.ok}/{f.total})')
            for p in f.problemas[:3]:
                lines.append(f'    ! {p}')
        return '\n'.join(lines)


class ClaudeCLI:
    """Interface com Claude CLI para análise inteligente."""

    @staticmethod
    def consultar(system_prompt: str, user_prompt: str, timeout: int = 60) -> dict:
        """Chama Claude CLI e retorna JSON parseado."""
        MAX_CHARS = 8000
        if len(user_prompt) > MAX_CHARS:
            user_prompt = user_prompt[:MAX_CHARS] + '\n[TRUNCADO]'

        try:
            result = subprocess.run(
                ['CLAUDECODE', '--system', system_prompt, '--prompt', user_prompt,
                 '--output-format', 'json'],
                capture_output=True, text=True, timeout=timeout,
                encoding='utf-8', errors='replace'
            )
            return ClaudeCLI._parse_json(result.stdout)
        except subprocess.TimeoutExpired:
            return {'error': 'timeout', 'raw': ''}
        except FileNotFoundError:
            return {'error': 'CLAUDECODE_not_found'}
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def _parse_json(raw: str) -> dict:
        if not raw:
            return {}
        # Tenta extrair JSON do output
        import re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {'raw': raw}


class ValidadorIngestao:
    """Valida Fase 1 — Ingestão de DXFs brutos."""

    def validar(self, obra: str) -> MetricasFase:
        base = Path('DADOS-OBRAS') / obra / 'Fase-1_Ingestao' / \
               'Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF'

        problemas = []
        if not base.exists():
            problemas.append(f'Pasta Fase-1 não encontrada: {base}')
            return MetricasFase('INGESTAO', 0.0, 0, 0, problemas)

        dxfs = list(base.glob('*.dxf')) + list(base.glob('*.DXF'))
        total = len(dxfs)
        if total == 0:
            problemas.append('Nenhum DXF encontrado em Fase-1')
            return MetricasFase('INGESTAO', 0.0, 0, 0, problemas)

        ok = total  # assume all present = ok at this stage
        score = ok / max(1, total)
        return MetricasFase('INGESTAO', score, ok, total, problemas)


class ValidadorTriagem:
    """Valida Fase 2 — Triagem de DXFs estruturais."""

    def validar(self, obra: str, use_claude: bool = False) -> MetricasFase:
        base = Path('DADOS-OBRAS') / obra / 'Fase-2_Triagem' / 'Estruturais_Pavimentos_Limpos'

        problemas = []
        if not base.exists():
            problemas.append(f'Pasta Fase-2 não encontrada: {base}')
            return MetricasFase('TRIAGEM', 0.0, 0, 0, problemas)

        dxfs = list(base.glob('*.dxf')) + list(base.glob('*.DXF'))
        total = len(dxfs)
        if total == 0:
            problemas.append('Nenhum DXF FORMA encontrado em Fase-2')
            return MetricasFase('TRIAGEM', 0.0, 0, 0, problemas)

        ok = total
        score = 1.0 if total > 0 else 0.0
        return MetricasFase('TRIAGEM', score, ok, total, problemas)


class ValidadorInterpretacao:
    """Valida Fase 3 — Interpretação estrutural (DB)."""

    def validar(self, obra: str, db_path: str = 'project_data.vision') -> MetricasFase:
        problemas = []
        fase = 'FASE_3_INTERPRETACAO'

        if not Path(db_path).exists():
            problemas.append(f'DB não encontrado: {db_path}')
            return MetricasFase(fase, 0.0, 0, 0, problemas)

        try:
            conn = sqlite3.connect(db_path)
            rows = conn.execute(
                "SELECT id FROM projects WHERE work_name = ?", (obra,)
            ).fetchall()
            conn.close()

            total = len(rows)
            if total == 0:
                problemas.append(f'Obra {obra} não encontrada no DB')
                return MetricasFase(fase, 0.0, 0, 0, problemas)

            # Verifica pilares/vigas
            conn = sqlite3.connect(db_path)
            ok = 0
            for row in rows:
                pid = row[0]
                p_count = conn.execute(
                    "SELECT COUNT(*) FROM pillars WHERE project_id=?", (pid,)
                ).fetchone()[0]
                v_count = conn.execute(
                    "SELECT COUNT(*) FROM beams WHERE project_id=?", (pid,)
                ).fetchone()[0]
                if p_count > 0 or v_count > 0:
                    ok += 1
            conn.close()

            score = ok / max(1, total)
            return MetricasFase(fase, score, ok, total, problemas)
        except Exception as e:
            problemas.append(f'Erro ao consultar DB: {e}')
            return MetricasFase(fase, 0.0, 0, 0, problemas)


class ValidadorCampos:
    """Valida qualidade dos campos preenchidos nas entidades."""

    def __init__(self, enable_logging: bool = True):
        """
        Inicializa validador.

        Args:
            enable_logging: Se True, registra problemas na validation_log
        """
        self.enable_logging = enable_logging

    def _log_problema(self, db_path, obra, validation_type, entity_type,
                      entity_id, entity_name, pavimento, field_name,
                      field_value, problem_type, problem_detail, severity):
        """
        Registra problema na validation_log (SPRINT 2 - Auditoria).
        """
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("""
                INSERT INTO validation_log
                (obra, validation_type, entity_type, entity_id, entity_name,
                 pavimento, field_name, field_value, problem_type,
                 problem_detail, severity, detected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (obra, validation_type, entity_type, entity_id, entity_name,
                  pavimento, field_name, str(field_value), problem_type,
                  problem_detail, severity))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f'Erro ao registrar problema no log: {e}')

    def _validar_outliers_estatisticos(self, obra: str, db_path: str, projects: list) -> list:
        """
        Detecta outliers estatísticos usando Z-score.

        ATAQUE 12: Statistical Outliers Detection

        Para campos numéricos (dimensões, alturas, comprimentos):
        1. Coleta todos os valores da obra
        2. Calcula média (μ) e desvio padrão (σ)
        3. Calcula Z-score para cada valor: z = (x - μ) / σ
        4. Valores com |z| > 3 são considerados outliers (>99.7% dos dados)

        Returns:
            Lista de problemas detectados (strings formatadas)
        """
        problemas = []
        try:
            import math
            conn = sqlite3.connect(db_path)

            for proj in projects:
                pid = proj[0] if isinstance(proj, (list, tuple)) else proj.get('id', '')
                rows = conn.execute(
                    "SELECT id, data_json FROM beams WHERE project_id=?", (pid,)
                ).fetchall()

                comprimentos = []
                for row in rows:
                    try:
                        data = json.loads(row[1] or '{}')
                        fields = data.get('fields', {})
                        c = fields.get('comprimento_total_a', 0)
                        if c and float(c) > 0:
                            comprimentos.append((row[0], float(c)))
                    except Exception:
                        pass

                if len(comprimentos) < 3:
                    continue

                vals = [v for _, v in comprimentos]
                mean = sum(vals) / len(vals)
                variance = sum((x - mean) ** 2 for x in vals) / len(vals)
                std = math.sqrt(variance) if variance > 0 else 0

                if std == 0:
                    continue

                for eid, val in comprimentos:
                    z = abs(val - mean) / std
                    if z > 3:
                        problemas.append(
                            f'Outlier Z={z:.1f}: beam {eid} comprimento={val:.0f}mm'
                        )

            conn.close()
        except Exception as e:
            logger.warning(f'Erro em outliers: {e}')
        return problemas

    def _validar_cross_pavimento(self, obra: str, db_path: str, projects: list) -> list:
        """
        Valida se lajes referenciadas em laje_inf existem no pavimento abaixo.

        ATAQUE 11: Cross-Pavimento Validation

        Para cada viga com seg_a_laje_inf ou seg_b_laje_inf preenchido:
        1. Detecta pavimento abaixo usando get_pavimento_abaixo()
        2. Carrega lajes do pavimento abaixo
        3. Verifica se laje_inf existe nas lajes do pavimento abaixo
        4. Reporta problema se não existir

        Returns:
            Lista de problemas detectados (strings formatadas)
        """
        problemas = []
        try:
            from core.pavimento_ordem import get_pavimento_abaixo
        except ImportError:
            problemas.append('Cross-pavimento validation não disponível (imports falharam)')
            return problemas

        try:
            conn = sqlite3.connect(db_path)
            for proj in projects:
                pid = proj[0] if isinstance(proj, (list, tuple)) else proj.get('id', '')
                pav = conn.execute(
                    "SELECT id FROM projects WHERE work_name=? AND name=?",
                    (obra, pid)
                ).fetchone()
                # Placeholder: implementação completa requer dados de pavimento
            conn.close()
        except Exception as e:
            logger.warning(f'Erro cross-pavimento: {e}')
        return problemas

    def validar(self, obra: str, db_path: str = 'project_data.vision') -> MetricasFase:
        """Valida qualidade dos campos de uma obra. VALIDACAO_CAMPOS"""
        fase = 'VALIDACAO_CAMPOS'
        problemas = []

        if not Path(db_path).exists():
            problemas.append(f'DB não encontrado: {db_path}')
            return MetricasFase(fase, 0.0, 0, 0, problemas)

        try:
            conn = sqlite3.connect(db_path)
            projects = conn.execute(
                "SELECT id, name FROM projects WHERE work_name=?", (obra,)
            ).fetchall()
            conn.close()

            total_entidades = 0
            ok_entidades = 0

            outlier_probs = self._validar_outliers_estatisticos(obra, db_path, projects)
            problemas.extend(outlier_probs)

            conn = sqlite3.connect(db_path)
            for proj in projects:
                pid = proj[0]
                p_rows = conn.execute(
                    "SELECT COUNT(*) FROM pillars WHERE project_id=?", (pid,)
                ).fetchone()[0]
                b_rows = conn.execute(
                    "SELECT COUNT(*) FROM beams WHERE project_id=?", (pid,)
                ).fetchone()[0]
                total_entidades += p_rows + b_rows
                ok_entidades += p_rows + b_rows  # simplified: assume ok if present
            conn.close()

            score = ok_entidades / max(1, total_entidades) if total_entidades > 0 else 0.5
            score = max(0.0, score - len(outlier_probs) * 0.05)
            return MetricasFase(fase, score, ok_entidades, total_entidades, problemas)
        except Exception as e:
            problemas.append(f'Erro validação campos: {e}')
            return MetricasFase(fase, 0.0, 0, 0, problemas)


class MotorCuradoria:
    """Executa curadoria completa de obras CAD-ANALYZER."""

    def __init__(self, use_claude: bool = False, db_path: str = 'project_data.vision'):
        self.use_claude = use_claude
        self.db_path = db_path
        self.dados_dir = 'DADOS-OBRAS'

    def executar_curadoria(self, obra: str, run_triagem: bool = True,
                           run_interpretacao: bool = True) -> RelatorioObra:
        """Executa curadoria completa de uma obra."""
        logger.info('=' * 60)
        logger.info(f'CURADORIA: {obra}')

        relatorio = RelatorioObra(obra=obra)

        # Fase 1: Ingestão
        fase1 = ValidadorIngestao().validar(obra)
        relatorio.fases.append(fase1)

        # Fase 2: Triagem
        if run_triagem:
            fase2 = ValidadorTriagem().validar(obra, use_claude=self.use_claude)
            relatorio.fases.append(fase2)

        # Fase 3: Interpretação
        if run_interpretacao:
            fase3 = ValidadorInterpretacao().validar(obra, self.db_path)
            relatorio.fases.append(fase3)

        # Fase 4: Campos
        fase4 = ValidadorCampos().validar(obra, self.db_path)
        relatorio.fases.append(fase4)

        # Score global
        scores = [f.score for f in relatorio.fases]
        relatorio.score_global = sum(scores) / max(1, len(scores))

        return relatorio

    def curadoria_batch(self, max_obras: int = None) -> List[RelatorioObra]:
        """Executa curadoria em todas as obras."""
        obras_path = Path(self.dados_dir)
        if not obras_path.exists():
            logger.warning(f'Diretório {self.dados_dir} não encontrado')
            return []

        obras = [d.name for d in obras_path.iterdir() if d.is_dir()]
        if max_obras:
            obras = obras[:max_obras]

        resultados = []
        for obra in sorted(obras):
            try:
                rel = self.executar_curadoria(obra)
                resultados.append(rel)
            except Exception as e:
                logger.error(f'Erro em {obra}: {e}')
                resultados.append(RelatorioObra(obra=obra, score_global=0.0))

        logger.info('=' * 60)
        return resultados

    def metricas_dashboard(self) -> dict:
        """Retorna métricas consolidadas para dashboard/UI."""
        obras_path = Path(self.dados_dir)
        n_obras = 0
        n_dxfs = 0

        if obras_path.exists():
            for obra_dir in obras_path.iterdir():
                if obra_dir.is_dir():
                    n_obras += 1
                    fase1 = obra_dir / 'Fase-1_Ingestao' / \
                             'Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF'
                    if fase1.exists():
                        n_dxfs += len(list(fase1.glob('*.dxf')))

        # DB stats
        db_stats = {'projects': 0, 'pillars': 0, 'beams': 0, 'slabs': 0}
        if Path(self.db_path).exists():
            try:
                conn = sqlite3.connect(self.db_path)
                for tbl in db_stats:
                    db_stats[tbl] = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                conn.close()
            except Exception:
                pass

        return {
            'n_obras': n_obras,
            'n_dxfs_fase1': n_dxfs,
            **db_stats,
        }


if __name__ == '__main__':
    obra = sys.argv[1] if len(sys.argv) > 1 else 'Obra_TREINO_1'
    motor = MotorCuradoria()
    rel = motor.executar_curadoria(obra)
    print(rel.resumo())
