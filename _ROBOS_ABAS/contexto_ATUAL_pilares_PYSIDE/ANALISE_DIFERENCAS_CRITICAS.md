# Análise de Diferenças Críticas: Legacy vs Atual

## Resumo Executivo

- **CIMA**: Legacy tem 728 linhas (10042 bytes), Atual tem 577 linhas (7840 bytes) - **151 linhas a menos (22% menor)**
- **ABCD**: Legacy tem 1428 linhas (18126 bytes), Atual tem 225 linhas (2080 bytes) - **1203 linhas a menos (84% menor!)**

## Diferenças Identificadas

### 1. Encoding e BOM ✅ CORRETO
- Ambos usam `encoding="utf-16"` que adiciona BOM automaticamente
- **Status**: Não precisa ajuste

### 2. Comandos LAYER ✅ CORRETO  
- Legacy CIMA: 49 comandos `_LAYER` (com underscore)
- Atual CIMA: 35 comandos `_LAYER` (com underscore)
- **Status**: Formato correto, mas quantidade diferente (menos comandos no atual)

### 3. Comandos -INSERT ❌ DIFERENTE
- Legacy: 20 comandos `-INSERT`
- Atual: 10 comandos `-INSERT`
- **Problema**: Metade dos comandos INSERT estão faltando

### 4. Ordem de Comandos ❌ DIFERENTE
- Comandos aparecem em ordem diferente
- Exemplo: Legacy tem `-INSERT` na linha 367, Atual tem `_LAYER` na linha 375
- **Problema**: Estrutura sequencial diferente

### 5. Conteúdo Faltante ❌ CRÍTICO
- Script atual tem **significativamente menos conteúdo**
- ABCD tem apenas 15% do conteúdo do legacy
- **Problema**: Lógica de geração está gerando menos elementos

## Causas Prováveis

1. **Dados de Entrada Diferentes**: O mapeamento `_pilar_model_to_legacy_dict` pode não estar passando todos os campos necessários
2. **Condições de Geração**: Algumas condições na lógica de geração podem estar impedindo a geração de elementos
3. **Processamento Pós-Geração**: Pode haver algum processamento que remove conteúdo após a geração

## Próximos Passos

1. Comparar dados de entrada: Verificar se os dados passados para o gerador legacy são idênticos
2. Verificar condições: Analisar condições que controlam a geração de elementos
3. Verificar processamento: Verificar se há algum processamento que modifica o script após geração
