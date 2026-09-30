
# Verification of Canvas Updates

## 1. Feature Map

| Feature | Implementation Status | Notes |
| :--- | :--- | :--- |
| **Zoom on Scroll** | ✅ Implemented | Overridden `wheelEvent` in `PilarCanvas`. |
| **Middle Click Pan** | ✅ Implemented | Added `mousePressEvent` and `mouseReleaseEvent` with `ScrollHandDrag`. |
| **Sarrafos (Internal Lines)** | ✅ Implemented | Added `_draw_sarrafos` drawing dashed lines at `h2`, `h3`, `h4`. |
| **Aberturas (Openings)** | ✅ Verified | `_draw_face_openings` exists and draws rectangles based on config. |
| **Field Bindings** | ✅ Implemented | Added `editingFinished` signal to ensure calc on focus out. |
| **Auto Levels** | ✅ Implemented | `Chegada`/`Saida`/`Altura` sync logic added. |
| **Screw Calculation** | ✅ Implemented | Using legacy `GradeCalculator` logic + cumulative heights. |
| **Missing Fields** | ✅ Implemented | Added Altura Detalhe to all groups special faces. |
| **Boot Error** | ✅ Fixed | Resolved `canvas` attribute error by safe init. |
| **Render Error** | ✅ Fixed | Resolved `TypeError` in canvas drawing by forcing float conversion. |

## 2. Validation

- **Canvas Interaction:**
  - Scrolling mouse wheel should now zoom in/out.
  - Holding Middle Mouse Button should pan the view.
- **Visuals:**
  - "Sarrafos" appear as brown dashed lines across the face width at appropriate heights.
  - Openings appear as dashed rectangles with labels.

## 3. Notes

- The coordinate system for `h` values is assumed to be from the bottom (0). The drawing logic uses `y = -h`.
- `Rebaixo` for openings is assumed to be from the top. Logic uses `oy = -total_h + pos_y`.

## 4. Next Steps

- User to test the canvas interaction.
- If Openings (Aberturas) are not appearing, user should check the `posicao` logic relative to Top/Bottom conventions in their specific project data.
