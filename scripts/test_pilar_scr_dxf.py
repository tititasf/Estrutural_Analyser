"""
Teste: gera SCRs de 1 pilar da Obra50_entidades e executa no AutoCAD via COM.
Resultado esperado: DXF salvo em D:/Agente-cad-PYSIDE/output_dxf_teste/
"""
import sys, os, json, time

# ── Paths ──────────────────────────────────────────────────────────────────────
PILARES_ROOT = "D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25"
SRC_DIR  = os.path.join(PILARES_ROOT, "src")
CORE_DIR = os.path.join(SRC_DIR, "core")
MOLDE    = "D:/Agente-cad-PYSIDE/BASE_DWG_PARA_COMANDOS_SCRIPTS.dwg"
OUT_DXF  = "D:/Agente-cad-PYSIDE/output_dxf_teste"
os.makedirs(OUT_DXF, exist_ok=True)

sys.path.insert(0, PILARES_ROOT)
sys.path.insert(0, SRC_DIR)
sys.path.insert(0, os.path.join(SRC_DIR, "interfaces"))
sys.path.insert(0, os.path.join(SRC_DIR, "robots"))
sys.path.insert(0, os.path.join(SRC_DIR, "utils"))
sys.path.insert(0, os.path.join(SRC_DIR, "models"))
sys.path.insert(0, os.path.join(SRC_DIR, "services"))

# ── 1. Carrega 1 pilar da Obra50 ───────────────────────────────────────────────
obras_path = os.path.join(CORE_DIR, "obras_salvas.json")
with open(obras_path, "r", encoding="utf-8") as f:
    obras = json.load(f)

pav = obras["Obra50_entidades"]["Pav50_entidades"]
pid = sorted(pav.keys())[0]  # primeiro pilar
dados = pav[pid]
print(f"Pilar selecionado: {pid}")
print(f"  comprimento={dados['comprimento']} largura={dados['largura']} altura={dados['altura']}")

# ── 2. Constrói PilarModel ──────────────────────────────────────────────────────
from models.pilar_model import PilarModel
from models.pavimento_model import PavimentoModel
from models.obra_model import ObraModel

pilar = PilarModel(**{k: v for k, v in dados.items() if k in PilarModel.model_fields})
pilar.pavimento = "Pav50_entidades"

pav_model = PavimentoModel(nome="Pav50_entidades", pilares=[pilar])
obra_model = ObraModel(nome="Obra50_entidades", pavimentos=[pav_model])

print(f"PilarModel criado: nome={pilar.nome} numero={pilar.numero}")

# ── 3. Gera SCRs via AutomationService ─────────────────────────────────────────
from services.automation_service import AutomationOrchestratorService as AutomationService

svc = AutomationService(project_root=PILARES_ROOT)
print(f"Scripts dir: {svc.scripts_dir}")

print("\nGerando CIMA...")
cima = svc.generate_item_script_cima(pilar, "Pav50_entidades", "Obra50_entidades")
print(f"  CIMA: {'OK' if cima else 'FALHOU'}")

print("Gerando ABCD...")
abcd = svc.generate_item_script_abcd(pilar, "Pav50_entidades", "Obra50_entidades")
print(f"  ABCD: {'OK' if abcd else 'FALHOU'}")

print("Gerando GRADES...")
grades = svc.generate_item_script_grades(pilar, "Pav50_entidades", "Obra50_entidades")
print(f"  GRADES: {'OK' if grades else 'FALHOU'}")

# Lista os SCRs gerados
scripts_dir = svc.scripts_dir
print(f"\nSCRs gerados em: {scripts_dir}")
for dirpath, _, files in os.walk(scripts_dir):
    for f in files:
        if f.endswith(".scr"):
            full = os.path.join(dirpath, f)
            print(f"  {full} ({os.path.getsize(full)} bytes)")

if not cima and not abcd and not grades:
    print("\nERRO: Nenhum SCR gerado. Abortando.")
    sys.exit(1)

# ── 4. Executa no AutoCAD via COM ──────────────────────────────────────────────
import win32com.client
import pythoncom

print("\nConectando ao AutoCAD...")
pythoncom.CoInitialize()

try:
    acad = win32com.client.GetActiveObject("AutoCAD.Application")
    print("  AutoCAD encontrado.")
except Exception as e:
    print(f"  AutoCAD não está aberto: {e}")
    print("  Abrindo AutoCAD...")
    acad = win32com.client.Dispatch("AutoCAD.Application")
    acad.Visible = True
    time.sleep(3)

acad.Visible = True
acad.WindowState = 3  # maximizado
time.sleep(4)  # aguarda AutoCAD inicializar

# Desabilita dialogs que bloqueiam COM
try:
    acad.ActiveDocument.SendCommand('(setvar "FILEDIA" 0)\n')
    acad.ActiveDocument.SendCommand('(setvar "CMDDIA" 0)\n')
    time.sleep(1)
except:
    pass

# Abre o MOLDE
print(f"\nAbrindo MOLDE: {MOLDE}")
doc = acad.Documents.Open(MOLDE.replace("/", "\\"))
time.sleep(4)  # aguarda MOLDE carregar

# Desabilita dialogs no documento aberto
try:
    doc.SendCommand('(setvar "FILEDIA" 0)\n')
    doc.SendCommand('(setvar "CMDDIA" 0)\n')
    time.sleep(1)
except:
    pass

# Executa cada SCR gerado
pav_safe = "Pav50_entidades"
for subdir in [f"{pav_safe}_CIMA", f"{pav_safe}_ABCD", f"{pav_safe}_GRADES"]:
    full_dir = os.path.join(scripts_dir, subdir)
    if not os.path.exists(full_dir):
        continue
    # Só executa o SCR do pilar P1 (nome = dados["nome"])
    nome_p = dados.get("nome") or dados.get("numero") or "1"
    scrs = sorted([f for f in os.listdir(full_dir) if f.endswith(".scr") and f.startswith(f"P{nome_p}")])
    if not scrs:
        scrs = sorted([f for f in os.listdir(full_dir) if f.endswith(".scr")])[:1]
    for scr in scrs:
        scr_path = os.path.join(full_dir, scr).replace("\\", "/")
        print(f"  Executando SCR: {scr_path}")
        doc.SendCommand(f'(command "SCRIPT" "{scr_path}")\n')
        time.sleep(5)  # aguarda script executar

# Aguarda finalizar
print("Aguardando AutoCAD finalizar scripts...")
time.sleep(5)

# Salva como DXF — formato 61 = acDXF (DXF R2010)
nome_pilar = f"P{dados.get('nome') or dados.get('numero') or '1'}"
dxf_path = os.path.join(OUT_DXF, f"{nome_pilar}.dxf").replace("/", "\\")
print(f"\nSalvando DXF: {dxf_path}")
try:
    doc.SaveAs(dxf_path, 61)  # 61 = acDXF R2010
    time.sleep(2)
    print(f"DXF salvo: {dxf_path}")
except Exception as e:
    print(f"SaveAs falhou ({e}), tentando DXFOUT via SendCommand...")
    doc.SendCommand(f'(command "DXFOUT" "{dxf_path.replace(chr(92), "/")}" "" "16" "")\n')
    time.sleep(3)
    if os.path.exists(dxf_path):
        print(f"DXF salvo via DXFOUT: {dxf_path}")
    else:
        print("AVISO: DXF nao encontrado em disco — verificar AutoCAD manualmente")

print("\nTeste concluido!")
