# -*- coding: utf-8 -*-
"""
Fase 1 - Ingestão de Dados do Pipeline GAP-5
VERSÃO OTIMIZADA - SPRINT 13
- Processamento paralelo de DXFs com ProcessPoolExecutor
- Cache de resultados para evitar reprocessamento
- Bulk inserts para SQLite
"""

import hashlib
import json
import logging
import os
import sqlite3
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from multiprocessing import cpu_count
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import ezdxf
except ImportError:
    ezdxf = None

try:
    from pdfminer.high_level import extract_text
except ImportError:
    extract_text = None

try:
    import cv2
    import numpy as np
    import pytesseract
except ImportError:
    cv2 = None
    np = None
    pytesseract = None

# Importar cache
try:
    from core.cache import DXFCache
except ImportError:
    DXFCache = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# Número de workers para processamento paralelo
NUM_WORKERS = min(cpu_count(), 8)  # Máximo 8 workers
BATCH_SIZE = 50  # Tamanho do batch para bulk insert


@dataclass
class DXFResultado:
    caminho: str
    entidades: List[Dict[str, Any]]
    layers: List[str]
    blocks: List[str]
    erro: Optional[str] = None
    tempo_processamento: float = 0.0


@dataclass
class PDFResultado:
    caminho: str
    texto: str
    tabelas: List[Dict[str, Any]]
    metadados: Dict[str, Any]
    erro: Optional[str] = None


@dataclass
class FotoResultado:
    caminho: str
    bordas: List[List[Tuple[int, int]]]
    contornos: List[Dict[str, Any]]
    texto_ocr: str
    dimensoes: Tuple[int, int]
    erro: Optional[str] = None


@dataclass
class IngestaoResultado:
    obra_dir: str
    arquivos_processados: int
    dxf_ingestados: int
    pdf_ingestados: int
    fotos_ingestadas: int
    entidades_extraidas: int
    cache_hits: int = 0
    cache_misses: int = 0
    erros: List[str] = field(default_factory=list)
    tempo_total_seg: float = 0.0
    tempo_paralelo_seg: float = 0.0


@dataclass
class Catalogo:
    pilares: List[Dict[str, Any]] = field(default_factory=list)
    vigas: List[Dict[str, Any]] = field(default_factory=list)
    lajes: List[Dict[str, Any]] = field(default_factory=list)
    textos: List[Dict[str, Any]] = field(default_factory=list)
    cotas: List[Dict[str, Any]] = field(default_factory=list)
    
    def total_entidades(self) -> int:
        return len(self.pilares) + len(self.vigas) + len(self.lajes) + len(self.textos) + len(self.cotas)


def processar_dxf_individual(caminho: str, usar_cache: bool = True, db_path: str = "project_data.vision") -> DXFResultado:
    """
    Função standalone para processar um único DXF.
    Usada pelo ProcessPoolExecutor para processamento paralelo.
    """
    inicio = time.time()
    
    if ezdxf is None:
        return DXFResultado(caminho=caminho, entidades=[], layers=[], blocks=[], 
                           erro="ezdxf nao instalado", tempo_processamento=time.time() - inicio)
    
    # Verificar cache
    cache = None
    if usar_cache and DXFCache is not None:
        try:
            cache = DXFCache(db_path)
            if cache.exists(caminho):
                resultado_cache = cache.get(caminho)
                if resultado_cache:
                    cache.close()
                    return DXFResultado(
                        caminho=caminho,
                        entidades=resultado_cache["entidades"],
                        layers=resultado_cache["layers"],
                        blocks=resultado_cache["blocks"],
                        tempo_processamento=time.time() - inicio
                    )
        except Exception as e:
            logger.debug(f"Erro ao verificar cache: {e}")
    
    try:
        doc = ezdxf.readfile(caminho)
        modelspace = doc.modelspace()
        
        entidades = []
        layers = set()
        blocks = set()
        
        for layer in doc.layers:
            layers.add(layer.dxf.name)
        
        if hasattr(doc, 'blocks'):
            for block in doc.blocks:
                blocks.add(block.name)
        
        for entity in modelspace:
            try:
                entidade_dict = _extrair_entidade_dxf(entity)
                if entidade_dict:
                    entidades.append(entidade_dict)
            except Exception as e:
                logger.debug(f"Erro ao extrair entidade: {e}")
        
        resultado = DXFResultado(
            caminho=caminho,
            entidades=entidades,
            layers=sorted(list(layers)),
            blocks=sorted(list(blocks)),
            tempo_processamento=time.time() - inicio
        )
        
        # Salvar no cache
        if cache is not None:
            try:
                cache.set(caminho, entidades, sorted(list(layers)), sorted(list(blocks)))
            except Exception as e:
                logger.debug(f"Erro ao salvar cache: {e}")
            finally:
                cache.close()
        
        return resultado
        
    except Exception as e:
        if cache:
            cache.close()
        return DXFResultado(caminho=caminho, entidades=[], layers=[], blocks=[], erro=str(e), 
                           tempo_processamento=time.time() - inicio)


def _extrair_entidade_dxf(entity) -> Optional[Dict[str, Any]]:
    """Extrai entidade DXF para dicionário."""
    if entity is None:
        return None
    
    try:
        entidade = {
            "tipo": entity.dxftype(),
            "layer": entity.dxf.layer if hasattr(entity.dxf, 'layer') else "",
        }
        
        if entity.dxftype() == "LINE":
            start = entity.dxf.start if hasattr(entity.dxf, 'start') else (0, 0)
            end = entity.dxf.end if hasattr(entity.dxf, 'end') else (0, 0)
            entidade["pontos"] = [{"x": float(start[0]), "y": float(start[1])}, 
                                 {"x": float(end[0]), "y": float(end[1])}]
            entidade["posicao_x"] = (float(start[0]) + float(end[0])) / 2
            entidade["posicao_y"] = (float(start[1]) + float(end[1])) / 2
            dx = float(end[0]) - float(start[0])
            dy = float(end[1]) - float(start[1])
            entidade["comprimento"] = (dx * dx + dy * dy) ** 0.5
        
        elif entity.dxftype() in ("POLYLINE", "LWPOLYLINE"):
            pontos = []
            try:
                for point in entity.get_points():
                    pontos.append({"x": float(point[0]), "y": float(point[1])})
            except:
                pass
            entidade["pontos"] = pontos
            if pontos:
                entidade["posicao_x"] = sum(p["x"] for p in pontos) / len(pontos)
                entidade["posicao_y"] = sum(p["y"] for p in pontos) / len(pontos)
        
        elif entity.dxftype() == "INSERT":
            insert = entity.dxf.insert if hasattr(entity.dxf, 'insert') else (0, 0)
            entidade["posicao_x"] = float(insert[0])
            entidade["posicao_y"] = float(insert[1])
            entidade["nome_block"] = entity.dxf.name if hasattr(entity.dxf, 'name') else ""
        
        elif entity.dxftype() in ("TEXT", "MTEXT"):
            text = entity.dxf.text if hasattr(entity.dxf, 'text') else ""
            insert = entity.dxf.insert if hasattr(entity.dxf, 'insert') else (0, 0)
            entidade["conteudo"] = str(text)
            entidade["posicao_x"] = float(insert[0])
            entidade["posicao_y"] = float(insert[1])
        
        return entidade
    except Exception as e:
        logger.debug(f"Erro ao extrair entidade: {e}")
        return None


class Fase1Ingestao:
    ENTIDADE_PILAR = {"INSERT", "BLOCK_REFERENCE"}
    ENTIDADE_VIGA = {"LINE", "POLYLINE", "LWPOLYLINE", "SPLINE"}
    ENTIDADE_LAJE = {"HATCH", "REGION"}
    ENTIDADE_TEXTO = {"TEXT", "MTEXT", "ATTRIB"}
    ENTIDADE_COTA = {"DIMENSION", "DIMLINEAR", "DIMALIGNED"}
    
    LAYERS_PILAR = {"PILAR", "PILARES", "PILLAR"}
    LAYERS_VIGA = {"VIGA", "VIGAS", "BEAM"}
    LAYERS_LAJE = {"LAJE", "LAJES", "SLAB"}
    LAYERS_COTA = {"COTA", "COTAS", "DIMENSION"}
    
    def __init__(self, obra_dir: str, db_path: str = "project_data.vision", 
                 usar_cache: bool = True, num_workers: int = None):
        self.obra_dir = Path(obra_dir)
        self.db_path = db_path
        self.usar_cache = usar_cache
        self.num_workers = num_workers or NUM_WORKERS
        self.conn: Optional[sqlite3.Connection] = None
        self.cache: Optional[DXFCache] = None
        self._connect()
        self._ensure_tables()
        
        if usar_cache and DXFCache is not None:
            self.cache = DXFCache(db_path)
    
    def _connect(self) -> sqlite3.Connection:
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path, timeout=30.0)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.execute("PRAGMA synchronous = NORMAL")
        return self.conn
    
    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
        if self.cache:
            self.cache.close()
            self.cache = None
    
    def _ensure_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dxf_entidades (
                id TEXT PRIMARY KEY,
                obra_id TEXT,
                arquivo_origem TEXT,
                tipo TEXT,
                layer TEXT,
                dados_json TEXT,
                posicao_x REAL,
                posicao_y REAL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entidades_obra ON dxf_entidades(obra_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entidades_tipo ON dxf_entidades(tipo)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entidades_layer ON dxf_entidades(layer)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entidades_arquivo ON dxf_entidades(arquivo_origem)")
        self.conn.commit()
    
    def executar(self, obra_id: Optional[str] = None) -> IngestaoResultado:
        logger.info(f"[{obra_id or 'N/A'}] Iniciando Fase 1 - Ingestao (OTIMIZADA - {self.num_workers} workers)")
        inicio = time.time()
        
        resultado = IngestaoResultado(
            obra_dir=str(self.obra_dir),
            arquivos_processados=0,
            dxf_ingestados=0,
            pdf_ingestados=0,
            fotos_ingestadas=0,
            entidades_extraidas=0,
            cache_hits=0,
            cache_misses=0
        )
        
        if not self.obra_dir.exists():
            resultado.erros.append(f"Diretorio nao existe: {self.obra_dir}")
            resultado.tempo_total_seg = time.time() - inicio
            return resultado
        
        # Coletar arquivos
        dxf_files = list(self.obra_dir.rglob("*.dxf")) + list(self.obra_dir.rglob("*.DXF"))
        pdf_files = list(self.obra_dir.rglob("*.pdf")) + list(self.obra_dir.rglob("*.PDF"))
        image_files = []
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.bmp"]:
            image_files.extend(list(self.obra_dir.rglob(ext)))
        
        logger.info(f"Encontrados: {len(dxf_files)} DXFs, {len(pdf_files)} PDFs, {len(image_files)} imagens")
        
        catalogo = Catalogo()
        
        # Processar DXFs em paralelo
        if dxf_files:
            dxf_resultados = self._processar_dxfs_paralelo(dxf_files, obra_id)
            
            for dxf_result in dxf_resultados:
                if dxf_result.erro:
                    resultado.erros.append(f"DXF {Path(dxf_result.caminho).name}: {dxf_result.erro}")
                else:
                    resultado.dxf_ingestados += 1
                    resultado.arquivos_processados += 1
                    resultado.entidades_extraidas += len(dxf_result.entidades)
                    self._catalogar_entidades_dxf(dxf_result.entidades, catalogo)
                    
                    if dxf_result.tempo_processamento < 0.01:
                        resultado.cache_hits += 1
                    else:
                        resultado.cache_misses += 1
        
        # Processar PDFs e imagens em paralelo (I/O bound)
        if pdf_files:
            pdf_resultados = self._processar_pdfs_paralelo(pdf_files)
            for pdf_result in pdf_resultados:
                if pdf_result.erro:
                    resultado.erros.append(f"PDF {Path(pdf_result.caminho).name}: {pdf_result.erro}")
                else:
                    resultado.pdf_ingestados += 1
                    resultado.arquivos_processados += 1
        
        if image_files:
            foto_resultados = self._processar_fotos_paralelo(image_files)
            for foto_result in foto_resultados:
                if foto_result.erro:
                    resultado.erros.append(f"Foto {Path(foto_result.caminho).name}: {foto_result.erro}")
                else:
                    resultado.fotos_ingestadas += 1
                    resultado.arquivos_processados += 1
        
        # Salvar entidades no SQLite com bulk insert
        if obra_id and catalogo.total_entidades() > 0:
            self._salvar_no_sqlite_bulk(catalogo, obra_id)
        
        resultado.tempo_total_seg = time.time() - inicio
        
        logger.info(f"[{obra_id}] Fase 1 completada: {resultado.arquivos_processados} arquivos, "
                   f"{resultado.entidades_extraidas} entidades em {resultado.tempo_total_seg:.2f}s")
        logger.info(f"[{obra_id}] Cache: {resultado.cache_hits} hits, {resultado.cache_misses} misses")
        
        return resultado
    
    def _processar_dxfs_paralelo(self, dxf_files: List[Path], obra_id: Optional[str] = None) -> List[DXFResultado]:
        """Processa múltiplos DXFs em paralelo usando ProcessPoolExecutor."""
        resultados = []
        inicio = time.time()
        
        # Usar ProcessPoolExecutor para CPU-bound tasks (processamento DXF)
        with ProcessPoolExecutor(max_workers=self.num_workers) as executor:
            future_to_dxf = {
                executor.submit(
                    processar_dxf_individual, 
                    str(dxf_path), 
                    self.usar_cache, 
                    self.db_path
                ): dxf_path 
                for dxf_path in dxf_files
            }
            
            for future in as_completed(future_to_dxf):
                dxf_path = future_to_dxf[future]
                try:
                    resultado = future.result()
                    resultados.append(resultado)
                except Exception as e:
                    logger.error(f"Erro ao processar {dxf_path}: {e}")
                    resultados.append(DXFResultado(
                        caminho=str(dxf_path),
                        entidades=[],
                        layers=[],
                        blocks=[],
                        erro=str(e)
                    ))
        
        tempo_paralelo = time.time() - inicio
        logger.info(f"Processamento paralelo DXF: {len(dxf_files)} arquivos em {tempo_paralelo:.2f}s "
                   f"({len(dxf_files)/tempo_paralelo:.1f} arquivos/s)")
        
        return resultados
    
    def _processar_pdfs_paralelo(self, pdf_files: List[Path]) -> List[PDFResultado]:
        """Processa múltiplos PDFs em paralelo usando ThreadPoolExecutor (I/O bound)."""
        resultados = []
        
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            future_to_pdf = {
                executor.submit(self.ingestar_pdf, str(pdf_path)): pdf_path 
                for pdf_path in pdf_files
            }
            
            for future in as_completed(future_to_pdf):
                try:
                    resultado = future.result()
                    resultados.append(resultado)
                except Exception as e:
                    pdf_path = future_to_pdf[future]
                    logger.error(f"Erro ao processar PDF {pdf_path}: {e}")
                    resultados.append(PDFResultado(
                        caminho=str(pdf_path),
                        texto="",
                        tabelas=[],
                        metadados={},
                        erro=str(e)
                    ))
        
        return resultados
    
    def _processar_fotos_paralelo(self, image_files: List[Path]) -> List[FotoResultado]:
        """Processa múltiplas fotos em paralelo usando ThreadPoolExecutor (I/O bound)."""
        resultados = []
        
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            future_to_foto = {
                executor.submit(self.ingestar_foto, str(foto_path)): foto_path 
                for foto_path in image_files
            }
            
            for future in as_completed(future_to_foto):
                try:
                    resultado = future.result()
                    resultados.append(resultado)
                except Exception as e:
                    foto_path = future_to_foto[future]
                    logger.error(f"Erro ao processar foto {foto_path}: {e}")
                    resultados.append(FotoResultado(
                        caminho=str(foto_path),
                        bordas=[],
                        contornos=[],
                        texto_ocr="",
                        dimensoes=(0, 0),
                        erro=str(e)
                    ))
        
        return resultados
    
    def _catalogar_entidades_dxf(self, entidades: List[Dict], catalogo: Catalogo):
        for entidade in entidades:
            tipo = entidade.get("tipo", "").upper()
            layer = entidade.get("layer", "").upper()
            
            if tipo in self.ENTIDADE_PILAR or any(l in layer for l in self.LAYERS_PILAR):
                catalogo.pilares.append(entidade)
            elif tipo in self.ENTIDADE_VIGA or any(l in layer for l in self.LAYERS_VIGA):
                catalogo.vigas.append(entidade)
            elif tipo in self.ENTIDADE_LAJE or any(l in layer for l in self.LAYERS_LAJE):
                catalogo.lajes.append(entidade)
            elif tipo in self.ENTIDADE_TEXTO:
                catalogo.textos.append(entidade)
            elif tipo in self.ENTIDADE_COTA:
                catalogo.cotas.append(entidade)
            else:
                catalogo.vigas.append(entidade)
    
    def ingestar_dxf(self, dxf_path: str) -> DXFResultado:
        """Método individual para ingestão de DXF (usa cache)."""
        return processar_dxf_individual(dxf_path, self.usar_cache, self.db_path)
    
    def ingestar_pdf(self, pdf_path: str) -> PDFResultado:
        logger.info(f"Ingestao PDF: {pdf_path}")
        
        if extract_text is None:
            return PDFResultado(caminho=pdf_path, texto="", tabelas=[], metadados={}, 
                               erro="pdfminer nao instalado")
        
        try:
            texto = extract_text(pdf_path)
            return PDFResultado(caminho=pdf_path, texto=texto, tabelas=[], metadados={})
        except Exception as e:
            return PDFResultado(caminho=pdf_path, texto="", tabelas=[], metadados={}, erro=str(e))
    
    def ingestar_foto(self, foto_path: str) -> FotoResultado:
        logger.info(f"Ingestao Foto: {foto_path}")
        
        if cv2 is None:
            return FotoResultado(caminho=foto_path, bordas=[], contornos=[], texto_ocr="", 
                                dimensoes=(0, 0), erro="opencv nao instalado")
        
        try:
            imagem = cv2.imread(foto_path)
            if imagem is None:
                return FotoResultado(caminho=foto_path, bordas=[], contornos=[], texto_ocr="", 
                                    dimensoes=(0, 0), erro="Nao foi possivel carregar imagem")
            
            dimensoes = (imagem.shape[1], imagem.shape[0])
            cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
            bordas = cv2.Canny(cinza, 50, 150)
            
            contornos_cv, _ = cv2.findContours(bordas, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contornos = []
            for contorno in contornos_cv:
                area = cv2.contourArea(contorno)
                if area > 100:
                    contornos.append({"area": float(area)})
            
            texto_ocr = ""
            if pytesseract is not None:
                try:
                    texto_ocr = pytesseract.image_to_string(cinza, lang='eng')
                except:
                    pass
            
            return FotoResultado(caminho=foto_path, bordas=[], contornos=contornos, 
                                texto_ocr=texto_ocr, dimensoes=dimensoes)
        except Exception as e:
            return FotoResultado(caminho=foto_path, bordas=[], contornos=[], texto_ocr="", 
                                dimensoes=(0, 0), erro=str(e))
    
    def catalogar_entidades(self, entidades: List[Dict]) -> Catalogo:
        logger.info(f"Catalogando {len(entidades)} entidades")
        catalogo = Catalogo()
        
        for entidade in entidades:
            tipo = entidade.get("tipo", "").upper()
            layer = entidade.get("layer", "").upper()
            
            if tipo in self.ENTIDADE_PILAR or any(l in layer for l in self.LAYERS_PILAR):
                catalogo.pilares.append(entidade)
            elif tipo in self.ENTIDADE_VIGA or any(l in layer for l in self.LAYERS_VIGA):
                catalogo.vigas.append(entidade)
            elif tipo in self.ENTIDADE_LAJE or any(l in layer for l in self.LAYERS_LAJE):
                catalogo.lajes.append(entidade)
            elif tipo in self.ENTIDADE_TEXTO:
                catalogo.textos.append(entidade)
            elif tipo in self.ENTIDADE_COTA:
                catalogo.cotas.append(entidade)
            else:
                catalogo.vigas.append(entidade)
        
        return catalogo
    
    def _salvar_no_sqlite_bulk(self, catalogo: Catalogo, obra_id: str) -> int:
        """Salva entidades usando bulk insert para performance."""
        logger.info(f"Salvando catalogo no SQLite com bulk insert para obra {obra_id}")
        cursor = self.conn.cursor()
        registros_salvos = 0
        
        try:
            # Preparar todos os registros
            todos_registros = []
            
            for pilar in catalogo.pilares:
                registro_id = f"{obra_id}_pilar_{registros_salvos}"
                todos_registros.append((
                    registro_id, obra_id, pilar.get("tipo", "PILAR"), pilar.get("layer", ""),
                    json.dumps(pilar), pilar.get("posicao_x", 0), pilar.get("posicao_y", 0)
                ))
                registros_salvos += 1
            
            for viga in catalogo.vigas:
                registro_id = f"{obra_id}_viga_{registros_salvos}"
                todos_registros.append((
                    registro_id, obra_id, viga.get("tipo", "VIGA"), viga.get("layer", ""),
                    json.dumps(viga), viga.get("posicao_x", 0), viga.get("posicao_y", 0)
                ))
                registros_salvos += 1
            
            for laje in catalogo.lajes:
                registro_id = f"{obra_id}_laje_{registros_salvos}"
                todos_registros.append((
                    registro_id, obra_id, laje.get("tipo", "LAJE"), laje.get("layer", ""),
                    json.dumps(laje), laje.get("posicao_x", 0), laje.get("posicao_y", 0)
                ))
                registros_salvos += 1
            
            for texto in catalogo.textos:
                registro_id = f"{obra_id}_texto_{registros_salvos}"
                todos_registros.append((
                    registro_id, obra_id, texto.get("tipo", "TEXTO"), texto.get("layer", ""),
                    json.dumps(texto), texto.get("posicao_x", 0), texto.get("posicao_y", 0)
                ))
                registros_salvos += 1
            
            # Bulk insert em batches
            for i in range(0, len(todos_registros), BATCH_SIZE):
                batch = todos_registros[i:i + BATCH_SIZE]
                cursor.executemany("""
                    INSERT OR REPLACE INTO dxf_entidades 
                    (id, obra_id, tipo, layer, dados_json, posicao_x, posicao_y)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, batch)
            
            self.conn.commit()
            logger.info(f"Salvos {registros_salvos} registros em {len(todos_registros)/BATCH_SIZE:.0f} batches")
            return registros_salvos
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Erro ao salvar no SQLite: {e}")
            raise
    
    def salvar_no_sqlite(self, catalogo: Catalogo, obra_id: str) -> int:
        """Método público para salvar no SQLite (usa bulk insert)."""
        return self._salvar_no_sqlite_bulk(catalogo, obra_id)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas do cache."""
        if self.cache:
            return self.cache.get_stats()
        return {}
