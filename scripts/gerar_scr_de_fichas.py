"""
fichas_pilares.json (extraído do DXF real) → SCR files via AutomationOrchestratorService

Lê as fichas extraídas pelo dxf_to_fichas_pilares.py e gera os SCR de cada pilar
usando o robot real (CIMA + ABCD + GRADES).

Uso:
    python scripts/gerar_scr_de_fichas.py \
        --fichas output_fichas/fichas_pilares.json \
        --obra "ALIMONTI PARAISO 1PAV" \
        --pavimento "1_PAVIMENTO" \
        [--apenas P1 P2 P3]   # limitar a pilares específicos
        [--output output_scr/]
"""
import sys, os, json, argparse
sys.stdout.reconfigure(encoding='utf-8')

# ── Caminhos do robot ──────────────────────────────────────────────────
BASE = "D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main"
ROBO_PATH = f"{BASE}/_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25"
ROBO_SRC  = f"{ROBO_PATH}/src"

for p in [ROBO_PATH, ROBO_SRC]:
    if p not in sys.path:
        sys.path.insert(0, p)

import tkinter as tk

# Cria root Tk oculto — necessário para instanciar widgets headless
_tk_root = tk.Tk()
_tk_root.withdraw()

# ── Patch headless: desabilita atualizar_preview (evita canvas.draw() em loop) ──
# GeradorPilar.atualizar_preview só desenha o preview matplotlib — não é necessário
# para geração de SCR. Sem o patch, canvas.draw() dispara tk.update() e re-entra
# nas StringVar traces indefinidamente.
try:
    import importlib as _il
    _robo_cima = _il.import_module('robots.Robo_Pilar_Visao_Cima')
    _robo_cima.GeradorPilar.atualizar_preview = lambda self: None
    print("[PATCH] GeradorPilar.atualizar_preview → no-op (headless)")

    # Também retira a janela do AplicacaoUnificada para não aparecer na tela
    _orig_app_init = _robo_cima.AplicacaoUnificada.__init__
    def _headless_app_init(self_app):
        _orig_app_init(self_app)
        try:
            self_app.root.withdraw()
        except Exception:
            pass
    _robo_cima.AplicacaoUnificada.__init__ = _headless_app_init
    print("[PATCH] AplicacaoUnificada.__init__ → root.withdraw() após criação")
except Exception as _patch_err:
    print(f"[PATCH WARNING] {_patch_err}")

from models.pilar_model   import PilarModel
from models.obra_model    import ObraModel
from models.pavimento_model import PavimentoModel
from services.automation_service import AutomationOrchestratorService


def ficha_to_pilar_model(ficha: dict) -> PilarModel:
    """Converte FichaFase3Pilar (dict) para PilarModel do robot."""
    return PilarModel(
        numero  = str(ficha.get('numero', '0')),
        nome    = ficha.get('id', 'P?'),
        comprimento = float(ficha.get('comprimento', 0)),
        largura     = float(ficha.get('largura', 0)),
        altura      = float(ficha.get('altura_cm', 0)),
        pavimento   = ficha.get('pavimento', '1_PAVIMENTO'),
        nivel_saida   = float(ficha.get('nivel_saida_m', 0)),
        nivel_chegada = float(ficha.get('nivel_chegada_m', 0)),
        # Armadura = zeros (não extraída do DXF de fôrma)
        par_1_2=0.0, par_2_3=0.0, par_3_4=0.0, par_4_5=0.0,
        par_5_6=0.0, par_6_7=0.0, par_7_8=0.0, par_8_9=0.0,
        grade_1=0.0, distancia_1=0.0,
        grade_2=0.0, distancia_2=0.0,
        grade_3=0.0,
        pilar_especial_ativo=bool(ficha.get('pilar_especial', False)),
        tipo_pilar_especial=str(ficha.get('tipo_pilar_especial', 'L')),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fichas',    required=True)
    parser.add_argument('--obra',      default='Obra')
    parser.add_argument('--pavimento', default='1_PAVIMENTO')
    parser.add_argument('--output',    default='D:/Agente-cad-PYSIDE/output_scr_engrev/')
    parser.add_argument('--apenas',    nargs='*', help='Gerar só estes pilares (ex: P1 P2)')
    args = parser.parse_args()

    # Lê fichas
    with open(args.fichas, 'r', encoding='utf-8') as f:
        fichas = json.load(f)

    if args.apenas:
        fichas = [f for f in fichas if f['id'] in args.apenas]

    print(f"Gerando SCR para {len(fichas)} pilares | obra={args.obra} | pav={args.pavimento}")
    print(f"Saída: {args.output}")

    os.makedirs(args.output, exist_ok=True)

    # O robot salva SCRs em SCRIPTS_ROBOS/ (determinado pelo robust_path_resolver interno).
    # O service.scripts_dir deve apontar para este mesmo lugar, senão não encontra os arquivos.
    SCRIPTS_ROBOS = f"{ROBO_PATH}/SCRIPTS_ROBOS"
    os.makedirs(SCRIPTS_ROBOS, exist_ok=True)

    service = AutomationOrchestratorService(BASE)
    service.scripts_dir = SCRIPTS_ROBOS

    obra = ObraModel(nome=args.obra, scripts_dir=SCRIPTS_ROBOS)

    resultados = []
    for ficha in fichas:
        pid = ficha['id']
        pilar = ficha_to_pilar_model(ficha)
        comp  = ficha.get('comprimento', 0)
        larg  = ficha.get('largura', 0)
        pd    = ficha.get('altura_cm', 0)
        print(f"\n  [{pid}] {comp}x{larg}cm  PD={pd:.0f}cm")

        status = {'id': pid, 'cima': False, 'abcd': False, 'grades': False}
        try:
            r = service.generate_single_pilar_script(pilar, obra)
            status['cima']   = 'CIMA' in str(r)
            status['abcd']   = 'ABCD' in str(r)
            status['grades'] = 'GRADES' in str(r)
            print(f"    OK: {r}")
        except Exception as e:
            print(f"    ERRO: {e}")
            import traceback; traceback.print_exc()
        resultados.append(status)

    # Resumo
    print(f"\n{'='*50}")
    print("RESUMO:")
    ok = sum(1 for r in resultados if r['cima'] or r['abcd'] or r['grades'])
    for r in resultados:
        c = '+' if r['cima'] else '-'
        a = '+' if r['abcd'] else '-'
        g = '+' if r['grades'] else '-'
        print(f"  {r['id']:<6} CIMA={c} ABCD={a} GRADES={g}")
    print(f"\n{ok}/{len(resultados)} pilares com ao menos 1 SCR gerado.")

    # Lista e copia arquivos SCR gerados do SCRIPTS_ROBOS para args.output
    import shutil
    scr_files = []
    for root_dir, dirs, files in os.walk(SCRIPTS_ROBOS):
        for fname in files:
            if fname.lower().endswith('.scr'):
                src = os.path.join(root_dir, fname)
                # Reproduz estrutura de subpasta relativa em args.output
                rel = os.path.relpath(src, SCRIPTS_ROBOS)
                dst = os.path.join(args.output, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                scr_files.append(dst)
    print(f"\nSCR files gerados: {len(scr_files)}")
    for s in sorted(scr_files)[:20]:
        sz = os.path.getsize(s) // 1024
        print(f"  {s}  ({sz}KB)")


if __name__ == '__main__':
    main()
