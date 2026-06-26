# Decision Log

Status: stage 80 for LV N2 V301.

Evidence:
- `n2_recorte.png` full render.
- `crop_01.png`, `crop_02.png`, `crop_03.png` component crops.
- `face_unit_*.png` unit renders generated from DXF bboxes.
- `canonical_ficha.json` now preserves section heights 55 and 120 with b=19.

Findings:
- Previous repeated section value was fixed: view 1 = 55x19, view 2 = 120x19.
- Previous global A/B mismatch came from merging disconnected H-line spans on the same Y. Grouping was corrected.
- Validation model now uses 8 `face_units` by label/continuation.
- `V301.B` has 2 segments in its own unit render; adjacent drawing is not part of that unit.

Decision:
- Promote this N2 iteration to stage 80 for V301.
- Do not promote to 90+ until fine details and N4/DXF round-trip are validated.

Next:
1. Validate sarrafos, grades, hatches and openings per `face_unit_*.png`.
2. Generate N4 fichas per face/section.
3. Generate unit DXFs and compare N4 render back against N2 visual evidence.


## N4 Sandbox Pass

Generated `n4_validation/` with 8 face-unit DXFs/PNGs and 2 section DXFs/PNGs.

Decision: do not promote to 90 yet. The N4 artifacts are technically generated, but visual inspection found text/layout overlap in small lateral segments and overlapping nomenclature in the section render. Keep V301 at stage 80 until the N4 generator is tuned and rerun.
