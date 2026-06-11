"""
Usa combined SCRs JA GERADOS em output_dxf_batch/.
Para cada P1..P10: abre MOLDE -> executa SCR -> salva DXF.
"""
import sys, os, time
import win32com.client, pythoncom, pywintypes

OUT   = "D:\\Agente-cad-PYSIDE\\output_dxf_batch"
MOLDE = "D:\\Agente-cad-PYSIDE\\BASE_DWG_PARA_COMANDOS_SCRIPTS.dwg"
NOMES = [str(i) for i in range(1, 11)]

pythoncom.CoInitialize()
print("Conectando ao AutoCAD (EnsureDispatch)...")
acad = win32com.client.gencache.EnsureDispatch("AutoCAD.Application")
print(f"  OK: {acad.Name}")
acad.Visible = True

def open_molde(retries=20, delay=3):
    for i in range(retries):
        try:
            doc = acad.Documents.Open(MOLDE)
            time.sleep(5)
            return doc
        except pywintypes.com_error as e:
            if e.hresult == -2147418111 and i < retries - 1:
                print(f"    [open {i+1}/{retries}] RPC rejected, wait {delay}s...")
                time.sleep(delay)
            else:
                raise

def send(doc, cmd, retries=12, delay=3):
    for i in range(retries):
        try:
            doc.SendCommand(cmd)
            return True
        except pywintypes.com_error as e:
            if e.hresult in (-2147418111, -2147417848) and i < retries - 1:
                print(f"    [send {i+1}/{retries}] RPC rejected, wait {delay}s...")
                time.sleep(delay)
            else:
                raise
    return False

results = []
for idx, nome in enumerate(NOMES, 1):
    combined = os.path.join(OUT, f"P{nome}_combined.scr")
    if not os.path.exists(combined):
        print(f"[{idx}/10] P{nome}: combined SCR nao encontrado, pulando.")
        results.append((nome, "SKIP"))
        continue

    print(f"\n[{idx}/10] P{nome}  ({os.path.getsize(combined)//1024}KB combined)")

    # Abre MOLDE
    print(f"  Abrindo MOLDE...")
    try:
        doc = open_molde()
        print(f"  MOLDE aberto.")
    except Exception as e:
        print(f"  FAIL abrindo MOLDE: {e}")
        results.append((nome, f"FAIL-molde"))
        continue

    # Desabilita dialogs
    for cmd in ['(setvar "FILEDIA" 0)\n', '(setvar "CMDDIA" 0)\n', '(setvar "ATTREQ" 0)\n']:
        try: send(doc, cmd)
        except: pass
    time.sleep(0.5)

    # Executa SCR
    scr_fwd = combined.replace("\\", "/")
    print(f"  Executando SCR...")
    try:
        send(doc, f'(command "SCRIPT" "{scr_fwd}")\n')
        time.sleep(35)
        print(f"  Aguardo concluido.")
    except Exception as e:
        print(f"  FAIL executando SCR: {e}")
        try: doc.Close(False)
        except: pass
        results.append((nome, "FAIL-script"))
        continue

    # Salva DXF
    dxf = os.path.join(OUT, f"P{nome}.dxf")
    saved = False
    try:
        doc.SaveAs(dxf, 61)
        time.sleep(3)
        if os.path.exists(dxf) and os.path.getsize(dxf) > 1000:
            print(f"  DXF OK: {os.path.getsize(dxf)//1024}KB")
            results.append((nome, "OK"))
            saved = True
    except Exception as e:
        print(f"  SaveAs falhou ({e}), tentando DXFOUT...")

    if not saved:
        dxf_fwd = dxf.replace("\\", "/")
        try:
            send(doc, f'(command "DXFOUT" "{dxf_fwd}" "" "16" "")\n', retries=5)
            time.sleep(5)
        except Exception as e:
            print(f"  DXFOUT falhou: {e}")
        if os.path.exists(dxf) and os.path.getsize(dxf) > 1000:
            print(f"  DXF OK via DXFOUT: {os.path.getsize(dxf)//1024}KB")
            results.append((nome, "OK-dxfout"))
            saved = True
        else:
            results.append((nome, "FAIL-dxf"))

    # Fecha doc
    try: doc.Close(False)
    except: pass
    time.sleep(5)

print(f"\n{'='*50}")
print("RESULTADO:")
for nome, st in results:
    print(f"  {'[OK]' if st.startswith('OK') else '[--]'} P{nome}: {st}")
ok = sum(1 for _, s in results if s.startswith("OK"))
print(f"\n{ok}/{len(results)} DXFs gerados.")
