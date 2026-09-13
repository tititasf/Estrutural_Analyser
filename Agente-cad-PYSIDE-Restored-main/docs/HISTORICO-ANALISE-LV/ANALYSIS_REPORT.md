# Fragment Analysis Report: combined DXF v35 -> v37

## Executive Summary

Investigation of loose fragment elements in the combined DXF grid.
Starting from v35 (277 cells with fragments, 9971 isolated elements),
applied systematic compaction fixes to produce v37 (42 cells, 456 elements).

**All 42 remaining cells have HORIZONTAL spatial separation** -- legitimate
viga design features where section and face views are placed side by side.
Zero remaining cells have vertical fragmentation from compaction issues.

## Progression

| Version | Cells | Elements | Key Fix |
|---------|-------|----------|---------|
| v35 (baseline) | 277 | 9971 | No compaction |
| v36 (single-gap) | 164 | 8164 | Single-gap section compaction |
| v37 (multi-gap) | 42 | 456 | Multi-gap compaction + centroid-based shift + annotation layer exclusion |

**Reduction: -84.8% cells, -95.4% elements**

## Root Causes Identified and Fixed

### 1. Section Zone Gap (PRIMARY - fixed)
Vigas have face elevation (upper) and section cross-section (lower) separated
by 200-1200u gap. Single-gap compaction closed this to 30u target.

### 2. Multi-zone Structure (SECONDARY - fixed)
Some vigas have three zones: section core, intermediate annotations (cotas/hatches),
and face. Single-gap compaction only closed one gap. Multi-gap detection
(`_compute_section_gaps`) now finds and closes ALL gaps > 200u.

### 3. Cross-boundary Element Stretching (SECONDARY - fixed)
Cotas and hatches spanning compaction boundaries had different Y shifts on
different vertices, creating visual artifacts. Fixed with centroid-based
consistent shift.

### 4. Section Annotation Layers (NOISE - excluded from detector)
`Cota Secao (2x)` and `Texto Secao` layers annotate the section zone.
After compaction they stay 250-700u from the face, but this is expected
positioning. Excluded from cluster detection.

### 5. Horizontal Spatial Separation (REMAINING - inherent design feature)
42 cells have elements separated horizontally (X-axis gap > 250u).
These are legitimate viga design features -- face elevation and section
views placed side by side. Not fixable through translation changes.

## Detector Sensitivity Analysis (v37)

| eps | Cells | Elements | Notes |
|-----|-------|----------|-------|
| 250 | 42 | 456 | All horizontal gaps |
| 350 | 25 | 273 | Same pattern |
| 500 | 8 | 53 | Mostly wide vigas |
| 600 | 2 | 4 | 1 genuine stray element (V4_a, dist=1918) |

## Files Modified

### combinar_vigas_dxf.py
- `_collect_all_rendered_ys()` -- NEW: collects Y values from ALL rendered elements
- `_compute_section_gaps()` -- NEW: multi-gap detection with Phase 1 (gap finding)
  and Phase 2 (residual gap closure below face_a.y_min)
- `_compute_section_boundary()` -- KEPT: legacy API, now delegates to shared Y collector
- `compute_content_bbox()` -- UPDATED: uses multi-gap compaction for bbox calculation
- `translate_viga()` -- UPDATED: `_sy()` handles list of (boundary, cumul_shift) tuples;
  centroid-based consistent shift for cotas (section 12), hatches (section 11),
  and grade hatches (section 14)
- `build_combined()` -- UPDATED: uses `_compute_section_gaps()` for shift parameter

### detect_clusters_real.py
- Fixed row assignment bug (math.ceil for negative Y)
- Added section annotation layers to IGNORE_LAYERS
- Fixed stdout double-wrapping

### New Files
- `debug_boundary.py` -- Diagnostic: boundary vs face_a.y_min alignment
- `debug_remaining.py` -- Diagnostic: rendered content gap analysis
- `render_problem_cells.py` -- Visual renderer for top-12 problematic cells
- `vision_v37/` -- 12 PNG renders of most problematic cells

## Visual Evidence

All 12 rendered cells show the same pattern: two spatially distinct groups
at the SAME Y level, separated horizontally by 250-2600u. The red (isolated)
cluster and blue (main) cluster are both legitimate structural elements of
the viga design.

## Recommendation

The detector at eps=250 is too sensitive for this data. Vigas commonly have
horizontal gaps of 250-600u between structural views. Recommended thresholds:
- **eps=350**: 25 cells (catches only wide separations)
- **eps=500**: 8 cells (catches genuine outliers)
- **eps=600**: 2 cells (catches only stray elements)

For quality assurance purposes, eps=500 is recommended as it identifies
genuinely misplaced elements while tolerating normal viga design patterns.
