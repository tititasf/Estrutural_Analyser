# -*- coding: utf-8 -*-
"""Pipeline Orchestrator - GAP-7

Orquestrador do pipeline de processamento de obras com estado persistente e checkpoint/resume.
SPRINT 13: Otimizações de Performance
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Importar fases do pipeline
try:
    from phases.fase1_ingestao import Fase1Ingestao, IngestaoResultado
    from phases.fase2_triagem import Fase2Triagem, TriagemResultado
    from phases.fase3_interpretacao import Fase3Interpretacao, InterpretacaoResultado
    from phases.fase3_revisor import Fase3Revisor
    FASES_DISPONIVEIS = True
except ImportError:
    FASES_DISPONIVEIS = False
    Fase1Ingestao = None
    Fase2Triagem = None
    Fase3Interpretacao = None
    InterpretacaoResultado = None
    Fase3Revisor = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Orquestrador do pipeline de processamento de obras com checkpoint/resume."""
    
    FASES = {
        1: "Ingestao",
        2: "Triagem",
        3: "Interpretacao",
        4: "Sincronizacao",
        5: "Geracao de Scripts",
        6: "Execucao CAD",
        7: "Consolidacao",
        8: "Revisao",
    }
    
    def __init__(self, db_path: str = "project_data.vision"):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._connect()
        self._ensure_tables()
        logger.info(f"PipelineOrchestrator inicializado com DB: {db_path}")
    
    def _connect(self) -> sqlite3.Connection:
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path, timeout=30.0)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.conn.execute("PRAGMA journal_mode = WAL")
        return self.conn
    
    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def _ensure_tables(self):
        cursor = self.conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS obras (
                id TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                pasta_origem TEXT NOT NULL,
                data_ingestao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fase_atual INTEGER DEFAULT 1,
                status TEXT DEFAULT 'iniciado',
                CHECK (status IN ('iniciado', 'em_processamento', 'pausado', 'completo', 'erro'))
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_state (
                obra_id TEXT PRIMARY KEY,
                fase_atual INTEGER DEFAULT 1,
                fases_completas TEXT DEFAULT '[]',
                fase_em_andamento TEXT,
                ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (obra_id) REFERENCES obras(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fase3_fichas (
                id TEXT PRIMARY KEY,
                obra_id TEXT,
                pavimento TEXT,
                tipo TEXT,
                codigo TEXT,
                dados_json TEXT,
                confidence REAL,
                revisado BOOLEAN DEFAULT FALSE,
                revisado_por TEXT,
                data_revisao TIMESTAMP,
                FOREIGN KEY (obra_id) REFERENCES obras(id)
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fichas_obra ON fase3_fichas(obra_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fichas_tipo ON fase3_fichas(tipo)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fichas_pavimento ON fase3_fichas(pavimento)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_obras_status ON obras(status)")
        
        # Tabela para metadata de ingestão
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ingestao_metadata (
                obra_id TEXT PRIMARY KEY,
                dxf_count INTEGER DEFAULT 0,
                pdf_count INTEGER DEFAULT 0,
                fotos_count INTEGER DEFAULT 0,
                entidades_count INTEGER DEFAULT 0,
                tempo_total REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (obra_id) REFERENCES obras(id)
            )
        """)
        
        # Tabela para metadata de triagem
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS triagem_metadata (
                obra_id TEXT PRIMARY KEY,
                pavimentos_count INTEGER DEFAULT 0,
                entidades_nomeadas INTEGER DEFAULT 0,
                detalhes_count INTEGER DEFAULT 0,
                indice_criado INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (obra_id) REFERENCES obras(id)
            )
        """)
        
        # Tabela de checkpoint (SPRINT 13)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_checkpoint (
                id TEXT PRIMARY KEY,
                obra_id TEXT NOT NULL,
                fase INTEGER NOT NULL,
                estado_json TEXT NOT NULL,
                progresso REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (obra_id) REFERENCES obras(id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_checkpoint_obra ON pipeline_checkpoint(obra_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_checkpoint_fase ON pipeline_checkpoint(fase)")
        
        # Tabela de métricas de performance (SPRINT 13)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id TEXT PRIMARY KEY,
                obra_id TEXT NOT NULL,
                fase INTEGER NOT NULL,
                tempo_inicio TIMESTAMP,
                tempo_fim TIMESTAMP,
                tempo_total_seg REAL,
                arquivos_processados INTEGER DEFAULT 0,
                entidades_processadas INTEGER DEFAULT 0,
                cache_hits INTEGER DEFAULT 0,
                cache_misses INTEGER DEFAULT 0,
                memoria_peak_mb REAL,
                workers_usados INTEGER,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (obra_id) REFERENCES obras(id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_performance_metrics_obra ON performance_metrics(obra_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_performance_metrics_fase ON performance_metrics(fase)")
        
        self.conn.commit()
    
    def registrar_obra(self, nome: str, pasta_origem: str) -> str:
        """Registra uma nova obra no sistema."""
        obra_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO obras (id, nome, pasta_origem, fase_atual, status)
                VALUES (?, ?, ?, 1, 'iniciado')
            """, (obra_id, nome, pasta_origem))
            
            cursor.execute("""
                INSERT INTO pipeline_state (obra_id, fase_atual, fases_completas, fase_em_andamento)
                VALUES (?, 1, '[]', ?)
            """, (obra_id, json.dumps({"fase": 1, "inicio": None, "progresso": 0})))
            
            self.conn.commit()
            logger.info(f"Obra registrada: {nome} (ID: {obra_id})")
            return obra_id
            
        except sqlite3.Error as e:
            self.conn.rollback()
            logger.error(f"Erro ao registrar obra: {e}")
            raise
    
    def get_obra(self, obra_id: str) -> Optional[Dict[str, Any]]:
        """Obtem informacoes de uma obra pelo ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM obras WHERE id = ?", (obra_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_obra_por_nome(self, nome: str) -> Optional[Dict[str, Any]]:
        """Obtem informacoes de uma obra pelo nome."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM obras WHERE nome = ?", (nome,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def listar_obras(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista todas as obras, opcionalmente filtradas por status."""
        cursor = self.conn.cursor()
        
        if status:
            cursor.execute("SELECT * FROM obras WHERE status = ? ORDER BY data_ingestao DESC", (status,))
        else:
            cursor.execute("SELECT * FROM obras ORDER BY data_ingestao DESC")
        
        return [dict(row) for row in cursor.fetchall()]
    
    def atualizar_status_obra(self, obra_id: str, status: str):
        """Atualiza o status de uma obra."""
        if status not in ('iniciado', 'em_processamento', 'pausado', 'completo', 'erro'):
            raise ValueError(f"Status invalido: {status}")
        
        cursor = self.conn.cursor()
        cursor.execute("UPDATE obras SET status = ? WHERE id = ?", (status, obra_id))
        self.conn.commit()
        logger.info(f"Obra {obra_id} atualizada para status: {status}")
    
    def get_pipeline_state(self, obra_id: str) -> Dict[str, Any]:
        """Obtem o estado do pipeline de uma obra."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM pipeline_state WHERE obra_id = ?", (obra_id,))
        row = cursor.fetchone()
        
        if not row:
            return {"obra_id": obra_id, "fase_atual": 1, "fases_completas": [], "fase_em_andamento": None, "ultima_atualizacao": None}
        
        state = dict(row)
        state["fases_completas"] = json.loads(state["fases_completas"] or "[]")
        state["fase_em_andamento"] = json.loads(state["fase_em_andamento"]) if state["fase_em_andamento"] else None
        
        return state
    
    def update_fase_atual(self, obra_id: str, fase: int):
        """Atualiza a fase atual de uma obra."""
        if fase < 1 or fase > 8:
            raise ValueError(f"Fase invalida: {fase}. Deve ser entre 1 e 8.")
        
        cursor = self.conn.cursor()
        
        cursor.execute("""
            UPDATE pipeline_state 
            SET fase_atual = ?, 
                fase_em_andamento = ?,
                ultima_atualizacao = CURRENT_TIMESTAMP
            WHERE obra_id = ?
        """, (fase, json.dumps({"fase": fase, "inicio": str(datetime.now()), "progresso": 0}), obra_id))
        
        cursor.execute("UPDATE obras SET fase_atual = ? WHERE id = ?", (fase, obra_id))
        
        self.conn.commit()
        logger.info(f"Obra {obra_id} atualizada para fase {fase}")
    
    def marcar_fase_completa(self, obra_id: str, fase: int):
        """Marca uma fase como completa."""
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT fases_completas FROM pipeline_state WHERE obra_id = ?", (obra_id,))
        row = cursor.fetchone()
        
        if row:
            fases_completas = json.loads(row["fases_completas"] or "[]")
        else:
            fases_completas = []
        
        if fase not in fases_completas:
            fases_completas.append(fase)
            fases_completas.sort()
        
        proxima_fase = fase + 1 if fase < 8 else 8
        
        cursor.execute("""
            UPDATE pipeline_state 
            SET fases_completas = ?,
                fase_atual = ?,
                fase_em_andamento = ?,
                ultima_atualizacao = CURRENT_TIMESTAMP
            WHERE obra_id = ?
        """, (json.dumps(fases_completas), proxima_fase, None, obra_id))
        
        cursor.execute("UPDATE obras SET fase_atual = ? WHERE id = ?", (proxima_fase, obra_id))
        
        self.conn.commit()
        logger.info(f"Fase {fase} marcada como completa para obra {obra_id}")
    
    def get_fases_completas(self, obra_id: str) -> List[int]:
        """Obtem lista de fases completas de uma obra."""
        state = self.get_pipeline_state(obra_id)
        return state.get("fases_completas", [])
    
    def get_ultima_fase_nao_completa(self, obra_id: str) -> int:
        """Obtem a ultima fase que nao foi completada."""
        fases_completas = self.get_fases_completas(obra_id)
        
        for fase in range(1, 9):
            if fase not in fases_completas:
                return fase
        
        return 8
    
    # =========================================================================
    # CHECKPOINT/RESUME - SPRINT 13
    # =========================================================================
    
    def salvar_checkpoint(self, obra_id: str, fase: int, estado: Dict[str, Any], progresso: float = 0) -> str:
        """Salva checkpoint de uma fase em execução."""
        checkpoint_id = f"checkpoint_{obra_id}_fase{fase}_{int(time.time())}"
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO pipeline_checkpoint 
            (id, obra_id, fase, estado_json, progresso, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (checkpoint_id, obra_id, fase, json.dumps(estado), progresso))
        
        self.conn.commit()
        logger.debug(f"Checkpoint salvo para obra {obra_id} fase {fase} (progresso: {progresso:.1%})")
        return checkpoint_id
    
    def carregar_checkpoint(self, obra_id: str, fase: int) -> Optional[Dict[str, Any]]:
        """Carrega o último checkpoint de uma fase específica."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT estado_json, progresso, created_at 
            FROM pipeline_checkpoint 
            WHERE obra_id = ? AND fase = ?
            ORDER BY updated_at DESC
            LIMIT 1
        """, (obra_id, fase))
        
        row = cursor.fetchone()
        if row:
            estado = json.loads(row["estado_json"])
            estado["progresso"] = row["progresso"]
            estado["criado_em"] = row["created_at"]
            logger.info(f"Checkpoint carregado para obra {obra_id} fase {fase}")
            return estado
        return None
    
    def deletar_checkpoint(self, obra_id: str, fase: Optional[int] = None) -> int:
        """Deleta checkpoints de uma obra ou fase específica."""
        cursor = self.conn.cursor()
        
        if fase is not None:
            cursor.execute("DELETE FROM pipeline_checkpoint WHERE obra_id = ? AND fase = ?", (obra_id, fase))
        else:
            cursor.execute("DELETE FROM pipeline_checkpoint WHERE obra_id = ?", (obra_id,))
        
        count = cursor.rowcount
        self.conn.commit()
        return count
    
    def listar_checkpoints(self, obra_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista todos os checkpoints ou de uma obra específica."""
        cursor = self.conn.cursor()
        
        if obra_id:
            cursor.execute("""
                SELECT id, obra_id, fase, estado_json, progresso, created_at, updated_at
                FROM pipeline_checkpoint 
                WHERE obra_id = ?
                ORDER BY fase, updated_at DESC
            """, (obra_id,))
        else:
            cursor.execute("""
                SELECT id, obra_id, fase, estado_json, progresso, created_at, updated_at
                FROM pipeline_checkpoint 
                ORDER BY obra_id, fase, updated_at DESC
            """)
        
        checkpoints = []
        for row in cursor.fetchall():
            checkpoints.append({
                "id": row["id"],
                "obra_id": row["obra_id"],
                "fase": row["fase"],
                "progresso": row["progresso"],
                "criado_em": row["created_at"],
                "atualizado_em": row["updated_at"]
            })
        
        return checkpoints
    
    def retomar_de_fase(self, obra_id: str, fase: int) -> bool:
        """Retoma o processamento de uma fase específica."""
        obra = self.get_obra(obra_id)
        if not obra:
            logger.error(f"Obra nao encontrada: {obra_id}")
            return False
        
        checkpoint = self.carregar_checkpoint(obra_id, fase)
        if checkpoint:
            logger.info(f"Retomando fase {fase} do checkpoint (progresso: {checkpoint.get('progresso', 0):.1%})")
        else:
            logger.info(f"Retomando fase {fase} sem checkpoint anterior")
        
        return self.executar_fase(obra_id, fase, checkpoint=checkpoint)
    
    def executar_com_checkpoint(self, obra_id: str, fase: int, **kwargs) -> bool:
        """Executa uma fase com salvamento automático de checkpoints."""
        if fase < 1 or fase > 8:
            logger.error(f"Fase invalida: {fase}")
            return False
        
        obra = self.get_obra(obra_id)
        if not obra:
            logger.error(f"Obra nao encontrada: {obra_id}")
            return False
        
        logger.info(f"[Pipeline] Iniciando Fase {fase} - {self.FASES[fase]} para obra {obra['nome']}")
        
        self.update_fase_atual(obra_id, fase)
        self.atualizar_status_obra(obra_id, "em_processamento")
        
        try:
            sucesso = False
            
            if fase == 1:
                sucesso = self._executar_fase1_ingestao(obra_id, **kwargs)
            elif fase == 2:
                sucesso = self._executar_fase2_triagem(obra_id, **kwargs)
            elif fase == 3:
                sucesso = self._executar_fase3_interpretacao(obra_id, **kwargs)
            elif fase == 4:
                sucesso = self._executar_fase4_sincronizacao(obra_id, **kwargs)
            elif fase == 5:
                sucesso = self._executar_fase5_geracao_scripts(obra_id, **kwargs)
            elif fase == 6:
                sucesso = self._executar_fase6_execucao_cad(obra_id, **kwargs)
            elif fase == 7:
                sucesso = self._executar_fase7_consolidacao(obra_id, **kwargs)
            elif fase == 8:
                sucesso = self._executar_fase8_revisao(obra_id, **kwargs)
            
            if sucesso:
                self.marcar_fase_completa(obra_id, fase)
                self.deletar_checkpoint(obra_id, fase)  # Limpa checkpoint após sucesso
                logger.info(f"[Pipeline] Fase {fase} completada com sucesso")
            else:
                self.atualizar_status_obra(obra_id, "erro")
                logger.error(f"[Pipeline] Fase {fase} falhou")
            
            return sucesso
            
        except Exception as e:
            self.atualizar_status_obra(obra_id, "erro")
            logger.error(f"[Pipeline] Erro na fase {fase}: {e}")
            return False
    
    # =========================================================================
    # MÉTODOS DE EXECUÇÃO DE FASES
    # =========================================================================
    
    def executar_fase(self, obra_id: str, fase: int, checkpoint: Optional[Dict] = None, **kwargs) -> bool:
        """Executa uma fase especifica do pipeline."""
        return self.executar_com_checkpoint(obra_id, fase, checkpoint=checkpoint, **kwargs)
    
    def executar_todas_fases(self, obra_id: str) -> bool:
        """Executa todas as fases em sequencia."""
        logger.info(f"[Pipeline] Iniciando execucao completa para obra {obra_id}")
        
        for fase in range(1, 9):
            logger.info(f"[Pipeline] === FASE {fase} - {self.FASES[fase]} ===")
            
            if not self.executar_com_checkpoint(obra_id, fase):
                logger.error(f"[Pipeline] Execucao interrompida na fase {fase}")
                return False
        
        self.atualizar_status_obra(obra_id, "completo")
        logger.info(f"[Pipeline] Execucao completa para obra {obra_id}")
        return True
    
    def retomar_processamento(self, obra_id: str) -> bool:
        """Retoma o processamento da ultima fase nao completada."""
        obra = self.get_obra(obra_id)
        if not obra:
            logger.error(f"Obra nao encontrada: {obra_id}")
            return False
        
        if obra["status"] == "completo":
            logger.info(f"Obra {obra['nome']} ja esta completa")
            return True
        
        proxima_fase = self.get_ultima_fase_nao_completa(obra_id)
        
        logger.info(f"Retomando processamento da fase {proxima_fase}")
        
        if obra["status"] == "pausado":
            self.atualizar_status_obra(obra_id, "em_processamento")
        
        return self.retomar_de_fase(obra_id, proxima_fase)
    
    def _executar_fase1_ingestao(self, obra_id: str, checkpoint: Optional[Dict] = None, **kwargs) -> bool:
        """Fase 1: Ingestão de DXF/PDF/Fotos com otimizações SPRINT 13."""
        logger.info(f"[{obra_id}] Iniciando Fase 1 - Ingestão (OTIMIZADA)")
        
        try:
            obra = self.get_obra(obra_id)
            if not obra:
                logger.error(f"Obra não encontrada: {obra_id}")
                return False
            
            pasta_origem = obra["pasta_origem"]
            
            # Verificar se fases estão disponíveis
            if not FASES_DISPONIVEIS:
                logger.warning("Fases não disponíveis, executando placeholder")
                logger.info(f"[{obra_id}] Fase 1: Ingestão placeholder completada")
                return True
            
            # Executar ingestão otimizada
            ingestao = Fase1Ingestao(pasta_origem, self.db_path, usar_cache=True)
            resultado = ingestao.executar(obra_id)
            
            logger.info(f"[{obra_id}] Fase 1: {resultado.arquivos_processados} arquivos, "
                       f"{resultado.entidades_extraidas} entidades em {resultado.tempo_total_seg:.2f}s")
            logger.info(f"[{obra_id}] Cache: {resultado.cache_hits} hits, {resultado.cache_misses} misses")
            
            if resultado.erros:
                logger.warning(f"[{obra_id}] Erros na ingestão: {resultado.erros}")
            
            # Salvar metadados da ingestão
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO ingestao_metadata 
                (obra_id, dxf_count, pdf_count, fotos_count, entidades_count, tempo_total)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                obra_id,
                resultado.dxf_ingestados,
                resultado.pdf_ingestados,
                resultado.fotos_ingestadas,
                resultado.entidades_extraidas,
                resultado.tempo_total_seg
            ))
            
            # Salvar métricas de performance
            self._salvar_performance_metric(obra_id, 1, resultado.tempo_total_seg,
                                           resultado.arquivos_processados, resultado.entidades_extraidas,
                                           resultado.cache_hits, resultado.cache_misses)
            
            self.conn.commit()
            
            ingestao.close()
            
            return len(resultado.erros) == 0 or resultado.dxf_ingestados > 0
            
        except Exception as e:
            logger.error(f"[{obra_id}] Erro na Fase 1: {e}")
            return False
    
    def _executar_fase2_triagem(self, obra_id: str, checkpoint: Optional[Dict] = None, **kwargs) -> bool:
        """Fase 2: Triagem e separação de pavimentos"""
        logger.info(f"[{obra_id}] Iniciando Fase 2 - Triagem")
        
        try:
            obra = self.get_obra(obra_id)
            if not obra:
                logger.error(f"Obra não encontrada: {obra_id}")
                return False
            
            pasta_origem = obra["pasta_origem"]
            
            if not FASES_DISPONIVEIS:
                logger.warning("Fases não disponíveis, executando placeholder")
                logger.info(f"[{obra_id}] Fase 2: Triagem placeholder completada")
                return True
            
            triagem = Fase2Triagem(pasta_origem, self.db_path)
            resultado = triagem.executar(obra_id)
            
            logger.info(f"[{obra_id}] Fase 2: {len(resultado.pavimentos_encontrados)} pavimentos, "
                       f"{resultado.entidades_nomeadas} entidades nomeadas")
            
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO triagem_metadata 
                (obra_id, pavimentos_count, entidades_nomeadas, detalhes_count, indice_criado)
                VALUES (?, ?, ?, ?, ?)
            """, (
                obra_id,
                len(resultado.pavimentos_encontrados),
                resultado.entidades_nomeadas,
                resultado.detalhes_separados,
                1 if resultado.indice_espacial_criado else 0
            ))
            
            self.conn.commit()
            
            triagem.close()
            
            return True
            
        except Exception as e:
            logger.error(f"[{obra_id}] Erro na Fase 2: {e}")
            return False
    
    def _executar_fase3_interpretacao(self, obra_id: str, checkpoint: Optional[Dict] = None, **kwargs) -> bool:
        """Fase 3: Interpretação e Extração"""
        logger.info(f"[{obra_id}] Iniciando Fase 3 - Interpretação")
        
        try:
            obra = self.get_obra(obra_id)
            if not obra:
                logger.error(f"Obra não encontrada: {obra_id}")
                return False
            
            if not FASES_DISPONIVEIS or Fase3Interpretacao is None:
                logger.warning("Fase 3 não disponível, executando placeholder")
                return True
            
            interpretacao = Fase3Interpretacao(self.db_path)
            resultado = interpretacao.executar(obra_id)
            
            logger.info(f"[{obra_id}] Fase 3: {len(resultado.pilares)} pilares, "
                       f"{len(resultado.vigas)} vigas, {len(resultado.lajes)} lajes")
            logger.info(f"[{obra_id}] Accuracy média: {resultado.accuracy_media:.2%}")
            
            if resultado.erros:
                for erro in resultado.erros:
                    logger.warning(f"[{obra_id}] Erro Fase 3: {erro}")
            
            interpretacao.close()
            
            return resultado.total_fichas > 0
            
        except Exception as e:
            logger.error(f"[{obra_id}] Erro na Fase 3: {e}")
            return False
    
    def _executar_fase4_sincronizacao(self, obra_id: str, **kwargs) -> bool:
        logger.info(f"[{obra_id}] Iniciando Fase 4 - Sincronizacao")
        
        try:
            obra = self.get_obra(obra_id)
            if not obra:
                logger.error(f"Obra nao encontrada: {obra_id}")
                return False
            
            pasta_origem = obra["pasta_origem"]
            pasta_fase3 = os.path.join(pasta_origem, "Fase-3")
            pasta_fase4 = os.path.join(pasta_origem, "Fase-4")
            
            if not os.path.exists(pasta_fase3):
                logger.info(f"[{obra_id}] Criando pastas Fase-3 e Fase-4 vazias")
                os.makedirs(pasta_fase3, exist_ok=True)
                os.makedirs(pasta_fase4, exist_ok=True)
                return True
            
            fichas_pilares = self._carregar_fichas(obra_id, "pilar")
            fichas_vigas = self._carregar_fichas(obra_id, "viga")
            fichas_lajes = self._carregar_fichas(obra_id, "laje")
            
            logger.info(f"[{obra_id}] Fichas carregadas: {len(fichas_pilares)} pilares, {len(fichas_vigas)} vigas, {len(fichas_lajes)} lajes")
            
            os.makedirs(pasta_fase4, exist_ok=True)
            
            if fichas_pilares:
                fichas_pilares_json = os.path.join(pasta_fase3, "fichas_pilares.json")
                self._salvar_fichas_json(fichas_pilares, fichas_pilares_json)
            
            if fichas_vigas:
                fichas_vigas_json = os.path.join(pasta_fase3, "fichas_vigas.json")
                self._salvar_fichas_json(fichas_vigas, fichas_vigas_json)
            
            if fichas_lajes:
                fichas_lajes_json = os.path.join(pasta_fase3, "fichas_lajes.json")
                self._salvar_fichas_json(fichas_lajes, fichas_lajes_json)
            
            logger.info(f"[{obra_id}] Fase 4 completada com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"[{obra_id}] Erro na Fase 4: {e}")
            return False
    
    def _executar_fase5_geracao_scripts(self, obra_id: str, **kwargs) -> bool:
        logger.info(f"[{obra_id}] Fase 5 - Geracao de Scripts: Nao implementada ainda")
        return True
    
    def _executar_fase6_execucao_cad(self, obra_id: str, **kwargs) -> bool:
        logger.info(f"[{obra_id}] Fase 6 - Execucao CAD: Nao implementada ainda")
        return True
    
    def _executar_fase7_consolidacao(self, obra_id: str, **kwargs) -> bool:
        logger.info(f"[{obra_id}] Fase 7 - Consolidacao: Nao implementada ainda")
        return True
    
    def _executar_fase8_revisao(self, obra_id: str, **kwargs) -> bool:
        logger.info(f"[{obra_id}] Fase 8 - Revisao: Nao implementada ainda")
        return True
    
    # =========================================================================
    # MÉTODOS AUXILIARES
    # =========================================================================
    
    def _carregar_fichas(self, obra_id: str, tipo: str) -> List[Dict[str, Any]]:
        """Carrega fichas de um tipo especifico do SQLite."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, obra_id, pavimento, tipo, codigo, dados_json, confidence
            FROM fase3_fichas
            WHERE obra_id = ? AND tipo = ?
        """, (obra_id, tipo))
        
        fichas = []
        for row in cursor.fetchall():
            ficha = dict(row)
            ficha["dados"] = json.loads(ficha["dados_json"]) if ficha["dados_json"] else {}
            del ficha["dados_json"]
            fichas.append(ficha)
        
        return fichas
    
    def _salvar_fichas_json(self, fichas: List[Dict], caminho: str):
        """Salva fichas em arquivo JSON."""
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(fichas, f, ensure_ascii=False, indent=2)
        logger.info(f"Fichas salvas em: {caminho}")
    
    def _salvar_performance_metric(self, obra_id: str, fase: int, tempo_total: float,
                                   arquivos: int, entidades: int, cache_hits: int = 0,
                                   cache_misses: int = 0, workers: int = 1):
        """Salva métricas de performance da execução de uma fase."""
        metric_id = f"metric_{obra_id}_fase{fase}_{int(time.time())}"
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO performance_metrics 
            (id, obra_id, fase, tempo_total_seg, arquivos_processados, entidades_processadas,
             cache_hits, cache_misses, workers_usados, tempo_inicio, tempo_fim)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (metric_id, obra_id, fase, tempo_total, arquivos, entidades, cache_hits, cache_misses, workers))
        
        self.conn.commit()
    
    def get_performance_metrics(self, obra_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtém métricas de performance de uma obra ou todas."""
        cursor = self.conn.cursor()
        
        if obra_id:
            cursor.execute("""
                SELECT * FROM performance_metrics 
                WHERE obra_id = ? 
                ORDER BY fase, created_at
            """, (obra_id,))
        else:
            cursor.execute("SELECT * FROM performance_metrics ORDER BY obra_id, fase, created_at")
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_performance_summary(self, obra_id: str) -> Dict[str, Any]:
        """Obtém resumo de performance de uma obra."""
        metrics = self.get_performance_metrics(obra_id)
        
        if not metrics:
            return {"total_tempo": 0, "fases_executadas": 0}
        
        total_tempo = sum(m.get("tempo_total_seg", 0) or 0 for m in metrics)
        total_cache_hits = sum(m.get("cache_hits", 0) or 0 for m in metrics)
        total_cache_misses = sum(m.get("cache_misses", 0) or 0 for m in metrics)
        
        return {
            "total_tempo_seg": total_tempo,
            "fases_executadas": len(metrics),
            "total_cache_hits": total_cache_hits,
            "total_cache_misses": total_cache_misses,
            "cache_hit_rate": total_cache_hits / max(total_cache_hits + total_cache_misses, 1)
        }
    
    def pausar_obra(self, obra_id: str):
        """Pausa o processamento de uma obra."""
        self.atualizar_status_obra(obra_id, "pausado")
        logger.info(f"Obra {obra_id} pausada")
    
    def resetar_obra(self, obra_id: str):
        """Reseta o estado de uma obra para reprocessamento."""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            UPDATE pipeline_state 
            SET fase_atual = 1,
                fases_completas = '[]',
                fase_em_andamento = ?,
                ultima_atualizacao = CURRENT_TIMESTAMP
            WHERE obra_id = ?
        """, (json.dumps({"fase": 1, "inicio": None, "progresso": 0}), obra_id))
        
        cursor.execute("""
            UPDATE obras 
            SET fase_atual = 1, status = 'iniciado'
            WHERE id = ?
        """, (obra_id,))
        
        self.deletar_checkpoint(obra_id)
        
        self.conn.commit()
        logger.info(f"Obra {obra_id} resetada")
    
    def deletar_obra(self, obra_id: str):
        """Deleta uma obra e todos os seus dados."""
        cursor = self.conn.cursor()
        
        cursor.execute("DELETE FROM pipeline_checkpoint WHERE obra_id = ?", (obra_id,))
        cursor.execute("DELETE FROM performance_metrics WHERE obra_id = ?", (obra_id,))
        cursor.execute("DELETE FROM pipeline_state WHERE obra_id = ?", (obra_id,))
        cursor.execute("DELETE FROM fase3_fichas WHERE obra_id = ?", (obra_id,))
        cursor.execute("DELETE FROM ingestao_metadata WHERE obra_id = ?", (obra_id,))
        cursor.execute("DELETE FROM triagem_metadata WHERE obra_id = ?", (obra_id,))
        cursor.execute("DELETE FROM obras WHERE id = ?", (obra_id,))
        
        self.conn.commit()
        logger.info(f"Obra {obra_id} deletada")


def main():
    """Função main com suporte a checkpoint/resume."""
    parser = argparse.ArgumentParser(description="Pipeline Orchestrator com Checkpoint/Resume")
    parser.add_argument("--obra", type=str, help="Nome ou ID da obra")
    parser.add_argument("--pasta", type=str, help="Pasta de origem da obra")
    parser.add_argument("--fase", type=int, help="Fase específica para executar (1-8)")
    parser.add_argument("--retomar", action="store_true", help="Retomar processamento")
    parser.add_argument("--retomar-fase", type=int, help="Retomar de uma fase específica")
    parser.add_argument("--executar-todas", action="store_true", help="Executar todas as fases")
    parser.add_argument("--pausar", action="store_true", help="Pausar obra")
    parser.add_argument("--resetar", action="store_true", help="Resetar obra")
    parser.add_argument("--deletar", action="store_true", help="Deletar obra")
    parser.add_argument("--listar", action="store_true", help="Listar obras")
    parser.add_argument("--status", action="store_true", help="Mostrar status detalhado")
    parser.add_argument("--checkpoints", action="store_true", help="Listar checkpoints")
    parser.add_argument("--db", type=str, default="project_data.vision", help="Caminho do banco de dados")
    
    args = parser.parse_args()
    
    orchestrator = PipelineOrchestrator(args.db)
    
    try:
        if args.listar:
            obras = orchestrator.listar_obras()
            print(f"\n{'='*60}")
            print(f"{'OBRAS REGISTRADAS':^60}")
            print(f"{'='*60}")
            for obra in obras:
                print(f"  ID: {obra['id'][:8]}... | Nome: {obra['nome']:<30} | Fase: {obra['fase_atual']} | Status: {obra['status']}")
            print(f"{'='*60}\n")
            return
        
        if args.checkpoints:
            checkpoints = orchestrator.listar_checkpoints(args.obra if args.obra else None)
            print(f"\n{'='*60}")
            print(f"{'CHECKPOINTS':^60}")
            print(f"{'='*60}")
            for cp in checkpoints:
                print(f"  Obra: {cp['obra_id'][:8]}... | Fase: {cp['fase']} | Progresso: {cp['progresso']:.1%}")
            print(f"{'='*60}\n")
            return
        
        if args.status:
            if not args.obra:
                parser.error("--status requer --obra")
            
            obra = orchestrator.get_obra_por_nome(args.obra)
            if not obra:
                obra = orchestrator.get_obra(args.obra)
            
            if not obra:
                print(f"Obra nao encontrada: {args.obra}")
                return
            
            state = orchestrator.get_pipeline_state(obra["id"])
            perf = orchestrator.get_performance_summary(obra["id"])
            
            print(f"\n{'='*60}")
            print(f"STATUS DA OBRA: {obra['nome']}")
            print(f"{'='*60}")
            print(f"  ID: {obra['id']}")
            print(f"  Status: {obra['status']}")
            print(f"  Fase Atual: {obra['fase_atual']}")
            print(f"  Fases Completas: {state['fases_completas']}")
            print(f"  Tempo Total: {perf.get('total_tempo_seg', 0):.2f}s")
            print(f"  Cache Hit Rate: {perf.get('cache_hit_rate', 0):.1%}")
            print(f"{'='*60}\n")
            return
        
        if args.retomar_fase:
            if not args.obra:
                parser.error("--retomar-fase requer --obra")
            
            obra = orchestrator.get_obra_por_nome(args.obra)
            if not obra:
                obra = orchestrator.get_obra(args.obra)
            
            if not obra:
                print(f"Obra nao encontrada: {args.obra}")
                return
            
            sucesso = orchestrator.retomar_de_fase(obra["id"], args.retomar_fase)
            if sucesso:
                print(f"Processamento retomado com sucesso!")
            else:
                print(f"Erro ao retomar processamento")
                sys.exit(1)
            return
        
        if args.retomar:
            if not args.obra:
                parser.error("--retomar requer --obra")
            
            obra = orchestrator.get_obra_por_nome(args.obra)
            if not obra:
                obra = orchestrator.get_obra(args.obra)
            
            if not obra:
                print(f"Obra nao encontrada: {args.obra}")
                return
            
            sucesso = orchestrator.retomar_processamento(obra["id"])
            if sucesso:
                print(f"Processamento retomado com sucesso!")
            else:
                print(f"Erro ao retomar processamento")
                sys.exit(1)
            return
        
        if args.executar_todas:
            if not args.obra:
                parser.error("--executar-todas requer --obra")
            
            obra = orchestrator.get_obra_por_nome(args.obra)
            if not obra:
                obra = orchestrator.get_obra(args.obra)
            
            if not obra:
                print(f"Obra nao encontrada: {args.obra}")
                return
            
            sucesso = orchestrator.executar_todas_fases(obra["id"])
            if sucesso:
                print(f"Todas as fases executadas com sucesso!")
            else:
                print(f"Erro na execucao de alguma fase")
                sys.exit(1)
            return
        
        if args.fase:
            if not args.obra:
                parser.error("--fase requer --obra")
            
            obra = orchestrator.get_obra_por_nome(args.obra)
            if not obra:
                obra = orchestrator.get_obra(args.obra)
            
            if not obra:
                print(f"Obra nao encontrada: {args.obra}")
                return
            
            sucesso = orchestrator.executar_fase(obra["id"], args.fase)
            if sucesso:
                print(f"Fase {args.fase} executada com sucesso!")
            else:
                print(f"Erro na fase {args.fase}")
                sys.exit(1)
            return
        
        if args.pausar:
            if not args.obra:
                parser.error("--pausar requer --obra")
            
            obra = orchestrator.get_obra_por_nome(args.obra)
            if not obra:
                obra = orchestrator.get_obra(args.obra)
            
            if not obra:
                print(f"Obra nao encontrada: {args.obra}")
                return
            
            orchestrator.pausar_obra(obra["id"])
            print(f"Obra {args.obra} pausada")
            return
        
        if args.resetar:
            if not args.obra:
                parser.error("--resetar requer --obra")
            
            obra = orchestrator.get_obra_por_nome(args.obra)
            if not obra:
                obra = orchestrator.get_obra(args.obra)
            
            if not obra:
                print(f"Obra nao encontrada: {args.obra}")
                return
            
            orchestrator.resetar_obra(obra["id"])
            print(f"Obra {args.obra} resetada")
            return
        
        if args.deletar:
            if not args.obra:
                parser.error("--deletar requer --obra")
            
            obra = orchestrator.get_obra_por_nome(args.obra)
            if not obra:
                obra = orchestrator.get_obra(args.obra)
            
            if not obra:
                print(f"Obra nao encontrada: {args.obra}")
                return
            
            confirm = input(f"Tem certeza que deseja deletar a obra '{args.obra}'? (s/n): ")
            if confirm.lower() == "s":
                orchestrator.deletar_obra(obra["id"])
                print(f"Obra {args.obra} deletada")
            else:
                print("Operacao cancelada")
            return
        
        # Registrar nova obra se pasta fornecida
        if args.obra and args.pasta:
            obra_id = orchestrator.registrar_obra(args.obra, args.pasta)
            print(f"Obra registrada: {args.obra} (ID: {obra_id[:8]}...)")
            return
        
        parser.print_help()
        
    finally:
        orchestrator.close()


if __name__ == "__main__":
    main()
