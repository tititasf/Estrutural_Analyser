"""Measured slab wing and beam stem, scoped to the actual plan footprints."""
import re
from copy import deepcopy

from shapely.geometry import LineString, mapping, shape as from_geojson


def incompatible_own_height(cut, slab):
    match = re.search(r'h\s*=\s*(\d+(?:[.,]\d+)?)',
                      str(slab.get('fields', {}).get('laje_dim', '')), re.I)
    try:
        return bool(match and abs(float(match.group(1).replace(',', '.'))
                                  - float((cut.get('ficha') or {})['own_slab_height'])) > .25)
    except (KeyError, TypeError, ValueError):
        return False


def own_wing_top(section, slab, own):
    """Only upright sections with one constant band in the proven own region.

    A rotated section needs its own orientation proof; it retains the existing
    reading. Endpoint touching and disconnected/mixed bands do not supply one.
    """
    from .segment_levels import geometry, numeric
    if section.geom_type != 'Polygon' or section.bounds[2]-section.bounds[0] <= section.bounds[3]-section.bounds[1]:
        return None
    region = (from_geojson(own['region_geometry']) if own.get('region_geometry')
              else geometry(slab.get('points')))
    if region is None or region.geom_type != 'Polygon':
        return None
    band = section.intersection(region.buffer(-.25))
    if band.geom_type != 'Polygon' or band.area <= 1:
        return None
    x0, y0, x1, y1 = band.bounds
    tops, widths = [], []
    for ratio in (.25, .5, .75):
        x = x0+(x1-x0)*ratio
        span = band.intersection(LineString([(x, y0-1), (x, y1+1)]))
        if span.geom_type != 'LineString' or span.length < 1:
            return None
        tops.append(span.bounds[3]); widths.append(span.length)
    height = numeric((slab.get('fields') or {}).get('laje_dim', '').split('=')[-1])
    if (height is None or max(tops)-min(tops) > .1 or max(widths)-min(widths) > .25
            or abs(sum(widths)/3-height) > .25):
        return None
    return sum(tops)/3


def for_fund(fact, fund, depth):
    """Use the matched stem's top, never the tallest stem in a compound cut."""
    from .segment_levels import cut_matches_fund, numeric
    top = numeric(fact.get('own_wing_top_coordinate_cm'))
    slab_level = numeric(fact.get('own_slab_value'))
    profile = fact.get('cut_profile_geometry')
    if top is None or slab_level is None or not cut_matches_fund(
            profile, fund, depth, fact.get('cut_height_evidence')):
        return fact
    stem = from_geojson(profile).intersection(fund)
    # This reader only records positive-Y upright section coordinates.
    if fund.bounds[2]-fund.bounds[0] >= fund.bounds[3]-fund.bounds[1]:
        return fact
    offset = stem.bounds[3]-top
    if not 0 <= offset < 100:
        return None
    result = deepcopy(fact)
    result.update(value=round(slab_level+offset/100, 4), top_offset_cm=round(offset, 4),
                  top_offset_source='matched_stem_and_scoped_own_wing',
                  matched_stem_geometry=mapping(stem))
    return result
