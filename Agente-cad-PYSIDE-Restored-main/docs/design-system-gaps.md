# Design System Gaps — Vision-Estrutural AI

**Audit Date:** 2026-05-17  
**Auditor:** Uma (UX Design Expert)  
**Scope:** `src/ui/` — all `.py` files + `style.qss`

---

## Summary

| Metric | Value |
|--------|-------|
| Total unique hex colors found | ~45 |
| Files with inline styles | 12+ |
| Existing centralized QSS | 1 (`style.qss` — partial) |
| Design token file | **CREATED** (`src/ui/theme.py`) |
| Cyan variants (inconsistent) | 3 (`#00d4ff`, `#00E5FF`, `#00b8e6`) |
| Font-size values inline | 15+ distinct values (8px to 24px) |

---

## Color Gaps — Inline Hex to Token Mapping

### Backgrounds

| File | Inline Color | Correct Token |
|------|-------------|---------------|
| `organisms.py` | `#1e1e1e` | `Colors.BG_PANEL` |
| `organisms.py` | `#252528` | `Colors.BG_SURFACE` |
| `organisms.py` | `#252525` | `Colors.BG_CARD` |
| `organisms.py` | `#2d2d30` | `Colors.BORDER_PANEL` |
| `login_widget.py` | `#121212` | `Colors.BG_DEEP` |
| `login_widget.py` | `#1E1E1E` | `Colors.BG_PANEL` |
| `central_controle.py` | `#1a1a1a` | `Colors.BG_PRIMARY` (approx) |
| `dashboard_components.py` | `#252528` | `Colors.BG_SURFACE` |
| `dashboard_components.py` | `#222` / `#282828` | `Colors.BG_CARD` (approx) |

### Accent / Cyan Variants (PRIMARY INCONSISTENCY)

| File | Inline Color | Correct Token |
|------|-------------|---------------|
| `organisms.py` | `#00d4ff` | `Colors.ACCENT_PRIMARY` |
| `organisms.py` | `#00E5FF` | `Colors.ACCENT_BRAND` |
| `user_profile_dialog.py` | `#00E5FF` (x5) | `Colors.ACCENT_BRAND` |
| `login_widget.py` | `#00E5FF` (x4) | `Colors.ACCENT_BRAND` |
| `detail_card.py` | `#00d4ff` (x3) | `Colors.ACCENT_PRIMARY` |
| `detail_card.py` | `#00bcd4` (x2) | `Colors.ACCENT_TEAL` |
| `dashboard_components.py` | `#00d4ff` (x5) | `Colors.ACCENT_PRIMARY` |
| `robot_ficha_dialog.py` | `#00d4ff` (x4) | `Colors.ACCENT_PRIMARY` |
| `link_manager.py` | `#00d4ff` | `Colors.ACCENT_PRIMARY` |
| `training_log_dialog.py` | `#00d4ff` | `Colors.ACCENT_PRIMARY` |

### Blues

| File | Inline Color | Correct Token |
|------|-------------|---------------|
| `organisms.py` | `#0078d4` | `Colors.ACCENT_BLUE` |
| `login_widget.py` | `#0078D4` (x3) | `Colors.ACCENT_BLUE` |
| `login_widget.py` | `#0099FF` | `Colors.ACCENT_BLUE_HOVER` |
| `login_widget.py` | `#005A9E` | (pressed state, keep inline or add token) |
| `central_controle.py` | `#0078d4` (x4) | `Colors.ACCENT_BLUE` |
| `detail_card.py` | `#0078D4` | `Colors.ACCENT_BLUE` |

### Greens

| File | Inline Color | Correct Token |
|------|-------------|---------------|
| `detail_card.py` | `#00cc66` (x6) | `Colors.ACCENT_SUCCESS_ALT` |
| `detail_card.py` | `#4CAF50` | `Colors.ACCENT_SUCCESS` |
| `detail_card.py` | `#00ffcc` | `Colors.ACCENT_MINT` |
| `style.qss` | `#4caf50` | `Colors.ACCENT_SUCCESS` |

### Yellows / Oranges

| File | Inline Color | Correct Token |
|------|-------------|---------------|
| `detail_card.py` | `#ffd600` (x3) | `Colors.ACCENT_INFO` (approx) |
| `detail_card.py` | `#ffb300` (x2) | `Colors.ACCENT_WARNING_ALT` |
| `detail_card.py` | `#ffca28` | `Colors.ACCENT_INFO` (approx) |
| `user_profile_dialog.py` | `#FFD700` | `Colors.ACCENT_GOLD` |
| `login_widget.py` | `#FFB74D` | `Colors.ACCENT_WARNING` (approx) |
| `style.qss` | `#ffeb3b` | (warning — consider adding token) |

### Reds

| File | Inline Color | Correct Token |
|------|-------------|---------------|
| `detail_card.py` | `#f44336` | `Colors.ACCENT_DANGER` |
| `detail_card.py` | `#ff5252` | `Colors.ACCENT_DANGER_ALT` |
| `user_profile_dialog.py` | `#D32F2F` (x2) | `Colors.ACCENT_DANGER` (darker variant) |
| `style.qss` | `#f44336` | `Colors.ACCENT_DANGER` |

### Text / Grays

| File | Inline Color | Correct Token |
|------|-------------|---------------|
| Multiple | `#e0e0e0` / `#eee` / `#ddd` | `Colors.TEXT_PRIMARY` |
| Multiple | `#888` / `#888888` | `Colors.TEXT_SECONDARY` |
| Multiple | `#555` / `#555555` | `Colors.TEXT_MUTED` |
| Multiple | `#666` / `#666666` | `Colors.TEXT_DIM` |
| Multiple | `#aaa` / `#aaaaaa` | Between SECONDARY and DIM — use `Colors.TEXT_SECONDARY` |
| Multiple | `#ccc` | Use `Colors.TEXT_PRIMARY` |
| Multiple | `#fff` / `#FFF` | `Colors.TEXT_BRIGHT` |

### Borders

| File | Inline Color | Correct Token |
|------|-------------|---------------|
| Multiple | `#333` / `#333333` | `Colors.BORDER_DEFAULT` |
| Multiple | `#444` / `#444444` | `Colors.BORDER_INPUT` |
| Multiple | `#2a2a2a` | `Colors.BORDER_SUBTLE` |
| Multiple | `#2d2d30` | `Colors.BORDER_PANEL` |
| `dashboard_components.py` | `#1f2029` | (unique — map to `Colors.BORDER_SUBTLE`) |

---

## Font-Size Gaps

| Size Found | Occurrences (approx) | Suggested Token |
|------------|---------------------|-----------------|
| 8px | 1 | `Fonts.SIZE_XS` (9px close enough) |
| 9px | 5 | `Fonts.SIZE_XS` |
| 10px | 25+ | `Fonts.SIZE_SM` |
| 11px | 15+ | `Fonts.SIZE_MD` |
| 12px | 10+ | `Fonts.SIZE_LG` |
| 13px | 8 | `Fonts.SIZE_XL` |
| 14px | 6 | `Fonts.SIZE_XXL` |
| 16px | 3 | `Fonts.SIZE_TITLE` |
| 18px | 2 | (between TITLE and HERO — use TITLE) |
| 20px | 2 | `Fonts.SIZE_HERO` |
| 22px | 1 | `Fonts.SIZE_HERO` |
| 24px | 2 | (add `SIZE_DISPLAY = "24px"` if needed) |

---

## Files Requiring Migration (Priority Order)

| Priority | File | Inline Styles | Complexity |
|----------|------|--------------|------------|
| P1 | `widgets/detail_card.py` | ~60 setStyleSheet calls | HIGH |
| P1 | `organisms/login_widget.py` | ~20 inline | MEDIUM |
| P1 | `organisms/user_profile_dialog.py` | ~25 inline | MEDIUM |
| P2 | `components/organisms.py` | ~15 inline | MEDIUM |
| P2 | `widgets/dashboard_components.py` | ~20 inline | MEDIUM |
| P2 | `widgets/central_controle.py` | ~15 inline | MEDIUM |
| P3 | `dialogs/robot_ficha_dialog.py` | ~10 inline | LOW |
| P3 | `widgets/link_manager.py` | ~8 inline | LOW |
| P3 | `widgets/training_log_dialog.py` | ~6 inline | LOW |
| P3 | `widgets/data_pipeline.py` | ~5 inline | LOW |
| P3 | `widgets/interpretation_dialog.py` | ~3 inline | LOW |

---

## Existing style.qss Analysis

The `src/ui/style.qss` file (200 lines) provides a base layer of global styles for:
- QMainWindow, QWidget (base bg/font)
- QScrollBar
- QTabWidget/QTabBar
- QPushButton (generic + #PrimaryButton)
- QLineEdit, QComboBox, QTextEdit
- QListWidget, QTreeWidget
- TopBar, StatusColors, MetricCard, ProfileCard

**Problem:** Components override these global styles with inline `setStyleSheet()` calls,
creating specificity conflicts and inconsistent appearance.

---

## Next Steps (Migration Strategy)

### Phase 1: Foundation (DONE)
- [x] Create `theme.py` with all design tokens
- [x] Fix duplicate `refresh()` in `organisms.py`
- [x] Document all gaps (this file)

### Phase 2: Incremental Adoption (DONE — 2026-05-17)
- [x] `modules/comparison_engine.py` — Fase8Panel stylesheet + ScoreLabel + tabs_hist + log_box + labels inline
- [x] `modules/diagnostic_hub.py` — _build_fase3_panel + btn_similar + row2 + all status labels + dynamic setStyleSheets
- [x] `main.py` — project_tabs + tabs_container (ModuleNav container)

**Remaining P1 files for Phase 2 continuation:**
1. `widgets/detail_card.py` (~60 setStyleSheet calls)
2. `organisms/login_widget.py` (~20 inline)
3. `organisms/user_profile_dialog.py` (~25 inline)
4. `components/organisms.py` (~15 inline)

### Phase 3: StyleSheet Consolidation
1. Move repeated QSS patterns to `StyleSheets` static methods
2. Replace inline `setStyleSheet("""...""")` with `setStyleSheet(StyleSheets.sidebar())`
3. Consider using `style.qss` for truly global styles, `theme.py` for programmatic use

### Phase 4: Unify Cyan
- **Decision needed:** Is `#00E5FF` (brand) different from `#00d4ff` (accent)?
  - If YES: Keep both tokens, document when to use which
  - If NO: Unify to `#00d4ff` everywhere (current majority)

### Phase 5: Font Rationalization
- Current: 12 distinct font-size values
- Target: 8 token sizes (`XS` through `HERO`)
- Map borderline sizes (18px, 22px) to nearest token

---

## Design Decisions Log

| Decision | Rationale |
|----------|-----------|
| Keep `style.qss` for global base | It works as a CSS reset/defaults layer |
| Use `theme.py` for programmatic tokens | Python-native, no file I/O, IDE autocomplete |
| Two cyan tokens (PRIMARY vs BRAND) | Existing code uses both; unify later after visual review |
| Spacing in int (not px string) | Used in `setContentsMargins()` and `setSpacing()` which take int |
| Include `StyleSheets` class | Most common patterns pre-built for drop-in replacement |
