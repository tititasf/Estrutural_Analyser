"""Guarded additive deployment. Never overwrite unrecognized concurrent edits."""
import json
from pathlib import Path
import shutil
import sqlite3
import sys

FILES = [
    'scripts/drawing_mode_config.py', 'config/drawing_mode_legacy_catalog.json',
    'portal/app/routers/drawing_mode_config_routes.py',
    'portal/app/static/drawing_mode_config.js', 'portal/app/static/drawing_mode_config.css',
    'scripts/check_drawing_mode_config_real.py',
]


def replacements(root):
    result = []
    def patch(path, old, new):
        assert (root / path).read_text(encoding='utf-8').count(new) == 1, (path, new[:80])
        result.append([path, old, new])
    patch('portal/app/main.py', '    base_global_routes,', '    base_global_routes,\n    drawing_mode_config_routes,')
    patch('portal/app/main.py', '    app.include_router(base_global_routes.router)', '    app.include_router(base_global_routes.router)\n    app.include_router(drawing_mode_config_routes.router)')
    base = (root / 'portal/app/templates/base.html').read_text(encoding='utf-8')
    button = base[base.index('          <button type="button" class="ui-feedback-nav-btn" id="drawing-mode-config-open">'):base.index("          {% if membro.papel == 'dono' %}")]
    anchor = "          {% if membro.papel == 'dono' %}"
    patch('portal/app/templates/base.html', anchor, button + anchor)
    start = base.index('  <dialog id="drawing-mode-config-dialog"')
    end = base.index('  <script src="/static/ui_feedback.js', start)
    anchor = '  <script src="/static/html2canvas.min.js?v=1.4.1"></script>\n'
    patch('portal/app/templates/base.html', anchor, anchor + base[start:end])
    patch('scripts/visual_modes.py', '                      robot_class: str = "") -> VisualModeStats:', '                      robot_class: str = "", behavior=None) -> VisualModeStats:')
    patch('scripts/visual_modes.py', '    if normalized == VISUAL_MODE_NOVA:\n        return stats', '    if normalized == VISUAL_MODE_NOVA:\n        from scripts.drawing_mode_config import apply_config\n        if cls in {\'PL\', \'LV\', \'FV\', \'LJ\'}:\n            apply_config(doc, normalized, cls, behavior)\n        return stats')
    patch('scripts/visual_modes.py', '    return stats\n', '    from scripts.drawing_mode_config import apply_config\n    if cls in {\'PL\', \'LV\', \'FV\', \'LJ\'}:\n        apply_config(doc, normalized, cls, behavior)\n    return stats\n')
    patch('scripts/gerar_pl_dxf_stog.py', 'from src.core.artifact_governance import guarded_saveas', 'from scripts.drawing_mode_config import configured_function, grade_positions\nfrom src.core.artifact_governance import guarded_saveas')
    patch('scripts/gerar_pl_dxf_stog.py', 'def generate_pilar_zone(', "@configured_function('PL')\ndef generate_pilar_zone(")
    patch('scripts/gerar_pl_dxf_stog.py', 'def generate_pilar(msp, pj, row_y_offset, visual_mode="NOVA"):', '@configured_function(\'PL\')\ndef generate_pilar(msp, pj, row_y_offset, visual_mode="NOVA"):')
    patch('scripts/gerar_pl_dxf_stog.py', '        horizontal_positions = grade_horizontal_positions_for_mode(visual_mode)', '        horizontal_positions = grade_positions(visual_mode) or grade_horizontal_positions_for_mode(visual_mode)')
    for cls in ('lv', 'fv', 'lj'):
        path = f'scripts/gerar_{cls}_dxf_stog.py'
        old = 'from src.core.artifact_governance import guarded_saveas'
        new = old + '\nfrom scripts.drawing_mode_config import configure_subprocess'
        if cls == 'lj':
            new += '\nfrom visual_modes import apply_visual_mode'
        patch(path, old, new)
        key = "'LV_' + (args.behavior or 'Para').upper()" if cls == 'lv' else repr(cls.upper())
        patch(path, '    args = parser.parse_args()', f'    args = parser.parse_args()\n    configure_subprocess(globals(), args.visual_mode, {key})')
    patch('scripts/gerar_lv_dxf_stog.py', "    apply_visual_mode(doc, args.visual_mode, 'LV')", "    apply_visual_mode(doc, args.visual_mode, 'LV', args.behavior)")
    patch('scripts/gerar_lj_dxf_stog.py', '    args = parser.parse_args()\n', "    parser.add_argument('--visual-mode', choices=['INI', 'NOVA'], default='NOVA')\n    args = parser.parse_args()\n")
    for old in (
        "            out_dxf = out_dir / f'LJ_preview_{args.item}.dxf'",
        '        out_dxf = out_dir / out_name',
        '    out_dxf = out_dir / out_name',
    ):
        indent = old[:len(old) - len(old.lstrip())]
        patch('scripts/gerar_lj_dxf_stog.py', old + '\n', old + '\n' + indent + "apply_visual_mode(doc, args.visual_mode, 'LJ')\n")
    headless = 'scripts/arete/headless_sa_analise.py'
    text = (root / headless).read_text(encoding='utf-8')
    for function in ('_generate_lv_n3_nova_previews', '_generate_lj_n3_nova_previews'):
        start = text.index(f'def {function}(')
        end = text.index(') -> tuple[list[str], list[str]]:', start)
        new = text[start:end]
        patch(headless, new.replace("    visual_mode: str = 'NOVA',\n", ''), new)
    patch(headless, "                    '--visual-mode', 'NOVA',", "                    '--visual-mode', visual_mode,")
    # A unique slab command anchor (other generators also use --mode).
    patch(headless, "            '--mode', 'planta',\n            '--json-dir', str(json_dir),", "            '--mode', 'planta',\n            '--visual-mode', visual_mode,\n            '--json-dir', str(json_dir),")
    for anchor in (
        '                            obra_dir, window.beams_found, Path(n3_temp) / \'dxf\',\n                            max_workers=3 if production_web else 1,',
        '                            obra_dir, window, Path(n3_temp) / \'dxf\', pavimento,\n                            max_workers=3 if production_web else 1,',
    ):
        patch(headless, anchor, anchor + '\n                            visual_mode=visual_mode,')
    return result


if len(sys.argv) == 1:
    root = Path(__file__).resolve().parents[1]
    payload = {'new': {name: (root / name).read_text(encoding='utf-8') for name in FILES}, 'patches': replacements(root)}
    (root / 'scripts/drawing_mode_deploy_payload.json').write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
else:
    root = Path('/opt/cad-analyzer')
    backup = Path('/root/backup_drawing_mode_config_20261001')
    with sqlite3.connect(root / 'portal_data.db') as conn:
        busy = conn.execute("select id,status from portal_jobs where status in ('na_fila','executando')").fetchall()
        if busy:
            raise RuntimeError(f'Active jobs; deployment deferred: {busy}')
    payload = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    staged = {}
    for relative, old, new in payload['patches']:
        path = root / relative
        text = staged.get(path, path.read_text(encoding='utf-8'))
        # Anchor must be a full line for indented LJ save sites and final return.
        import re
        expression = re.compile(r'(?m)^' + re.escape(old))
        if len(expression.findall(text)) != 1:
            raise RuntimeError(f'Concurrent change/ambiguous anchor: {relative}/{old[:80]}')
        staged[path] = expression.sub(lambda _: new, text, count=1)
    for relative, value in payload['new'].items():
        path = root / relative
        if path.exists():
            raise RuntimeError(f'New file already exists: {relative}')
        staged[path] = value
    # Validate all code before touching any production files.
    for path, value in staged.items():
        if path.suffix == '.py':
            compile(value, str(path), 'exec')
    for path, value in staged.items():
        if path.exists():
            target = backup / path.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise RuntimeError(f'Backup collision: {target}')
            shutil.copy2(path, target)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding='utf-8')
        print(path.relative_to(root))
