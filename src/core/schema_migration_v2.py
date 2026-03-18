"""
Schema Migration v2 -- Adiciona tabelas de apoio para features CAD-2.x

Tabelas criadas:
    1. pavimento_pi       -- Dados do Processo Interno por pavimento
    2. name_proximity_cache -- Cache de busca de nomes por proximidade textual
    3. element_extensions   -- Extensoes para elementos especiais (cambotado, misula, etc.)

Versionamento:
    Usa tabela _schema_version para rastrear migracoes executadas.
    Cada migracao e idempotente (verifica existencia antes de criar).

Uso:
    migration = SchemaMigrationV2('D:/Agente-cad-PYSIDE/project_data.vision')
    result = migration.run()
    print(result)  # {'pavimento_pi': True, 'name_proximity_cache': True, 'element_extensions': True}
"""

import sqlite3
import logging
from datetime import datetime, timezone
from typing import Dict

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2

MIGRATIONS = {
    'pavimento_pi': """
        CREATE TABLE IF NOT EXISTS pavimento_pi (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            pavimento_nome TEXT,
            pe_direito REAL,
            cota_saida REAL,
            delimitacao TEXT,
            area_pilar_m2 REAL,
            area_viga_m2 REAL,
            area_fundo_adicional_m2 REAL,
            area_laje_m2 REAL,
            area_tira_reesc_m2 REAL,
            jogos_formas INTEGER DEFAULT 1,
            fundos_adicionais INTEGER DEFAULT 0,
            tiras_reescoramento INTEGER DEFAULT 0,
            validated BOOLEAN DEFAULT FALSE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """,
    'name_proximity_cache': """
        CREATE TABLE IF NOT EXISTS name_proximity_cache (
            id TEXT PRIMARY KEY,
            entity_id TEXT NOT NULL,
            pavimento TEXT,
            entity_type TEXT,
            candidate_names_json TEXT,
            selected_name TEXT,
            confidence REAL,
            selection_source TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """,
    'element_extensions': """
        CREATE TABLE IF NOT EXISTS element_extensions (
            id TEXT PRIMARY KEY,
            entity_id TEXT NOT NULL,
            extension_type TEXT NOT NULL,
            extra_params_json TEXT,
            curvature_radius REAL,
            wall_thickness REAL,
            height REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """,
}

# Indices para performance
INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_pavimento_pi_project ON pavimento_pi(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_pavimento_pi_nome ON pavimento_pi(pavimento_nome)",
    "CREATE INDEX IF NOT EXISTS idx_name_prox_entity ON name_proximity_cache(entity_id)",
    "CREATE INDEX IF NOT EXISTS idx_name_prox_pav ON name_proximity_cache(pavimento)",
    "CREATE INDEX IF NOT EXISTS idx_name_prox_type ON name_proximity_cache(entity_type)",
    "CREATE INDEX IF NOT EXISTS idx_elem_ext_entity ON element_extensions(entity_id)",
    "CREATE INDEX IF NOT EXISTS idx_elem_ext_type ON element_extensions(extension_type)",
]

VERSION_TABLE_DDL = """
    CREATE TABLE IF NOT EXISTS _schema_version (
        version INTEGER PRIMARY KEY,
        description TEXT,
        applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
"""


class SchemaMigrationV2:
    """
    Migracao de schema v2 para project_data.vision.

    Cria 3 novas tabelas e indices, com versionamento para idempotencia.

    Uso:
        migration = SchemaMigrationV2('project_data.vision')
        result = migration.run()
        # result = {'pavimento_pi': True, 'name_proximity_cache': True, 'element_extensions': True}
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Abre conexao com o DB."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def check_version(self) -> int:
        """
        Retorna a versao atual do schema.

        Returns:
            Versao mais alta registrada, ou 0 se nenhuma migracao foi aplicada.
        """
        try:
            conn = self._get_connection()
            # Verificar se tabela _schema_version existe
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='_schema_version'"
            )
            if not cur.fetchone():
                conn.close()
                return 0

            cur = conn.execute("SELECT MAX(version) FROM _schema_version")
            row = cur.fetchone()
            conn.close()
            return row[0] if row and row[0] is not None else 0
        except Exception as e:
            logger.error(f"Erro ao verificar versao do schema: {e}")
            return 0

    def already_migrated(self, table_name: str) -> bool:
        """
        Verifica se uma tabela ja foi criada.

        Args:
            table_name: Nome da tabela.

        Returns:
            True se tabela existe no schema.
        """
        try:
            conn = self._get_connection()
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            exists = cur.fetchone() is not None
            conn.close()
            return exists
        except Exception as e:
            logger.error(f"Erro ao verificar tabela {table_name}: {e}")
            return False

    def run(self) -> Dict[str, bool]:
        """
        Executa todas as migracoes pendentes.

        Returns:
            Dict table_name -> True se criada com sucesso, False se erro/ja existe.
        """
        result: Dict[str, bool] = {}

        current_version = self.check_version()
        if current_version >= SCHEMA_VERSION:
            logger.info(f"Schema ja esta na versao {current_version}, nada a fazer")
            for table_name in MIGRATIONS:
                result[table_name] = self.already_migrated(table_name)
            return result

        try:
            conn = self._get_connection()

            # Garantir tabela de versao
            conn.execute(VERSION_TABLE_DDL)
            conn.commit()

            # Executar cada migracao
            for table_name, ddl in MIGRATIONS.items():
                try:
                    conn.execute(ddl)
                    result[table_name] = True
                    logger.info(f"Tabela '{table_name}' criada/verificada com sucesso")
                except Exception as e:
                    result[table_name] = False
                    logger.error(f"Erro ao criar tabela '{table_name}': {e}")

            # Criar indices
            for idx_ddl in INDICES:
                try:
                    conn.execute(idx_ddl)
                except Exception as e:
                    logger.warning(f"Erro ao criar indice: {e}")

            # Registrar versao
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO _schema_version (version, description, applied_at) VALUES (?, ?, ?)",
                (SCHEMA_VERSION, "CAD-2.x: pavimento_pi + name_proximity_cache + element_extensions", now)
            )
            conn.commit()
            conn.close()

            logger.info(f"Schema migrado para versao {SCHEMA_VERSION}: {result}")

        except Exception as e:
            logger.error(f"Erro fatal na migracao: {e}")
            for table_name in MIGRATIONS:
                if table_name not in result:
                    result[table_name] = False

        return result


if __name__ == '__main__':
    import sys

    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    )

    # Path do banco
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = 'D:/Agente-cad-PYSIDE/project_data.vision'

    print(f"=== Schema Migration v2 ===")
    print(f"DB: {db_path}")

    migration = SchemaMigrationV2(db_path)

    print(f"Versao atual: {migration.check_version()}")
    print(f"Executando migracoes...")

    result = migration.run()

    print(f"\nResultados:")
    for table, created in result.items():
        status = "OK" if created else "FALHA"
        print(f"  {table}: {status}")

    print(f"\nVersao apos migracao: {migration.check_version()}")
