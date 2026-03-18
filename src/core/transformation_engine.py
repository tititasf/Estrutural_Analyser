"""
Transformation Engine - Sprint 4
Nucleo do sistema de transformacao Fase 2 -> Fase 4.

Responsabilidades:
- Carregar regras de transformacao do project_data.vision
- Receber entity (beam, pillar, slab) e transformar para formato dos robos
- Aplicar DNA key lookup -> dna_frequency_map (alta precisao, baixa cobertura)
- Fallback para global_default quando DNA nao encontrado
- Cache em memoria para performance
- Log de transformacoes para auditoria

Workflow:
    StructuralEntity (do structural_vectorizer)
        -> TransformationEngine.transform(entity_type, entity_data, ...)
        -> Lookup na transformation_rules (por DNA key)
        -> Se encontrar: usar dna_frequency_map (most_common)
        -> Fallback: global_default da regra
        -> Retornar JSON para o robo correspondente
"""

import sqlite3
import json
import hashlib
import logging
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

VALID_ENTITY_TYPES = ('beam', 'pillar', 'slab')
VALID_TARGET_ROBOTS = ('Crane', 'Bolt', 'Slab', 'auto')

# Mapeamento entity_type -> prefixo de regra na transformation_rules
ENTITY_TO_RULE_PREFIX = {
    'beam': 'Viga_',
    'pillar': 'Pilar_',
    'slab': 'Laje_',
}

# Campos a retornar por tipo de entidade
ENTITY_OUTPUT_FIELDS = {
    'beam': [
        'Viga_name', 'Viga_dim', 'Viga_viga_segs',
        'Viga_viga_a_seg_1_ini_name', 'Viga_viga_a_seg_1_comprimento_total',
    ],
    'pillar': [
        'Pilar_name', 'Pilar_dim', 'Pilar_pilar_segs',
        'Pilar_p_sA_l1_n', 'Pilar_p_sA_l1_h',
        'Pilar_p_sA_l2_n', 'Pilar_p_sA_l2_h',
        'Pilar_p_sB_l1_n', 'Pilar_p_sB_l1_h',
    ],
    'slab': [
        'Laje_name', 'Laje_laje_dim', 'Laje_laje_outline_segs',
        'Laje_laje_nivel', 'Laje_laje_islands', 'Laje_id_item',
    ],
}


class TransformationEngine:
    """
    Motor de transformacao de entities estruturais para formato de robos.

    Workflow:
    1. Recebe entity (beam, pillar, slab) do StructuralVectorizer
    2. Gera DNA key a partir das features
    3. Busca na transformation_rules (dna_frequency_map)
    4. Fallback para global_default se DNA nao encontrado
    5. Retorna dict com os campos preditos para o robo

    Uso:
        engine = TransformationEngine(db_path=Path('project_data.vision'))
        result = engine.transform(
            entity_type='beam',
            entity_data={'features': [1.0,0.0,0.0,1.0,...], 'layer': 'Paineis'},
            target_robot='Crane',
        )
        if result['status'] == 'success':
            predicted = result['fields']  # {'Viga_name': 'V1a', 'Viga_dim': '19/53', ...}
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        enable_cache: bool = True,
        enable_logging: bool = True,
    ):
        self.db_path = db_path or Path('project_data.vision')
        self.enable_cache = enable_cache
        self.enable_logging = enable_logging

        self._rules_cache: Dict[str, Dict] = {}   # rule_name -> rule dict
        self._dna_cache: Dict[str, str] = {}       # (rule_name, dna_key) -> predicted_value
        self._stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'dna_matches': 0,
            'global_fallbacks': 0,
            'skipped': 0,
            'errors': 0,
        }

        self._load_rules()
        logger.info(
            f"TransformationEngine initialized (cache={enable_cache}, logging={enable_logging})"
        )

    def _load_rules(self):
        """Carrega todas as regras de transformacao do DB."""
        if not Path(self.db_path).exists():
            logger.warning(f"DB not found: {self.db_path}")
            return

        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cur = conn.execute("""
                SELECT name, entity_type, rule_logic, accuracy_pct, is_production, status
                FROM transformation_rules
                WHERE status = 'active'
            """)
            for row in cur.fetchall():
                rule = dict(row)
                try:
                    rule['rule_logic'] = json.loads(rule['rule_logic'])
                except (json.JSONDecodeError, TypeError):
                    rule['rule_logic'] = {}
                self._rules_cache[row['name']] = rule
            conn.close()
            logger.info(f"Loaded {len(self._rules_cache)} transformation rules")
        except Exception as e:
            logger.error(f"Error loading transformation rules: {e}")

    def transform(
        self,
        entity_type: str,
        entity_data: Dict[str, Any],
        target_robot: str = 'auto',
        obra: str = '',
        pavimento: str = '',
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Transforma entity em JSON para robo.

        Args:
            entity_type: Tipo da entity ('beam', 'pillar', 'slab')
            entity_data: Dict com features, layer, text_content, dna_key, etc.
            target_robot: Robot de destino ('Crane', 'Bolt', 'Slab', 'auto')
            obra: Nome da obra (para context-aware prediction)
            pavimento: Nome do pavimento
            config: Configuracao opcional

        Returns:
            Dict com: status, id, fields, confidence, rule_name, errors
        """
        if entity_type not in VALID_ENTITY_TYPES:
            return {'status': 'error', 'id': 'unknown', 'error': f'Invalid entity_type: {entity_type}'}

        if target_robot not in VALID_TARGET_ROBOTS:
            return {'status': 'error', 'id': 'unknown', 'error': f'Invalid target_robot: {target_robot}'}

        # Generate entity ID
        entity_id = entity_data.get('entity_id') or entity_data.get('id', 'unknown')
        dna_key = entity_data.get('dna_key', '')

        # Check cache
        cache_key = f"{entity_type}:{dna_key}:{obra}"
        if self.enable_cache and cache_key in self._dna_cache:
            self._stats['cache_hits'] += 1
            logger.debug(f"Cache hit: {entity_id} -> {cache_key}")
            return self._dna_cache[cache_key]

        self._stats['cache_misses'] += 1

        # Get rules for this entity type
        prefix = ENTITY_TO_RULE_PREFIX.get(entity_type, '')
        relevant_rules = {
            name: rule for name, rule in self._rules_cache.items()
            if name.startswith(prefix)
        }

        if not relevant_rules:
            self._stats['skipped'] += 1
            return {
                'status': 'skipped',
                'id': entity_id,
                'error': f'No transformation rules found for {entity_type}',
                'fields': {},
            }

        # Predict each field
        fields = {}
        confidence_scores = []
        errors = []
        applied_rules = []

        output_fields = ENTITY_OUTPUT_FIELDS.get(entity_type, [])
        for field_name in output_fields:
            if field_name not in relevant_rules:
                continue

            rule = relevant_rules[field_name]
            predicted, conf, source = self._predict_field(
                rule=rule,
                dna_key=dna_key,
                entity_data=entity_data,
                obra=obra,
            )

            if predicted is not None:
                fields[field_name] = predicted
                confidence_scores.append(conf)
                applied_rules.append(f"{field_name}({source}:{conf:.2f})")
            else:
                errors.append(f"No prediction for {field_name}")

        if not fields:
            self._stats['errors'] += 1
            return {
                'status': 'error',
                'id': entity_id,
                'error': f'All rules failed for {entity_type}:{entity_id}',
                'fields': {},
                'errors': errors,
            }

        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0

        # Validate (basic checks)
        validation_errors = self._validate(entity_type, fields)
        if validation_errors:
            logger.warning(f"Validation failed: {entity_id}: {validation_errors}")

        result = {
            'status': 'success',
            'id': entity_id,
            'entity_type': entity_type,
            'fields': fields,
            'confidence': round(avg_confidence, 3),
            'rule_name': ', '.join(applied_rules[:3]),
            'errors': validation_errors,
        }

        if self.enable_cache:
            self._dna_cache[cache_key] = result

        if self.enable_logging:
            self._log_transformation(entity_type, entity_id, obra, pavimento, result)

        return result

    def _predict_field(
        self,
        rule: Dict,
        dna_key: str,
        entity_data: Dict,
        obra: str,
    ) -> Tuple[Optional[str], float, str]:
        """
        Prediz o valor de um campo.

        Strategy:
        1. DNA key lookup in dna_frequency_map (high precision)
        2. Fallback to global_default (lower precision, higher coverage)

        Returns: (predicted_value, confidence, source)
        """
        logic = rule.get('rule_logic', {})
        dna_map = logic.get('dna_frequency_map', {})
        global_default = logic.get('global_default')
        global_accuracy = logic.get('global_accuracy', 0.5)

        # 1. DNA key match
        if dna_key and dna_key in dna_map:
            entry = dna_map[dna_key]
            if isinstance(entry, dict):
                most_common = entry.get('most_common')
                count = entry.get('count', 1)
                total = sum(entry.get('distribution', {v: count}).values())
                conf = count / total if total > 0 else 0.5
            else:
                most_common = entry
                conf = 0.7
            if most_common:
                self._stats['dna_matches'] += 1
                return most_common, conf, 'dna'

        # 2. Global default fallback
        if global_default:
            self._stats['global_fallbacks'] += 1
            return global_default, global_accuracy, 'global'

        return None, 0.0, 'none'

    def _validate(self, entity_type: str, fields: Dict) -> List[str]:
        """Validacoes basicas dos campos preditos."""
        errors = []

        if entity_type == 'beam':
            name = fields.get('Viga_name', '')
            if name and not (name.startswith('V') or name.startswith('v')):
                errors.append(f"Viga_name '{name}' nao comeca com V")

        elif entity_type == 'pillar':
            name = fields.get('Pilar_name', '')
            if name and not (name.startswith('P') or name.startswith('p')):
                errors.append(f"Pilar_name '{name}' nao comeca com P")

        elif entity_type == 'slab':
            name = fields.get('Laje_name', '')
            if name and not (name.startswith('L') or name.startswith('l')):
                errors.append(f"Laje_name '{name}' nao comeca com L")

        return errors

    def _log_transformation(
        self, entity_type: str, entity_id: str,
        obra: str, pavimento: str, result: Dict
    ):
        """Log da transformacao (pode ser sobrescrito para persistir em DB)."""
        status = result.get('status', 'unknown')
        conf = result.get('confidence', 0)
        logger.debug(
            f"Transform {entity_type}:{entity_id} obra={obra} pav={pavimento} "
            f"status={status} conf={conf:.2f}"
        )

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatisticas de uso do engine."""
        return {
            **self._stats,
            'rules_loaded': len(self._rules_cache),
            'cache_size': len(self._dna_cache),
            'hit_rate': (
                self._stats['cache_hits'] /
                max(1, self._stats['cache_hits'] + self._stats['cache_misses'])
            ),
        }

    def reload_rules(self):
        """Recarrega regras do DB (apos atualizacao)."""
        self._rules_cache.clear()
        self._dna_cache.clear()
        self._load_rules()
        logger.info("Rules reloaded")
