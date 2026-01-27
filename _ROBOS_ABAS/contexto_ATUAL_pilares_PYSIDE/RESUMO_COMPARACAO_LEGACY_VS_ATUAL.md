# Resumo da Comparação: Legacy vs Atual

**Data:** 2026-01-23 14:30

## Status Geral

### CIMA
- **Legacy:** 728 linhas, 10042 bytes
- **Atual:** 577 linhas, 7840 bytes
- **Diferenças:** 233
- **Status:** ⚠️ **INCOMPLETO** - Faltam ~151 linhas

### ABCD
- **Legacy:** 1428 linhas, 18126 bytes
- **Atual:** 225 linhas, 2080 bytes
- **Diferenças:** 1209
- **Status:** ❌ **MUITO INCOMPLETO** - Faltam ~1203 linhas (84% do conteúdo)

## Análise Detalhada

### ABCD - O que está faltando:

1. **Painéis A, B, C, D completos:**
   - Legacy tem centenas de comandos `_PLINE` para desenhar cada painel
   - Legacy tem muitos comandos `_ZOOM` para ajustar visualização
   - Atual tem apenas nomenclatura (P1.A, P1.B, P1.C, P1.D) mas não desenha os painéis

2. **Comandos INSERT:**
   - Legacy tem muitos `-INSERT` para blocos:
     - `SLIPTEE` (slip tee)
     - `SLIPTDD` (slip tee duplo)
     - `furacao` (furação)
   - Atual não tem nenhum comando INSERT

3. **Comandos DIMLINEAR (cotas):**
   - Legacy tem muitos comandos `_DIMLINEAR` para cotar os painéis
   - Atual tem apenas 1 comando DIMLINEAR inicial

4. **Camadas e tipos de linha:**
   - Legacy alterna entre camadas `Painéis`, `SARR_2.2x7`, `cota`, `nomenclatura`
   - Legacy alterna entre tipos de linha `DASHED` e `CONTINUOUS`
   - Atual tem apenas algumas mudanças de camada básicas

5. **Valores de dados:**
   - Legacy: `Subsolo - PD: 3,00` e `NÍVEL DE CHEGADA: 3,00`
   - Atual: `Subsolo - PD: 0,00` e `NÍVEL DE CHEGADA: INDEFINIDO`
   - **Problema:** Os dados extraídos do log não incluem `nivel_chegada` e `nivel_diferencial`

## Problemas Identificados

### 1. Dados Faltantes no Mapeamento
- `nivel_chegada`: Legacy tem `3,00`, Atual tem `INDEFINIDO`
- `nivel_diferencial`: Legacy tem `3,00`, Atual tem `0,00`
- Esses valores não foram extraídos do log porque não estavam no dicionário `[CIMA_SCRIPT] Dados recebidos`

### 2. Gerador ABCD Incompleto
- O gerador ABCD atual não está gerando:
  - Desenhos dos painéis A, B, C, D
  - Inserções de blocos (SLIPTEE, SLIPTDD, furacao)
  - Cotas detalhadas (DIMLINEAR)
  - Alternância de camadas e tipos de linha

### 3. Gerador CIMA Parcialmente Completo
- O gerador CIMA atual está mais próximo, mas ainda faltam:
  - Alguns comandos INSERT
  - Alguns comandos LAYER
  - Alguns comandos DIMLINEAR

## Próximos Passos

1. **Extrair dados completos do log legacy:**
   - Procurar por `nivel_chegada` e `nivel_diferencial` no log
   - Verificar se há outros campos faltantes

2. **Verificar gerador ABCD:**
   - Analisar código do gerador ABCD legacy
   - Comparar com gerador ABCD atual
   - Identificar por que não está gerando os painéis

3. **Ajustar mapeamento de dados:**
   - Adicionar campos faltantes no `_pilar_model_to_legacy_dict`
   - Garantir que todos os valores sejam mapeados corretamente

4. **Verificar lógica de geração:**
   - Verificar condições que determinam quando gerar cada elemento
   - Verificar se há dados que estão zerados e impedindo a geração

## Observações

- Os dados extraídos do log (`Ptestelegacy`) foram usados para gerar os scripts atuais
- O nome do pilar foi mapeado de `Ptestelegacy` para `P1` (normalização)
- Os valores de `nivel_chegada` e `nivel_diferencial` precisam ser extraídos de outra parte do log
