# Enciclopedia de Classes - Contrato das 8 Dimensoes

## Fonte Canonica

O registro declarativo fica em `data/classe_registry.json`.

- `schema_version`: versao do contrato.
- `unknown_policy=preserve_unmapped`: categorias desconhecidas permanecem visiveis.
- `dimensions`: exatamente oito dimensoes, com IDs unicos de 1 a 8.
- `classes`: classes habilitadas, nomes e aliases nao ambiguos.

O loader `scripts/classe_registry.py` valida o arquivo antes do uso.

## Dimensoes

1. Visual estrutural N1.
2. Desenho dos robos N3/N4.
3. Dados, fichas e campos.
4. Descricao, geometria e logica.
5. Obra, pavimento e item.
6. Engenharia reversa N2.
7. Layers, cores e historico DXF.
8. Corpus global entre obras.

Cobertura significa apenas que existe uma fonte materializada. Nao significa que a
compreensao esta correta ou validada.

## Classes Iniciais

| ID | Nome | Aliases seguros |
|----|------|-----------------|
| PIL | Pilar | PILAR |
| LV | Lateral de Viga | LATERAL_VIGA, LATERAL DE VIGA |
| FV | Fundo de Viga | FUNDO_VIGA, FUNDO DE VIGA |
| LAJ | Laje | LAJE |

`VIGA` nao e alias automatico de LV ou FV porque a origem pode ser ambigua.

## Adicao de Nova Classe

1. Adicionar ID, nome e aliases inequivocos ao registro.
2. Executar `python -m pytest tests/test_classe_registry.py -q`.
3. Confirmar que a Curadoria mostra a nova classe com cobertura inicial real.
4. Criar regras semanticas somente apos confirmacao do dono.
5. Validar instancias individualmente para gerar T1.

## Proibicoes

- Nao copiar regras de outra classe por padrao.
- Nao transformar categoria desconhecida em alias por similaridade textual.
- Nao promover instancias T0 ao registrar uma classe.
- Nao indexar fichas em bulk.
- Nao esconder categorias nao harmonizadas.
