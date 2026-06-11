"""
Simples: AutoCAD ja aberto. Para cada pilar:
  1. Gera SCRs
  2. Envia (command "SCRIPT" ...) via ActiveDocument
  3. Aguarda
  4. Envia DXFOUT via ActiveDocument
"""
import sys, os, json, time

PILARES_ROOT = "D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25"
SRC_DIR  = os.path.join(PILARES_ROOT, "src")
CORE_DIR = os.path.join(SRC_DIR, "core")
OUT      = "D:/Agente-cad-PYSIDE/output_dxf_batch"
OBRA     = "Obra50_entidades"
PAV      = "Pav50_entidades"
LOTE     = 10

os.makedirs(OUT, exist_ok=True)

for p in [PILARES_ROOT, SRC_DIR,
          os.path.join(SRC_DIR, "interfaces"),
          os.path.join(SRC_DIR, "robots"),
          os.path.join(SRC_DIR, "utils"),
          os.path.join(SRC_DIR, "models"),
          os.path.join(SRC_DIR, "services")]:
    sys.path.insert(0, p)

from models.pilar_model import PilarModel
from services.automation_service import AutomationOrchestratorService as AutomationService
import win32com.client, pythoncom, pywintypes

# ── Conecta ao AutoCAD existente (early binding para interface completa) ───────
pythoncom.CoInitialize()
print("Conectando ao AutoCAD...")
try:
    # EnsureDispatch gera type library e retorna interface completa (Documents, ActiveDocument, etc.)
    acad = win32com.client.gencache.EnsureDispatch("AutoCAD.Application")
    print(f"  OK (EnsureDispatch): {acad.Name}")
except Exception as e1:
    print(f"  EnsureDispatch falhou ({e1}), tentando GetActiveObject...")
    try:
        raw = win32com.client.GetActiveObject("AutoCAD.Application")
        acad = win32com.client.Dispatch(raw)
        print(f"  OK (GetActiveObject+Dispatch): {acad.Name}")
    except Exception as e2:
        print(f"  Abrindo nova instancia... ({e2})")
        acad = win32com.client.Dispatch("AutoCAD.Application")
        acad.Visible = True
        time.sleep(15)
        print(f"  OK (nova instancia): {acad.Name}")

# ── Carrega pilares ────────────────────────────────────────────────────────────
with open(os.path.join(CORE_DIR, "obras_salvas.json"), encoding="utf-8") as f:
    obras = json.load(f)
pav_data = obras[OBRA][PAV]
pids = sorted(pav_data.keys(), key=lambda k: int(k.split("_")[-1]) if k.split("_")[-1].isdigit() else 9999)[:LOTE]
print(f"Pilares: {[p.split('_')[-1] for p in pids]}")

svc = AutomationService(project_root=PILARES_ROOT)
results = []

MOLDE = "D:\\Agente-cad-PYSIDE\\BASE_DWG_PARA_COMANDOS_SCRIPTS.dwg"

def get_doc():
    """Abre MOLDE com retry em RPC_CALL_REJECTED."""
    for attempt in range(15):
        try:
            doc = acad.Documents.Open(MOLDE)
            time.sleep(6)
            return doc
        except pywintypes.com_error as e:
            if e.hresult == -2147418111 and attempt < 14:
                print(f"    [open retry {attempt+1}/15] AutoCAD ocupado, aguardando 4s...")
                time.sleep(4)
            else:
                raise

def send(doc, cmd, wait=0):
    """Envia comando ao doc com retry em call rejected/disconnected."""
    for attempt in range(12):
        try:
            doc.SendCommand(cmd)
            if wait:
                time.sleep(wait)
            return True
        except pywintypes.com_error as e:
            if e.hresult in (-2147418111, -2147417848) and attempt < 11:
                print(f"    [retry {attempt+1}/12] AutoCAD ocupado ({e.hresult:#010x}), aguardando 4s...")
                time.sleep(4)
            else:
                print(f"    SendCommand ERRO: {e}")
                return False
    return False

# ── Loop principal ─────────────────────────────────────────────────────────────
for idx, pid in enumerate(pids, 1):
    dados = pav_data[pid]
    nome  = str(dados.get("nome") or dados.get("numero") or pid.split("_")[-1])
    print(f"\n{'='*50}")
    print(f"[{idx:02d}/{LOTE}] P{nome}  comp={dados['comprimento']}  larg={dados['largura']}  alt={dados['altura']}")

    # 1. Gera SCRs
    pilar = PilarModel(**{k: v for k, v in dados.items() if k in PilarModel.model_fields})
    pilar.pavimento = PAV
    cima   = svc.generate_item_script_cima  (pilar, PAV, OBRA)
    abcd   = svc.generate_item_script_abcd  (pilar, PAV, OBRA)
    grades = svc.generate_item_script_grades(pilar, PAV, OBRA)
    print(f"  SCRs: CIMA={'OK' if cima else 'X'}  ABCD={'OK' if abcd else 'X'}  GRADES={'OK' if grades else 'X'}")

    # 2. Combina SCRs
    scripts_dir = svc.scripts_dir
    scr_files = [
        os.path.join(scripts_dir, f"{PAV}_CIMA",   f"P{nome}_CIMA.scr"),
        os.path.join(scripts_dir, f"{PAV}_ABCD",   f"P{nome}_ABCD.scr"),
        os.path.join(scripts_dir, f"{PAV}_GRADES",  f"P{nome}.scr"),
    ]
    combined = os.path.join(OUT, f"P{nome}_combined.scr")
    with open(combined, "w", encoding="cp1252", errors="replace") as out_f:
        for sp in scr_files:
            if os.path.exists(sp):
                with open(sp, "r", encoding="cp1252", errors="replace") as sf:
                    c = sf.read()
                out_f.write(c)
                if not c.endswith("\n"):
                    out_f.write("\n")
    combined_fwd = combined.replace("\\", "/")
    print(f"  Combined: {os.path.getsize(combined)} bytes")

    # 3. Abre MOLDE e obtém doc COM completo
    print(f"  Abrindo MOLDE...")
    try:
        doc = get_doc()
        print(f"  MOLDE aberto.")
    except Exception as e:
        print(f"  Falhou ao abrir MOLDE: {e}")
        results.append((nome, "FAIL-molde"))
        continue

    # 4. Desabilita dialogs
    send(doc, '(setvar "FILEDIA" 0)\n')
    send(doc, '(setvar "CMDDIA" 0)\n')
    time.sleep(0.5)

    # 5. Executa SCR
    print(f"  Executando SCR...")
    ok = send(doc, f'(command "SCRIPT" "{combined_fwd}")\n', wait=35)
    if not ok:
        print(f"  FALHOU no SCRIPT — pulando P{nome}")
        results.append((nome, "FAIL-script"))
        try: doc.Close(False)
        except: pass
        continue
    print(f"  SCR concluido.")

    # 6. Salva DXF — tenta SaveAs COM direto primeiro
    dxf_win = os.path.join(OUT, f"P{nome}.dxf").replace("/", "\\")
    dxf_fwd = dxf_win.replace("\\", "/")
    print(f"  Salvando DXF...")
    saved = False
    try:
        doc.SaveAs(dxf_win, 61)   # 61 = acDXF R2010
        time.sleep(3)
        if os.path.exists(dxf_win) and os.path.getsize(dxf_win) > 1000:
            print(f"  DXF OK via SaveAs: {os.path.getsize(dxf_win)//1024} KB")
            results.append((nome, "OK"))
            saved = True
    except Exception as e:
        print(f"  SaveAs falhou ({e}), tentando DXFOUT...")

    if not saved:
        send(doc, f'(command "DXFOUT" "{dxf_fwd}" "" "16" "")\n', wait=5)
        if os.path.exists(dxf_win) and os.path.getsize(dxf_win) > 1000:
            print(f"  DXF OK via DXFOUT: {os.path.getsize(dxf_win)//1024} KB")
            results.append((nome, "OK-dxfout"))
            saved = True
        else:
            print(f"  DXF nao encontrado.")
            results.append((nome, "FAIL-dxf"))

    # 7. Fecha documento e pausa
    try:
        doc.Close(False)
        time.sleep(3)
    except Exception as e:
        print(f"  Close: {e}")
    print(f"  Pausa 5s...")
    time.sleep(5)

# ── Resumo ─────────────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print("RESULTADO:")
for nome, status in results:
    print(f"  {'[OK]' if status.startswith('OK') else '[--]'} P{nome}: {status}")
ok_count = sum(1 for _, s in results if s.startswith("OK"))
print(f"\n{ok_count}/{len(results)} DXFs gerados.")
