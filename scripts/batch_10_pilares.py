"""
Batch: gera SCRs + DXFs para os primeiros 10 pilares da Obra50_entidades.
Um por vez, com pausa e fechamento de documento entre cada pilar.
"""
import sys, os, json, time

PILARES_ROOT = "D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25"
SRC_DIR  = os.path.join(PILARES_ROOT, "src")
CORE_DIR = os.path.join(SRC_DIR, "core")
MOLDE    = "D:\\Agente-cad-PYSIDE\\BASE_DWG_PARA_COMANDOS_SCRIPTS.dwg"
OUT_DXF  = "D:\\Agente-cad-PYSIDE\\output_dxf_batch"
OBRA     = "Obra50_entidades"
PAV      = "Pav50_entidades"
LOTE     = 10   # primeiros N pilares

os.makedirs(OUT_DXF, exist_ok=True)

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

RPC_REJECTED = -2147418111   # A chamada foi rejeitada pelo chamado

def send_safe(doc, cmd, retries=8, delay=3):
    """SendCommand com retry em RPC_E_CALL_REJECTED."""
    for attempt in range(1, retries + 1):
        try:
            doc.SendCommand(cmd)
            return True
        except pywintypes.com_error as e:
            if e.hresult == RPC_REJECTED and attempt < retries:
                print(f"    [retry {attempt}/{retries}] AutoCAD ocupado, aguardando {delay}s...")
                time.sleep(delay)
            else:
                raise
    return False

# ── Carrega pilares ────────────────────────────────────────────────────────────
obras_path = os.path.join(CORE_DIR, "obras_salvas.json")
with open(obras_path, "r", encoding="utf-8") as f:
    obras = json.load(f)

pav_data = obras[OBRA][PAV]
def _sort_key(k):
    # Extrai numero final: 'Obra50_entidades_Pav50_entidades_7' -> 7
    parts = k.split("_")
    try:
        return int(parts[-1])
    except:
        return 9999

pids = sorted(pav_data.keys(), key=_sort_key)[:LOTE]
print(f"Lote: {len(pids)} pilares -> {pids}")

svc = AutomationService(project_root=PILARES_ROOT)

# ── Conecta AutoCAD (uma vez para todo o lote) ─────────────────────────────────
pythoncom.CoInitialize()
print("\nConectando ao AutoCAD...")
try:
    acad = win32com.client.GetActiveObject("AutoCAD.Application")
    print("  OK - instancia existente.")
except Exception as e:
    print(f"  Abrindo nova instancia... ({e})")
    acad = win32com.client.Dispatch("AutoCAD.Application")
    acad.Visible = True
    time.sleep(15)   # aguarda AutoCAD inicializar completamente

acad.Visible = True
try:
    acad.WindowState = 3
except:
    pass
# Aguarda AutoCAD estabilizar antes de qualquer operação COM
print("  Aguardando AutoCAD estabilizar (10s)...")
time.sleep(10)

results = []

for idx, pid in enumerate(pids, 1):
    dados = pav_data[pid]
    nome  = str(dados.get("nome") or dados.get("numero") or pid)
    print(f"\n{'='*55}")
    print(f"[{idx:02d}/{LOTE}] P{nome}  "
          f"comp={dados['comprimento']}  larg={dados['largura']}  alt={dados['altura']}")

    # ── 1. Gera SCRs ──────────────────────────────────────────────────────────
    pilar = PilarModel(**{k: v for k, v in dados.items() if k in PilarModel.model_fields})
    pilar.pavimento = PAV

    cima   = svc.generate_item_script_cima  (pilar, PAV, OBRA)
    abcd   = svc.generate_item_script_abcd  (pilar, PAV, OBRA)
    grades = svc.generate_item_script_grades(pilar, PAV, OBRA)
    print(f"  SCRs gerados -> CIMA:{'OK' if cima else 'X'}  ABCD:{'OK' if abcd else 'X'}  GRADES:{'OK' if grades else 'X'}")

    if not (cima or abcd or grades):
        print(f"  SKIP: nenhum SCR gerado.")
        results.append((nome, "SKIP-no-scr"))
        continue

    # ── 2. Combina 3 SCRs em 1 ────────────────────────────────────────────────
    scripts_dir = svc.scripts_dir
    scr_files = [
        os.path.join(scripts_dir, f"{PAV}_CIMA",   f"P{nome}_CIMA.scr"),
        os.path.join(scripts_dir, f"{PAV}_ABCD",   f"P{nome}_ABCD.scr"),
        os.path.join(scripts_dir, f"{PAV}_GRADES",  f"P{nome}.scr"),
    ]
    combined = os.path.join(OUT_DXF, f"P{nome}_combined.scr")
    with open(combined, "w", encoding="cp1252", errors="replace") as out_f:
        for scr_path in scr_files:
            if os.path.exists(scr_path):
                with open(scr_path, "r", encoding="cp1252", errors="replace") as sf:
                    content = sf.read()
                out_f.write(content)
                if not content.endswith("\n"):
                    out_f.write("\n")
    combined_fwd = combined.replace("\\", "/")
    print(f"  Combined SCR: {os.path.getsize(combined)} bytes")

    # ── 3. Abre MOLDE ──────────────────────────────────────────────────────────
    doc = None
    try:
        doc = acad.Documents.Open(MOLDE)
        time.sleep(8)
        print("  MOLDE aberto.")
    except Exception as e:
        print(f"  Documents.Open falhou: {e} — usando ActiveDocument")
        try:
            doc = acad.ActiveDocument
            time.sleep(2)
        except Exception as e2:
            print(f"  ActiveDocument falhou: {e2}")
            results.append((nome, f"FAIL-doc"))
            continue

    # Desabilita dialogs
    for cmd in ['(setvar "FILEDIA" 0)', '(setvar "CMDDIA" 0)', '(setvar "ATTREQ" 0)']:
        try:
            send_safe(doc, cmd + '\n', retries=5, delay=2)
        except:
            pass
    time.sleep(1)

    # ── 4. Executa SCR combinado ───────────────────────────────────────────────
    print(f"  Executando SCR combinado...")
    send_safe(doc, f'(command "SCRIPT" "{combined_fwd}")\n', retries=10, delay=4)
    time.sleep(35)   # aguarda AutoCAD processar todos os comandos
    print("  Aguardo concluido.")

    # ── 5. Salva DXF ──────────────────────────────────────────────────────────
    dxf = os.path.join(OUT_DXF, f"P{nome}.dxf")
    ok  = False
    try:
        doc.SaveAs(dxf, 61)   # 61 = acDXF R2010
        time.sleep(3)
        if os.path.exists(dxf) and os.path.getsize(dxf) > 1000:
            print(f"  DXF OK: {os.path.getsize(dxf)//1024} KB  -> {dxf}")
            results.append((nome, "OK"))
            ok = True
        else:
            print(f"  DXF ausente/pequeno apos SaveAs.")
    except Exception as e:
        print(f"  SaveAs falhou ({e}) — tentando DXFOUT...")
        dxf_fwd = dxf.replace("\\", "/")
        send_safe(doc, f'(command "DXFOUT" "{dxf_fwd}" "" "16" "")\n', retries=5, delay=3)
        time.sleep(5)
        if os.path.exists(dxf) and os.path.getsize(dxf) > 1000:
            print(f"  DXF OK via DXFOUT: {os.path.getsize(dxf)//1024} KB")
            results.append((nome, "OK-dxfout"))
            ok = True
        else:
            print(f"  FALHOU.")
            results.append((nome, f"FAIL:{e}"))

    # ── 6. Fecha documento (limpa para proximo pilar) ─────────────────────────
    try:
        doc.Close(False)
        time.sleep(3)
        print("  Documento fechado.")
    except Exception as e:
        print(f"  Close falhou: {e}")

    print(f"  Pausa de 5s antes do proximo...")
    time.sleep(5)

# ── Resumo ─────────────────────────────────────────────────────────────────────
print(f"\n{'='*55}")
print("RESULTADO FINAL:")
for nome, status in results:
    mark = "OK" if status.startswith("OK") else "FAIL"
    print(f"  [{mark}] P{nome}: {status}")
ok_count = sum(1 for _, s in results if s.startswith("OK"))
print(f"\n{ok_count}/{len(results)} DXFs gerados com sucesso.")
