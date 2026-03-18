"""
spatial_index.py - Indice Espacial para Geometrias DXF

Wrapper em torno do rtree para indexacao espacial rapida de entidades DXF.
Usado por BeamTracer, SlabTracer, ContextEngine, BeamWalker e TextAssociator.

Operacoes suportadas:
  - Insercao de entidades com bounding box (minx, miny, maxx, maxy)
  - Query por interseccao de bounding box
  - Query por proximidade (nearest neighbors)
  - Limpeza completa do indice
"""

from rtree import index
from typing import List, Any, Dict, Tuple


class SpatialIndex:
    """
    Wrapper em torno do rtree para indexar geometrias do DXF.
    Permite queries espaciais rapidas (ex: encontrar texto proximo a um pilar).

    Atributos:
        idx: Instancia do rtree.Index para queries espaciais.
        items: Dicionario mapeando ID interno -> objeto original inserido.
        counter: Contador auto-incrementado para IDs internos.
    """

    def __init__(self) -> None:
        """Inicializa o indice espacial 2D com rtree."""
        properties = index.Property()
        properties.dimension = 2
        self.idx: index.Index = index.Index(properties=properties)
        self.items: Dict[int, Any] = {}
        self.counter: int = 0

    def insert(self, item: Any, bounds: Tuple[float, float, float, float]) -> None:
        """
        Insere um item no indice.

        Args:
            item: Objeto original a ser armazenado (poligono, linha, texto, etc.).
            bounds: Bounding box no formato (minx, miny, maxx, maxy).
        """
        self.idx.insert(self.counter, bounds)
        self.items[self.counter] = item
        self.counter += 1

    def query_bbox(self, bounds: Tuple[float, float, float, float]) -> List[Any]:
        """
        Retorna todos os itens que intersectam o bounding box.

        Args:
            bounds: Bounding box de busca no formato (minx, miny, maxx, maxy).

        Returns:
            Lista de objetos originais cujos bounding boxes intersectam o dado.
        """
        hits = list(self.idx.intersection(bounds))
        return [self.items[i] for i in hits]

    def query_nearest(
        self, coords: Tuple[float, float], num_results: int = 1
    ) -> List[Any]:
        """
        Retorna os 'num_results' itens mais proximos das coordenadas dadas.

        Args:
            coords: Ponto de referencia no formato (x, y).
            num_results: Numero maximo de resultados a retornar.

        Returns:
            Lista dos objetos mais proximos ordenados por distancia.
        """
        # rtree.nearest espera bounds (minx, miny, maxx, maxy);
        # para pontos, duplicar as coordenadas funciona: (x, y, x, y)
        hits = list(self.idx.nearest(coords * 2, num_results))
        return [self.items[i] for i in hits]

    def clear(self) -> None:
        """Limpa completamente o indice, removendo todos os itens."""
        self.idx = index.Index()
        self.items = {}
        self.counter = 0
