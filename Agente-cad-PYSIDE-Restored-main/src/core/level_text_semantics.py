"""Elevation text evidence, independent of drawing names, layers and magnitude."""
import math
import re

_NUMBER = r"[+-]?\d+(?:[.,]\d+)?"
_LEVEL = re.compile(rf"^(?:(?:n[ií]vel|level|el|n)\s*[:=]?\s*)?({_NUMBER})\s*$", re.I)
_EXPLICIT = re.compile(r"^(?:[+-]|(?:n[ií]vel|level|el|n)\s*[:=]?\s*[+-]?\d)", re.I)


def elevation_value(token, *, trusted_layer=False, reference_level=None, floor_height=None):
    """A decimal alone is not altitude. Dimensions always remain dimensions.

    Unsigned numbers require a learned elevation layer or an independently
    established floor band; explicit elevation notation remains usable when
    the absolute floor reference is unknown.
    """
    if not isinstance(token, dict) or token.get('annotation_role') == 'dimension':
        return None
    text = str(token.get('text', token.get('raw', '')) or '').strip()
    match = _LEVEL.fullmatch(text)
    if not match:
        return None
    value = float(match.group(1).replace(',', '.'))
    if not math.isfinite(value):
        return None
    if _EXPLICIT.match(text) or trusted_layer:
        return value
    if reference_level is not None and floor_height and abs(value - float(reference_level)) <= abs(float(floor_height)) * .25:
        return value
    return None
