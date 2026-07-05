# Proveniência de Campos — Arete

## LAJ — ficha de robô

Esta tabela é o pré-requisito do Gate G4 para LAJ. O N2 é somente o gabarito
de validação; ele nunca pode alimentar o N3.

| Campo | Categoria | Fonte/regra N1→ficha |
|---|---|---|
| `nome`, `numero` | (a) extraível do N1 | rótulo da laje interpretado pelo Structural Analyzer |
| `coordenadas` | (a) extraível do N1 | contorno de `slabs.points_json`/vínculo `laje_outline_segs` |
| `comprimento`, `largura`, `area_cm2` | (a) extraível do N1 | derivados geometricamente do contorno N1 |
| `linhas_verticais`, `linhas_horizontais` | (b) algorítmico | grade calculada pela conversão; não é copiada do N2/N4 |
| `obstaculos` | (b) algorítmico | vínculo geométrico N1 filtrado pelo contorno da laje |
| `modo_selecionado` | (b) algorítmico | orientação escolhida pelo algoritmo de distribuição |
| `unioes_nos_bordes`, `pontaletes` | (b) algorítmico | derivados da grade e das regras gerais de montagem |
| `cotas_paineis`, `observacoes` | (c) só-no-N2/estilo | conteúdo de apresentação; precisa de regra geral de estilo, nunca cópia por item |

### Regra anti-vazamento

- Fonte N1 permitida no G4: tabela `slabs` do projeto selecionado no Structural Analyzer.
- Fonte proibida: `slab_elements.campos_json`, pois ela armazena a ficha N3 materializada e pode conter enriquecimento aprendido.
- Fontes de padrão proibidas ao gerar N3: prefixos `N4_DXF:`, `N2/N4:` e `N2/N4_validated`.
- O harness deve marcar FAIL, e não PASS, quando faltar um campo (a) ou (b).

Não há campo LAJ classificado como (d) teto estrutural nesta etapa. Uma exclusão futura
exige evidência por obra e aprovação humana registrada.
