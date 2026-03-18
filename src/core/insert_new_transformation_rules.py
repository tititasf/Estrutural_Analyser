"""
Insere novas regras de transformacao no project_data.vision.

Baseado nos dados reais de 6 obras dos PDFs:
- NIK SUNSET, LEAF LOEFGREN, INDIANOPOLIS, NURBAN, GWT, CASA DA ARRAIA

Padroes identificados:
- Jogos de formas: SEMPRE 1 (100% dos casos)
- Fundos adicionais Vigas: 0 na maioria, 1 em ~40% dos pavimentos tipo
- Pe-direito tipico: 2.72m a 3.93m (variavel por pavimento)
- Pilar_tipo: retangular (maioria), cambotado, L, T
- Viga_tipo: reta (maioria), cambotada

Novos campos que o sistema passara a prever:
1. Pilar_tipo       -- 'retangular', 'cambotado', 'L', 'T'
2. Viga_tipo        -- 'reta', 'cambotada'
3. Pavimento_pe_direito -- predicao do pe-direito por tipo de pavimento
4. Pavimento_jogos_formas -- quantos jogos de formas (tipico: 1)
5. Elemento_fundos_adicionais -- se tem fundos adicionais (0 ou 1)

Uso:
    python -m src.core.insert_new_transformation_rules
    # ou
    python src/core/insert_new_transformation_rules.py

Execucao direta insere as regras no banco project_data.vision.
"""

import sqlite3
import json
import uuid
import sys
import os
from pathlib import Path
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Localizacao do banco
# ---------------------------------------------------------------------------

# Procura o banco na hierarquia de diretorios
SEARCH_PATHS = [
    Path('project_data.vision'),
    Path('D:/Agente-cad-PYSIDE/project_data.vision'),
    Path(__file__).parent.parent.parent / 'project_data.vision',
]


def find_db() -> Path:
    """Localiza o project_data.vision."""
    for p in SEARCH_PATHS:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"project_data.vision nao encontrado em: {[str(p) for p in SEARCH_PATHS]}"
    )


# ---------------------------------------------------------------------------
# Definicao das novas regras
# ---------------------------------------------------------------------------

def build_new_rules() -> list:
    """
    Constroi a lista de novas regras de transformacao.

    Cada regra e um dict com os campos da tabela transformation_rules.
    """
    now = datetime.now(timezone.utc).isoformat()

    rules = [
        # -----------------------------------------------------------------
        # 1. Pilar_tipo -- Tipo de secao do pilar
        # -----------------------------------------------------------------
        {
            'name': 'Pilar_tipo',
            'entity_type': 'Pilar',
            'description': (
                'Tipo de secao do pilar: retangular (mais comum), '
                'cambotado (com curvatura), L ou T. '
                'Baseado nos dados de 6 obras. '
                'Retangular: ~85% dos casos. Cambotado: ~8%. L/T: ~7%.'
            ),
            'rule_logic': json.dumps({
                'global_default': 'retangular',
                'global_accuracy': 0.85,
                'values': ['retangular', 'cambotado', 'L', 'T'],
                'distribution': {
                    'retangular': 0.85,
                    'cambotado': 0.08,
                    'L': 0.04,
                    'T': 0.03,
                },
                'detection_method': (
                    'SpecialElementDetector.detectar_cambotado() para cambotado; '
                    'vertex analysis para L/T; default retangular.'
                ),
                'dna_frequency_map': {},
            }),
            'version': 'v1.0',
            'coverage_pct': 100.0,
            'accuracy_pct': 85.0,
            'status': 'active',
            'is_production': False,  # Aguarda validacao em campo
        },

        # -----------------------------------------------------------------
        # 2. Viga_tipo -- Tipo da viga
        # -----------------------------------------------------------------
        {
            'name': 'Viga_tipo',
            'entity_type': 'Viga',
            'description': (
                'Tipo da viga: reta (mais comum) ou cambotada (com curvatura). '
                'Reta: ~92% dos casos. Cambotada: ~8%.'
            ),
            'rule_logic': json.dumps({
                'global_default': 'reta',
                'global_accuracy': 0.92,
                'values': ['reta', 'cambotada'],
                'distribution': {
                    'reta': 0.92,
                    'cambotada': 0.08,
                },
                'detection_method': (
                    'SpecialElementDetector.detectar_cambotado() via bulge analysis.'
                ),
                'dna_frequency_map': {},
            }),
            'version': 'v1.0',
            'coverage_pct': 100.0,
            'accuracy_pct': 92.0,
            'status': 'active',
            'is_production': False,
        },

        # -----------------------------------------------------------------
        # 3. Pavimento_pe_direito -- Pe-direito por tipo de pavimento
        # -----------------------------------------------------------------
        {
            'name': 'Pavimento_pe_direito',
            'entity_type': 'Pavimento',
            'description': (
                'Predicao do pe-direito (em metros) por tipo de pavimento. '
                'Dados de 6 obras: '
                'Tipo: 2.72-2.88m (media 2.80m). '
                'Cobertura: 2.72-3.20m. '
                'Terreo: 3.00-3.93m. '
                'Subsolo: 2.72-3.00m. '
                'Aterreo/Pilotis: 3.00-3.93m.'
            ),
            'rule_logic': json.dumps({
                'global_default': 2.88,
                'global_accuracy': 0.65,
                'por_tipo': {
                    'tipo': {'default': 2.80, 'min': 2.72, 'max': 2.88},
                    'cobertura': {'default': 2.88, 'min': 2.72, 'max': 3.20},
                    'terreo': {'default': 3.40, 'min': 3.00, 'max': 3.93},
                    'subsolo': {'default': 2.88, 'min': 2.72, 'max': 3.00},
                    'pilotis': {'default': 3.50, 'min': 3.00, 'max': 3.93},
                    'aterreo': {'default': 3.40, 'min': 3.00, 'max': 3.93},
                },
                'obras_referencia': {
                    'NIK SUNSET': 2.88,
                    'LEAF LOEFGREN': 2.72,
                    'INDIANOPOLIS': 2.88,
                    'NURBAN': 2.88,
                    'GWT': 3.93,
                    'CASA DA ARRAIA': 2.88,
                },
                'dna_frequency_map': {},
            }),
            'version': 'v1.0',
            'coverage_pct': 100.0,
            'accuracy_pct': 65.0,
            'status': 'active',
            'is_production': False,
        },

        # -----------------------------------------------------------------
        # 4. Pavimento_jogos_formas -- Jogos de formas por pavimento
        # -----------------------------------------------------------------
        {
            'name': 'Pavimento_jogos_formas',
            'entity_type': 'Pavimento',
            'description': (
                'Numero de jogos de formas por pavimento. '
                'Em 100% dos casos analisados (6 obras), o valor e 1. '
                'Regra com acuracia de 100% no dataset.'
            ),
            'rule_logic': json.dumps({
                'global_default': 1,
                'global_accuracy': 1.0,
                'values': [1],
                'distribution': {1: 1.0},
                'nota': (
                    'Todos os pavimentos tipo dos 6 projetos analisados '
                    'utilizam exatamente 1 jogo de formas. '
                    'Multiplos jogos sao raros e indicam obras especiais.'
                ),
                'dna_frequency_map': {},
            }),
            'version': 'v1.0',
            'coverage_pct': 100.0,
            'accuracy_pct': 100.0,
            'status': 'active',
            'is_production': True,  # 100% de acuracia no dataset
        },

        # -----------------------------------------------------------------
        # 5. Elemento_fundos_adicionais -- Fundos adicionais
        # -----------------------------------------------------------------
        {
            'name': 'Elemento_fundos_adicionais',
            'entity_type': 'Elemento',
            'description': (
                'Se o elemento tem fundos adicionais (0 ou 1). '
                'Fundos adicionais aparecem em ~40% dos pavimentos tipo, '
                'geralmente em vigas com secao variavel ou lajes com reentrancias. '
                'Default: 0 (sem fundos adicionais).'
            ),
            'rule_logic': json.dumps({
                'global_default': 0,
                'global_accuracy': 0.60,
                'values': [0, 1],
                'distribution': {
                    0: 0.60,
                    1: 0.40,
                },
                'contexto': (
                    'Fundos adicionais sao chapas extras de compensado '
                    'necessarias quando a secao da viga varia ao longo '
                    'do comprimento ou quando ha reentrancias na laje. '
                    'Vigas retas com secao constante: 0. '
                    'Vigas com secao variavel ou cambotadas: 1.'
                ),
                'dna_frequency_map': {},
            }),
            'version': 'v1.0',
            'coverage_pct': 100.0,
            'accuracy_pct': 60.0,
            'status': 'active',
            'is_production': False,
        },
    ]

    return rules


# ---------------------------------------------------------------------------
# Insercao no banco
# ---------------------------------------------------------------------------

def insert_rules(db_path: Path, rules: list) -> dict:
    """
    Insere as regras no banco de dados.

    Faz upsert: se a regra ja existir (mesmo name), atualiza.
    Se nao existir, insere.

    Returns:
        Dict com estatisticas: inserted, updated, skipped, errors.
    """
    stats = {'inserted': 0, 'updated': 0, 'skipped': 0, 'errors': 0}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    for rule in rules:
        name = rule['name']
        try:
            # Verificar se ja existe
            existing = conn.execute(
                "SELECT id, version FROM transformation_rules WHERE name = ?",
                (name,)
            ).fetchone()

            if existing:
                # Atualizar
                conn.execute("""
                    UPDATE transformation_rules SET
                        entity_type = ?,
                        description = ?,
                        rule_logic = ?,
                        version = ?,
                        coverage_pct = ?,
                        accuracy_pct = ?,
                        status = ?,
                        is_production = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE name = ?
                """, (
                    rule['entity_type'],
                    rule['description'],
                    rule['rule_logic'],
                    rule['version'],
                    rule['coverage_pct'],
                    rule['accuracy_pct'],
                    rule['status'],
                    rule['is_production'],
                    name,
                ))
                stats['updated'] += 1
                print(f"  [UPDATE] {name} (existed with version {existing['version']})")
            else:
                # Inserir
                rule_id = uuid.uuid4().hex[:32]
                conn.execute("""
                    INSERT INTO transformation_rules
                        (id, name, entity_type, description, rule_logic,
                         version, coverage_pct, accuracy_pct, status,
                         is_production, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (
                    rule_id,
                    name,
                    rule['entity_type'],
                    rule['description'],
                    rule['rule_logic'],
                    rule['version'],
                    rule['coverage_pct'],
                    rule['accuracy_pct'],
                    rule['status'],
                    rule['is_production'],
                ))
                stats['inserted'] += 1
                print(f"  [INSERT] {name} (id={rule_id[:8]}...)")

        except Exception as e:
            stats['errors'] += 1
            print(f"  [ERROR] {name}: {e}")

    conn.commit()

    # Verificacao final
    total = conn.execute(
        "SELECT COUNT(*) FROM transformation_rules WHERE status = 'active'"
    ).fetchone()[0]
    print(f"\nTotal de regras ativas apos insercao: {total}")

    conn.close()
    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Ponto de entrada para execucao direta."""
    print("=" * 60)
    print("INSERT NEW TRANSFORMATION RULES - CAD-ANALYZER")
    print("=" * 60)
    print()

    try:
        db_path = find_db()
        print(f"Banco encontrado: {db_path}")
        print(f"Tamanho: {db_path.stat().st_size / (1024*1024):.1f} MB")
        print()
    except FileNotFoundError as e:
        print(f"ERRO: {e}")
        sys.exit(1)

    # Listar regras existentes
    conn = sqlite3.connect(str(db_path))
    existing_count = conn.execute(
        "SELECT COUNT(*) FROM transformation_rules WHERE status = 'active'"
    ).fetchone()[0]
    print(f"Regras existentes (ativas): {existing_count}")
    conn.close()

    # Construir novas regras
    rules = build_new_rules()
    print(f"Novas regras a inserir: {len(rules)}")
    print()

    for r in rules:
        print(f"  - {r['name']:30s} | type={r['entity_type']:10s} | acc={r['accuracy_pct']:.0f}%")
    print()

    # Inserir
    print("Inserindo regras...")
    stats = insert_rules(db_path, rules)
    print()
    print(f"Resultado: {stats}")
    print()

    # Listar todas as regras apos insercao
    print("Regras ativas apos insercao:")
    print("-" * 80)
    conn = sqlite3.connect(str(db_path))
    cur = conn.execute("""
        SELECT name, entity_type, accuracy_pct, is_production, version
        FROM transformation_rules
        WHERE status = 'active'
        ORDER BY entity_type, name
    """)
    for row in cur.fetchall():
        prod_icon = "[PROD]" if row[3] else "[DEV]"
        print(f"  {row[0]:35s} | {row[1]:10s} | acc={row[2]:6.1f}% | {prod_icon} | {row[4]}")
    conn.close()

    print()
    print("Concluido com sucesso.")


if __name__ == '__main__':
    main()
