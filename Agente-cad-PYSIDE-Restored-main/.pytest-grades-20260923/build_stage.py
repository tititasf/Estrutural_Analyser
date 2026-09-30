from pathlib import Path

root = Path(__file__).resolve().parent
project = root.parent

def read(name):
    return (root / name).read_text(encoding='utf-8')

def write(name, content):
    (root / name).write_text(content, encoding='utf-8', newline='')

def replace_once(content, old, new):
    assert content.count(old) == 1, (old[:80], content.count(old))
    return content.replace(old, new, 1)

local_py = (project / 'portal/app/routers/n1_routes.py').read_text(encoding='utf-8')
start = local_py.index('def _grades_detail_contract(')
end = local_py.index('def _resumo_pilar_n1(', start)
grade_helper = local_py[start:end]
remote_py = read('remote_n1_routes.py')
remote_py = replace_once(remote_py, 'def _resumo_pilar_n1(', grade_helper + 'def _resumo_pilar_n1(')
old = '''    return {"obra_id": obra_id, "classe": classe, "pavimento": pav, "item_id": base_id,
            "ficha": ficha, "visualizacoes_n3": visualizacoes_n3,
            "visual_mode": ficha_reader.modo_visual_n3(
                obra_dir, pav, classe, {"beam_name": base_id}, vista or "cima",
                visual_mode,
            ),
'''
new = '''    resolved_visual_mode = ficha_reader.modo_visual_n3(
        obra_dir, pav, classe, {"beam_name": base_id}, vista or "cima", visual_mode,
    )
    grades_detail = None
    if vista and vista.startswith("grades"):
        grade_ficha = {**ficha, "cima_contract": cima_contract}
        grade_robot = {**robot, **pillar_n3_ficha.robot_patch(grade_ficha)}
        grades_detail = _grades_detail_contract(grade_robot, resolved_visual_mode)
    return {"obra_id": obra_id, "classe": classe, "pavimento": pav, "item_id": base_id,
            "ficha": ficha, "visualizacoes_n3": visualizacoes_n3,
            "visual_mode": resolved_visual_mode,
'''
remote_py = replace_once(remote_py, old, new)
remote_py = replace_once(remote_py, '            "cima_contract": cima_contract,\n', '            "cima_contract": cima_contract,\n            "grades_detail": grades_detail,\n')
write('staged_n1_routes.py', remote_py)

local_js = (project / 'portal/app/static/pillar_ficha.js').read_text(encoding='utf-8')
start = local_js.index('  App.prototype.renderGrades = function(){')
end = local_js.index('  window.PillarFicha', start)
grade_render = local_js[start:end]
remote_js = read('remote_pillar_ficha.js')
remote_js = replace_once(remote_js,
    'self.cimaContract = body.cima_contract || body.ficha; self.views =',
    'self.cimaContract = body.cima_contract || body.ficha; self.gradesDetail=body.grades_detail||{}; self.views =')
start = remote_js.index('  App.prototype.renderGrades = function(){')
end = remote_js.index('  window.PillarFicha', start)
remote_js = remote_js[:start] + grade_render + remote_js[end:]
write('staged_pillar_ficha.js', remote_js)

local_css = (project / 'portal/app/static/pillar_ficha.css').read_text(encoding='utf-8')
grade_css = local_css[local_css.index('.plf-grade-intro{'):]
remote_css = read('remote_pillar_ficha.css')
assert '.plf-grade-intro{' not in remote_css
write('staged_pillar_ficha.css', remote_css.rstrip() + '\n' + grade_css)

template = read('remote_obra_detalhe.html')
template = replace_once(template, '-pillar-levels-v7', '-pillar-grades-v1')
template = replace_once(template, '-pillar-levels-v10', '-pillar-grades-v1')
write('staged_obra_detalhe.html', template)
