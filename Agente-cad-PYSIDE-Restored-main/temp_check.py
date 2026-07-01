import json
report_path = r'D:\Agente-cad-PYSIDE\validacao_visual\engrev_laj_recorte_loop_test\engrev_laj_recorte_loop_report.json'
with open(report_path) as f:
    data = json.load(f)
for item in data.get('items', []):
    if item.get('id') in ['L307', 'L315']:
        print(f"--- {item.get('id')} ---")
        print(f"Approved Outline: {item.get('approved_outline')}")
        print(f"Motor Outline: {item.get('motor_outline')}")
        print(f"Motor Ficha Largura: {item.get('motor_ficha', {}).get('largura')}")
        print(f"Motor Ficha Comprimento: {item.get('motor_ficha', {}).get('comprimento')}")
