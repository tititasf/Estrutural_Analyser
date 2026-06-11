"""
Executa os SCRs existentes do P1 no AutoCAD e salva DXF.
Nao regenera SCRs — usa os ja existentes.
"""
import sys, os, time
import win32com.client, pythoncom

SCRIPTS_ROOT = "D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/SCRIPTS_ROBOS"
MOLDE  = "D:\\Agente-cad-PYSIDE\\BASE_DWG_PARA_COMANDOS_SCRIPTS.dwg"
OUT    = "D:\\Agente-cad-PYSIDE\\output_dxf_teste"
os.makedirs(OUT, exist_ok=True)

NOME   = "1"   # nome do pilar
SCRS = [
    os.path.join(SCRIPTS_ROOT, "Pav50_entidades_CIMA",   f"P{NOME}_CIMA.scr"),
    os.path.join(SCRIPTS_ROOT, "Pav50_entidades_ABCD",   f"P{NOME}_ABCD.scr"),
    os.path.join(SCRIPTS_ROOT, "Pav50_entidades_GRADES", f"P{NOME}.scr"),
]

for s in SCRS:
    exists = os.path.exists(s)
    print(f"  {'OK' if exists else 'FALTA'} {os.path.basename(s)}")
    if not exists:
        print("SCR nao encontrado. Rode o gerador primeiro.")
        sys.exit(1)

# Conecta ao AutoCAD
pythoncom.CoInitialize()
print("\nConectando ao AutoCAD...")
try:
    acad_raw = win32com.client.GetActiveObject("AutoCAD.Application")
    acad = win32com.client.Dispatch(acad_raw)
    print("  Conectado a instancia existente.")
except Exception as e:
    print(f"  Nao conectou ({e}), abrindo nova instancia...")
    acad = win32com.client.Dispatch("AutoCAD.Application")
    acad.Visible = True
    time.sleep(5)

acad.Visible = True
try: acad.WindowState = 3
except: pass
time.sleep(2)

# Abre MOLDE
print(f"Abrindo MOLDE...")
try:
    doc = acad.Documents.Open(MOLDE)
    time.sleep(4)
except Exception as e1:
    print(f"  Documents.Open falhou ({e1}), usando ActiveDocument...")
    try:
        doc = acad.ActiveDocument
        time.sleep(1)
    except Exception as e2:
        print(f"  Erro: {e2}")
        sys.exit(1)

# Suprime dialogs
for cmd in ['(setvar "FILEDIA" 0)', '(setvar "CMDDIA" 0)', '(setvar "ATTREQ" 0)']:
    try: doc.SendCommand(cmd + '\n')
    except: pass
time.sleep(1)

# Combina os 3 SCRs em um unico arquivo temporario
combined_scr = os.path.join(OUT, f"P{NOME}_combined.scr").replace("\\", "/")
print(f"Combinando SCRs em: {os.path.basename(combined_scr)}")
with open(combined_scr, "w", encoding="cp1252", errors="replace") as out_f:
    for scr in SCRS:
        with open(scr, "r", encoding="cp1252", errors="replace") as in_f:
            content = in_f.read()
        out_f.write(content)
        if not content.endswith("\n"):
            out_f.write("\n")

# Executa SCR combinado uma unica vez
print(f"  Executando SCR combinado ({os.path.getsize(combined_scr)} bytes)...")
doc.SendCommand(f'(command "SCRIPT" "{combined_scr}")\n')

time.sleep(25)

# Salva DXF
dxf = os.path.join(OUT, f"P{NOME}.dxf")
print(f"Salvando DXF: {dxf}")
try:
    doc.SaveAs(dxf, 61)
    time.sleep(2)
    if os.path.exists(dxf):
        print(f"DXF salvo: {dxf}  ({os.path.getsize(dxf)} bytes)")
    else:
        print("Arquivo nao encontrado apos SaveAs.")
except Exception as e:
    print(f"SaveAs falhou ({e}), tentando DXFOUT...")
    dxf_fwd = dxf.replace("\\", "/")
    doc.SendCommand(f'(command "DXFOUT" "{dxf_fwd}" "" "16" "")\n')
    time.sleep(4)
    if os.path.exists(dxf):
        print(f"DXF salvo via DXFOUT: {dxf}  ({os.path.getsize(dxf)} bytes)")
    else:
        print("AVISO: DXF nao encontrado — verificar AutoCAD.")
