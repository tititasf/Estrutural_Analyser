# -*- coding: utf-8 -*-
"""
DXF Generator - Gera arquivos DXF de saída para os robôs.

Cria linhas, textos, polilinhas, hatches, cotas e blocos via ezdxf.
Usado na Fase 4 (Robot Output) do pipeline.
"""

import os
from typing import Any, Dict, List, Optional, Tuple, Union

import ezdxf
from ezdxf.enums import TextEntityAlignment


class DXFGenerator:
    """
    Gerador de arquivos DXF.

    Cria um documento DXF novo e fornece métodos para adicionar
    entidades geométricas (linhas, polylines, textos, hatches, cotas, blocos).
    """

    def __init__(
        self,
        filename: str = "output.dxf",
        doc=None,
        add_standard_layers: bool = True,
        **kwargs,
    ):
        """
        Args:
            filename: Nome do arquivo de saída.
            doc: Documento ezdxf existente (None = cria novo R2010).
            add_standard_layers: Se True, configura layers padrão.
        """
        self.filename = filename
        self.doc = doc or ezdxf.new("R2010")
        self.msp = self.doc.modelspace()
        self._stats = {
            "lines": 0,
            "polylines": 0,
            "texts": 0,
            "hatches": 0,
            "dimensions": 0,
            "blocks": 0,
        }

        if add_standard_layers:
            self._setup_standard_layers()
        self._setup_styles()

    def _setup_standard_layers(self):
        """Configura os layers baseados no Knowledge Graph Vector."""
        layers = [
            ("VIGAS", 1, "CONTINUOUS"),
            ("PILARES", 2, "CONTINUOUS"),
            ("LAJES", 3, "CONTINUOUS"),
            ("EIXOS", 7, "DASHED"),
            ("COTAS", 5, "CONTINUOUS"),
            ("TEXTOS", 7, "CONTINUOUS"),
            ("SARRAFOS", 4, "CONTINUOUS"),
            ("ARMADURA", 6, "CONTINUOUS"),
        ]
        for name, color, linetype in layers:
            if name not in self.doc.layers:
                self.doc.layers.add(name, color=color, linetype=linetype)

    def setup_layers(self, layers: Dict[str, Dict[str, Any]]):
        """
        Configura layers personalizados vindos de um dicionário.

        Args:
            layers: Dict {name: {color: int, linetype: str}}
        """
        for name, props in layers.items():
            color = props.get("color", 7)
            linetype = props.get("linetype", "CONTINUOUS")
            if name not in self.doc.layers:
                layer = self.doc.layers.add(name, color=color, linetype=linetype)

    def _setup_styles(self):
        """Configura estilos de texto, cotas, MLINE e layers de template."""
        # Estilos de texto
        if "STR_STANDARD" not in self.doc.styles:
            self.doc.styles.add("STR_STANDARD", font="arial.ttf")
        if "ARIAL" not in self.doc.styles:
            self.doc.styles.add("ARIAL", font="Arial.ttf")

        # Estilos de mline
        try:
            if "SAR2" not in self.doc.mline_styles:
                mline_style = self.doc.mline_styles.new("SAR2")
        except Exception:
            pass

        # Layers de template padrão
        template_layers = [
            ("PAINEL-NOVA", 7),
        ]
        for name, color in template_layers:
            if name not in self.doc.layers:
                self.doc.layers.add(name, color=color)

        # Dimstyles ground truth (Fase 7)
        gt_dimstyles = ["EZ DXF"]
        for ds_name in gt_dimstyles:
            if ds_name not in self.doc.dimstyles:
                ds = self.doc.dimstyles.new(ds_name)

    def add_polyline(
        self,
        points: List[Tuple[float, float]],
        layer: str = "0",
        closed: bool = False,
    ):
        """Adiciona uma polilinha (LWPOLYLINE) ao desenho."""
        self.msp.add_lwpolyline(points, dxfattribs={"layer": layer}, close=closed)
        self._stats["polylines"] += 1

    def add_rectangle_pline(
        self,
        points: List[Tuple[float, float]],
        layer: str = "0",
    ):
        """Adiciona um retângulo (alias para polyline fechada)."""
        self.add_polyline(points, layer=layer, closed=True)

    def add_mline(
        self,
        points: List[Tuple[float, float]],
        style: str = "SAR2",
        scale: float = 1.0,
        layer: str = "0",
    ):
        """Adiciona uma Multilinha (usada para sarrafos)."""
        # ezdxf não suporta mline nativamente em todas as versões,
        # fallback para polyline com espessura
        self.add_polyline(points, layer=layer)

    def add_line(
        self,
        start: Tuple[float, float, float],
        end: Tuple[float, float, float],
        layer: str = "0",
    ):
        """Adiciona uma linha simples."""
        self.msp.add_line(start, end, dxfattribs={"layer": layer})
        self._stats["lines"] += 1

    def add_text(
        self,
        text: str,
        insert: Tuple[float, float],
        height: float = 2.5,
        layer: str = "0",
        rotation: float = 0,
    ):
        """Adiciona texto formatado (TEXT)."""
        self.msp.add_text(
            text,
            dxfattribs={
                "insert": insert,
                "height": height,
                "layer": layer,
                "rotation": rotation,
                "style": "STR_STANDARD",
            },
        )
        self._stats["texts"] += 1

    def add_mtext(
        self,
        text: str,
        insert: Tuple[float, float],
        height: float = 2.5,
        layer: str = "0",
        width: float = 0,
        attachment_point: int = 1,
    ):
        """Adiciona MTEXT formatado."""
        mtext = self.msp.add_mtext(
            text,
            dxfattribs={
                "insert": insert,
                "char_height": height,
                "layer": layer,
                "style": "ARIAL",
            },
        )
        if width:
            mtext.dxf.width = width
        if attachment_point:
            mtext.dxf.attachment_point = attachment_point
        self._stats["texts"] += 1

    def add_hatch(
        self,
        boundary_points: List[Tuple[float, float]],
        pattern: str = "SOLID",
        layer: str = "0",
        scale: float = 1.0,
        color: int = None,
        angle: float = 0,
    ):
        """Adiciona um hatch (preenchimento) com boundary poligonal."""
        hatch = self.msp.add_hatch(color=color or 256, dxfattribs={"layer": layer})
        hatch.paths.add_polyline_path(boundary_points, is_closed=True)
        if pattern != "SOLID":
            hatch.set_pattern_fill(pattern, scale=scale, angle=angle)
        self._stats["hatches"] += 1

    def add_dimension(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        location: Tuple[float, float] = None,
        layer: str = "0",
    ):
        """Adiciona uma cota linear (usa EZ DXF dimstyle -- ground truth Fase 7)."""
        loc = location or (
            (start[0] + end[0]) / 2,
            (start[1] + end[1]) / 2 + 5,
        )
        dim = self.msp.add_linear_dim(
            base=loc,
            p1=start,
            p2=end,
            dimstyle="EZ DXF",
            dxfattribs={"layer": layer},
        )
        dim.render()
        self._stats["dimensions"] += 1

    def add_block_ref(
        self,
        name: str,
        insert: Tuple[float, float],
        scale: float = 1.0,
        rotation: float = 0,
    ):
        """Insere uma referência de bloco."""
        self.msp.add_blockref(
            name,
            insert,
            dxfattribs={
                "xscale": scale,
                "yscale": scale,
                "rotation": rotation,
            },
        )
        self._stats["blocks"] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas da geração."""
        return {
            "filename": self.filename,
            "status": "generated",
            **self._stats,
        }

    def save(self, filepath: str = None):
        """Salva o arquivo DXF final."""
        target = filepath or self.filename
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        self.doc.saveas(target)
        print(f"DXF gerado com sucesso: {target}")
