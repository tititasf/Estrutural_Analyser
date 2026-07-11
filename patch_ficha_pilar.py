import re
path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\ficha_reader.py'
with open(path, 'r', encoding='utf-8') as f: txt = f.read()

new_pilar = '''def _normalizar_pilar(p: dict) -> dict:
    return {
        "item_id": p.get("name"),
        "titulo": p.get("name"),
        "campos": {
            "Nome": p.get("name"),
            "Classificação": p.get("classification"),
            "Orientação": p.get("orientation"),
            "Nível": p.get("nivel_str") or p.get("nivel"),
            "Lado A": p.get("lado_A"),
            "Lado B": p.get("lado_B"),
            "Lado C": p.get("lado_C"),
            "Lado D": p.get("lado_D"),
            "Lajes contíguas": ", ".join(p.get("lajes", [])) if p.get("lajes") else "Nenhuma",
        },
        "atencao": p.get("atencao") or "",
        "points": p.get("points") or [],
        "beam_name": p.get("name"),
    }'''

txt = re.sub(r'def _normalizar_pilar\(p: dict\) -> dict:.*?    }', new_pilar, txt, flags=re.DOTALL)
with open(path, 'w', encoding='utf-8') as f: f.write(txt)
print('Patched pilar')
