import re
import os

def patch_file(filepath):
    print(f"Patching {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. replace .pkl with .json in strings
    content = content.replace('.pkl', '.json')

    # 2. replace pickle with json in imports
    content = content.replace('import pickle', 'import json')
    content = content.replace(', pickle', ', json')
    content = content.replace('pickle, ', 'json, ')

    # 3. replace pickle.load and pickle.dump
    # Note: json doesn't have the same binary mode requirements
    
    # Substituir escrita: with open(path, 'wb') as f: pickle.dump(data, f)
    # -> with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
    def replace_dump(match):
        indent = match.group(1)
        path = match.group(2)
        f_name = match.group(3)
        data = match.group(4)
        return f"{indent}with open({path}, 'w', encoding='utf-8') as {f_name}:\n{indent}    json.dump({data}, {f_name}, indent=4, ensure_ascii=False)"

    content = re.sub(r'(\s+)with open\(([^,]+),\s*[\'"]wb[\'"]\)\s+as\s+(\w+):\s+pickle\.dump\(([^,]+),\s*\3\)', 
                    replace_dump, content)

    # Substituir leitura: with open(path, 'rb') as f: data = pickle.load(f)
    # -> with open(path, 'r', encoding='utf-8') as f: data = json.load(f)
    def replace_load(match):
        indent = match.group(1)
        path = match.group(2)
        f_name = match.group(3)
        var_name = match.group(4)
        return f"{indent}with open({path}, 'r', encoding='utf-8') as {f_name}:\n{indent}    {var_name} = json.load({f_name})"

    content = re.sub(r'(\s+)with open\(([^,]+),\s*[\'"]rb[\'"]\)\s+as\s+(\w+):\s+([^=]+)\s*=\s*pickle\.load\(\3\)', 
                    replace_load, content)

    # Casos residuais sem 'with'
    content = content.replace('pickle.load(', 'json.load(')
    content = content.replace('pickle.dump(', 'json.dump(')
    
    # Mudar modos de abertura residuais
    content = content.replace("'rb'", "'r'").replace('"rb"', '"r"')
    content = content.replace("'wb'", "'w'").replace('"wb"', '"w"')
    
    # Caso específico para encoding em json.dump se não estiver presente
    # (isso é difícil via replace simples, mas o dump padrão do json funciona bem)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    base_dirs = [
        r"c:\Users\Ryzen\Desktop\GITHUB\Agente-cad-PYSIDE\_ROBOS_ABAS\Robo_Pilares\pilares-atualizado-09-25\src",
        r"c:\Users\Ryzen\Desktop\GITHUB\Agente-cad-PYSIDE\_ROBOS_ABAS\Robo_Fundos_de_Vigas",
        r"c:\Users\Ryzen\Desktop\GITHUB\Agente-cad-PYSIDE\_ROBOS_ABAS\Robo_Laterais_de_Vigas",
        r"c:\Users\Ryzen\Desktop\GITHUB\Agente-cad-PYSIDE\_ROBOS_ABAS\Robo_Lajes"
    ]
    
    for bdir in base_dirs:
        if not os.path.exists(bdir): continue
        for root, dirs, files in os.walk(bdir):
            for file in files:
                if file.endswith(".py"):
                    fpath = os.path.join(root, file)
                    # Não precisamos ler o arquivo inteiro só pra checar pickle se o script for rápido
                    patch_file(fpath)
