"""Validate the numeric section authority without changing source coordinates."""
import re

from shapely.geometry import Polygon


def reconciled_depth(evidence, stem, fund, depth, width, axis):
    """Return measured depth only for the same traced physical beam section.

    Numeric height replaces drawing depth, never width, component identity or
    rectangular stem validation. An unrelated label cannot relax any tolerance.
    """
    if not isinstance(evidence, dict):
        return None
    if (evidence.get('source') != 'declared_section_bound_to_physical_run'
            or evidence.get('binding_method') != 'own_label_two_source_walls_aligned_section'):
        return None
    try:
        height = float(evidence['height_cm'])
        declared_width = float(evidence['width_cm'])
        measured = float(evidence['geometry_depth_cm'])
        angle = float(evidence['axis_deg']) % 180
        text = evidence['source_text']
        pair = re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*[/xX]\s*(\d+(?:[.,]\d+)?)\s*', text['text'])
        if pair is None or not text.get('handle'):
            return None
        text_width, text_height = [float(v.replace(',', '.')) for v in pair.groups()]
        if (abs(height-depth) > .25 or abs(declared_width-width) > .25
                or abs(text_width-declared_width) > .25 or abs(text_height-height) > .25
                or abs(angle-(0 if axis == 0 else 90)) > .1):
            return None
        run = Polygon(evidence['run_footprint'])
        traced_stem = Polygon(evidence['stem_footprint'])
        if (not run.is_valid or not traced_stem.is_valid or not run.buffer(.1).covers(stem)
                or stem.symmetric_difference(traced_stem.intersection(fund)).area > .25):
            return None
        bounds = stem.bounds
        if measured <= 0 or abs(bounds[axis+2]-bounds[axis]-measured) > .25:
            return None
        return measured
    except (KeyError, TypeError, ValueError, IndexError):
        return None
