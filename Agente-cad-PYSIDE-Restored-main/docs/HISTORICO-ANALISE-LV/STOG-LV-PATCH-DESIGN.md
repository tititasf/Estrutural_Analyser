# STOG LV DXF Reconstruction - Patch Design Document

**Author:** Aria (Architect Agent)
**Date:** 2026-03-16
**Score baseline:** 55/100
**Target score:** 85+/100

---

## Executive Summary

The STOG LV pipeline extracts 249 formwork beam parameters from DXF source drawings and reconstructs them into a combined DXF. Five critical gaps reduce the output quality from 100% to 55%. This document provides the technical design for five patches (A through E) with dependency ordering, risk analysis, and pseudo-code.

### Root Cause Map

| Gap | Metric | Root Cause |
|-----|--------|-----------|
| Zone x boundaries null | 115/249 vigas | `compute_zone` returns `None` for edge vigas in row (leftmost has no left neighbor, rightmost has no right neighbor). Zone was computed at extraction time but the `zone_size` field was not persisted (all 249 vigas have `zone_size=None`). |
| face_b missing | 234/249 vigas | `detect_faces_by_clustering` uses a hardcoded Y prefilter of `y_top - 350`, which is correct for zone spans around 500u but fails for zone spans of 1229u. The monkey-patched `patch_face_b.py` addresses this but still only recovers 15 vigas because zone x boundaries are null for many vigas, causing the X filter in clustering to be too wide and merge neighboring vigas' lines. |
| Grade entities missing | 0/107 for TREINO_1 | `patch_grade_entities.py` only extracts grade for vigas whose `layers_used` dict contains grade layer names. But TREINO_1 DXFs have grade entities on layers (Forcador, GARFOS, etc.) located approximately 1760u to the LEFT of the insert point, OUTSIDE the zone x boundaries. The `collect_zone_entities` function never sees them because `entity_in_zone` rejects entities outside `x_left..x_right`. |
| Face/Column labels missing | 0 column labels captured | The text extraction in `collect_zone_entities` captures P-number labels (P1, P2, etc.) but not face identity labels (V101.A, V101.B) or column labels (C16, C17). These texts exist in the DXF on NOMENCLATURA or other text layers but are filtered by the regex `r'^P?\d+$'` which only matches panel numbers. |
| Sarrafo y-range imprecise | Unknown severity | `face_panel_y_range()` in `patch_synth_sarr.py` uses heuristic hline selection to determine the panel rectangle y extent, but the algorithm may produce incorrect ranges for vigas with sparse or absent hlines, especially when face_b is missing. |

---

## Dependency Graph

```
PATCH-A (zone boundaries) ──> PATCH-B (face_b detection)
                           ├──> PATCH-D (grade zone expansion)
                           └──> PATCH-C (label extraction)
                                          |
PATCH-E (sarrafo validation) ←── PATCH-B ──┘
```

**Execution order:** A -> B -> C -> D -> E

PATCH-A is the keystone: without correct zone x boundaries, PATCH-B cannot accurately X-filter the face clustering, PATCH-D cannot scope the grade collection area, and PATCH-C needs correct zone boundaries to locate labels near the correct viga.

---

## PATCH-A: Fix Zone X Boundaries

### ADR-PATCH-A: Zone Boundary Inference from DXF Context

**Status:** Proposed
**Context:** 115/249 vigas have `x_left=None` or `x_right=None` (or both, for 9 vigas). These are edge vigas in their row -- the leftmost viga has no left neighbor (so `compute_zone` returns `x_left=None`) and the rightmost has no right neighbor (`x_right=None`). The zone `y_top` and `y_bot` are always present. The `insert.x` is always present (never 0 in the actual data; earlier analysis showed 0 due to reading `zone.insert_x` which does not exist -- the real insert is at `p['insert']['x']`).

**Decision:** Infer missing x boundaries using a two-strategy fallback approach:

1. **Strategy 1 (Neighbor interpolation):** For vigas in the same DXF row (same `y_top`), the zone boundaries are midpoints between adjacent inserts. For the leftmost viga, `x_left` should be `insert_x - (x_right - insert_x)` (mirror the right span). For the rightmost, `x_right = insert_x + (insert_x - x_left)`.

2. **Strategy 2 (Face-extent-based):** When face_a is already extracted with valid `face_x_min`/`face_x_max`, use `face_x_min - margin` as x_left and `face_x_max + margin` as x_right, where margin accounts for the section geometry area (typically ~300u to the left of face_x_min) and any annotation area.

**Consequences:**
- Positive: Enables PATCH-B, C, D to operate with correct spatial constraints
- Positive: No DXF re-reading required -- uses existing data in params JSON
- Risk: Mirror-based inference assumes vigas are roughly symmetric in their row; for asymmetric rows, face-extent fallback provides tighter bounds

### Design

```python
# patch_zone_boundaries.py

def patch_zone_boundaries(params):
    """
    For each viga with x_left=None or x_right=None, infer the missing boundary.

    Strategy 1: Group vigas by (obra, dxf_source, y_top) to identify row-mates.
                Within each row, sort by insert_x and compute midpoints.
                For edge vigas, mirror the known span.

    Strategy 2: Use face_a face_x_min/face_x_max with margin.
    """
    # Group vigas by row: same (obra, dxf_source, y_top rounded to 10u)
    rows = defaultdict(list)
    for i, p in enumerate(params):
        yt = p['zone']['y_top']
        key = (p['obra'], p.get('dxf_source', ''), round(yt / 10) * 10)
        rows[key].append(i)

    patched = 0
    for key, indices in rows.items():
        row_vigas = [(i, params[i]) for i in indices]
        # Sort by insert_x
        row_vigas.sort(key=lambda iv: iv[1]['insert']['x'])

        for pos, (i, p) in enumerate(row_vigas):
            z = p['zone']
            ins_x = p['insert']['x']
            needs_left = z.get('x_left') is None
            needs_right = z.get('x_right') is None

            if not needs_left and not needs_right:
                continue

            # Strategy 1: neighbor-based midpoints
            if needs_left and pos > 0:
                left_neighbor_x = row_vigas[pos - 1][1]['insert']['x']
                z['x_left'] = (ins_x + left_neighbor_x) / 2
                patched += 1

            if needs_right and pos < len(row_vigas) - 1:
                right_neighbor_x = row_vigas[pos + 1][1]['insert']['x']
                z['x_right'] = (ins_x + right_neighbor_x) / 2
                patched += 1

            # For remaining nulls: mirror the known span
            if z.get('x_left') is None and z.get('x_right') is not None:
                span = z['x_right'] - ins_x
                z['x_left'] = ins_x - span
                patched += 1

            if z.get('x_right') is None and z.get('x_left') is not None:
                span = ins_x - z['x_left']
                z['x_right'] = ins_x + span
                patched += 1

            # Strategy 2: face_a extent fallback (for both-null vigas that are alone in row)
            if z.get('x_left') is None or z.get('x_right') is None:
                fa = p.get('face_a', {})
                fa_xmin = fa.get('face_x_min')
                fa_xmax = fa.get('face_x_max')
                if fa_xmin and fa_xmax:
                    SECTION_MARGIN = 400  # section geometry is ~300u left of face
                    ANNOTATION_MARGIN = 200
                    if z.get('x_left') is None:
                        z['x_left'] = fa_xmin - SECTION_MARGIN
                        patched += 1
                    if z.get('x_right') is None:
                        z['x_right'] = fa_xmax + ANNOTATION_MARGIN
                        patched += 1

    return patched
```

### Validation

- After patch: verify all 249 vigas have non-null x_left AND x_right
- Verify x_left < insert_x < x_right for all vigas
- Verify zone width (x_right - x_left) is in plausible range [300, 5000]
- Spot-check 5 vigas per obra against DXF visual inspection

### Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Mirror inference too wide for asymmetric rows | Medium | Strategy 2 (face_a extent) provides a tighter bound as secondary check; also PATCH-B uses its own X-filter which tolerates some overestimation |
| Lone vigas in row (zone_size=1, both null) | High for 9 vigas | Strategy 2 is the only option; if face_a also has no valid extent (1 case: V310 with face_span=59), manual inspection needed |
| Introduces false positives in entity collection | Low | The zone boundary is only used as a coarse filter; per-face X-capping in `extract_panels_from_face` provides a second tighter filter |

---

## PATCH-B: Expand face_b Detection

### ADR-PATCH-B: Adaptive Y-Prefilter and Zone-Aware Clustering

**Status:** Proposed
**Context:** 234/249 vigas lack face_b. The root causes are (a) the Y prefilter in `detect_faces_by_clustering` uses a fixed 350u window below y_top, which fails for zone spans of 1229u (TREINO_1 top rows), and (b) null zone x boundaries cause the X filter to be too permissive, pulling in neighboring viga lines that confuse the anchor grouping. PATCH-A resolves (b). This patch resolves (a) and also addresses the monkey-patch in `patch_face_b.py` by integrating the fix directly into the extraction function.

**Decision:** Replace the fixed 350u Y prefilter with an adaptive formula: `max(350, zone_span * 0.75)`. Also modify the extraction pipeline so that `patch_face_b.py` re-extracts with the corrected function rather than monkey-patching, or preferably integrate the fix into `extrair_parametros_viga_v3.py` directly.

**Consequences:**
- Positive: Expected to recover face_b for 180+ vigas (up from 15)
- Positive: Eliminates need for monkey-patching
- Risk: Wider prefilter may capture noise lines from the lower viga row for short-zone vigas (zone_span ~500u); mitigated by the anchor grouping step which separates by ANCHOR_GROUP_GAP=220

### Design

```python
# Changes to detect_faces_by_clustering in extrair_parametros_viga_v3.py

def detect_faces_by_clustering(panel_h_lines, panel_v_lines, insert_y,
                                insert_x=None, x_left=None, x_right=None,
                                y_top=None, y_bot=None):  # ADD y_bot parameter
    """Detect Face A and Face B with adaptive Y prefilter.

    CHANGE 1: Accept y_bot parameter.
    CHANGE 2: Replace fixed 350u prefilter with adaptive formula.
    CHANGE 3: When y_bot known, clamp prefilter to y_bot + 10 (never go below zone bottom).
    """
    if not panel_h_lines:
        return None, None

    # === STEP 0: Adaptive Y proximity pre-filter ===
    if y_top is not None:
        if y_bot is not None:
            zone_span = y_top - y_bot
            prefilter_dist = max(350, zone_span * 0.75)
            y_prefilter_min = max(y_top - prefilter_dist, y_bot + 10)
        else:
            y_prefilter_min = y_top - 350  # original fallback

        prefiltered = [l for l in panel_h_lines if l['y'] >= y_prefilter_min]
        if len(prefiltered) >= 2:
            panel_h_lines = prefiltered

    # ... rest of function unchanged ...
```

```python
# Changes to extract_viga_v3

def extract_viga_v3(doc, viga_name, zone):
    # ...
    face_a_data, face_b_data = detect_faces_by_clustering(
        ents['panel_h_lines'], ents['panel_v_lines'], insert_y,
        insert_x=zone['insert_x'],
        x_left=zone.get('x_left'),
        x_right=zone.get('x_right'),
        y_top=zone.get('y_top'),
        y_bot=zone.get('y_bot'),   # NEW: pass y_bot
    )
    # ...
```

```python
# Updated patch_face_b.py: no more monkey-patching

def main():
    """Re-extract face_b for all vigas using the corrected detect function."""
    params = json.loads(PARAMS_FILE.read_text(encoding='utf-8'))

    vigas_sem_b = [p for p in params
                   if not p.get('face_b') or p['face_b'].get('panel_count', 0) == 0]

    # Group by (obra, dxf_source) to minimize DXF reads
    # For each viga:
    #   1. Open DXF
    #   2. collect_zone_entities with UPDATED zone (from PATCH-A)
    #   3. Call detect_faces_by_clustering with y_bot
    #   4. extract_panels_from_face for face_b
    # No monkey-patching needed because fix is in the function
```

### Validation

- After patch: count vigas with face_b.panel_count > 0 (target: 180+)
- For vigas where face_b is newly detected, verify:
  - face_b.y_max < face_a.y_min (face_b is below face_a) OR
  - face_b.y_min > face_a.y_max (face_b is above face_a, which happens in some STOG layouts)
  - face_b.panel_count in range [1, 12]
- Cross-reference 10 vigas against DXF visual inspection

### Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Wider prefilter captures lines from lower row | Low | y_bot clamping prevents going below zone boundary; ANCHOR_GROUP_GAP=220 separates face groups |
| False face_b detection (noise cluster identified as face) | Medium | Validate face_b max_width >= 50; validate face_b has at least 2 anchor lines; reject face_b candidates with < 3 lines |
| Vigas where face_a is actually face_b and vice versa | Low | Existing sanity check (line 607-609) compares distance to insert_y; already handles this |

### Dependency

- **Requires PATCH-A:** Zone x boundaries must be populated for accurate X-filtering in the clustering step. Without PATCH-A, the wider Y window would bring in even more foreign lines from adjacent vigas.

---

## PATCH-C: Label Extraction (Face V###.A/B and Column C##)

### ADR-PATCH-C: Extend Text Extraction for Face Identity and Column Labels

**Status:** Proposed
**Context:** The current pipeline captures panel number labels (P1, P2...) and continuation texts (CONT. V###, VEM DA V#) but does not capture face identity labels like "V101.A", "V101.B" or column labels like "C16", "C17". These labels exist in the DXF as TEXT/MTEXT entities on NOMENCLATURA or other text layers. They are valuable for cross-referencing faces with the structural plan and for identifying which columns bound each beam.

Current filtering in `extract_viga_v3` (line 1338) uses `re.match(r'^P?\d+$', t['text'])` which only matches `P1`, `P2`, `12`, etc.

From the data, 46 face labels (V###.A/B pattern) are already captured in `panel_texts_positioned` (they pass the zone filter but NOT the regex filter for panel_texts). Zero column labels (C##) are captured.

**Decision:** Add two new output fields to the extraction: `face_labels` and `column_labels`. Extract them from `ents['texts']` using dedicated regex patterns. Do NOT modify the existing `panel_texts` field to maintain backward compatibility.

**Consequences:**
- Positive: Face identity labels enable automated face-to-plan cross-referencing
- Positive: Column labels enable beam-column connectivity mapping
- Positive: Zero impact on existing data fields (additive only)
- Risk: Column labels may be outside the current zone boundaries (typically placed above or beside the title block)

### Design

```python
# New regex patterns for label extraction
FACE_LABEL_RE = re.compile(
    r'(?:CONT\.\s*)?V[A-Z]?\d+(?:\+V\w+)?\.?\s*[AB]',
    re.IGNORECASE
)
# Matches: "V101.A", "V101.B", "VF301.A", "CONT. VF301.A", "V231+V232.A"

COLUMN_LABEL_RE = re.compile(
    r'^C\d{1,3}$'
)
# Matches: "C16", "C17", "C1", "C123"

# Also capture "P##/##" style labels sometimes used for face identification
FACE_PANEL_GROUP_RE = re.compile(
    r'^P\d+/P?\d+$'
)

# In extract_viga_v3, add after panel_texts_pos:

face_labels = []
column_labels = []
for t in ents['texts']:
    text = t['text'].strip()
    # Face identity labels
    if FACE_LABEL_RE.search(text):
        face_labels.append({
            'text': text,
            'x': t['x'], 'y': t['y'],
            'layer': t['layer'],
            # Classify: is this for face_a or face_b?
            'face_hint': classify_face_by_y(t['y'], face_a, face_b),
        })
    # Column labels
    if COLUMN_LABEL_RE.match(text):
        column_labels.append({
            'text': text,
            'x': t['x'], 'y': t['y'],
            'layer': t['layer'],
        })

def classify_face_by_y(text_y, face_a, face_b):
    """Classify which face a label belongs to based on Y proximity."""
    if not face_a or face_a.get('y_min', 0) == 0:
        return 'unknown'
    dist_a = abs(text_y - (face_a['y_min'] + face_a['y_max']) / 2)
    if face_b and face_b.get('y_min', 0) > 0:
        dist_b = abs(text_y - (face_b['y_min'] + face_b['y_max']) / 2)
        return 'a' if dist_a <= dist_b else 'b'
    return 'a'
```

```python
# For column labels: expand the text search zone slightly above y_top
# Column labels are typically near the title block, within 100u of insert_y

# In collect_zone_entities, modify entity_in_zone to accept optional expanded_y_top:
# OR: do a separate targeted text scan for column labels
def extract_column_labels(msp, zone, face_a):
    """Targeted extraction for C## labels near the title block."""
    insert_x = zone['insert_x']
    insert_y = zone['insert_y']
    y_search_min = zone['y_bot']
    y_search_max = zone['y_top'] + 50  # small upward expansion
    x_search_min = zone.get('x_left', insert_x - 500) or (insert_x - 500)
    x_search_max = zone.get('x_right', insert_x + 2000) or (insert_x + 2000)

    labels = []
    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        x, y = e.dxf.insert.x, e.dxf.insert.y
        if not (y_search_min <= y <= y_search_max):
            continue
        if not (x_search_min <= x <= x_search_max):
            continue
        text = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
        if COLUMN_LABEL_RE.match(text):
            labels.append({'text': text, 'x': round(x, 1), 'y': round(y, 1),
                          'layer': e.dxf.layer})
    return labels
```

### Output Schema Addition

```json
{
  "face_labels": [
    {"text": "V101.A", "x": 3901.2, "y": 8097.0, "layer": "NOMENCLATURA", "face_hint": "a"},
    {"text": "V101.B", "x": 3901.2, "y": 7906.0, "layer": "NOMENCLATURA", "face_hint": "b"}
  ],
  "column_labels": [
    {"text": "C16", "x": 3500.0, "y": 8200.0, "layer": "NOMENCLATURA"},
    {"text": "C17", "x": 4800.0, "y": 8200.0, "layer": "NOMENCLATURA"}
  ]
}
```

### Validation

- After patch: count vigas with face_labels (target: 100+ based on the 46 already visible in texts)
- Verify face_hint accuracy by checking y proximity to face_a/face_b
- Verify column_labels are plausible (C1-C200 range, positions near title block)
- Column labels may require DXF re-reading if not already in ents['texts']

### Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Column labels outside zone boundaries | High | `extract_column_labels` does a targeted scan with expanded Y range and full X range of the zone |
| False positive face labels (continuation texts) | Low | FACE_LABEL_RE includes "CONT." prefix handling; store both the raw text and a parsed viga_name |
| MTEXT formatting codes corrupting label text | Low | Existing MTEXT stripping logic already handles this |

### Dependency

- **Benefits from PATCH-A:** Correct x boundaries improve label attribution accuracy
- **Benefits from PATCH-B:** face_b detection allows correct face_hint classification
- **Independent execution possible:** Labels can be extracted even without PATCH-A/B, but face_hint will be less accurate

---

## PATCH-D: Grade Entities Zone Expansion

### ADR-PATCH-D: Lateral Zone Expansion for Grade Entity Collection

**Status:** Proposed
**Context:** Grade entities (Forcador, GARFOS, Escoras, Demarcacao, etc.) are present in DXFs for TREINO_10 (8 vigas), TREINO_21 (7), TREINO_22 (6), TREINO_3 (1), TREINO_9 (2) but completely absent for TREINO_1 (0/107 vigas). The issue is that `collect_zone_entities` filters entities by `entity_in_zone` which requires entities to be within `[x_left, x_right]`. For TREINO_1, the grade entities are positioned approximately 1760u to the LEFT of the insert point, which is OUTSIDE the zone x boundaries.

The `patch_grade_entities.py` script already has a separate grade extraction with its own X-filtering logic, but it only runs on vigas whose `layers_used` dict contains grade layer names. Since `collect_zone_entities` never sees the grade entities (they are outside the zone), `layers_used` never includes those layers, so `patch_grade_entities.py` skips TREINO_1 entirely.

**Decision:** Modify `patch_grade_entities.py` to:
1. Remove the `layers_used` gate -- run grade extraction for ALL vigas
2. Expand the X filter to include the area to the LEFT of the zone by at least 2000u (covers the typical 1760u grade offset plus margin)
3. Add a cap: only include vigas where grade entities were actually found

**Consequences:**
- Positive: TREINO_1 vigas will gain grade entities (estimated 80+ of 107)
- Risk: Running on all 249 vigas increases DXF reads; mitigate by caching doc per (obra, dxf_source) group
- Risk: Expanded X filter may capture grade entities from neighboring vigas for closely-spaced vigas

### Design

```python
# Modified patch_grade_entities.py

def extract_grade_expanded(dxf_path, zone, fa, insert_x):
    """
    Extract grade entities with expanded X search area.

    KEY CHANGE: For vigas where grade is to the LEFT of the insert,
    extend the search area leftward by GRADE_OFFSET_MAX = 2200u.
    This covers the typical ~1760u offset plus safety margin.

    IMPORTANT: Use insert_x as the reference point, NOT x_left,
    because x_left may itself be too narrow.
    """
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    y_top = zone['y_top']
    y_bot = zone['y_bot']

    # Grade is typically to the LEFT of insert
    GRADE_OFFSET_MAX = 2200  # covers 1760u typical + margin

    # Build X filter: from (insert_x - GRADE_OFFSET_MAX) to face_a right edge
    fa_xmax = max(
        [h['x2'] for h in fa.get('face_hlines', [])] +
        [v['x'] for v in fa.get('face_vlines', [])] +
        [insert_x + 200]  # fallback
    )

    filter_xmin = insert_x - GRADE_OFFSET_MAX
    filter_xmax = fa_xmax + 100

    # Also include x_left/x_right if they expand the range
    x_left = zone.get('x_left')
    x_right = zone.get('x_right')
    if x_left is not None:
        filter_xmin = min(filter_xmin, x_left - 200)
    if x_right is not None:
        filter_xmax = max(filter_xmax, x_right + 200)

    # ... rest of entity collection same as current extract_grade ...
    # But with the expanded filter_xmin

def main():
    params = json.loads(PARAMS_FILE.read_text(encoding='utf-8'))

    # Process ALL vigas, not just those with grade layers in layers_used
    # Group by (obra, dxf_source) to reuse doc handle
    groups = defaultdict(list)
    for i, p in enumerate(params):
        groups[(p['obra'], p.get('dxf_source', ''))].append(i)

    patched = 0
    for (obra, dxf_src), indices in groups.items():
        dxf_path = find_dxf(obra, dxf_src)
        if not dxf_path:
            continue
        doc = ezdxf.readfile(str(dxf_path))

        for i in indices:
            p = params[i]
            fa = p.get('face_a', {})
            ins_x = p.get('insert', {}).get('x', 0)
            zone = p.get('zone', {})

            grade = extract_grade_expanded_from_doc(
                doc, zone, fa, ins_x
            )
            total = sum(len(v) for v in grade.values())
            if total > 0:
                p['grade_entities'] = grade
                patched += 1

    # Save...
```

### Key Insight

The grade area for TREINO_1 is at approximately `insert_x - 1760`. For VF301 with insert_x=3709, the grade area starts around x=1949, which is well below the zone's x_right=4500 but might be below x_left (which is null, meaning the zone filter was already too restrictive).

After PATCH-A populates x_left (e.g., via mirror: x_left = 3709 - (4500 - 3709) = 2918), the grade area at x=1949 is STILL outside x_left=2918. This confirms that grade extraction MUST use a separate, expanded X filter, not rely on zone boundaries.

### Validation

- After patch: count TREINO_1 vigas with grade_entities (target: 80+/107)
- Verify grade entity counts are reasonable (not absorbing from neighbors)
- Spot-check 5 vigas: open DXF, visually confirm grade entities match
- Verify grade_lines x-range falls within [insert_x - 2200, insert_x + 200]

### Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Grade from adjacent viga captured | Medium | Post-filter: only keep grade entities whose X centroid is within [insert_x - 2200, insert_x - 200] OR within the face X range; discard grade groups whose X centroid is closer to a DIFFERENT viga's insert_x |
| DXF re-reading for all vigas is slow | Medium | Cache doc per (obra, dxf_source) group; only iterate msp once per doc, pre-collecting all grade-layer entities then distributing to vigas by Y/X proximity |
| Some TREINO_1 vigas genuinely have no grade | Low | Acceptable; the patch only adds grade_entities when entities are found |

### Dependency

- **Independent of PATCH-A** (uses insert_x directly, not zone x boundaries)
- **Runs after PATCH-A** in the pipeline for consistency, but technically decoupled

---

## PATCH-E: Sarrafo Y-Range Validation

### ADR-PATCH-E: Ground Truth Validation for Sarrafo Synthetic Positions

**Status:** Proposed
**Context:** `patch_synth_sarr.py` generates synthetic horizontal sarrafo lines within panels for vigas that have count labels (e.g., "8 1/2pont") but no drawn sarrafo lines. The y-range of these synthetic lines is determined by `face_panel_y_range()`, which uses heuristics on face hlines to find the panel rectangle bounds. The concern is that this heuristic may produce incorrect y bounds, especially for:
- Vigas with sparse hlines (e.g., face_b just detected by PATCH-B)
- Vigas where the panel rectangle top is ambiguous (section cut area above)

**Decision:** Build a validation script that compares synthetic sarrafo y positions against ground truth from TREINO_1 vigas that have BOTH real sarrafo lines AND count labels.

**Consequences:**
- Positive: Quantifies the accuracy of the y-range heuristic
- Positive: May reveal systematic offset that can be corrected
- Risk: TREINO_1 may not have enough vigas with both real sarrafos and labels for robust validation

### Design

```python
# validate_sarr_yrange.py

def validate():
    """
    For each TREINO_1 viga that has:
    1. Real sarr22_lines (horizontal, within face_a or face_b)
    2. panel_labels with N >= 2

    Compare:
    - face_panel_y_range() output (y_min, y_max)
    - Actual y positions of real sarr22_lines within the panel

    Report:
    - Delta between predicted y_min and actual min sarr y
    - Delta between predicted y_max and actual max sarr y
    - Whether synthetic lines would overlap correctly with real ones
    """
    params = load_params()

    ground_truth_vigas = []
    for p in params:
        if p.get('obra') != 'Obra_TREINO_1':
            continue

        sarr_lines = p.get('sarr22_lines', [])
        panel_labels = p.get('panel_labels', [])
        fa = p.get('face_a', {})

        if not panel_labels or not sarr_lines or not fa.get('panel_count'):
            continue

        # Get real horizontal sarr lines within face_a y range
        fa_ymin = fa.get('y_min', 0)
        fa_ymax = fa.get('y_max', 0)
        real_h_sarr = [
            s for s in sarr_lines
            if abs(s['y1'] - s['y2']) < 2  # horizontal
            and fa_ymin - 10 <= s['y1'] <= fa_ymax + 10
        ]

        if len(real_h_sarr) < 2:
            continue

        # Compute face_panel_y_range prediction
        pred_ymin, pred_ymax = face_panel_y_range(fa)

        # Actual sarrafo y range
        real_ys = sorted(set(round(s['y1'], 1) for s in real_h_sarr))
        actual_ymin = min(real_ys)
        actual_ymax = max(real_ys)

        ground_truth_vigas.append({
            'viga': p['viga'],
            'pred_ymin': pred_ymin,
            'pred_ymax': pred_ymax,
            'actual_ymin': actual_ymin,
            'actual_ymax': actual_ymax,
            'delta_min': (pred_ymin - actual_ymin) if pred_ymin else None,
            'delta_max': (pred_ymax - actual_ymax) if pred_ymax else None,
            'real_count': len(real_ys),
        })

    # Report
    if not ground_truth_vigas:
        print("WARN: No ground truth vigas found with both sarr lines and labels")
        return

    print(f"Ground truth vigas: {len(ground_truth_vigas)}")
    for gt in ground_truth_vigas:
        print(f"  {gt['viga']}: pred=[{gt['pred_ymin']:.0f},{gt['pred_ymax']:.0f}] "
              f"actual=[{gt['actual_ymin']:.0f},{gt['actual_ymax']:.0f}] "
              f"delta_min={gt['delta_min']:.1f} delta_max={gt['delta_max']:.1f}")

    # Compute aggregate stats
    deltas_min = [g['delta_min'] for g in ground_truth_vigas if g['delta_min'] is not None]
    deltas_max = [g['delta_max'] for g in ground_truth_vigas if g['delta_max'] is not None]
    if deltas_min:
        print(f"\nDelta y_min: mean={sum(deltas_min)/len(deltas_min):.1f}, "
              f"max={max(abs(d) for d in deltas_min):.1f}")
    if deltas_max:
        print(f"Delta y_max: mean={sum(deltas_max)/len(deltas_max):.1f}, "
              f"max={max(abs(d) for d in deltas_max):.1f}")

    # DECISION CRITERIA:
    # If mean delta > 10u: the heuristic has a systematic bias -> apply correction
    # If max delta > 30u: some vigas have gross errors -> investigate individually
    # If mean delta < 5u: heuristic is accurate enough, no correction needed
```

### Correction Strategy (if validation reveals issues)

```python
# If systematic bias is found, apply correction to face_panel_y_range:

def face_panel_y_range_corrected(face_data, correction_offset=0):
    """
    Same as face_panel_y_range but with empirical correction.

    If validation shows pred_ymin is consistently 15u too high:
        correction_offset = -15

    Applied to pred_ymin only (y_max is typically accurate as it
    aligns with the bottom rail of the face).
    """
    y_min, y_max = face_panel_y_range(face_data)
    if y_min is not None:
        y_min += correction_offset
    return y_min, y_max
```

### Alternative: Use Face Hlines Directly

If the heuristic proves unreliable, an alternative approach uses the panel_positions from face_a/face_b directly:

```python
def sarr_y_range_from_face_rails(face_data):
    """
    Use the two widest hlines as the panel top and bottom rails.
    The sarrafo y range is between these two rails.
    """
    hlines = face_data.get('face_hlines', [])
    total_w = face_data.get('total_width', 0) or 1

    # Wide hlines (>40% of total width) are structural rails
    rails = sorted(
        [h for h in hlines if h.get('len', 0) >= total_w * 0.4],
        key=lambda h: h['y']
    )

    if len(rails) >= 2:
        return rails[0]['y'], rails[1]['y']  # bottom, second-from-bottom
    elif rails:
        return rails[0]['y'], rails[0]['y'] + 70  # fallback
    else:
        return face_data.get('y_min'), face_data.get('y_min', 0) + 70
```

### Validation

- Compare predicted vs actual y-ranges for TREINO_1 ground truth
- Verify synthetic sarr lines fall within actual panel rectangle
- Visual spot-check in combined DXF: do synthetic sarrafos align with real ones?

### Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Insufficient ground truth vigas | Medium | Use all obras, not just TREINO_1; also use vigas where face_a has real sarr lines even without panel_labels |
| face_b has no hlines (just detected by PATCH-B) | Medium | For face_b without hlines, fall back to [y_min, y_min + 70] which is the current fallback behavior |
| Systematic correction invalidates non-TREINO_1 vigas | Low | Validate correction against all obras; if obra-specific, parameterize correction by obra |

### Dependency

- **Requires PATCH-B:** More face_b detections means more sarrafo targets to validate
- **Independent of PATCH-A, C, D**

---

## Combined Patch Execution Plan

### Phase 1: Data Repair (no DXF re-reading required)

1. **PATCH-A** `patch_zone_boundaries.py`
   - Input: `viga_params_v3.json`
   - Output: `viga_params_v3.json` (updated in place, zone x boundaries populated)
   - Duration: < 1 second (JSON manipulation only)

### Phase 2: Extraction Enhancement (DXF re-reading required)

2. **PATCH-B** `patch_face_b.py` (updated)
   - Input: `viga_params_v3.json` + DXF source files
   - Output: `viga_params_v3.json` (face_b populated for 180+ vigas)
   - Duration: ~5-10 minutes (reads all DXFs)

3. **PATCH-D** `patch_grade_entities.py` (updated)
   - Input: `viga_params_v3.json` + DXF source files
   - Output: `viga_params_v3.json` (grade_entities for TREINO_1)
   - Duration: ~5-10 minutes (reads all DXFs)
   - NOTE: Can run in parallel with PATCH-B (independent DXF passes)

4. **PATCH-C** `patch_labels.py` (new)
   - Input: `viga_params_v3.json` + DXF source files
   - Output: `viga_params_v3.json` (face_labels + column_labels added)
   - Duration: ~5-10 minutes
   - NOTE: Best run AFTER PATCH-B for accurate face_hint classification

### Phase 3: Validation

5. **PATCH-E** `validate_sarr_yrange.py` (new)
   - Input: `viga_params_v3.json`
   - Output: Validation report + optional correction to `patch_synth_sarr.py`
   - Duration: < 1 second (JSON analysis only)

### Phase 4: Reconstruction

6. Re-run `combinar_vigas_dxf.py` to generate updated combined DXF
7. Visual inspection of combined DXF output

### Expected Score Impact

| Gap | Current | After Patch | Score Impact |
|-----|---------|-------------|-------------|
| Zone boundaries | 134/249 complete | 249/249 | +10 |
| face_b detection | 15/249 | 180+/249 | +15 |
| Grade entities | 14/249 | 90+/249 | +5 |
| Face/Column labels | 0 column labels | 100+ face, 50+ column | +5 |
| Sarrafo y-range | Unknown | Validated/corrected | +5 |
| **Total** | **55/100** | **~90/100** | **+35** |

---

## File Manifest

| File | Status | Action |
|------|--------|--------|
| `patch_zone_boundaries.py` | NEW | Create |
| `patch_face_b.py` | EXISTS | Modify (remove monkey-patch, use y_bot param) |
| `extrair_parametros_viga_v3.py` | EXISTS | Modify (add y_bot to detect_faces_by_clustering) |
| `patch_grade_entities.py` | EXISTS | Modify (remove layers_used gate, expand X filter) |
| `patch_labels.py` | NEW | Create |
| `validate_sarr_yrange.py` | NEW | Create |
| `combinar_vigas_dxf.py` | EXISTS | No changes needed (already renders all data) |
| `patch_synth_sarr.py` | EXISTS | Possibly modify face_panel_y_range if PATCH-E finds issues |
| `reconstruir_lv_dxf.py` | EXISTS | No changes needed |

---

## Security Implications

- No network operations, no credential handling
- All file operations are local (D:/Agente-cad-PYSIDE)
- DXF files are read-only (never modified)
- Only `viga_params_v3.json` is modified (written atomically)
- No new dependencies required (ezdxf already installed)

## Backward Compatibility

- All new fields (face_labels, column_labels) are additive
- Existing fields (face_a, face_b, zone, panel_texts, etc.) maintain same schema
- `combinar_vigas_dxf.py` already handles missing face_b and grade_entities gracefully
- `patch_synth_sarr.py` already handles missing face_b with fallback logic

---

*-- Aria, arquitetando o futuro*
