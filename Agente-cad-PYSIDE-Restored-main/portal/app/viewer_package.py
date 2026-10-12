"""Lossless, optional SVG derivative. Engineering inputs are never modified.

Only independent matplotlib LineCollection M/L paths are partitioned. All
other painting units stay in the shell, including glyphs, curves and fills.
Unknown selectors/compositing reject the derivative instead of guessing bounds.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import struct
import os
import tempfile
import threading
from pathlib import Path
import xml.etree.ElementTree as ET
from dataclasses import dataclass

VERSION = "regional-ml-v1"
_LOCKS = [threading.Lock() for _ in range(32)]
NUMBER = rb"[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?"
ML = re.compile(rb"\s*M\s*(" + NUMBER + rb")\s+(" + NUMBER + rb")\s*L\s*(" + NUMBER + rb")\s+(" + NUMBER + rb")\s*\Z")
PATH = re.compile(rb"<path\b[^>]*?/>", re.S)
GROUP = re.compile(rb'<g\s+id="LineCollection_[\w.-]+"\s*>(.*?)</g\s*>', re.S)


class UnsupportedSVG(ValueError):
    """The original viewer must be used for this SVG."""


@dataclass
class Package:
    manifest: dict
    shell: bytes
    fragments: list[bytes]
    segments: bytes

    def reconstruct(self) -> bytes:
        return re.sub(rb'<g data-cad-chunk="(\d+)"></g>',
                      lambda match: self.fragments[int(match[1])], self.shell)


def marker(index: int) -> bytes:
    return f'<g data-cad-chunk="{index}"></g>'.encode()


def build(svg: bytes, source_revision: str, chunk_size: int = 256) -> Package:
    if not 1 <= chunk_size <= 4096:
        raise ValueError("invalid chunk size")
    root = ET.fromstring(svg)
    if root.tag != "{http://www.w3.org/2000/svg}svg":
        raise UnsupportedSVG("not an SVG document")
    # Endpoint bounds are valid only with the renderer's bounded, fixed-pixel
    # strokes. Unknown/inherited stroke widths must use the integral viewer.
    thin = root.find("{http://www.w3.org/2000/svg}style[@id='cad-thin-strokes']")
    contract = "vector-effect:non-scaling-stroke!important;stroke-width:0.55px!important;stroke-linecap:butt!important;stroke-linejoin:miter!important;"
    if root.get("data-cad-thin-strokes") != "1" or thin is None or contract not in re.sub(r"\s+", "", thin.text or ""):
        raise UnsupportedSVG("unbounded stroke painting")
    allowed = {b"*", b'svg[data-cad-thin-strokes="1"]:is(path,line,polyline,polygon)'}
    for css in re.findall(rb"<style\b[^>]*>(.*?)</style\s*>", svg, re.S):
        css = css.replace(b"<![CDATA[", b"").replace(b"]]>", b"")
        if b"@" in css or any(re.sub(rb"\s+", b"", s) not in allowed
                                for s in re.findall(rb"([^{}]+)\{[^{}]*\}", css)):
            raise UnsupportedSVG("unknown CSS selector")
        if re.search(rb"(?:[;{]|^)\s*(?:filter|mask|opacity|transform|mix-blend-mode|marker-start|marker-end|marker-mid)\s*:", css):
            raise UnsupportedSVG("dependent CSS painting")
    # Conservative initial scope. These may affect descendants outside endpoint
    # bounds or make painting depend on siblings absent from the current region.
    forbidden = {"transform", "opacity", "filter", "mask", "mix-blend-mode", "marker-start", "marker-end", "marker-mid"}
    def check(element, unsafe=False):
        unsafe = unsafe or bool(forbidden.intersection(element.attrib))
        style = element.get("style", "")
        unsafe = unsafe or any(re.search(r"(?:^|;)\s*" + key + r"\s*:", style) for key in forbidden)
        if element.get("id", "").startswith("LineCollection_"):
            if unsafe or set(element.attrib) != {"id"}:
                raise UnsupportedSVG("dependent LineCollection")
            for path in element:
                if path.tag != "{http://www.w3.org/2000/svg}path" or forbidden.intersection(path.attrib):
                    raise UnsupportedSVG("unsupported LineCollection child")
                if set(path.attrib) - {"d", "style", "clip-path", "id"}:
                    raise UnsupportedSVG("unknown path bounds")
                if any(re.search(r"(?:^|;)\s*" + key + r"\s*:", path.get("style", "")) for key in forbidden):
                    raise UnsupportedSVG("dependent path compositing")
        for child in element:
            check(child, unsafe)
    check(root)
    home = [float(v) for v in root.get("viewBox", "").split()]
    if len(home) != 4 or not all(math.isfinite(v) for v in home) or min(home[2:]) <= 0:
        raise UnsupportedSVG("invalid viewBox")
    fragments, units, segments = [], [], bytearray()
    def partition(group):
        body = group[1]
        paths = list(PATH.finditer(body))
        if not paths or PATH.sub(b"", body).strip():
            raise UnsupportedSVG("non-path LineCollection content")
        coords = []
        for path in paths:
            d = re.search(rb'\bd="([^"]*)"', path[0])
            match = ML.fullmatch(d[1]) if d else None
            if match is None:
                # Keep the complete group, never invent bounds for curves.
                return group[0]
            point = tuple(float(v) for v in match.groups())
            if not all(math.isfinite(v) for v in point):
                raise UnsupportedSVG("non-finite coordinates")
            coords.append(point)
        replacements = []
        for start in range(0, len(paths), chunk_size):
            stop = min(start + chunk_size, len(paths))
            left = 0 if start == 0 else paths[start - 1].end()
            right = len(body) if stop == len(paths) else paths[stop - 1].end()
            fragment = body[left:right]
            points = coords[start:stop]
            xs = [v for p in points for v in (p[0], p[2])]
            ys = [v for p in points for v in (p[1], p[3])]
            index = len(fragments)
            fragments.append(fragment)
            units.append({"id": index, "bounds": [min(xs), min(ys), max(xs), max(ys)],
                          "paths": stop-start, "bytes": len(fragment),
                          "sha256": hashlib.sha256(fragment).hexdigest()})
            for point in points:
                segments.extend(struct.pack("<4d", *point))
            replacements.append(marker(index))
        return group[0][:group.start(1)-group.start()] + b"".join(replacements) + group[0][group.end(1)-group.start():]
    shell = GROUP.sub(partition, svg)
    if not units:
        raise UnsupportedSVG("no independent linear painting units")
    manifest = {"version": VERSION, "source_revision": source_revision,
                "source_sha256": hashlib.sha256(svg).hexdigest(), "source_bytes": len(svg),
                "home": home, "units": units, "path_count": len(PATH.findall(svg)),
                "shell_paths": len(PATH.findall(shell)), "segment_count": len(segments)//32,
                "segments_sha256": hashlib.sha256(segments).hexdigest(),
                "shell_sha256": hashlib.sha256(shell).hexdigest()}
    package = Package(manifest, shell, fragments, bytes(segments))
    # Publication gate: complete original byte stream, including duplicate paths,
    # order, whitespace and dependencies, must be recoverable exactly.
    if package.reconstruct() != svg:
        raise ValueError("lossless reconstruction failed")
    return package


def write(package: Package, directory):
    """Write only into a caller-owned staging directory; publish by rename."""
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "shell.svg").write_bytes(package.shell)
    (directory / "segments.f64").write_bytes(package.segments)
    for unit, fragment in zip(package.manifest["units"], package.fragments):
        (directory / f'{unit["id"]}.svgpart').write_bytes(fragment)
    (directory / "manifest.json").write_text(json.dumps(package.manifest, separators=(",", ":")), encoding="utf-8")


def cache_key(source_revision: str) -> str:
    return hashlib.sha256((VERSION + ":" + source_revision).encode()).hexdigest()


def ensure_cached(source_revision: str, cache_dir: Path, load_svg, current_revision) -> Path:
    """Atomic publication, bounded locks and source-race protection.

    The caller supplies the original renderer and revalidation callback. Neither
    this module nor its derivatives are ever inputs to structural analysis.
    """
    key = cache_key(source_revision)
    folder = cache_dir / (key + ".regional")
    with _LOCKS[int(key[:8], 16) % len(_LOCKS)]:
        if (folder / "manifest.json").is_file():
            manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            if manifest.get("version") == VERSION and manifest.get("source_revision") == source_revision:
                return folder
            raise ValueError("invalid regional cache manifest")
        svg = load_svg()
        package = build(svg, source_revision)
        if current_revision() != source_revision:
            raise ValueError("source changed while preparing viewer")
        cache_dir.mkdir(parents=True, exist_ok=True)
        # mkdtemp reserves an owned staging parent; write creates its child.
        staging = Path(tempfile.mkdtemp(prefix=key + ".staging-", dir=cache_dir))
        try:
            write(package, staging / "package")
            if current_revision() != source_revision:
                raise ValueError("source changed before viewer publication")
            os.rename(staging / "package", folder)
        finally:
            # Remove only our empty staging parent. A failed package is retained
            # as diagnostic evidence; never recursively delete a computed path.
            if not any(staging.iterdir()):
                staging.rmdir()
    return folder
