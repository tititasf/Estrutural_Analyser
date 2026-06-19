"""
dxf_loader_worker.py — subprocess helper para extrair ops vetoriais de DXF.

Usa ezdxf.addons.drawing (Frontend + backend customizado) que processa TODOS os tipos
de entidade: LINE, LWPOLYLINE, ARC, CIRCLE, ELLIPSE, SPLINE, HATCH, INSERT/blocks,
MLINE, DIMENSION, etc.

Protocolo de saída (stdout binário):
  - pickle de lista de ops: [(type, color_hex, lineweight, data), ...]
    * 'path'   : ('path', '#rrggbb', lw, [(cmd, x, y, [ctrl pts])])
    * 'fill'   : ('fill', '#rrggbb', lw, [(cmd, x, y, [ctrl pts])])
    * 'polygon': ('polygon', '#rrggbb', lw, [(x, y), ...])
    * 'line'   : ('line', '#rrggbb', lw, (x0,y0), (x1,y1))
    * 'point'  : ('point', '#rrggbb', lw, (x, y))
  - Em caso de DXF muito grande (>_MAX_DXF_MB): pickle [('too_large', None, mb)]
  - Em caso de erro: pickle [('error', 'msg')]

NÃO importa PySide6 — isola ezdxf do processo principal (evita GC crash Python 3.14).
"""
import sys, io, warnings, pickle
from pathlib import Path

# Redirecionar stdout texto → stderr. Só bytes pickle vão para stdout.
_real_stdout = sys.stdout
sys.stdout = sys.stderr

warnings.filterwarnings('ignore')

_MAX_DXF_MB = 30.0
_SENTINEL_X = -5000

# Layers administrativos/decorativos que NUNCA devem ser mostrados no viewer
_SKIP_LAYERS_VIEWER = frozenset({'Folhas', 'CARIMBO', 'ESTRUTURACAO', 'Forcador', 'Perfil Metálico'})


# ── Bbox helper ────────────────────────────────────────────────────────────────

def get_bbox(doc, sentinel_x=_SENTINEL_X):
    """Calcula bbox do conteúdo real (ignora sentinelas em x < sentinel_x e layers admin)."""
    xs, ys = [], []
    try:
        for e in doc.modelspace():
            try:
                if e.dxf.layer in _SKIP_LAYERS_VIEWER:
                    continue
            except Exception:
                pass
            t = e.dxftype()
            try:
                if t == 'LWPOLYLINE':
                    for pt in e.vertices():
                        if pt[0] > sentinel_x:
                            xs.append(pt[0]); ys.append(pt[1])
                elif t == 'LINE':
                    sx2, ex2 = e.dxf.start.x, e.dxf.end.x
                    if sx2 > sentinel_x and ex2 > sentinel_x:
                        xs += [sx2, ex2]; ys += [e.dxf.start.y, e.dxf.end.y]
                elif t in ('TEXT', 'MTEXT'):
                    if hasattr(e.dxf, 'insert'):
                        ix, iy = e.dxf.insert.x, e.dxf.insert.y
                        if ix > sentinel_x:
                            xs.append(ix); ys.append(iy)
                elif t in ('CIRCLE', 'ARC') and hasattr(e.dxf, 'center'):
                    cx2, cy2 = e.dxf.center.x, e.dxf.center.y
                    if cx2 > sentinel_x:
                        xs.append(cx2); ys.append(cy2)
                elif t == 'INSERT' and hasattr(e.dxf, 'insert'):
                    ix, iy = e.dxf.insert.x, e.dxf.insert.y
                    if ix > sentinel_x:
                        xs.append(ix); ys.append(iy)
            except Exception:
                pass
    except Exception:
        pass
    if not xs:
        return None
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    mx = max(w * 0.04, 10)
    my = max(h * 0.05, 10)
    return (min(xs) - mx, min(ys) - my, max(xs) + mx, max(ys) + my)


# ── Backend serializador ───────────────────────────────────────────────────────

def _color_hex(color_str: str) -> str:
    """Normaliza cor: '#rrggbb' ou fallback branco."""
    if color_str and color_str.startswith('#') and len(color_str) >= 7:
        return color_str[:7].upper()
    return '#FFFFFF'


def _path_to_cmds(path):
    """Converte ezdxf Path ou BkPath2d em lista de comandos serializáveis.
    Formato de args alinhado com QPainterPath:
      M x y
      L x y
      Q ctrl_x ctrl_y end_x end_y   (quadTo)
      C ctrl1_x ctrl1_y ctrl2_x ctrl2_y end_x end_y  (cubicTo)
    """
    from ezdxf.path import Command

    # BkPath2d (NumpyPath2d) → converter para ezdxf.Path via .to_path()
    if hasattr(path, 'to_path'):
        path = path.to_path()

    cmds = []
    start = path.start
    cmds.append(('M', start.x, start.y))
    for cmd in path:
        t = cmd.type
        if t == Command.LINE_TO:
            cmds.append(('L', cmd.end.x, cmd.end.y))
        elif t == Command.CURVE3_TO:
            # quadTo(ctrl, end)
            cmds.append(('Q', cmd.ctrl.x, cmd.ctrl.y, cmd.end.x, cmd.end.y))
        elif t == Command.CURVE4_TO:
            # cubicTo(ctrl1, ctrl2, end)
            cmds.append(('C', cmd.ctrl1.x, cmd.ctrl1.y,
                         cmd.ctrl2.x, cmd.ctrl2.y, cmd.end.x, cmd.end.y))
        elif t == Command.MOVE_TO:
            cmds.append(('M', cmd.end.x, cmd.end.y))
    return cmds


class SerializingBackend:
    """Backend ezdxf que serializa draw calls para lista de ops Python puras.
    Sem limite de ops — viewport culling no paintEvent trata a performance.
    Linhas do mesmo segmento são batched em listas para reduzir objects."""

    def __init__(self, bbox=None):
        self.ops = []
        self._bbox = bbox   # (x0, y0, x1, y1) para referência
        self._max_ops = 500_000   # limite de segurança contra OOM (DXFs enormes)
        # Pré-extrai limites X para culling rápido (None = sem filtro)
        if bbox:
            self._cx0, self._cx1 = bbox[0], bbox[2]
        else:
            self._cx0 = self._cx1 = None

    def _skip_x(self, *xs) -> bool:
        """True se TODOS os pontos dados estão fora do intervalo X do bbox."""
        if self._cx0 is None:
            return False
        return max(xs) < self._cx0 or min(xs) > self._cx1

    # ── Interface obrigatória ──────────────────────────────────────────────────

    def configure(self, config):
        pass

    def clear(self):
        self.ops.clear()

    def set_background(self, color):
        pass

    def finalize(self):
        pass

    def enter_entity(self, entity, properties):
        pass

    def exit_entity(self, entity):
        pass

    # ── Draw calls ────────────────────────────────────────────────────────────

    def _over_limit(self):
        return len(self.ops) >= self._max_ops

    def draw_point(self, pos, properties):
        if self._over_limit() or self._skip_x(pos.x):
            return
        color = _color_hex(properties.color)
        lw = properties.lineweight or 0.25
        self.ops.append(('point', color, lw, (pos.x, pos.y)))

    def draw_line(self, start, end, properties):
        if self._over_limit() or self._skip_x(start.x, end.x):
            return
        color = _color_hex(properties.color)
        lw = properties.lineweight or 0.25
        self.ops.append(('line', color, lw, (start.x, start.y), (end.x, end.y)))

    def draw_solid_lines(self, lines, properties):
        """Batch: serializa todas as linhas de um LWPOLYLINE/LINE juntas."""
        if self._over_limit():
            return
        color = _color_hex(properties.color)
        lw = properties.lineweight or 0.25
        # Serializar como 'lines' batch: ('lines', color, lw, [(x0,y0,x1,y1), ...])
        segs = []
        for start, end in lines:
            if self._skip_x(start.x, end.x):
                continue
            segs.append((start.x, start.y, end.x, end.y))
            if len(segs) + len(self.ops) >= self._max_ops:
                break
        if segs:
            self.ops.append(('lines', color, lw, segs))

    def draw_path(self, path, properties):
        if self._over_limit():
            return
        color = _color_hex(properties.color)
        lw = properties.lineweight or 0.25
        try:
            cmds = _path_to_cmds(path)
            if cmds:
                # Culling por X: verifica todos os valores X dos comandos
                if self._cx0 is not None:
                    xs = [c[1] for c in cmds]  # índice 1 = primeiro valor numérico (x)
                    if self._skip_x(*xs):
                        return
                self.ops.append(('path', color, lw, cmds))
        except Exception:
            pass

    def draw_filled_paths(self, paths, properties):
        color = _color_hex(properties.color)
        lw = properties.lineweight or 0.25
        for path in paths:
            if self._over_limit():
                break
            try:
                cmds = _path_to_cmds(path)
                if cmds:
                    if self._cx0 is not None:
                        xs = [c[1] for c in cmds]
                        if self._skip_x(*xs):
                            continue
                    self.ops.append(('fill', color, lw, cmds))
            except Exception:
                pass

    def draw_filled_polygon(self, points, properties):
        if self._over_limit():
            return
        color = _color_hex(properties.color)
        lw = properties.lineweight or 0.25
        # BkPoints2d (NumpyPoints2d) tem .to_tuples() → list of (x, y)
        try:
            pts = list(points.to_tuples())
        except AttributeError:
            try:
                pts = [(p.x, p.y) for p in points]
            except Exception:
                pts = []
        if pts:
            if self._skip_x(*(p[0] for p in pts)):
                return
            self.ops.append(('polygon', color, lw, pts))

    def draw_image(self, image_data, properties):
        pass   # Ignorar imagens raster embutidas


# ── Render principal ───────────────────────────────────────────────────────────

def render_ops(dxf_path: Path, bbox) -> list:
    """Renderiza DXF usando ezdxf Frontend + backend serializador.
    Retorna (ops, fit_bbox) onde fit_bbox é a bbox REAL do conteúdo filtrado
    (Y range do conteúdo real, X range do corte explícito) para zoom correto."""
    import ezdxf
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.config import Configuration, HatchPolicy

    doc = ezdxf.readfile(str(dxf_path))

    # Sempre calcular bbox real do conteúdo (exclui skip layers e sentinelas)
    content_bbox = get_bbox(doc)

    if bbox is None:
        culling_bbox = content_bbox
        fit_bbox = content_bbox
    else:
        culling_bbox = bbox
        # fit_bbox: Y range real do conteúdo + X range do corte explícito
        # Evita zoom minúsculo causado por Y=-9999..9999 nos bboxes de split
        if content_bbox:
            bx0, _by0, bx1, _by1 = bbox
            cx0, cy0, cx1, cy1 = content_bbox
            fx0 = max(bx0, cx0) if bx0 > -5000 else cx0
            fx1 = min(bx1, cx1) if bx1 < 50000 else cx1
            fit_bbox = (fx0, cy0, fx1, cy1) if fx0 < fx1 else content_bbox
        else:
            fit_bbox = bbox

    backend = SerializingBackend(bbox=culling_bbox)
    ctx = RenderContext(doc)

    # Forçar layers visíveis, exceto layers administrativos (Folhas, CARIMBO, etc.)
    # lp.layer = nome real do layer (ezdxf 1.x: LayerProperties.layer guarda o nome)
    def _force_visible_except_admin(layers):
        for lp in layers:
            lp.is_visible = (lp.layer not in _SKIP_LAYERS_VIEWER)

    ctx.set_layer_properties_override(_force_visible_except_admin)

    # Configuração máxima: exibe DEFPOINTS, hatches com padrão real
    config = Configuration(
        show_defpoints=True,                 # exibe layer DEFPOINTS (cotas, etc.)
        hatch_policy=HatchPolicy.NORMAL,     # padrão real: ANSI31 mostra linhas diagonais
    )

    frontend = Frontend(ctx, backend, config=config)
    frontend.draw_layout(doc.modelspace())

    return backend.ops, fit_bbox


# ── Protocolo I/O ──────────────────────────────────────────────────────────────

def _write_pickle(obj):
    _real_stdout.buffer.write(pickle.dumps(obj))
    _real_stdout.buffer.flush()


if __name__ == '__main__':
    import json

    if len(sys.argv) < 2:
        sys.stderr.write('Usage: dxf_loader_worker.py <dxf_path> [bbox_json|null]\n')
        sys.exit(1)

    dxf_path = Path(sys.argv[1])

    bbox = None
    if len(sys.argv) >= 3 and sys.argv[2] != 'null':
        try:
            bbox = tuple(json.loads(sys.argv[2]))
        except Exception:
            bbox = None

    # Guard de tamanho
    try:
        size_mb = dxf_path.stat().st_size / 1024 / 1024
        if size_mb > _MAX_DXF_MB:
            _write_pickle([('too_large', None, size_mb)])
            sys.exit(0)
    except Exception as e:
        _write_pickle([('error', f'stat failed: {e}')])
        sys.exit(1)

    try:
        ops, computed_bbox = render_ops(dxf_path, bbox)
        # Prefixar com bbox computada para que o viewer possa usar
        result = [('bbox', computed_bbox)] + ops
        _write_pickle(result)
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        _write_pickle([('error', err[:800])])
        sys.exit(1)
