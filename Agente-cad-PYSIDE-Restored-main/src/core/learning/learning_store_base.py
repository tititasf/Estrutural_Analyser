# src/core/learning/learning_store_base.py
"""
Classe base do Learning Store.
Interface comum para todas as classes estruturais (laje, pilar, viga lateral, viga fundo).

Features:
- Persistencia JSON (atomic write: .tmp + os.rename)
- Idempotencia por element_id + field_name + timestamp
- Thread-safe via file locking (msvcrt no Windows)
- Cache integrado (LearningStoreCache)
- Ajuste automatico de parametros apos N validacoes
"""
from __future__ import annotations

import json
import os
import hashlib
import threading
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .feedback_models import FeedbackEntry, LearnedParameter


MIN_SAMPLES_FOR_ADJUSTMENT = 5
MIN_SAMPLES_FOR_GLOBAL = 10


class LearningStoreBase:
    """Interface comum para todas as classes estruturais."""

    def __init__(self, project_uuid: str, class_type: str, base_dir: str = ""):
        self.project_uuid = project_uuid
        self.class_type = class_type
        self.base_dir = base_dir or os.getcwd()
        self.local_path = os.path.join(
            self.base_dir, "projects_repo", project_uuid, "learning",
            f"{class_type}_learning.json"
        )
        self.global_path = os.path.join(
            self.base_dir, "projects_repo", "global_learning",
            f"global_{class_type}_learning.json"
        )
        self._lock = threading.Lock()

    # ================================================================
    # PERSISTENCIA
    # ================================================================

    def _ensure_dirs(self) -> None:
        """Cria diretorios se nao existirem."""
        os.makedirs(os.path.dirname(self.local_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.global_path), exist_ok=True)

    def _load_local(self) -> dict:
        """Carrega JSON local. Retorna estrutura vazia se nao existe."""
        if not os.path.exists(self.local_path):
            return {"feedback_entries": [], "learned_parameters": []}
        try:
            with open(self.local_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"feedback_entries": [], "learned_parameters": []}

    def _atomic_write(self, path: str, data: dict) -> None:
        """Escrita atomica: escreve em .tmp + rename."""
        self._ensure_dirs()
        dir_path = os.path.dirname(path)
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # No Windows, os.replace e atomico
            os.replace(tmp_path, path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    # ================================================================
    # ESCRITA (apos feedback do usuario)
    # ================================================================

    def record_feedback(self, entry: FeedbackEntry) -> None:
        """Grava uma validacao do usuario.
        Idempotente por element_id + field_name + timestamp.
        Thread-safe via threading.Lock.
        """
        with self._lock:
            data = self._load_local()
            entries = data.get("feedback_entries", [])

            # Idempotencia: nao duplicar
            idem_key = entry.idempotency_key()
            existing_keys = {
                f"{e.get('element_id')}|{e.get('field_name')}|{e.get('timestamp')}"
                for e in entries
            }
            if idem_key not in existing_keys:
                entries.append(entry.to_dict())
                data["feedback_entries"] = entries
                self._atomic_write(self.local_path, data)

            # Recalcular parametros se amostras suficientes
            sample_count = sum(
                1 for e in entries
                if e.get("field_name") == entry.field_name
            )
            if sample_count >= MIN_SAMPLES_FOR_ADJUSTMENT:
                params = self._recompute_parameters(entry.field_name, entries)
                if params:
                    self._update_learned_parameters(data, entry.field_name, params)
                    self._atomic_write(self.local_path, data)

    def _recompute_parameters(self, field_name: str, entries: list) -> dict:
        """Recalcula parametros otimos baseado no historico de hits/misses."""
        field_entries = [
            e for e in entries
            if e.get("field_name") == field_name
        ]
        if len(field_entries) < MIN_SAMPLES_FOR_ADJUSTMENT:
            return {}

        hits = [e for e in field_entries if e.get("was_correct", False)]
        misses = [e for e in field_entries if not e.get("was_correct", False)]
        hit_rate = len(hits) / len(field_entries) if field_entries else 0.0

        conf_correct = [
            e.get("confidence_at_prediction", 0.0) for e in hits
        ]
        conf_wrong = [
            e.get("confidence_at_prediction", 0.0) for e in misses
        ]

        avg_conf_correct = sum(conf_correct) / len(conf_correct) if conf_correct else 0.0
        avg_conf_wrong = sum(conf_wrong) / len(conf_wrong) if conf_wrong else 0.0

        adjustments = {}

        # Confidence mal calibrado: acertando mas com baixa confidence
        if hit_rate > 0.8 and avg_conf_correct < 0.6:
            adjustments["confidence_boost"] = 0.15

        # Errando muito: reduz confidence e prefere teacher
        if hit_rate < 0.4:
            adjustments["confidence_penalty"] = 0.2
            adjustments["fallback_to_teacher"] = True

        # Bias sistemtico: sempre superestima ou subestima
        if misses:
            errors = []
            for e in misses:
                pred = e.get("predicted_value")
                actual = e.get("actual_value")
                if isinstance(pred, (int, float)) and isinstance(actual, (int, float)):
                    errors.append(pred - actual)
            if errors:
                error_bias = sum(errors) / len(errors)
                if abs(error_bias) > 0.1:
                    adjustments[f"{field_name}_bias_correction"] = -error_bias

        return adjustments

    def _update_learned_parameters(self, data: dict, field_name: str, params: dict) -> None:
        """Atualiza parametros aprendidos no data dict."""
        learned = data.get("learned_parameters", [])
        now = datetime.now().isoformat()

        field_entries = [
            e for e in data.get("feedback_entries", [])
            if e.get("field_name") == field_name
        ]
        hit_rate = (
            sum(1 for e in field_entries if e.get("was_correct")) / len(field_entries)
            if field_entries else 0.0
        )

        for param_name, param_value in params.items():
            # Atualizar existente ou criar novo
            found = False
            for lp in learned:
                if lp.get("field_name") == field_name and lp.get("parameter_name") == param_name:
                    lp["parameter_value"] = param_value
                    lp["sample_count"] = len(field_entries)
                    lp["hit_rate"] = hit_rate
                    lp["last_updated"] = now
                    found = True
                    break
            if not found:
                learned.append({
                    "class_type": self.class_type,
                    "field_name": field_name,
                    "context_key": "global",
                    "parameter_name": param_name,
                    "parameter_value": param_value,
                    "sample_count": len(field_entries),
                    "hit_rate": hit_rate,
                    "last_updated": now,
                })
        data["learned_parameters"] = learned

    # ================================================================
    # LEITURA (antes da deteccao)
    # ================================================================

    def get_field_stats(self, field_name: str, context_signature: dict = None) -> dict:
        """Retorna hit_rate, sample_count, parametros ajustados para um campo."""
        data = self._load_local()
        entries = data.get("feedback_entries", [])
        field_entries = [e for e in entries if e.get("field_name") == field_name]

        if not field_entries:
            return {
                "hit_rate": None,
                "sample_count": 0,
                "parameters": {},
                "needs_validation": True,
                "low_performance_warning": False,
            }

        hits = sum(1 for e in field_entries if e.get("was_correct", False))
        hit_rate = hits / len(field_entries)

        # Buscar parametros aprendidos
        learned = data.get("learned_parameters", [])
        params = {}
        for lp in learned:
            if lp.get("field_name") == field_name:
                params[lp["parameter_name"]] = lp["parameter_value"]

        return {
            "hit_rate": hit_rate,
            "sample_count": len(field_entries),
            "parameters": params,
            "needs_validation": len(field_entries) < MIN_SAMPLES_FOR_ADJUSTMENT,
            "low_performance_warning": hit_rate < 0.4 and len(field_entries) >= MIN_SAMPLES_FOR_ADJUSTMENT,
        }

    def get_adjusted_parameters(self, field_name: str = None) -> dict:
        """Retorna parametros ajustados pelo learning. Dict vazio se sem dados."""
        data = self._load_local()
        learned = data.get("learned_parameters", [])

        if field_name:
            return {
                lp["parameter_name"]: lp["parameter_value"]
                for lp in learned
                if lp.get("field_name") == field_name
            }
        else:
            # Todos os parametros, agrupados por field_name
            result = {}
            for lp in learned:
                fn = lp.get("field_name", "global")
                if fn not in result:
                    result[fn] = {}
                result[fn][lp["parameter_name"]] = lp["parameter_value"]
            return result

    def get_confidence_override(self, field_name: str, method: str) -> Optional[float]:
        """Se o learning tem dados suficientes, retorna confidence ajustado."""
        data = self._load_local()
        learned = data.get("learned_parameters", [])

        boost = None
        penalty = None
        for lp in learned:
            if lp.get("field_name") == field_name:
                if lp["parameter_name"] == "confidence_boost":
                    boost = lp["parameter_value"]
                elif lp["parameter_name"] == "confidence_penalty":
                    penalty = lp["parameter_value"]

        if penalty is not None:
            return max(0.0, 1.0 - penalty)
        if boost is not None:
            return min(1.0, 0.8 + boost)
        return None

    # ================================================================
    # PROMOCAO (local -> global)
    # ================================================================

    def promote_to_global(self) -> int:
        """Promove aprendizado local para global. Retorna count de registros."""
        data = self._load_local()
        entries = data.get("feedback_entries", [])

        # Filtrar entradas com amostras suficientes
        field_counts = {}
        for e in entries:
            fn = e.get("field_name", "")
            field_counts[fn] = field_counts.get(fn, 0) + 1

        stable_entries = [
            e for e in entries
            if field_counts.get(e.get("field_name", ""), 0) >= MIN_SAMPLES_FOR_GLOBAL
        ]

        if not stable_entries:
            return 0

        with self._lock:
            # Carregar global
            if os.path.exists(self.global_path):
                try:
                    with open(self.global_path, "r", encoding="utf-8") as f:
                        global_data = json.load(f)
                except (json.JSONDecodeError, IOError):
                    global_data = {"feedback_entries": [], "learned_parameters": []}
            else:
                global_data = {"feedback_entries": [], "learned_parameters": []}

            # Merge: adicionar entradas que nao existem no global
            existing_keys = {
                f"{e.get('element_id')}|{e.get('field_name')}|{e.get('timestamp')}"
                for e in global_data.get("feedback_entries", [])
            }

            added = 0
            for e in stable_entries:
                key = f"{e.get('element_id')}|{e.get('field_name')}|{e.get('timestamp')}"
                if key not in existing_keys:
                    global_data.setdefault("feedback_entries", []).append(e)
                    existing_keys.add(key)
                    added += 1

            # Merge learned parameters
            local_params = data.get("learned_parameters", [])
            global_params = global_data.setdefault("learned_parameters", [])
            for lp in local_params:
                found = False
                for gp in global_params:
                    if (gp.get("field_name") == lp.get("field_name") and
                        gp.get("parameter_name") == lp.get("parameter_name")):
                        gp.update(lp)
                        found = True
                        break
                if not found:
                    global_params.append(lp)

            self._atomic_write(self.global_path, global_data)

        return added

    # ================================================================
    # CONSULTAS
    # ================================================================

    def get_hit_rate(self, field_name: str = None) -> float:
        """Hit rate agregado por campo ou geral."""
        data = self._load_local()
        entries = data.get("feedback_entries", [])

        if field_name:
            entries = [e for e in entries if e.get("field_name") == field_name]

        if not entries:
            return 0.0
        hits = sum(1 for e in entries if e.get("was_correct", False))
        return hits / len(entries)

    def get_fields_needing_validation(self, min_samples: int = 3) -> list:
        """Campos com poucas amostras de feedback (prioridade para coletar)."""
        data = self._load_local()
        entries = data.get("feedback_entries", [])

        field_counts = {}
        for e in entries:
            fn = e.get("field_name", "")
            field_counts[fn] = field_counts.get(fn, 0) + 1

        return [fn for fn, count in field_counts.items() if count < min_samples]
