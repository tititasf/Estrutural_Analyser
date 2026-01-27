# 📊 Guia de Análise: Parafusos e Grades CIMA

## 🎯 Objetivo

Este guia documenta as correções aplicadas para garantir que os scripts CIMA gerados tenham parafusos e grades corretos, alinhados com a versão legacy.

## 🔧 Correções Aplicadas

### 1. Parafusos - Cálculo Corrigido

**Problema:** Cálculo usava `/70` + `+1` e distribuía resto no meio

**Solução:** 
- Alterado para `/72` sem `+1`
- Distribuição de resto nas extremidades alternando (legacy)

**Arquivos modificados:**
- `Robo_Pilar_Visao_Cima.py` - `calcular_valores()` (linha ~5526)
- `Robo_Pilar_Visao_Cima.py` - `gerar_script()` (linha ~3741)

### 2. Parafusos - Preservação de Valores

**Problema:** `calcular_valores()` preenchia valores incorretos antes de preencher corretos

**Solução:**
- Parafusos são zerados imediatamente após `calcular_valores()`
- Valores corretos do modelo são preenchidos depois
- NÃO há recálculo após preencher

**Arquivo modificado:**
- `CIMA_FUNCIONAL_EXCEL.py` - `preencher_campos_diretamente_e_gerar_scripts()` (linha ~608)

### 3. Grades - Preservação de Valores

**Problema:** `calcular_valores()` calcula grades com lógica diferente (faixas fixas)

**Solução:**
- Valores do modelo (calculados com `GradeCalculator.calcular_grades()`) são preenchidos depois
- NÃO há recálculo após preencher
- Valores do modelo são preservados

**Arquivo modificado:**
- `CIMA_FUNCIONAL_EXCEL.py` - Seções 5, 7 e 9

## 🧪 Como Testar

### 1. Gerar Scripts

Use o sistema normal para gerar scripts CIMA para um pavimento.

### 2. Analisar Scripts Gerados

```bash
python _ROBOS_ABAS/Robo_Pilares/analisar_scripts_cima.py SCRIPTS_ROBOS/P_1_CIMA --pavimento "P_1" --saida relatorio.json
```

### 3. Comparar com Legacy

Compare os valores de parafusos e grades entre:
- Scripts gerados pelo sistema atual
- Scripts gerados pelo sistema legacy

## 📋 Checklist de Validação

- [ ] Quantidade de parafusos está correta (usando `/72` sem `+1`)
- [ ] Valores de parafusos estão corretos (distribuição nas extremidades)
- [ ] Grades estão sendo preservadas do modelo
- [ ] Não há recálculo após preencher valores corretos
- [ ] Scripts gerados são idênticos aos legacy (ou próximos)

## 📝 Arquivos de Referência

- `ANALISE_PARAFUSOS_GRADES.md` - Análise detalhada das diferenças
- `analisar_scripts_cima.py` - Script de análise comparativa
- `grade_calculator.py` - Lógica de cálculo de grades e parafusos

## ⚠️ Notas Importantes

1. **Parafusos:** Agora usam lógica legacy correta (`/72` sem `+1`)
2. **Grades:** Valores do modelo são preservados (não sobrescritos)
3. **Fluxo:** `calcular_valores()` ainda é chamado, mas valores corretos são preenchidos depois
