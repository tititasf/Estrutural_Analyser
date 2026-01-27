# Ajustes Realizados para Alinhar Scripts Atual com Legacy

## Data: 2026-01-23

## Ajustes Completados

### 1. ✅ Encoding e BOM
- **Status**: Verificado - Ambos usam `encoding="utf-16"` que adiciona BOM automaticamente
- **Ação**: Nenhuma ação necessária

### 2. ✅ Comandos LAYER
- **Status**: Verificado - Ambos usam `_LAYER` (com underscore) corretamente
- **Ação**: Nenhuma ação necessária

### 3. ✅ Espaçamentos e Formatação
- **Status**: Verificado - Onde há conteúdo, espaçamentos estão idênticos
- **Ação**: Nenhuma ação necessária

### 4. ✅ Comandos Específicos
- **Status**: Verificado - Ambos usam `-DIMSTYLE`, `-INSERT`, `-STYLE` (com hífen) corretamente
- **Ação**: Nenhuma ação necessária

### 5. ✅ Mapeamento de Dados - CORRIGIDO
- **Problema Identificado**: Faltavam dicionários `grades_grupo2`, `detalhes_grades`, `detalhes_grades_grupo2`, `detalhes_grades_especiais`
- **Ação Realizada**: 
  - Adicionado `grades_grupo2` como dicionário
  - Adicionado `detalhes_grades` como dicionário
  - Adicionado `detalhes_grades_grupo2` como dicionário
  - Adicionado `detalhes_grades_especiais` como dicionário
- **Arquivo Modificado**: `automation_service.py` - função `_pilar_model_to_legacy_dict`

## Problemas Identificados (Não Resolvidos Ainda)

### 1. ❌ Conteúdo Faltante (CRÍTICO)
- **CIMA**: Legacy 728 linhas vs Atual 577 linhas (151 linhas a menos, 22% menor)
- **ABCD**: Legacy 1428 linhas vs Atual 225 linhas (1203 linhas a menos, 84% menor!)
- **Causa Provável**: 
  - Dados de entrada diferentes
  - Condições de geração diferentes
  - Lógica de geração diferente

### 2. ❌ Quantidade de Comandos Diferente
- **LAYER**: Legacy 49 vs Atual 35 (14 a menos)
- **INSERT**: Legacy 20 vs Atual 10 (10 a menos, 50% menos!)
- **DIMLINEAR**: Legacy 15 vs Atual 8 (7 a menos)

### 3. ❌ Ordem de Comandos Diferente
- Comandos aparecem em ordem diferente
- Estrutura sequencial diferente

### 4. ❌ Valores Numéricos Diferentes
- Coordenadas diferentes nos INSERTs
- Exemplo: Legacy `-4.5,61.0` vs Atual `11.0,61.0`

## Próximos Passos Necessários

1. **Investigar Dados de Entrada**: Comparar dados passados para o gerador legacy vs dados esperados
2. **Verificar Condições**: Analisar condições que controlam a geração de elementos
3. **Verificar Lógica**: Analisar a lógica de geração no código legacy
4. **Ajustar Mapeamento**: Garantir que todos os campos necessários estão sendo mapeados corretamente

## Observações

- Os ajustes de formatação (encoding, comandos, espaçamentos) estão corretos
- O problema principal é conteúdo faltante, não formatação
- Os dicionários necessários foram adicionados ao mapeamento
- Ainda é necessário investigar por que há menos conteúdo sendo gerado
