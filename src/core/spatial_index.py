from rtree import index
from typing import List, Any, Dict, Tuple

class SpatialIndex:
    """
    Wrapper em torno do rtree para indexar geometrias do DXF.
    Permite queries espaciais rápidas (ex: encontrar texto próximo a um pilar).
    """
    def __init__(self):
        properties = index.Property()
        properties.dimension = 2
        self.idx = index.Index(properties=properties)
        self.items: Dict[int, Any] = {} # Mapeia ID -> Objeto original
        self.counter = 0

    def insert(self, item: Any, bounds: Tuple[float, float, float, float]):
        """
        Insere um item no índice.
        bounds format: (minx, miny, maxx, maxy)
        """
        self.idx.insert(self.counter, bounds)
        self.items[self.counter] = item
        self.counter += 1

    def query_bbox(self, bounds: Tuple[float, float, float, float]) -> List[Any]:
        """
        Retorna todos os itens que intersectam o bounding box.
        """
        hits = list(self.idx.intersection(bounds))
        return [self.items[i] for i in hits]

    def query_nearest(self, coords: Tuple[float, float], num_results: int = 1) -> List[Any]:
        """
        Retorna os 'num_results' itens mais próximos das coordenadas dadas.
        coords: (x, y)
        """
        # Rtree nearest espera limites também, mas para pontos duplicar funciona
        hits = list(self.idx.nearest(coords * 2, num_results))
        return [self.items[i] for i in hits]

    def clear(self):
        self.idx = index.Index()
        self.items = {}
        self.counter = 0
