import logging
import os
import glob
import ezdxf
from pathlib import Path
from typing import Dict, Any, List
from src.core.optimizers.base_optimizer import BaseOptimizer

logger = logging.getLogger(__name__)

class CuttingPlanOptimizer(BaseOptimizer):
    """
    Otimizador de Plano de Corte (Nesting 2D) focado em compensados e sarrafos.
    Lê os DXFs finais e extrai todos os elementos geométricos da layer "PAINEL", "CHAPA" ou similares
    para contabilizar as chapas necessárias.
    """
    
    def __init__(self, board_length: float = 244.0, board_width: float = 122.0, kerf: float = 0.5):
        self.board_length = board_length
        self.board_width = board_width
        self.kerf = kerf
        self.last_results = {}

    def _extract_panels_from_dxf(self, dxf_path: str) -> List[Dict[str, float]]:
        """Abre o DXF e extrai a largura e altura de todos os LWPOLYLINEs na layer PAINEL/CHAPA."""
        panels = []
        sarrafos = []
        try:
            doc = ezdxf.readfile(dxf_path)
            msp = doc.modelspace()
            
            # Buscar LWPOLYLINEs
            for entity in msp.query('LWPOLYLINE'):
                layer = entity.dxf.layer.upper()
                # Compatibiliza com 'Painéis' (com acento quebrado) ou 'CHAPA'
                if "PAIN" in layer or "CHAP" in layer or "F-CORTE" in layer:
                    pts = list(entity.get_points(format='xy'))
                    if len(pts) >= 4:
                        xs = [p[0] for p in pts]
                        ys = [p[1] for p in pts]
                        w = max(xs) - min(xs)
                        h = max(ys) - min(ys)
                        if w > 0 and h > 0:
                            panels.append({
                                "source": Path(dxf_path).name,
                                "layer": entity.dxf.layer,
                                "w": round(w, 2),
                                "h": round(h, 2)
                            })
                            
            # Buscar LINEs para sarrafos
            for entity in msp.query('LINE'):
                layer = entity.dxf.layer.upper()
                if "SARR" in layer:
                    start = entity.dxf.start
                    end = entity.dxf.end
                    length = ((end.x - start.x)**2 + (end.y - start.y)**2)**0.5
                    if length > 0:
                        sarrafos.append({
                            "source": Path(dxf_path).name,
                            "layer": entity.dxf.layer,
                            "len": round(length, 2)
                        })
        except Exception as e:
            logger.error(f"Erro lendo DXF no Otimizador (arquivo: {dxf_path}): {e}")
            
        return panels, sarrafos

    def optimize(self, elements: List[Dict[str, Any]], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Neste cenário, 'elements' é esperado como uma lista de caminhos absolutos para arquivos DXF.
        """
        logger.info(f"Otimizando plano de corte a partir de {len(elements)} arquivos DXF...")
        
        all_panels = []
        all_sarrafos = []
        for dxf_obj in elements:
            dxf_path = dxf_obj.get('file_path')
            if dxf_path and os.path.exists(dxf_path):
                panels, sarrafos = self._extract_panels_from_dxf(dxf_path)
                all_panels.extend(panels)
                all_sarrafos.extend(sarrafos)
                
        logger.debug(f"Total de painéis extraídos: {len(all_panels)}. Sarrafos: {len(all_sarrafos)}")
        
        area_chapa = self.board_length * self.board_width
        area_total_pecas = sum((p["w"] * p["h"]) for p in all_panels)
        
        # Heurística inicial para chapas
        area_requerida_estimada = area_total_pecas * 1.15 
        chapas_necessarias = max(1, int(-(-area_requerida_estimada // area_chapa))) if area_total_pecas > 0 else 0
        
        eficiencia = (area_total_pecas / (chapas_necessarias * area_chapa)) * 100 if chapas_necessarias > 0 else 0.0
        
        # Heurística para Sarrafos
        comprimento_sarrafos_cm = sum(s["len"] for s in all_sarrafos)
        comprimento_sarrafos_m = comprimento_sarrafos_cm / 100.0
        # Assumindo barra de sarrafo comercial típica de 3 metros (300 cm)
        barras_sarrafo_3m = max(1, int(-(-comprimento_sarrafos_m // 3.0))) if comprimento_sarrafos_m > 0 else 0
        
        self.last_results = {
            "arquivos_dxf_lidos": len(elements),
            "pecas_corte": len(all_panels),
            "area_total_pecas_cm2": area_total_pecas,
            "area_total_pecas_m2": round(area_total_pecas / 10000.0, 2),
            "chapas_estimadas": chapas_necessarias,
            "eficiencia_estimada_porcento": round(eficiencia, 2),
            "dimensao_chapa_cm": f"{self.board_length}x{self.board_width}",
            "metodo_chapas": "Area_Heuristic_15_perc_overhead",
            "sarrafos_corte": len(all_sarrafos),
            "comprimento_total_sarrafos_m": round(comprimento_sarrafos_m, 2),
            "barras_sarrafo_estimadas_3m": barras_sarrafo_3m
        }
        return self.last_results

    def report(self) -> str:
        if not self.last_results:
            return "Nenhum plano de corte gerado ainda."
            
        return (
            f"=== RELATÓRIO DO PLANO DE CORTE E MATERIAIS ===\n"
            f"DXFs analisados: {self.last_results['arquivos_dxf_lidos']}\n"
            f"-- MADEIRITE/COMPENSADO --\n"
            f"Total de Peças (Painéis): {self.last_results['pecas_corte']}\n"
            f"Área Total Líquida: {self.last_results['area_total_pecas_m2']:.2f} m²\n"
            f"Chapas Necessárias ({self.last_results['dimensao_chapa_cm']}): {self.last_results['chapas_estimadas']}\n"
            f"Eficiência Estimada (Nesting): {self.last_results['eficiencia_estimada_porcento']}%\n"
            f"-- SARRAFOS --\n"
            f"Total de Ripas/Travessas: {self.last_results['sarrafos_corte']}\n"
            f"Metros Lineares Totais: {self.last_results['comprimento_total_sarrafos_m']} m\n"
            f"Barras Comerciais (3m) Estimadas: {self.last_results['barras_sarrafo_estimadas_3m']}\n"
            f"==============================================="
        )
