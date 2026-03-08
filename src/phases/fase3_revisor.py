# -*- coding: utf-8 -*-
"""
Fase 3 - Revisor de Interpretação

Módulo de revisão semi-automática das fichas Fase 3.
Permite correção manual e salva correções como training_events.
"""

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pipeline.transformation_engine import TransformationEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class Sugestao:
    """Sugestão de correção para uma ficha."""
    campo: str
    valor_atual: Any
    valor_sugerido: Any
    confidence: float
    motivo: str
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TrainingEvent:
    """Evento de treinamento para retreinamento do modelo."""
    id: str
    project_id: str
    type: str
    role: str
    context_dna_json: str
    target_value: str
    status: str
    timestamp: str
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RevisaoResultado:
    """Resultado da revisão de uma obra."""
    obra_id: str
    revisor: str
    fichas_revisadas: int = 0
    correcoes_aplicadas: int = 0
    sugestões_aceitas: int = 0
    sugestoes_rejeitadas: int = 0
    training_events_criados: int = 0
    tempo_total_seg: float = 0.0


class Fase3Revisor:
    """Revisão semi-automática das fichas Fase 3."""
    
    CONFIDENCE_THRESHOLD = 0.7
    
    def __init__(self, db_path: str = "project_data.vision"):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.transform_engine: Optional[TransformationEngine] = None
        self._connect()
    
    def _connect(self) -> sqlite3.Connection:
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
        if self.transform_engine:
            self.transform_engine.close()
            self.transform_engine = None
    
    def revisar_obra(self, obra_id: str, revisor_nome: str) -> RevisaoResultado:
        """
        Revisão semi-automática das fichas Fase 3.
        
        1. Carrega fichas da obra
        2. Ordena por confidence (menor primeiro)
        3. Para cada ficha com confidence < threshold:
           - Mostra dados atuais
           - Sugere correções baseadas em regras
           - Permite edição manual
        4. Salva correções como training_events
        5. Atualiza fichas
        """
        logger.info(f"[{obra_id}] Iniciando revisão com revisor: {revisor_nome}")
        
        resultado = RevisaoResultado(obra_id=obra_id, revisor=revisor_nome)
        
        try:
            # Carregar fichas da obra
            fichas = self._carregar_fichas_obra(obra_id)
            if not fichas:
                logger.warning(f"Nenhuma ficha encontrada para obra: {obra_id}")
                return resultado
            
            # Ordenar por confidence (menor primeiro)
            fichas.sort(key=lambda f: f.get("confidence", 1.0))
            
            # Inicializar TransformationEngine
            self.transform_engine = TransformationEngine(self.db_path)
            self.transform_engine.load_rules_from_db()
            
            # Revisar fichas com baixa confidence
            for ficha in fichas:
                if ficha.get("confidence", 1.0) < self.CONFIDENCE_THRESHOLD:
                    resultado.fichas_revisadas += 1
                    
                    # Obter sugestões de correção
                    sugestoes = self.sugerir_correcoes(ficha)
                    
                    # Aplicar correções automaticamente se confidence alta
                    for sugestao in sugestoes:
                        if sugestao.confidence > 0.9:
                            self._aplicar_correcao_ficha(ficha, sugestao)
                            resultado.correcoes_aplicadas += 1
                            resultado.sugestões_aceitas += 1
                            
                            # Salvar como training event
                            self.salvar_correcao(
                                ficha["id"],
                                {sugestao.campo: sugestao.valor_sugerido},
                                revisor_nome,
                                ficha
                            )
                            resultado.training_events_criados += 1
            
            # Atualizar fichas no banco
            self._atualizar_fichas(fichas, obra_id)
            
            logger.info(f"[{obra_id}] Revisão completada: {resultado.fichas_revisadas} fichas, "
                       f"{resultado.correcoes_aplicadas} correções")
            
        except Exception as e:
            logger.error(f"[{obra_id}] Erro na revisão: {e}")
        
        return resultado
    
    def _carregar_fichas_obra(self, obra_id: str) -> List[dict]:
        """Carrega todas as fichas da obra."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, obra_id, pavimento, tipo, codigo, dados_json, confidence, revisado, revisado_por, data_revisao
            FROM fase3_fichas WHERE obra_id = ?
        """, (obra_id,))
        
        fichas = []
        for row in cursor.fetchall():
            ficha = dict(row)
            try:
                ficha["dados"] = json.loads(ficha["dados_json"]) if ficha["dados_json"] else {}
            except:
                ficha["dados"] = {}
            del ficha["dados_json"]
            fichas.append(ficha)
        
        return fichas
    
    def sugerir_correcoes(self, ficha: dict) -> List[Sugestao]:
        """
        Usa TransformationEngine para sugerir correções.
        
        Compara campos atuais com regras derivadas e retorna sugestões.
        """
        sugestoes = []
        
        if not self.transform_engine:
            return sugestoes
        
        dados = ficha.get("dados", {})
        tipo = ficha.get("tipo", "")
        dna_vector = dados.get("dna_vector", [])
        
        # Determinar role baseado no tipo
        role_map = {
            "pilar": "Pilar_name",
            "viga": "Viga_name",
            "laje": "Laje_name"
        }
        role = role_map.get(tipo)
        
        if not role or not dna_vector:
            return sugestoes
        
        # Aplicar regra para obter valor previsto
        predicted = self.transform_engine.apply_rule(role, dna_vector)
        
        if predicted:
            # Determinar campo a corrigir
            if tipo == "pilar":
                campo = "id"
                valor_atual = ficha.get("codigo", dados.get("id", ""))
            elif tipo == "viga":
                campo = "codigo"
                valor_atual = ficha.get("codigo", "")
            else:  # laje
                campo = "codigo"
                valor_atual = ficha.get("codigo", "")
            
            if valor_atual != predicted:
                # Calcular confidence da sugestão
                confidence = self._calcular_confidence_sugestao(ficha, predicted)
                
                sugestoes.append(Sugestao(
                    campo=campo,
                    valor_atual=valor_atual,
                    valor_sugerido=predicted,
                    confidence=confidence,
                    motivo=f"Regra {role} sugere valor baseado em DNA vector"
                ))
        
        # Sugestões baseadas em validação
        sugestoes_validacao = self._sugerir_correcoes_validacao(ficha)
        sugestoes.extend(sugestoes_validacao)
        
        return sugestoes
    
    def _sugerir_correcoes_validacao(self, ficha: dict) -> List[Sugestao]:
        """Sugere correções baseadas em validação de campos."""
        sugestoes = []
        dados = ficha.get("dados", {})
        tipo = ficha.get("tipo", "")
        
        if tipo == "pilar":
            # Validar dimensões
            largura = dados.get("largura", 0)
            comprimento = dados.get("comprimento", 0)
            
            if largura < 20:
                sugestoes.append(Sugestao(
                    campo="largura",
                    valor_atual=largura,
                    valor_sugerido=20.0,
                    confidence=0.8,
                    motivo="Largura mínima recomendada para pilares é 20cm"
                ))
            
            if comprimento < 20:
                sugestoes.append(Sugestao(
                    campo="comprimento",
                    valor_atual=comprimento,
                    valor_sugerido=20.0,
                    confidence=0.8,
                    motivo="Comprimento mínimo recomendado para pilares é 20cm"
                ))
        
        elif tipo == "viga":
            largura = dados.get("largura", 0)
            altura = dados.get("altura", 0)
            
            if largura < 12:
                sugestoes.append(Sugestao(
                    campo="largura",
                    valor_atual=largura,
                    valor_sugerido=12.0,
                    confidence=0.8,
                    motivo="Largura mínima recomendada para vigas é 12cm"
                ))
            
            if altura < 25:
                sugestoes.append(Sugestao(
                    campo="altura",
                    valor_atual=altura,
                    valor_sugerido=25.0,
                    confidence=0.8,
                    motivo="Altura mínima recomendada para vigas é 25cm"
                ))
        
        elif tipo == "laje":
            espessura = dados.get("espessura", 10.0)
            
            if espessura < 7:
                sugestoes.append(Sugestao(
                    campo="espessura",
                    valor_atual=espessura,
                    valor_sugerido=10.0,
                    confidence=0.8,
                    motivo="Espessura mínima recomendada para lajes é 7cm"
                ))
        
        return sugestoes
    
    def _calcular_confidence_sugestao(self, ficha: dict, valor_sugerido: str) -> float:
        """Calcula confidence da sugestão."""
        confidence = 0.5  # Base
        
        # Aumentar confidence se ficha tem baixa confidence
        ficha_confidence = ficha.get("confidence", 1.0)
        if ficha_confidence < 0.5:
            confidence += 0.2
        elif ficha_confidence < 0.7:
            confidence += 0.1
        
        # Aumentar confidence se há consistência com outras fichas
        # (implementação simplificada)
        
        return min(confidence, 1.0)
    
    def _aplicar_correcao_ficha(self, ficha: dict, sugestao: Sugestao):
        """Aplica correção à ficha."""
        if sugestao.campo in ficha:
            ficha[sugestao.campo] = sugestao.valor_sugerido
        
        if "dados" in ficha and sugestao.campo in ficha["dados"]:
            ficha["dados"][sugestao.campo] = sugestao.valor_sugerido
    
    def _atualizar_fichas(self, fichas: List[dict], obra_id: str):
        """Atualiza fichas no banco de dados."""
        cursor = self.conn.cursor()
        
        for ficha in fichas:
            try:
                cursor.execute("""
                    UPDATE fase3_fichas 
                    SET codigo = ?, dados_json = ?, confidence = ?, revisado = ?, revisado_por = ?, data_revisao = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    ficha.get("codigo"),
                    json.dumps(ficha.get("dados", {})),
                    ficha.get("confidence", 0),
                    1,
                    ficha.get("revisado_por"),
                    ficha["id"]
                ))
            except Exception as e:
                logger.debug(f"Erro ao atualizar ficha {ficha['id']}: {e}")
        
        self.conn.commit()
    
    def salvar_correcao(self, ficha_id: str, correcoes: dict, revisor: str, ficha: dict) -> Optional[TrainingEvent]:
        """
        Salva correção como training_event para retreinamento.
        
        level_1_project: obra, pavimento
        level_2_item: tipo, nome, dna_vector
        level_3_field: campo alterado, valor_antigo, valor_novo
        target_label: valor correto
        """
        try:
            dados = ficha.get("dados", {})
            tipo = ficha.get("tipo", "desconhecido")
            
            # Construir context DNA
            context_dna = {
                "level_1_project": {
                    "obra": ficha.get("obra_id", ""),
                    "pavimento": ficha.get("pavimento", "")
                },
                "level_2_item": {
                    "tipo": tipo,
                    "nome": ficha.get("codigo", ""),
                    "dna_vector": dados.get("dna_vector", [])
                },
                "level_3_field": {
                    "campo": list(correcoes.keys())[0] if correcoes else "",
                    "valor_antigo": list(correcoes.values())[0] if correcoes else "",
                    "valor_novo": ""
                },
                "target_label": ""
            }
            
            # Preencher valores
            for campo, valor in correcoes.items():
                context_dna["level_3_field"]["valor_novo"] = valor
                context_dna["target_label"] = str(valor)
            
            # Criar training event
            event_id = str(uuid.uuid4())
            event = TrainingEvent(
                id=event_id,
                project_id=ficha.get("obra_id", ""),
                type="correcao_revisao",
                role=f"{tipo}_name",
                context_dna_json=json.dumps(context_dna),
                target_value=str(list(correcoes.values())[0]) if correcoes else "",
                status="pending",
                timestamp=str(datetime.now())
            )
            
            # Salvar no banco
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO training_events (id, project_id, type, role, context_dna_json, target_value, status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.id,
                event.project_id,
                event.type,
                event.role,
                event.context_dna_json,
                event.target_value,
                event.status,
                event.timestamp
            ))
            self.conn.commit()
            
            logger.info(f"Training event criado: {event_id}")
            return event
            
        except Exception as e:
            logger.error(f"Erro ao salvar training event: {e}")
            self.conn.rollback()
            return None
    
    def revisar_ficha_manual(self, ficha_id: str, correcoes: dict, revisor: str) -> bool:
        """
        Permite edição manual de uma ficha específica.
        
        Args:
            ficha_id: ID da ficha
            correcoes: Dict com campos e valores a corrigir
            revisor: Nome do revisor
        
        Returns:
            True se sucesso
        """
        try:
            # Carregar ficha atual
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM fase3_fichas WHERE id = ?", (ficha_id,))
            row = cursor.fetchone()
            
            if not row:
                logger.error(f"Ficha não encontrada: {ficha_id}")
                return False
            
            ficha = dict(row)
            dados = json.loads(ficha["dados_json"]) if ficha["dados_json"] else {}
            
            # Aplicar correções
            for campo, valor in correcoes.items():
                if campo in ficha:
                    ficha[campo] = valor
                dados[campo] = valor
            
            # Salvar training event
            self.salvar_correcao(ficha_id, correcoes, revisor, {
                "id": ficha_id,
                "obra_id": ficha["obra_id"],
                "pavimento": ficha["pavimento"],
                "tipo": ficha["tipo"],
                "codigo": ficha["codigo"],
                "dados": dados
            })
            
            # Atualizar ficha
            cursor.execute("""
                UPDATE fase3_fichas 
                SET codigo = ?, dados_json = ?, confidence = ?, revisado = 1, revisado_por = ?, data_revisao = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                ficha.get("codigo"),
                json.dumps(dados),
                min(ficha.get("confidence", 0) + 0.2, 1.0),  # Aumentar confidence após revisão
                revisor,
                ficha_id
            ))
            self.conn.commit()
            
            logger.info(f"Ficha {ficha_id} revisada manualmente por {revisor}")
            return True
            
        except Exception as e:
            logger.error(f"Erro na revisão manual: {e}")
            self.conn.rollback()
            return False
    
    def get_fichas_para_revisao(self, obra_id: str, threshold: float = 0.7) -> List[dict]:
        """Retorna fichas que precisam de revisão (confidence < threshold)."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, obra_id, pavimento, tipo, codigo, dados_json, confidence, revisado
            FROM fase3_fichas 
            WHERE obra_id = ? AND confidence < ? AND revisado = 0
            ORDER BY confidence ASC
        """, (obra_id, threshold))
        
        fichas = []
        for row in cursor.fetchall():
            ficha = dict(row)
            try:
                ficha["dados"] = json.loads(ficha["dados_json"]) if ficha["dados_json"] else {}
            except:
                ficha["dados"] = {}
            del ficha["dados_json"]
            fichas.append(ficha)
        
        return fichas
    
    def get_stats_revisao(self, obra_id: str) -> dict:
        """Retorna estatísticas de revisão da obra."""
        cursor = self.conn.cursor()
        
        # Total de fichas
        cursor.execute("SELECT COUNT(*) as total FROM fase3_fichas WHERE obra_id = ?", (obra_id,))
        total = cursor.fetchone()["total"]
        
        # Fichas revisadas
        cursor.execute("SELECT COUNT(*) as revisadas FROM fase3_fichas WHERE obra_id = ? AND revisado = 1", (obra_id,))
        revisadas = cursor.fetchone()["revisadas"]
        
        # Confidence média
        cursor.execute("SELECT AVG(confidence) as media FROM fase3_fichas WHERE obra_id = ?", (obra_id,))
        media_confidence = cursor.fetchone()["media"] or 0
        
        # Por tipo
        stats_por_tipo = {}
        for tipo in ["pilar", "viga", "laje"]:
            cursor.execute("""
                SELECT COUNT(*) as total, AVG(confidence) as media 
                FROM fase3_fichas 
                WHERE obra_id = ? AND tipo = ?
            """, (obra_id, tipo))
            row = cursor.fetchone()
            stats_por_tipo[tipo] = {
                "total": row["total"],
                "revisadas": 0,
                "media_confidence": row["media"] or 0
            }
            
            cursor.execute("""
                SELECT COUNT(*) as revisadas 
                FROM fase3_fichas 
                WHERE obra_id = ? AND tipo = ? AND revisado = 1
            """, (obra_id, tipo))
            stats_por_tipo[tipo]["revisadas"] = cursor.fetchone()["revisadas"]
        
        return {
            "obra_id": obra_id,
            "total_fichas": total,
            "fichas_revisadas": revisadas,
            "media_confidence": media_confidence,
            "por_tipo": stats_por_tipo
        }


def main():
    """CLI para revisão Fase 3."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fase 3 - Revisor")
    parser.add_argument("--obra", type=str, required=True, help="ID da obra")
    parser.add_argument("--revisor", type=str, default="admin", help="Nome do revisor")
    parser.add_argument("--db", type=str, default="project_data.vision", help="Banco de dados")
    parser.add_argument("--stats", action="store_true", help="Mostrar estatísticas")
    parser.add_argument("--threshold", type=float, default=0.7, help="Threshold de confidence")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("FASE 3 - REVISOR")
    print("=" * 70)
    
    revisor = Fase3Revisor(args.db)
    
    try:
        if args.stats:
            stats = revisor.get_stats_revisao(args.obra)
            print(f"\nEstatísticas da obra {args.obra}:")
            print(f"  Total fichas: {stats['total_fichas']}")
            print(f"  Revisadas: {stats['fichas_revisadas']}")
            print(f"  Confidence média: {stats['media_confidence']:.2%}")
            print(f"  Por tipo:")
            for tipo, stats_tipo in stats["por_tipo"].items():
                print(f"    {tipo}: {stats_tipo['total']} total, {stats_tipo['revisadas']} revisadas, "
                      f"{stats_tipo['media_confidence']:.2%} confidence")
        else:
            resultado = revisor.revisar_obra(args.obra, args.revisor)
            print(f"\nResultado da revisão:")
            print(f"  Fichas revisadas: {resultado.fichas_revisadas}")
            print(f"  Correções aplicadas: {resultado.correcoes_aplicadas}")
            print(f"  Training events criados: {resultado.training_events_criados}")
    
    finally:
        revisor.close()


if __name__ == "__main__":
    main()
