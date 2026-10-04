"""Independent QA benchmark measurements; model confidence is never accuracy.

References must come from original drawings or independently adjudicated labels.
These measurements do not certify a class or promote production geometry.
"""
import math
from shapely.geometry import Polygon, LineString, shape


def _coordinate_pairs(value):
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError('coordenadas inválidas')
    if all(isinstance(v, (int, float)) for v in value):
        if len(value) != 2 or any(isinstance(v, bool) or not math.isfinite(v) for v in value):
            raise ValueError('coordenadas inválidas')
        return
    for child in value:
        _coordinate_pairs(child)


def _polygon(value):
    """Simple rings or explicit GeoJSON polygons; never heal reference topology."""
    coordinates = value.get('coordinates') if isinstance(value, dict) else value
    _coordinate_pairs(coordinates)
    if isinstance(value, dict):
        if value.get('type') not in {'Polygon', 'MultiPolygon'}:
            raise ValueError('tipo de contorno inválido')
    try:
        result = shape(value) if isinstance(value, dict) else Polygon(value)
    except (ValueError, TypeError, IndexError) as exc:
        raise ValueError('contorno inválido') from exc
    if result.is_empty or not result.is_valid or result.area <= 1e-6:
        raise ValueError('contorno inválido; não reparar automaticamente a referência')
    return result


def _topology(value):
    parts = list(value.geoms) if value.geom_type == 'MultiPolygon' else [value]
    return {'components': len(parts), 'holes': sum(len(p.interiors) for p in parts)}


def geometry(candidate, reference, *, units_per_cm, tolerance_cm=0.5, min_iou=0.99):
    for value in (units_per_cm, tolerance_cm, min_iou):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('escala/tolerância inválida')
    if not math.isfinite(units_per_cm) or units_per_cm <= 0:
        raise ValueError('escala independente deve ser positiva')
    if not math.isfinite(tolerance_cm) or tolerance_cm < 0 or not 0 < min_iou <= 1:
        raise ValueError('tolerância inválida')
    c, r = _polygon(candidate), _polygon(reference)
    iou = c.intersection(r).area / c.union(r).area
    distance = c.boundary.hausdorff_distance(r.boundary) / units_per_cm
    candidate_topology, reference_topology = _topology(c), _topology(r)
    topology_pass = candidate_topology == reference_topology
    return {'iou': iou, 'boundary_error_cm': distance,
            'extra_area_cm2': c.difference(r).area / units_per_cm**2,
            'missing_area_cm2': r.difference(c).area / units_per_cm**2,
            'area_error_percent': abs(c.area-r.area)/r.area*100,
            'candidate_topology': candidate_topology, 'reference_topology': reference_topology,
            'topology_pass': topology_pass,
            'gate_pass': topology_pass and iou >= min_iou and distance <= tolerance_cm,
            'tolerance_cm': tolerance_cm, 'min_iou': min_iou}


def polyline(candidate, reference, *, units_per_cm, tolerance_cm=0.5,
             length_tolerance_cm=0.5):
    """LV wall boundaries: distance, endpoints and length against independent points.

    Direction may reverse. No area/IoU is invented for zero-area linework.
    """
    for value in (units_per_cm, tolerance_cm, length_tolerance_cm):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('escala/tolerância inválida')
    if units_per_cm <= 0 or min(tolerance_cm, length_tolerance_cm) < 0:
        raise ValueError('escala/tolerância inválida')
    lines = []
    for points in (candidate, reference):
        _coordinate_pairs(points)
        if len(points) < 2 or any(not isinstance(p, (list, tuple)) or len(p) != 2 for p in points):
            raise ValueError('linha inválida')
        line = LineString(points)
        if line.is_empty or not line.is_valid or not line.is_simple or line.is_ring or line.length <= 1e-6:
            raise ValueError('linha inválida; não reparar automaticamente')
        lines.append(line)
    c, r = lines
    distance = c.hausdorff_distance(r) / units_per_cm
    ends_c, ends_r = [c.coords[0], c.coords[-1]], [r.coords[0], r.coords[-1]]
    endpoint_error = min(max(math.dist(ends_c[i], order[i]) for i in (0, 1))
                         for order in (ends_r, list(reversed(ends_r)))) / units_per_cm
    length_error = abs(c.length-r.length) / units_per_cm
    return {'boundary_error_cm': distance, 'endpoint_error_cm': endpoint_error,
            'length_error_cm': length_error, 'candidate_length_cm': c.length / units_per_cm,
            'reference_length_cm': r.length / units_per_cm,
            'gate_pass': max(distance, endpoint_error) <= tolerance_cm and length_error <= length_tolerance_cm,
            'tolerance_cm': tolerance_cm, 'length_tolerance_cm': length_tolerance_cm}


def decisions(rows):
    """Binary correctness labels with pass/fail/uncertain/technical outcomes.

    Uncertain and technical outcomes count against end-to-end accuracy, and are
    excluded only from explicitly named selective accuracy. No unlabeled rows.
    A confidence_percent describes certainty of the *decision*, not P(pass), so
    it cannot honestly produce a Brier score for correctness of the drawing.
    """
    counts = dict(tp=0, tn=0, fp=0, fn=0, uncertain=0, technical=0)
    human = 0
    for row in rows:
        if type(row.get('reference_correct')) is not bool:
            raise ValueError('rótulo independente ausente')
        prediction = row.get('assessment')
        if prediction not in {'pass','fail','inconclusive','technical_failure'}:
            raise ValueError('veredito inválido')
        human += bool(row.get('human_label_verified'))
        if prediction == 'inconclusive': counts['uncertain'] += 1
        elif prediction == 'technical_failure': counts['technical'] += 1
        else:
            key = ('tp' if row['reference_correct'] else 'fp') if prediction == 'pass' else (
                'fn' if row['reference_correct'] else 'tn')
            counts[key] += 1
    n = len(rows)
    decisive = sum(counts[k] for k in ('tp','tn','fp','fn'))
    correct = counts['tp']+counts['tn']
    def ratio(a,b): return a/b if b else None
    # Wilson interval for end-to-end observed correctness, including abstentions.
    interval = None
    if n:
        z=1.96; p=correct/n; den=1+z*z/n
        centre=(p+z*z/(2*n))/den
        delta=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
        interval=[max(0,centre-delta),min(1,centre+delta)]
    return {'n':n, **counts, 'end_to_end_accuracy':ratio(correct,n),
            'selective_accuracy':ratio(correct,decisive), 'decision_coverage':ratio(decisive,n),
            'false_approval_rate':ratio(counts['fp'],counts['fp']+counts['tn']),
            'observed_accuracy_wilson95':interval, 'human_verified_labels':human,
            'calibrated_confidence':False, 'certified':False,
            'limitation':'Amostra local; ampliar referências independentes e adjudicação humana antes de generalizar.'}
