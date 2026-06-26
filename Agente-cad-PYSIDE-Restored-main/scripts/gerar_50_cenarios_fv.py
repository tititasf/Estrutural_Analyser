#!/usr/bin/env python3
"""Generate 50 FV scenarios via real robot (decompiled gerar_script)."""
import sys, os, json

# The FV robot is compiled (.pyc only). We need to import from the pyc
FV_ROOT = os.path.join(os.path.dirname(__file__), '..', '_ROBOS_ABAS', 'Robo_Fundos_de_Vigas', 'compactador-producao')
sys.path.insert(0, FV_ROOT)
sys.path.insert(0, os.path.join(FV_ROOT, '__pycache__'))

# Try importing gerar_script from the robot
try:
    from Robo_fundos_TASF_limpo_copy_22 import gerar_script
    print("FV gerar_script imported OK")
except ImportError:
    # Fallback: use our ezdxf generator
    print("FV robot not importable - using ezdxf fallback")
    gerar_script = None

# If robot not available, generate via ezdxf
EZDXF_FV = os.path.join(os.path.dirname(__file__), 'gerar_fv_dxf_stog.py')

def make_fv(nome, largura, altura, paineis, recuos=None, aberturas=None,
            sarrafo_esq=True, sarrafo_dir=True, continuacao='UltimoSegmento'):
    return {
        'numero': nome.replace('FV',''),
        'nome': nome,
        'pavimento': 'CENARIOS',
        'largura': largura,
        'altura': altura,
        'paineis': paineis + [0]*(6-len(paineis)),
        'recuos': recuos or [0,0,0,0],
        'aberturas': aberturas or [[0,0],[0,0],[0,0],[0,0]],
        'sarrafo_esq': sarrafo_esq,
        'sarrafo_dir': sarrafo_dir,
        'texto_esquerda': 'ESQ',
        'texto_direita': 'DIR',
        'continuacao': continuacao,
    }

cenarios = [
    # Básicos (variação largura/altura)
    make_fv('FV01', 200, 14, [200]),
    make_fv('FV02', 200, 19, [200]),
    make_fv('FV03', 200, 24, [200]),
    make_fv('FV04', 200, 45, [200]),
    make_fv('FV05', 200, 60, [200]),
    make_fv('FV06', 200, 100, [200]),
    make_fv('FV07', 300, 19, [244, 56]),
    make_fv('FV08', 400, 19, [244, 156]),
    make_fv('FV09', 500, 19, [244, 244, 12]),
    make_fv('FV10', 700, 19, [244, 244, 212]),
    # Multi-paineis
    make_fv('FV11', 244, 19, [244]),
    make_fv('FV12', 488, 19, [244, 244]),
    make_fv('FV13', 732, 19, [244, 244, 244]),
    make_fv('FV14', 976, 19, [244, 244, 244, 244]),
    make_fv('FV15', 1220, 19, [244, 244, 244, 244, 244]),
    make_fv('FV16', 1464, 19, [244, 244, 244, 244, 244, 244]),
    # Alturas variadas (muda sarrafo pattern)
    make_fv('FV17', 300, 14, [244, 56]),
    make_fv('FV18', 300, 19, [244, 56]),
    make_fv('FV19', 300, 24, [244, 56]),
    make_fv('FV20', 300, 27, [244, 56]),
    make_fv('FV21', 300, 44, [244, 56]),
    make_fv('FV22', 300, 45, [244, 56]),
    make_fv('FV23', 300, 60, [244, 56]),
    make_fv('FV24', 300, 100, [244, 56]),
    # Com chanfros (recuos)
    make_fv('FV25', 300, 19, [244, 56], recuos=[10, 0, 0, 0]),
    make_fv('FV26', 300, 19, [244, 56], recuos=[0, 10, 0, 0]),
    make_fv('FV27', 300, 19, [244, 56], recuos=[0, 0, 10, 0]),
    make_fv('FV28', 300, 19, [244, 56], recuos=[0, 0, 0, 10]),
    make_fv('FV29', 300, 19, [244, 56], recuos=[10, 10, 0, 0]),
    make_fv('FV30', 300, 19, [244, 56], recuos=[10, 10, 10, 10]),
    # Com aberturas
    make_fv('FV31', 300, 19, [244, 56], aberturas=[[50, 5], [0,0], [0,0], [0,0]]),
    make_fv('FV32', 300, 19, [244, 56], aberturas=[[0,0], [50, 5], [0,0], [0,0]]),
    make_fv('FV33', 300, 19, [244, 56], aberturas=[[0,0], [0,0], [50, 5], [0,0]]),
    make_fv('FV34', 300, 19, [244, 56], aberturas=[[0,0], [0,0], [0,0], [50, 5]]),
    make_fv('FV35', 300, 19, [244, 56], aberturas=[[50,5], [50,5], [50,5], [50,5]]),
    # Continuação
    make_fv('FV36', 300, 19, [244, 56], continuacao='UltimoSegmento'),
    make_fv('FV37', 300, 19, [244, 56], continuacao='Obstaculo'),
    make_fv('FV38', 300, 19, [244, 56], continuacao='Abertura'),
    # Sem sarrafos
    make_fv('FV39', 300, 19, [244, 56], sarrafo_esq=False),
    make_fv('FV40', 300, 19, [244, 56], sarrafo_dir=False),
    make_fv('FV41', 300, 19, [244, 56], sarrafo_esq=False, sarrafo_dir=False),
    # Combinações
    make_fv('FV42', 500, 45, [244, 244, 12], recuos=[10, 10, 0, 0]),
    make_fv('FV43', 700, 60, [244, 244, 212], aberturas=[[50,5],[0,0],[50,5],[0,0]]),
    make_fv('FV44', 300, 19, [244, 56], recuos=[10,0,10,0], aberturas=[[50,5],[0,0],[0,0],[0,0]]),
    make_fv('FV45', 500, 100, [244, 244, 12], recuos=[10,10,10,10], continuacao='Obstaculo'),
    # Extremos
    make_fv('FV46', 100, 14, [100]),
    make_fv('FV47', 1500, 19, [244, 244, 244, 244, 244, 280]),
    make_fv('FV48', 300, 150, [244, 56]),
    make_fv('FV49', 50, 14, [50]),
    make_fv('FV50', 300, 19, [244, 56]),
]

# Since FV robot is compiled, just save the data as JSON for now
out_dir = os.path.join(os.path.dirname(__file__), '..', 'DADOS-OBRAS', 'cenarios_fv')
os.makedirs(out_dir, exist_ok=True)

results = []
for dados in cenarios:
    nome = dados['nome']
    jpath = os.path.join(out_dir, f'{nome}.json')
    with open(jpath, 'w') as f:
        json.dump(dados, f, indent=2)
    results.append((nome, dados['largura'], dados['altura'], len(dados['paineis']), 'SAVED'))
    print(f"  {nome}: {dados['largura']}x{dados['altura']} paineis={[p for p in dados['paineis'] if p > 0]} [SAVED]")

print(f"\n=== RESUMO FV: {len(results)} cenários salvos como JSON ===")
print(f"Para gerar SCR: usar Robo_fundos_TASF ou gerar_fv_dxf_stog.py")

with open(os.path.join(out_dir, 'cenarios_fv_resumo.json'), 'w') as f:
    json.dump(results, f, indent=2)
