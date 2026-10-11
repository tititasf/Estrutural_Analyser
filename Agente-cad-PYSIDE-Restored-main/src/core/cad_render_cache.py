"""Bounded, process-local CAD canvas reuse for sequential batch renderers.

Only the structural background is retained. Per-view artists are removed even
on failure. Callers must use separate processes, never concurrent threads.
"""
from contextlib import contextmanager
from collections import OrderedDict
from pathlib import Path
import os

_canvases = OrderedDict()


def _draw_cad_drawing(doc, ax):
    """Draw the modelspace keeping styled linetypes as one dashed artist each.

    ezdxf's accurate linetype stage explodes every styled line into its dashes.
    TQS patterns are ~1 drawing unit long, so a whole floor turns into hundreds
    of thousands of sub-pixel segments (60 MB per SVG view).  Here the stage
    forwards the undivided line/path and tags the artist with ezdxf's own
    pattern (drawing units, ltscale and min dash already applied);
    ``visible_cad_strokes`` turns it into the view's stroke dash array.
    """
    from ezdxf.math import Vec2
    from ezdxf.addons.drawing.frontend import UniversalFrontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    from ezdxf.addons.drawing.pipeline import (
        BackendStage2d, ClippingStage2d, LinetypeStage2d, RenderPipeline2d)
    from ezdxf.addons.drawing import RenderContext

    class DashedBackend(MatplotlibBackend):
        dash = ()

        def _tagged(self, artists, draw):
            count = len(artists)
            draw()
            for artist in artists[count:]:
                artist._cad_dash_pattern = self.dash

        def draw_line(self, start, end, properties):
            self._tagged(self.ax.lines, lambda: super(DashedBackend, self).draw_line(start, end, properties))

        def draw_path(self, path, properties):
            self._tagged(self.ax.patches, lambda: super(DashedBackend, self).draw_path(path, properties))

    class DashedStage(LinetypeStage2d):
        def _forward(self, properties, draw):
            pattern = self.pattern(properties) if len(properties.linetype_pattern) >= 2 else ()
            backend.dash = tuple(pattern)
            try:
                draw()
            finally:
                backend.dash = ()

        def draw_line(self, start, end, properties):
            self._forward(properties, lambda: self.next_stage.draw_line(Vec2(start), Vec2(end), properties))

        def draw_path(self, path, properties):
            self._forward(properties, lambda: self.next_stage.draw_path(path, properties))

    class DashedPipeline(RenderPipeline2d):
        def build_render_pipeline(self):
            last = BackendStage2d(self.backend, converter=self.get_backend_properties)
            dashes = DashedStage(self.config, get_ltype_scale=self.get_vp_ltype_scale, next_stage=last)
            return ClippingStage2d(self.config, self.clipping_portal, next_stage=dashes)

    backend = DashedBackend(ax)
    UniversalFrontend(RenderContext(doc), DashedPipeline(backend)).draw_layout(doc.modelspace())


def _apply_view_dashes(ax):
    """Scale each tagged drawing-unit pattern to this view (points, unscaled by width)."""
    import matplotlib
    origin, unit = ax.transData.transform([(0.0, 0.0), (1.0, 0.0)])
    points = abs(unit[0] - origin[0]) * 72.0 / ax.figure.dpi
    with matplotlib.rc_context({"lines.scale_dashes": False}):
        for artist in (*ax.lines, *ax.patches):
            pattern = getattr(artist, "_cad_dash_pattern", ())
            if pattern:
                artist.set_linestyle((0, [length * points for length in pattern]))


def close_cached_canvas():
    import matplotlib.pyplot as plt
    for fig, _ in _canvases.values():
        plt.close(fig)
    _canvases.clear()


@contextmanager
def prepared_cad_canvas(path, width, height, dpi, *, reuse=True):
    """Yield the unchanged full CAD drawing with a clean per-view overlay."""
    import ezdxf
    import matplotlib
    import matplotlib.pyplot as plt

    path = Path(path).resolve()
    stat = path.stat()
    key = (os.getpid(), str(path), stat.st_dev, stat.st_ino,
           stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, width, height, dpi,
           repr(sorted(matplotlib.rcParams.items())))
    if not reuse:
        close_cached_canvas()
    if key not in _canvases:
        # Two palettes allow plain CAD text and outlined annotation text to
        # alternate without rebuilding the entire structural drawing per item.
        while len(_canvases) >= 2:
            _, (old_fig, _) = _canvases.popitem(last=False)
            plt.close(old_fig)
        doc = ezdxf.readfile(str(path))
        fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_facecolor("#0d0d0d")
        fig.patch.set_facecolor("#0d0d0d")
        try:
            _draw_cad_drawing(doc, ax)
        except BaseException:
            plt.close(fig)
            raise
        _canvases[key] = (fig, ax)
    _canvases.move_to_end(key)
    fig, ax = _canvases[key]
    figure_size = fig.get_size_inches().copy()
    children = set(ax.get_children())
    limits = (ax.get_xlim(), ax.get_ylim())
    data_lim = ax.dataLim.frozen()
    position = ax.get_position(original=True).frozen()
    try:
        yield fig, ax
    finally:
        for artist in list(ax.get_children()):
            if artist not in children:
                artist.remove()
        ax.dataLim.set(data_lim)
        ax.set_xlim(limits[0])
        ax.set_ylim(limits[1])
        ax.set_position(position)
        fig.set_size_inches(figure_size, forward=True)
        if not reuse:
            close_cached_canvas()


def render_worker_limit(requested, item_count):
    """Bound explicit parallelism by available CPUs and spare host memory."""
    try:
        cpus = len(os.sched_getaffinity(0))
    except AttributeError:
        cpus = os.cpu_count() or 1
    memory_limit = cpus
    try:
        values = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        available = int(values['MemAvailable'].split()[0]) * 1024
        # Host MemAvailable can exceed a systemd/container memory.max.
        relative = next((line.split(':', 2)[2] for line in
            Path('/proc/self/cgroup').read_text().splitlines()
            if line.startswith('0::')), None)
        if relative is not None:
            group = Path('/sys/fs/cgroup') / relative.lstrip('/')
            # The v2 hierarchy root need not expose memory.max/current.
            # Keep the measured ancestor budget if a root controller is absent.
            while group.is_relative_to(Path('/sys/fs/cgroup')) and group != Path('/sys/fs/cgroup'):
                maximum = (group / 'memory.max').read_text().strip()
                if maximum != 'max':
                    spare = int(maximum) - int((group / 'memory.current').read_text())
                    available = min(available, max(0, spare))
                group = group.parent
        memory_limit = max(1, (available - 512 * 1024**2) // (1024**3))
    except (OSError, KeyError, ValueError):
        pass
    return max(1, min(max(1, requested), max(1, item_count), cpus, memory_limit))


@contextmanager
def visible_cad_strokes(ax):
    """Skip wholly invisible CAD dash paths only during a clipped view export.

    Paths crossing or touching the view are retained in full and in their
    original paint order. The complete cached drawing is restored afterwards.
    The SVG's permanent axes clip already hides the excluded paths.
    """
    import numpy as np
    from matplotlib.collections import LineCollection
    restored = []
    ax.apply_aspect()
    _apply_view_dashes(ax)
    try:
        for collection in ax.collections:
            if not isinstance(collection, LineCollection):
                continue
            if not collection.get_clip_on() or collection.get_transform() != ax.transData:
                continue
            clip = collection.get_clip_box()
            if clip is None or not np.allclose(clip.extents, ax.bbox.extents):
                continue
            if len(collection.get_linewidths()) != 1 or len(collection.get_colors()) != 1:
                continue
            if collection.get_path_effects() or collection.get_offsets().any():
                continue
            paths = collection.get_paths()
            if not paths or any(len(p.vertices) != 2 for p in paths):
                continue
            vertices = np.asarray([p.vertices for p in paths])
            # Generous guard for stroke width and antialias at the clip edge.
            guard = float(collection.get_linewidths()[0]) * ax.figure.dpi / 72 + 4
            box = ax.bbox.expanded(1 + 2*guard/ax.bbox.width, 1 + 2*guard/ax.bbox.height)
            bounds = ax.transData.inverted().transform(box.get_points())
            lo, hi = bounds.min(axis=0), bounds.max(axis=0)
            keep = np.all(vertices.max(axis=1) >= lo, axis=1) & np.all(vertices.min(axis=1) <= hi, axis=1)
            if not keep.all():
                restored.append((collection, collection._paths))
                collection._paths = [p for p, visible in zip(paths, keep) if visible]
        yield
    finally:
        for collection, paths in restored:
            collection._paths = paths
