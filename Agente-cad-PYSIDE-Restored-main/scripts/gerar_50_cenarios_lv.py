#!/usr/bin/env python3
"""Generate 50 LV scenarios via real robot."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '_ROBOS_ABAS', 'Robo_Laterais_de_Vigas'))
from gerador_script_viga import GeradorScriptViga

gerador = GeradorScriptViga()
out_dir = os.path.join(os.path.dirname(__file__), '..', '_ROBOS_ABAS', 'Robo_Laterais_de_Vigas', 'SCRIPTS', 'CENARIOS_LV')
os.makedirs(out_dir, exist_ok=True)

def mv(nome, largura, h1, h2=0, n_paineis=3, tipo1='Sarrafeado', tipo2='Sarrafeado',
       laje_sup=0, laje_inf=0, laje_central=0, grade_h1=0, grade_h2=0,
       continuacao='Proxima Parte', pilar_esq=0, pilar_dir=0):
    pw = largura / max(n_paineis, 1)
    return {
        'nome': nome, 'numero': nome.replace('V',''), 'obs': '',
        'texto_esq': 'ESQ', 'texto_dir': 'DIR',
        'largura': largura, 'altura_geral': str(h1) if h2==0 else f'{h1}+{h2}',
        'paineis_larguras': [pw]*n_paineis,
        'paineis_alturas': [h1]*n_paineis,
        'paineis_alturas2': [h2]*n_paineis,
        'paineis_tipo1': [tipo1]*n_paineis,
        'paineis_tipo2': [tipo2]*n_paineis,
        'paineis_grade_h1': [grade_h1]*n_paineis,
        'paineis_grade_h2': [grade_h2]*n_paineis,
        'lajes_sup': [laje_sup]*n_paineis,
        'lajes_inf': [laje_inf]*n_paineis,
        'lajes_central_alt': [laje_central]*n_paineis,
        'continuacao': continuacao,
        'sarrafo_esq_id': 0, 'sarrafo_dir_id': 0,
        'sarrafo_h2_esq_id': 0, 'sarrafo_h2_dir_id': 0,
        'fundo_viga': 0,
        'pilar_esq_dist': pilar_esq, 'pilar_esq_larg': 25 if pilar_esq > 0 else 0,
        'pilar_dir_dist': pilar_dir, 'pilar_dir_larg': 25 if pilar_dir > 0 else 0,
        'aberturas': [[0.0, 0.0, 0.0]] * 4,
    }

cenarios = [
    mv('V01',200,30), mv('V02',200,60), mv('V03',200,120),
    mv('V04',300,30), mv('V05',300,60), mv('V06',300,120),
    mv('V07',500,30), mv('V08',500,60), mv('V09',500,120),
    mv('V10',700,60),
    mv('V11',300,60,40), mv('V12',500,120,60), mv('V13',300,30,30),
    mv('V14',300,60,laje_sup=7), mv('V15',300,60,laje_inf=7),
    mv('V16',300,60,laje_sup=7,laje_inf=7),
    mv('V17',300,60,40,laje_sup=7,laje_inf=7,laje_central=15),
    mv('V18',300,60,tipo1='Grade',grade_h1=12),
    mv('V19',300,60,40,tipo1='Grade',tipo2='Grade',grade_h1=12,grade_h2=10),
    mv('V20',500,120,tipo1='Grade',grade_h1=20),
    mv('V21',200,60,n_paineis=1), mv('V22',200,60,n_paineis=2),
    mv('V23',400,60,n_paineis=4), mv('V24',600,60,n_paineis=5),
    mv('V25',700,60,n_paineis=6),
    mv('V26',300,60,continuacao='Obstaculo'),
    mv('V27',300,60,continuacao='Viga Continuacao'),
    mv('V28',300,60,pilar_esq=30), mv('V29',300,60,pilar_dir=30),
    mv('V30',300,60,pilar_esq=30,pilar_dir=25),
    mv('V31',300,15), mv('V32',300,25), mv('V33',300,80),
    mv('V34',300,100), mv('V35',300,180),
    mv('V36',100,10,n_paineis=1), mv('V37',800,200,n_paineis=6),
    mv('V38',244,60,n_paineis=1), mv('V39',488,60,n_paineis=2),
    mv('V40',500,120,60,laje_sup=7,laje_inf=7,tipo1='Grade',grade_h1=15),
    mv('V41',700,60,n_paineis=6,pilar_esq=30,pilar_dir=25),
    mv('V42',300,120,pilar_esq=30),
    mv('V43',500,60,40,laje_sup=7,continuacao='Obstaculo'),
    mv('V44',300,60,40,laje_sup=7,laje_inf=7,laje_central=15,tipo1='Grade',grade_h1=12),
    mv('V45',600,120,60,n_paineis=5,laje_sup=7,pilar_esq=30),
    mv('V46',400,30,n_paineis=4,tipo1='Grade',grade_h1=7),
    mv('V47',200,200,n_paineis=1), mv('V48',800,10,n_paineis=6),
    mv('V49',500,60,40,pilar_esq=30,pilar_dir=25,continuacao='Obstaculo'),
    mv('V50',300,60),
]

results = []
for dados in cenarios:
    nome = dados['nome']
    try:
        script_text, path = gerador.gerar_script(dados, out_dir)
        sz = os.path.getsize(path) if path else 0
        status = 'OK' if sz > 100 else 'FAIL'
    except Exception as e:
        sz = 0; status = f'ERR:{str(e)[:40]}'
    results.append((nome, dados['largura'], dados['altura_geral'], sz, status))
    print(f"  {nome}: {dados['largura']}x{dados['altura_geral']} -> {sz} bytes [{status}]")

ok = sum(1 for r in results if r[4]=='OK')
print(f"\n=== RESUMO LV: {ok}/{len(results)} OK ===")
json.dump(results, open(os.path.join(out_dir,'cenarios_lv_resumo.json'),'w'), indent=2)
