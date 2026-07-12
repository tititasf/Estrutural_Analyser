"""Log de auditoria (STORY-04, AC 5) — JSONL append-only, arquivo FISICAMENTE
distinto de `public_consulta.db` (que permanece `mode=ro`, nunca escrito pela
zona pública). Único ponto de escrita da API pública.

O código consultado nunca é gravado em texto puro — só um hash truncado
(12 hex chars), pra não virar, ele mesmo, uma superfície de enumeração caso
o log vaze (AC 5, subtask 4.3).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class AuditLogger:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, evento: dict) -> None:
        evento = {"ts": datetime.now(timezone.utc).isoformat(), **evento}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(evento, ensure_ascii=False) + "\n")

    @staticmethod
    def hash_code(code: Optional[str]) -> Optional[str]:
        if not code:
            return None
        return hashlib.sha256(code.encode("utf-8")).hexdigest()[:12]

    def log_acesso(self, *, ip: str, path: str, status: int, code: Optional[str] = None) -> None:
        self._write({
            "tipo": "acesso", "ip": ip, "path": path, "status": status,
            "code_hash": self.hash_code(code),
        })

    def log_evento(self, tipo: str, **kwargs) -> None:
        self._write({"tipo": tipo, **kwargs})
