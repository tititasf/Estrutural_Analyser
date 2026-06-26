# Decision Log

Status: agent vision pass 1 complete.

Stage: 60%.

Evidence:
- `n2_recorte.png` shows V301 with multiple A/B continuations and two section views.
- `crop_01.png` shows two section views at the left of the upper group.
- DXF text listing contains `Cota Secao (2x)` values 55 and 120, both with b=19 nearby.

Findings:
- `section_views` count = 2 appears correct.
- Extractor records both `h_section` values as 55. Vision/tool-supported reading says VC #1 = 55 and VC #2 = 120.
- Extractor returned `segments_A=13` and `segments_B=12`; this does not pair cleanly and must be validated by unit crops before approval.

Decision:
- Do not promote N2 V301 yet.
- Treat this as 60% similarity: main item found and VC count exists, but dimensional VC field and A/B segment pairing are not reliable.

Next actions:
1. Add unit crop generation for each face/continuation/VC.
2. Fix `motor_reverso_lv.py` section view association so it preserves 55 and 120 for V301.
3. Re-run V301 and verify A/B pairing.
