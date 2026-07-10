import re
from pathlib import Path

path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\torre_crop.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

validation_logic = '''
def _ler_validacao(out_dir: Path) -> dict:
    vf = out_dir / "validado.json"
    if vf.is_file():
        import json
        try:
            return json.loads(vf.read_text(encoding="utf-8"))
        except:
            return {}
    return {}

def _salvar_validacao(out_dir: Path, data: dict):
    vf = out_dir / "validado.json"
    import json
    vf.write_text(json.dumps(data), encoding="utf-8")

def set_recorte_validado(obra_dir: Path, bruto_stem: str, item_id: str, validado: bool):
    out_dir = _dir_recortes_bruto(obra_dir, bruto_stem)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = _ler_validacao(out_dir)
    data[item_id] = validado
    _salvar_validacao(out_dir, data)

'''

content = content.replace('def gerar_recortes_bruto(', validation_logic + 'def gerar_recortes_bruto(')

content = content.replace('for i, torre in enumerate(regions["torres"], 1):', '''
    validados = _ler_validacao(out_dir)
    for i, torre in enumerate(regions["torres"], 1):
        nome_torre = f"torre_{i}"
        out_path = out_dir / f"{nome_torre}.dxf"
        if validados.get(nome_torre) and out_path.is_file():
            resultado["torres"].append({"nome": nome_torre, "path": str(out_path), "entidades": 0, "cached": True})
            continue
''')

# Handle the detalhes part
detalhes_old = '''    if regions["detalhes"]:
        bboxes = [d["bbox"] for d in regions["detalhes"]]
        out_path = out_dir / "detalhes.dxf"
        crop = crop_dxf_multi(dxf_bruto_path, out_path, bboxes, padding_pct=0.01)
        if crop.get("error"):
            resultado["error"] = f"detalhes: {crop['error']}"
        else:
            resultado["detalhes"] = {"nome": "detalhes", "path": str(out_path),
                                      "entidades": crop["entities_copied"]}'''

detalhes_new = '''    if regions["detalhes"]:
        out_path = out_dir / "detalhes.dxf"
        if validados.get("detalhes") and out_path.is_file():
            resultado["detalhes"] = {"nome": "detalhes", "path": str(out_path), "entidades": 0, "cached": True}
        else:
            bboxes = [d["bbox"] for d in regions["detalhes"]]
            crop = crop_dxf_multi(dxf_bruto_path, out_path, bboxes, padding_pct=0.01)
            if crop.get("error"):
                resultado["error"] = f"detalhes: {crop['error']}"
            else:
                resultado["detalhes"] = {"nome": "detalhes", "path": str(out_path),
                                          "entidades": crop["entities_copied"]}'''

content = content.replace(detalhes_old, detalhes_new)

# Update listar_recortes_bruto
listar_old = '''    itens = [
        {"item_id": p.stem, "titulo": p.stem.replace("_", " ").title(), "path": str(p)}
        for p in sorted(out_dir.glob("torre_*.dxf"))
    ]
    det = out_dir / "detalhes.dxf"
    if det.is_file():
        itens.append({"item_id": "detalhes", "titulo": "Detalhes e Convenções", "path": str(det)})'''

listar_new = '''    validados = _ler_validacao(out_dir)
    itens = [
        {"item_id": p.stem, "titulo": p.stem.replace("_", " ").title(), "path": str(p), "validado": validados.get(p.stem, False)}
        for p in sorted(out_dir.glob("torre_*.dxf"))
    ]
    det = out_dir / "detalhes.dxf"
    if det.is_file():
        itens.append({"item_id": "detalhes", "titulo": "Detalhes e Convenções", "path": str(det), "validado": validados.get("detalhes", False)})'''

content = content.replace(listar_old, listar_new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
