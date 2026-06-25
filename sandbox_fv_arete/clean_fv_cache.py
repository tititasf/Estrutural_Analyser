"""
LIMPEZA TOTAL: Remove TODOS os DXFs FV cached em ambos os locais.
Isso forca a UI a SEMPRE regenerar pelo motor novo.
"""
import os, glob

fase6 = 'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD'

# 1. Remove FV DXFs na raiz do Fase-6
removed = 0
for f in glob.glob(os.path.join(fase6, 'FV_preview_*.dxf')):
    os.remove(f)
    removed += 1
    print(f"  DEL {f}")

# 2. Remove FV DXFs no subdir n4/
for f in glob.glob(os.path.join(fase6, 'n4', 'FV_preview_*.dxf')):
    os.remove(f)
    removed += 1
    print(f"  DEL {f}")

# 3. Remove JSONs temporarios n4er
json_dir = 'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-4_Sincronizacao/JSON_Vigas_Fundo'
for f in glob.glob(os.path.join(json_dir, '*n4er*')):
    os.remove(f)
    removed += 1
    print(f"  DEL {f}")

# 4. Remove o FV_gerado.dxf antigo
old = os.path.join(fase6, 'FV_gerado.dxf')
if os.path.exists(old):
    os.remove(old)
    removed += 1
    print(f"  DEL {old}")

print(f"\nTotal removido: {removed} arquivos")
