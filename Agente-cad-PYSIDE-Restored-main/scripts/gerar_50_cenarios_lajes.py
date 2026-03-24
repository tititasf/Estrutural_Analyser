#!/usr/bin/env python3
"""Generate 50 laje scenarios via SmartPanner + save as JSON."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from smart_panner import distribute_panels

out_dir = os.path.join(os.path.dirname(__file__), '..', 'DADOS-OBRAS', 'cenarios_lajes')
os.makedirs(out_dir, exist_ok=True)

def make_laje(nome, comp, larg, obstaculos=None):
    smart = distribute_panels(comp, larg, obstaculos)
    coords = [[0,0],[comp,0],[comp,larg],[0,larg],[0,0]]
    return {
        'numero': int(nome.replace('LJ','')),
        'nome': nome,
        'comprimento': comp,
        'largura': larg,
        'pavimento': 'CENARIOS',
        'coordenadas': coords,
        'area_cm2': comp * larg,
        'linhas_verticais': smart['linhas_verticais'],
        'linhas_horizontais': smart['linhas_horizontais'],
        'obstaculos': obstaculos or [],
        'modo_selecionado': 0,
        'unioes_nos_bordes': False,
        'observacoes': '',
    }

cenarios = [
    # Básicos (variação dimensão)
    make_laje('LJ01', 100, 100),
    make_laje('LJ02', 200, 100),
    make_laje('LJ03', 200, 200),
    make_laje('LJ04', 244, 122),
    make_laje('LJ05', 244, 244),
    make_laje('LJ06', 300, 200),
    make_laje('LJ07', 300, 300),
    make_laje('LJ08', 400, 200),
    make_laje('LJ09', 400, 400),
    make_laje('LJ10', 500, 244),
    # Grandes
    make_laje('LJ11', 500, 500),
    make_laje('LJ12', 600, 400),
    make_laje('LJ13', 700, 300),
    make_laje('LJ14', 800, 244),
    make_laje('LJ15', 1000, 244),
    make_laje('LJ16', 1000, 500),
    make_laje('LJ17', 1500, 244),
    make_laje('LJ18', 2000, 244),
    make_laje('LJ19', 2154, 244),
    make_laje('LJ20', 2500, 500),
    # Estreitas
    make_laje('LJ21', 300, 60),
    make_laje('LJ22', 300, 100),
    make_laje('LJ23', 300, 122),
    make_laje('LJ24', 500, 60),
    make_laje('LJ25', 500, 100),
    # Quadradas
    make_laje('LJ26', 122, 122),
    make_laje('LJ27', 150, 150),
    make_laje('LJ28', 200, 200),
    make_laje('LJ29', 300, 300),
    make_laje('LJ30', 400, 400),
    # Irregulares (eixo menor < 200cm)
    make_laje('LJ31', 400, 150),
    make_laje('LJ32', 500, 180),
    make_laje('LJ33', 600, 120),
    make_laje('LJ34', 300, 80),
    make_laje('LJ35', 200, 50),
    # Com obstáculos
    make_laje('LJ36', 400, 300, [{'x': 100, 'y': 100, 'width': 50, 'height': 50}]),
    make_laje('LJ37', 500, 400, [{'x': 200, 'y': 150, 'width': 80, 'height': 60}]),
    make_laje('LJ38', 600, 300, [{'x': 50, 'y': 50, 'width': 30, 'height': 30}, {'x': 400, 'y': 200, 'width': 40, 'height': 40}]),
    # Painéis padrão STOG (testando módulo 244/122/60)
    make_laje('LJ39', 244, 244),
    make_laje('LJ40', 488, 244),
    make_laje('LJ41', 732, 244),
    make_laje('LJ42', 976, 244),
    make_laje('LJ43', 1220, 244),
    # Combinações reais (Obra_TREINO_1)
    make_laje('LJ44', 406, 423),
    make_laje('LJ45', 418, 423),
    make_laje('LJ46', 1887, 152),
    make_laje('LJ47', 405, 558),
    make_laje('LJ48', 129, 459),
    make_laje('LJ49', 234, 423),
    make_laje('LJ50', 413, 423),
]

results = []
for dados in cenarios:
    nome = dados['nome']
    comp = dados['comprimento']
    larg = dados['largura']
    n_v = len(dados['linhas_verticais'])
    n_h = len(dados['linhas_horizontais'])
    n_obs = len(dados['obstaculos'])

    jpath = os.path.join(out_dir, f'{nome}.json')
    with open(jpath, 'w') as f:
        json.dump(dados, f, indent=2)

    results.append((nome, comp, larg, n_v, n_h, n_obs, 'OK'))
    print(f"  {nome}: {comp}x{larg} V={n_v} H={n_h} obs={n_obs}")

print(f"\n=== RESUMO LAJES: {len(results)}/50 cenários salvos ===")

with open(os.path.join(out_dir, 'cenarios_lajes_resumo.json'), 'w') as f:
    json.dump(results, f, indent=2)
